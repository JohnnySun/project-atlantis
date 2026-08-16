#!/usr/bin/env python3
"""Bounded M1.9 runtime QA for the A6SJ M1.8 narrow-glyph POC.

This probe keeps the original source text local and emits only hashes, offsets,
register/address metadata, counts, and a small self-rendered tile-cache hash.
It uses one GDB connection per fresh mGBA process.  The controlled consumer
phase is permitted only after the already-verified font initializer has written
both live base slots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from core.gba.gdbstub_client import GdbClient, parse_stop_watch
from m17_layout import code_unit_slot, read_source_records, tokenize_payload
from m18_narrow_allocator import render_narrow_4bpp, sha256

# Import the game-specific M1.6 runtime constants/functions without copying the
# GDB packet client or font initializer implementation.
from probe_font_resource import (  # noqa: E402
    CODEPAGE_LOOKUP,
    CONSUMER,
    GLYPH_COMPLETE,
    NARROW_GLYPH_ADD,
    NARROW_SLOT,
    SLOTS,
    TILE_WRITER,
    _assert_initialized,
    capture_initializer,
    gdb_pc_argument,
    summarize_bytes,
    write_bounded_memory,
)


ROM_BASE = 0x08000000
TARGET_OFFSET = 0x080858
ADJACENT_OFFSET = 0x080860
KNOWN_EXISTING_OFFSET = 0x07B3FC
NARROW_RESOURCE_SIZE = 0x1980
NARROW_STRIDE = 12
NARROW_GLYPH_BYTES = 12
TARGET_PAYLOAD_PATCHED = bytes.fromhex("83e883e7")
KEYINPUT = 0x04000130
TEMP_STACK = 0x0203FF00
CACHE_CLEAR_START = 0x02019010
CACHE_CLEAR_LENGTH = 0x1000
NATURAL_VRAM = (0x06000000, 0x18000)
NATURAL_PALETTE = (0x05000000, 0x400)
NATURAL_OAM = (0x07000000, 0x400)

BASE_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
PATCHED_ROM_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
BPS_SHA256 = "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"
BPS_SIZE = 66


class RuntimeQAError(RuntimeError):
    """A bounded runtime invariant failed closed."""


def address(value: int) -> str:
    return f"0x{value:08X}"


def read_one_jsonl(path: Path) -> Dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise RuntimeQAError(f"expected one JSONL record: {path}")
    return rows[0]


def read_payload(rom: bytes, offset: int) -> Tuple[bytes, int]:
    if not 0 <= offset < len(rom):
        raise RuntimeQAError(f"record offset outside ROM: {address(offset)}")
    terminator = rom.find(b"\x00", offset)
    if terminator < 0:
        raise RuntimeQAError(f"record has no NUL terminator: {address(offset)}")
    return rom[offset:terminator], terminator


def code_units(payload: bytes) -> Tuple[int, ...]:
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        raise RuntimeQAError("record contains opaque/control/unaligned units")
    if any(token.glyph_class != "narrow" for token in tokenization.tokens):
        raise RuntimeQAError("M1.9 record is not narrow-only")
    return tuple(int.from_bytes(token.raw, "little") for token in tokenization.tokens)


def record_metadata(
    rom: bytes,
    offset: int,
    *,
    source_ledger_sha256: Optional[str] = None,
    role: str,
) -> Dict[str, Any]:
    payload, terminator = read_payload(rom, offset)
    units = code_units(payload)
    return {
        "role": role,
        "string_id": offset,
        "source_address": address(ROM_BASE + offset),
        "source_raw_sha256": sha256(payload),
        "source_ledger_sha256": source_ledger_sha256,
        "payload_length": len(payload),
        "unit_count": len(units),
        "line_width": len(units) * 8,
        "terminator": "NUL",
        "terminator_address": address(ROM_BASE + terminator),
        "control_tokens": [],
        "code_units": [f"0x{unit:04X}" for unit in units],
        "record_end_exclusive": address(ROM_BASE + terminator + 1),
    }


def glyph_bytes_for_unit(rom: bytes, unit: int) -> Dict[str, Any]:
    slot = code_unit_slot(unit, "narrow", NARROW_RESOURCE_SIZE)
    if slot is None:
        raise RuntimeQAError(f"narrow code unit outside resource: 0x{unit:04X}")
    file_offset = 0x14F664 + slot * NARROW_STRIDE
    glyph = rom[file_offset : file_offset + NARROW_GLYPH_BYTES]
    if len(glyph) != NARROW_GLYPH_BYTES:
        raise RuntimeQAError(f"glyph window outside ROM: slot={slot}")
    return {
        "code_unit": f"0x{unit:04X}",
        "slot": slot,
        "rom_address": address(ROM_BASE + file_offset),
        "glyph": glyph,
        "summary": summarize_bytes(glyph, ROM_BASE + file_offset),
    }


def expected_tile_layout(glyphs: Sequence[bytes]) -> bytes:
    if not glyphs or any(len(glyph) != NARROW_GLYPH_BYTES for glyph in glyphs):
        raise RuntimeQAError("expected narrow glyph list is empty or malformed")
    width = 8 * len(glyphs)
    tile_columns = math.ceil(width / 8)
    tile_rows = math.ceil(12 / 8)
    output = bytearray(tile_columns * tile_rows * 32)
    for glyph_index, glyph in enumerate(glyphs):
        for y, row in enumerate(render_narrow_4bpp(glyph)):
            # render_narrow_4bpp is four bytes per source row.
            row_index = y // 4
            byte_in_row = y % 4
            tile_x = glyph_index
            tile_y = row_index // 8
            tile_row = row_index % 8
            destination = (tile_y * tile_columns + tile_x) * 32 + tile_row * 4 + byte_in_row
            output[destination] = row
    return bytes(output)


def expected_row_pixels(glyphs: Sequence[bytes]) -> bytes:
    pixels = bytearray()
    for row in range(12):
        for glyph in glyphs:
            packed = render_narrow_4bpp(glyph)[row * 4 : row * 4 + 4]
            for value in packed:
                pixels.append(value & 0x0F)
                pixels.append((value >> 4) & 0x0F)
    return bytes(pixels)


def writer_pixel_render(
    writer_calls: Sequence[Mapping[str, Any]],
    *,
    expected_width: int,
    expected_height: int = 12,
) -> Dict[str, Any]:
    tile_columns = math.ceil(expected_width / 8)
    tile_rows = math.ceil(expected_height / 8)
    width = tile_columns * 8
    height = tile_rows * 8
    pixels = bytearray(width * height)
    if not writer_calls:
        raise RuntimeQAError("consumer produced no tile-writer calls")
    base = min(int(call["writer_base"], 16) for call in writer_calls)
    outside_pixels = 0
    for call in writer_calls:
        destination = int(call["destination"], 16)
        value = int(call["tile_value"], 16)
        relative = destination - base
        tile_index = relative // 32
        tile_x = tile_index % tile_columns
        tile_y = tile_index // tile_columns
        within = relative % 32
        row = within // 4
        halfword = (within % 4) // 2
        x = tile_x * 8 + halfword * 4
        y = tile_y * 8 + row
        for pixel in range(4):
            px = x + pixel
            nibble = (value >> (pixel * 4)) & 0x0F
            if px >= width or y >= height:
                outside_pixels += nibble != 0
            else:
                pixels[y * width + px] = nibble
    cropped = bytearray()
    for row in range(expected_height):
        cropped.extend(pixels[row * width : row * width + expected_width])
    return {
        "width": expected_width,
        "height": expected_height,
        "tile_columns": tile_columns,
        "tile_rows": tile_rows,
        "tile_row_stride_bytes": tile_columns * 32,
        "pixel_nibble_sha256": sha256(bytes(cropped)),
        "pixel_nibble_nonzero": sum(value != 0 for value in cropped),
        "outside_nonzero_pixels": outside_pixels,
        "pixels": bytes(cropped),
    }


def write_pgm(path: Path, pixels: bytes, width: int, height: int) -> None:
    if len(pixels) != width * height:
        raise RuntimeQAError("PGM pixel length mismatch")
    image = bytes(value * 17 for value in pixels)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + image)


def _registers_metadata(regs: Mapping[str, int]) -> Dict[str, str]:
    names = ("r0", "r1", "r2", "r3", "r4", "r5", "sp", "lr", "pc")
    return {name: address(int(regs[name])) for name in names}


def _writer_event(client: GdbClient, regs: Mapping[str, int]) -> Dict[str, Any]:
    fifth = int.from_bytes(client.read_memory(regs["sp"] + 0x10, 4), "little")
    offset = ((fifth >> 3) << 5) + (regs["r2"] << 2) + (2 if fifth & 7 else 0) + regs["r3"]
    destination = regs["r0"] + offset
    return {
        "pc": address(regs["pc"]),
        "lr": address(regs["lr"]),
        "writer_base": address(regs["r0"]),
        "source_tile_value": f"0x{regs['r1'] & 0xFFFF:04X}",
        "row": regs["r2"],
        "tile_offset": f"0x{regs['r3']:04X}",
        "fifth_argument_pixel_x": fifth,
        "computed_offset": f"0x{offset:04X}",
        "destination": address(destination),
        "strh_bytes": 2,
        "registers": _registers_metadata(regs),
    }


def capture_record(
    client: GdbClient,
    rom: bytes,
    *,
    offset: int,
    role: str,
    source_ledger_sha256: Optional[str],
    output_dir: Optional[Path],
) -> Dict[str, Any]:
    metadata = record_metadata(
        rom,
        offset,
        source_ledger_sha256=source_ledger_sha256,
        role=role,
    )
    units = tuple(int(value, 16) for value in metadata["code_units"])
    static_glyphs = [glyph_bytes_for_unit(rom, unit) for unit in units]
    expected_raw = expected_tile_layout([entry["glyph"] for entry in static_glyphs])
    expected_pixels = expected_row_pixels([entry["glyph"] for entry in static_glyphs])
    slot_values = _assert_initialized(client)
    breakpoints = [CODEPAGE_LOOKUP, NARROW_GLYPH_ADD, TILE_WRITER, GLYPH_COMPLETE]
    codepage_events: List[Dict[str, Any]] = []
    glyph_events: List[Dict[str, Any]] = []
    writer_calls: List[Dict[str, Any]] = []
    complete: Optional[Dict[str, Any]] = None

    write_bounded_memory(client, CACHE_CLEAR_START, bytes(CACHE_CLEAR_LENGTH))
    cache_before = client.read_memory(CACHE_CLEAR_START, CACHE_CLEAR_LENGTH)
    for breakpoint in breakpoints:
        client.set_breakpoint(breakpoint)
    try:
        client.write_memory(TEMP_STACK, struct.pack("<I", 1))
        client.write_register(0, ROM_BASE + offset)
        client.write_register(1, 0)
        client.write_register(2, 0)
        client.write_register(3, CACHE_CLEAR_START)
        client.write_register(13, TEMP_STACK)
        client.write_register(14, TEMP_STACK | 1)
        client.write_register(15, gdb_pc_argument(CONSUMER, "thumb"))

        for _ in range(256):
            stop = client.continue_until_stop(8.0)
            kind, watched = parse_stop_watch(stop)
            if kind is not None:
                raise RuntimeQAError(f"unexpected watchpoint during {role}: {stop}")
            regs = client.read_registers()
            pc = regs["pc"]
            if pc == CODEPAGE_LOOKUP:
                codepage_events.append(
                    {
                        "pc": address(pc),
                        "lr": address(regs["lr"]),
                        "callsite": address(regs["lr"] - 5),
                        "source_pointer": address(regs["r5"]),
                        "code_unit": f"0x{regs['r0'] & 0xFFFF:04X}",
                        "mode": regs["r1"],
                    }
                )
            elif pc == NARROW_GLYPH_ADD:
                unit_index = len(glyph_events)
                pointer = regs["r0"]
                offset_value = regs["r4"]
                expected_pointer = slot_values["narrow"] + offset_value
                if pointer != expected_pointer:
                    raise RuntimeQAError(
                        f"glyph pointer mismatch at {role}: {address(pointer)} != {address(expected_pointer)}"
                    )
                glyph = client.read_memory(pointer, NARROW_GLYPH_BYTES)
                glyph_events.append(
                    {
                        "index": unit_index,
                        "pc": address(pc),
                        "lr": address(regs["lr"]),
                        "callsite": address(regs["lr"] - 5),
                        "code_unit": (
                            codepage_events[unit_index]["code_unit"]
                            if unit_index < len(codepage_events)
                            else "unknown"
                        ),
                        "initialized_base": address(slot_values["narrow"]),
                        "glyph_offset": f"0x{offset_value:04X}",
                        "glyph_pointer": address(pointer),
                        "glyph": summarize_bytes(glyph, pointer),
                    }
                )
            elif pc == TILE_WRITER:
                writer_calls.append(_writer_event(client, regs))
            elif pc == GLYPH_COMPLETE:
                if not writer_calls:
                    raise RuntimeQAError(f"no tile writer calls for {role}")
                base = min(int(call["writer_base"], 16) for call in writer_calls)
                tile_columns = math.ceil(metadata["line_width"] / 8)
                tile_rows = math.ceil(12 / 8)
                output_length = tile_columns * tile_rows * 32
                output_bytes = client.read_memory(base, output_length)
                cache_after = client.read_memory(CACHE_CLEAR_START, CACHE_CLEAR_LENGTH)
                complete = {
                    "pc": address(pc),
                    "cache": summarize_bytes(cache_after, CACHE_CLEAR_START),
                    "cache_before": summarize_bytes(cache_before, CACHE_CLEAR_START),
                    "tile_cache": summarize_bytes(output_bytes, base),
                    "tile_cache_expected_sha256": sha256(expected_raw),
                    "tile_cache_exact_expected": output_bytes == expected_raw,
                    "tile_writer_calls": len(writer_calls),
                    "tile_writer_byte_count": len(writer_calls) * 2,
                    "tile_writer_event_sha256": sha256(
                        b"".join(
                            struct.pack(
                                "<IH", int(call["destination"], 16), int(call["source_tile_value"], 16)
                            )
                            for call in writer_calls
                        )
                    ),
                }
                break
            else:
                raise RuntimeQAError(f"unexpected breakpoint in {role}: {stop} at {address(pc)}")
        else:
            raise RuntimeQAError(f"consumer stop budget exhausted for {role}")
    finally:
        for breakpoint in breakpoints:
            try:
                client.remove_breakpoint(breakpoint)
            except Exception:
                pass

    if complete is None:
        raise RuntimeQAError(f"consumer did not complete {role}")
    if len(codepage_events) != len(units) or len(glyph_events) != len(units):
        raise RuntimeQAError(
            f"consumer unit count mismatch for {role}: codepage={len(codepage_events)} "
            f"glyph={len(glyph_events)} expected={len(units)}"
        )
    runtime_render = writer_pixel_render(
        writer_calls,
        expected_width=int(metadata["line_width"]),
    )
    runtime_render_pixels = bytes(runtime_render.pop("pixels"))
    runtime_render["expected_pixel_nibble_sha256"] = sha256(expected_pixels)
    runtime_render["pixel_render_exact_expected"] = runtime_render["pixel_nibble_sha256"] == sha256(expected_pixels)
    runtime_render["line_width_expected"] = metadata["line_width"]
    runtime_render["newline_branch_observed"] = False
    runtime_render["layout_status"] = (
        "exact_8x12_narrow_tile_layout" if runtime_render["pixel_render_exact_expected"] else "mismatch"
    )

    if output_dir is not None:
        write_pgm(
            output_dir / f"{role}-runtime-tile-cache.pgm",
            runtime_render_pixels,
            int(runtime_render["width"]),
            int(runtime_render["height"]),
        )

    for index, event in enumerate(glyph_events):
        if index < len(static_glyphs):
            event["static_glyph_sha256"] = static_glyphs[index]["summary"]["sha256"]
            event["runtime_static_glyph_match"] = event["glyph"]["sha256"] == static_glyphs[index]["summary"]["sha256"]

    return {
        "record": metadata,
        "consumer": {
            "pc": address(CONSUMER),
            "controlled": True,
            "control_method": "single bounded argument/index setup after live font-base guard",
            "font_slots": {name: address(value) for name, value in slot_values.items()},
            "codepage_lookup": codepage_events,
            "glyph_addressing": glyph_events,
            "tile_writer": {
                "pc": address(TILE_WRITER),
                "calls": writer_calls,
                "destination_first": address(min(int(call["destination"], 16) for call in writer_calls)),
                "destination_last": address(max(int(call["destination"], 16) for call in writer_calls)),
                "strh_bytes_each": 2,
            },
            "complete": complete,
            "runtime_render": runtime_render,
            "termination": {
                "terminator": "NUL",
                "codepage_units_consumed": len(codepage_events),
                "codepage_units_expected": len(units),
                "record_not_truncated": len(codepage_events) == len(units),
            },
        },
    }


def natural_screen_hash(client: GdbClient) -> Dict[str, Any]:
    regions = {
        "vram": NATURAL_VRAM,
        "palette": NATURAL_PALETTE,
        "oam": NATURAL_OAM,
    }
    blobs = {name: client.read_memory(start, length) for name, (start, length) in regions.items()}
    io = client.read_memory(0x04000000, 0x40)
    combined = b"".join(blobs[name] for name in ("vram", "palette", "oam")) + io
    return {
        name: summarize_bytes(data, regions[name][0]) for name, data in blobs.items()
    } | {
        "io_sha256": sha256(io),
        "screen_state_sha256": sha256(combined),
    }


def natural_path(
    client: GdbClient,
    *,
    name: str,
    duration: float,
    actions: Sequence[Tuple[str, int, int]],
) -> Dict[str, Any]:
    """Try one explicit natural path; button values are active-low KEYINPUT."""
    events: List[Dict[str, Any]] = []
    consumer_hits = 0
    target_reads = 0
    target_breakpoint = TARGET_OFFSET + ROM_BASE
    client.set_breakpoint(CONSUMER)
    client.set_watchpoint(target_breakpoint, 4, 3)
    if not actions:
        try:
            stop = client.continue_and_interrupt(duration)
            kind, watched = parse_stop_watch(stop)
            regs = client.read_registers()
            if kind == "rwatch" and watched == target_breakpoint:
                target_reads = 1
                events.append(
                    {
                        "kind": "target_source_read",
                        "pc": address(regs["pc"]),
                        "lr": address(regs["lr"]),
                        "source_pointer": address(regs["r0"]),
                    }
                )
            elif kind is None and regs["pc"] == CONSUMER:
                consumer_hits = 1
                events.append(
                    {
                        "kind": "consumer_hit",
                        "pc": address(regs["pc"]),
                        "lr": address(regs["lr"]),
                        "registers": _registers_metadata(regs),
                    }
                )
            else:
                events.append({"kind": "window_stop", "stop": stop, "pc": address(regs["pc"])})
        except (OSError, TimeoutError) as exc:
            # A GDB interrupt timeout leaves mGBA's single connection in an
            # undefined state.  Do not read screen memory or continue into the
            # controlled phase on a possibly-running target; that would mix a
            # transport failure with runtime evidence.
            events.append({"kind": "transport_negative", "error": str(exc)})
            return {
                "name": name,
                "mode": "natural_navigation_attempt",
                "duration_seconds": duration,
                "button_path": [],
                "consumer_hits": consumer_hits,
                "target_source_reads": target_reads,
                "events": events,
                "screen": None,
                "coverage": "transport_negative",
            }
        finally:
            try:
                client.remove_breakpoint(CONSUMER, 2, 1)
            except Exception:
                pass
            try:
                client.remove_watchpoint(target_breakpoint, 2, 3)
            except Exception:
                pass
        return {
            "name": name,
            "mode": "natural_navigation_attempt",
            "duration_seconds": duration,
            "button_path": [],
            "consumer_hits": consumer_hits,
            "target_source_reads": target_reads,
            "events": events,
            "screen": natural_screen_hash(client),
            "coverage": "target_not_reached" if target_reads == 0 else "target_source_read_observed",
        }
    if actions:
        client.set_watchpoint(KEYINPUT, 2, 3)
    action_index = 0
    action_reads = 0
    deadline = time.monotonic() + duration
    try:
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                stop = client.continue_until_stop(min(2.0, remaining))
            except TimeoutError:
                stop = client.interrupt(timeout=2.0)
                events.append({"kind": "window_interrupt", "stop": stop})
                break
            kind, watched = parse_stop_watch(stop)
            regs = client.read_registers()
            if kind == "rwatch" and watched == KEYINPUT:
                if action_index < len(actions):
                    label, value, repeats = actions[action_index]
                    client.write_register(0, value)
                    events.append(
                        {
                            "kind": "button_injected_at_key_read",
                            "label": label,
                            "active_low_value": f"0x{value:03X}",
                            "read_index": action_reads,
                            "pc": address(regs["pc"]),
                        }
                    )
                    action_reads += 1
                    if action_reads >= repeats:
                        action_index += 1
                        action_reads = 0
                else:
                    client.write_register(0, 0x3FF)
                continue
            if kind == "rwatch" and watched == target_breakpoint:
                target_reads += 1
                events.append(
                    {
                        "kind": "target_source_read",
                        "pc": address(regs["pc"]),
                        "lr": address(regs["lr"]),
                        "source_pointer": address(regs["r0"]),
                    }
                )
                continue
            if kind is None and regs["pc"] == CONSUMER:
                consumer_hits += 1
                events.append(
                    {
                        "kind": "consumer_hit",
                        "pc": address(regs["pc"]),
                        "lr": address(regs["lr"]),
                        "registers": _registers_metadata(regs),
                    }
                )
                continue
            events.append(
                {
                    "kind": "other_stop",
                    "stop": stop,
                    "pc": address(regs["pc"]),
                }
            )
    finally:
        for operation in (
            ("breakpoint", CONSUMER, 2, 1),
            ("watchpoint", target_breakpoint, 2, 3),
            ("watchpoint", KEYINPUT, 2, 3),
        ):
            if operation[0] == "watchpoint" and operation[1] == KEYINPUT and not actions:
                continue
            try:
                if operation[0] == "breakpoint":
                    client.remove_breakpoint(operation[1], operation[2], operation[3])
                else:
                    client.remove_watchpoint(operation[1], operation[2], operation[3])
            except Exception:
                pass
    return {
        "name": name,
        "mode": "natural_navigation_attempt",
        "duration_seconds": duration,
        "button_path": [
            {"label": label, "active_low_value": f"0x{value:03X}", "read_repeats": repeats}
            for label, value, repeats in actions
        ],
        "consumer_hits": consumer_hits,
        "target_source_reads": target_reads,
        "events": events,
        "screen": natural_screen_hash(client),
        "coverage": "target_not_reached" if target_reads == 0 else "target_source_read_observed",
    }


def compare_reports(base: Mapping[str, Any], patched: Mapping[str, Any]) -> Dict[str, Any]:
    base_records = base["records"]
    patched_records = patched["records"]
    target_base = base_records["target"]
    target_patched = patched_records["target"]
    adjacent_base = base_records["adjacent"]
    adjacent_patched = patched_records["adjacent"]
    base_target_runtime = target_base["consumer"]
    patched_target_runtime = target_patched["consumer"]
    base_adj_runtime = adjacent_base["consumer"]
    patched_adj_runtime = adjacent_patched["consumer"]
    base_adj_glyphs = [event["glyph"]["sha256"] for event in base_adj_runtime["glyph_addressing"]]
    patched_adj_glyphs = [event["glyph"]["sha256"] for event in patched_adj_runtime["glyph_addressing"]]
    if len(base_adj_glyphs) != len(patched_adj_glyphs):
        raise RuntimeQAError("adjacent glyph count changed between base and patched runtime")
    return {
        "schema": "super-robot-taisen-d-m19-runtime-qa-v1",
        "base_rom_sha256": base["rom"]["sha256"],
        "patched_rom_sha256": patched["rom"]["sha256"],
        "bps": patched.get("bps"),
        "target": {
            "string_id": TARGET_OFFSET,
            "same_payload_length": target_base["record"]["payload_length"] == target_patched["record"]["payload_length"],
            "base_payload_sha256": target_base["record"]["source_raw_sha256"],
            "patched_payload_sha256": target_patched["record"]["source_raw_sha256"],
            "payload_changed": target_base["record"]["source_raw_sha256"] != target_patched["record"]["source_raw_sha256"],
            "base_runtime_tile_cache_sha256": base_target_runtime["complete"]["tile_cache"]["sha256"],
            "patched_runtime_tile_cache_sha256": patched_target_runtime["complete"]["tile_cache"]["sha256"],
            "runtime_render_changed": base_target_runtime["runtime_render"]["pixel_nibble_sha256"] != patched_target_runtime["runtime_render"]["pixel_nibble_sha256"],
            "patched_record_readable": patched_target_runtime["termination"]["record_not_truncated"],
            "patched_layout_exact": patched_target_runtime["runtime_render"]["pixel_render_exact_expected"],
            "patched_controlled": patched_target_runtime["controlled"],
        },
        "adjacent": {
            "string_id": ADJACENT_OFFSET,
            "payload_sha256_equal": adjacent_base["record"]["source_raw_sha256"] == adjacent_patched["record"]["source_raw_sha256"],
            "tile_cache_sha256_equal": base_adj_runtime["complete"]["tile_cache"]["sha256"] == patched_adj_runtime["complete"]["tile_cache"]["sha256"],
            "render_sha256_equal": base_adj_runtime["runtime_render"]["pixel_nibble_sha256"] == patched_adj_runtime["runtime_render"]["pixel_nibble_sha256"],
            "existing_glyph_hashes_equal": base_adj_glyphs == patched_adj_glyphs,
            "runtime_layout_exact_base": base_adj_runtime["runtime_render"]["pixel_render_exact_expected"],
            "runtime_layout_exact_patched": patched_adj_runtime["runtime_render"]["pixel_render_exact_expected"],
            "untouched_runtime": (
                adjacent_base["record"]["source_raw_sha256"] == adjacent_patched["record"]["source_raw_sha256"]
                and base_adj_runtime["complete"]["tile_cache"]["sha256"] == patched_adj_runtime["complete"]["tile_cache"]["sha256"]
                and base_adj_glyphs == patched_adj_glyphs
            ),
        },
        "font_initialization": {
            "slot_values_equal": base["initializer"]["slot_values"] == patched["initializer"]["slot_values"],
            "resource_hashes_equal": base["initializer"]["resource_hashes"] == patched["initializer"]["resource_hashes"],
            "nonzero_base_guard": base["initializer"]["nonzero_base_guard"] and patched["initializer"]["nonzero_base_guard"],
        },
        "natural_navigation": {
            "base": base.get("natural_paths", []),
            "patched": patched.get("natural_paths", []),
            "target_natural_coverage": "not_observed" if not any(path.get("target_source_reads") for path in base.get("natural_paths", []) + patched.get("natural_paths", [])) else "observed",
        },
        "gate": {
            "accepted_static_runtime_slice": (
                target_patched["consumer"]["termination"]["record_not_truncated"]
                and target_patched["consumer"]["runtime_render"]["pixel_render_exact_expected"]
                and adjacent_base["consumer"]["runtime_render"]["pixel_render_exact_expected"]
                and adjacent_patched["consumer"]["runtime_render"]["pixel_render_exact_expected"]
            ),
            "translation_status": "ai_draft",
            "natural_screen_not_claimed": True,
        },
    }


def run_probe(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    rom = rom_path.read_bytes()
    rom_hash = sha256(rom)
    expected_hash = BASE_ROM_SHA256 if args.label == "base" else PATCHED_ROM_SHA256
    if rom_hash != expected_hash:
        raise RuntimeQAError(f"{args.label} ROM hash mismatch: {rom_hash}")
    bps_meta: Optional[Dict[str, Any]] = None
    if args.bps:
        bps_data = Path(args.bps).read_bytes()
        bps_meta = {
            "sha256": sha256(bps_data),
            "size": len(bps_data),
            "expected_sha256": BPS_SHA256,
            "expected_size": BPS_SIZE,
            "hash_match": sha256(bps_data) == BPS_SHA256 and len(bps_data) == BPS_SIZE,
        }
        if not bps_meta["hash_match"]:
            raise RuntimeQAError("BPS hash/size mismatch")

    source_records = read_source_records(Path(args.source_table))
    source_by_offset = {int(row["offset"]): row for row in source_records}
    if TARGET_OFFSET not in source_by_offset or ADJACENT_OFFSET not in source_by_offset:
        raise RuntimeQAError("target or adjacent source record missing")
    ledger = read_one_jsonl(Path(args.ledger))
    ledger_source_hash = str(ledger["source_hash"])
    source_text = str(source_by_offset[TARGET_OFFSET]["text"])
    if sha256(source_text.encode("utf-8")) != ledger_source_hash:
        raise RuntimeQAError("M1.8 ledger source hash no longer matches local source table")

    output_dir = Path(args.render_dir) if args.render_dir else None
    natural_paths: List[Dict[str, Any]] = []
    initializer: Dict[str, Any]
    with GdbClient(port=args.port, timeout=max(8.0, args.stop_timeout)) as client:
        if args.natural:
            natural_result = natural_path(client, name="idle_boot", duration=1.5, actions=[])
            natural_paths.append(natural_result)
            if natural_result["coverage"] == "transport_negative":
                raise RuntimeQAError(
                    "natural path ended in GDB transport negative; rerun the controlled "
                    "phase with a fresh mGBA process and without --natural"
                )
        initializer = capture_initializer(
            client,
            rom,
            boot_seconds=args.boot_seconds,
            stop_timeout=args.stop_timeout,
        )
        slot_values = initializer["slot_values"]
        resource_hashes = {
            event_name: event.get(event_name, {}).get("resource_hash", {}).get("sha256")
            for event in initializer["events"]
            for event_name in ("narrow", "wide")
            if event.get(event_name)
        }
        initializer_summary = {
            "slot_values": slot_values,
            "resource_hashes": resource_hashes,
            "nonzero_base_guard": all(value != "0x00000000" for value in slot_values.values()),
            "writer_events": [
                {
                    "kind": event.get("kind"),
                    "pc": event.get("pc"),
                    "lr": event.get("lr"),
                    "caller_callsite": event.get("caller_callsite"),
                    "watched_address": event.get("watched_address"),
                    "writer_pc": event.get("writer_pc"),
                    "slots": event.get("slots"),
                }
                for event in initializer["events"]
            ],
        }
        records = {
            "target": capture_record(
                client,
                rom,
                offset=TARGET_OFFSET,
                role="target",
                source_ledger_sha256=ledger_source_hash,
                output_dir=output_dir,
            ),
            "adjacent": capture_record(
                client,
                rom,
                offset=ADJACENT_OFFSET,
                role="adjacent_untouched",
                source_ledger_sha256=None,
                output_dir=output_dir,
            ),
        }
    report = {
        "schema": "super-robot-taisen-d-m19-runtime-qa-v1",
        "game_code": "A6SJ",
        "label": args.label,
        "rom": {
            "path_role": args.label,
            "sha256": rom_hash,
            "expected_sha256": expected_hash,
            "hash_match": True,
        },
        "bps": bps_meta,
        "gdb": {
            "port": args.port,
            "single_connection": True,
            "fresh_process_required": True,
            "controlled_consumer_after_initialized_base": True,
        },
        "source_confidence": {
            "method": "strict Shift-JIS NUL-bounded source table plus M1.8 same-length static patch",
            "target_string_id": TARGET_OFFSET,
            "ledger_source_hash_match": True,
            "source_text_emitted": False,
        },
        "natural_paths": natural_paths,
        "initializer": initializer_summary,
        "records": records,
        "translation_status": "ai_draft",
        "runtime_scope": "controlled consumer/tile-cache render; no natural screen claim",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"m19_runtime_qa=accepted label={args.label} output={output}")


def compare_probe(args: argparse.Namespace) -> None:
    base = json.loads(Path(args.base_report).read_text(encoding="utf-8"))
    patched = json.loads(Path(args.patched_report).read_text(encoding="utf-8"))
    comparison = compare_reports(base, patched)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"m19_runtime_compare=accepted output={output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("rom", type=Path)
    run.add_argument("--label", choices=("base", "patched"), required=True)
    run.add_argument("--port", type=int, required=True)
    run.add_argument("--source-table", type=Path, required=True)
    run.add_argument("--ledger", type=Path, required=True)
    run.add_argument("--bps", type=Path)
    run.add_argument("--boot-seconds", type=float, default=1.0)
    run.add_argument("--stop-timeout", type=float, default=8.0)
    run.add_argument("--natural", action="store_true")
    run.add_argument("--render-dir", type=Path)
    run.add_argument("--output", type=Path, required=True)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--base-report", type=Path, required=True)
    compare.add_argument("--patched-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "run":
            run_probe(args)
        else:
            compare_probe(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m19_rejected={exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
