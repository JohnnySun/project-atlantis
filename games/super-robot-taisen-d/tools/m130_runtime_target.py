#!/usr/bin/env python3
"""Bounded corrected mGBA capture for the M1.8 target record.

The historical M1.9 probe treated one call to ``0x08008724`` as if it
consumed a complete record.  The verified M1.6 path shows that this function
consumes one glyph unit per call.  This probe therefore makes one controlled
consumer call per two-byte unit and joins only hashes/counts for the record.

The mGBA 0.10.5 GDB stub used here accepts an architectural PC in ``P15`` and
rebuilds its prefetch pipeline.  The probe writes the actual instruction
address (not an adjusted address), a convention verified against the local
stub source.  It enters the existing Thumb initializer caller directly and
does not alter ROM or executable RAM.

Reports contain source-safe hashes, addresses, register metadata, counts, and
render hashes only.  ROMs, source tables, screenshots, and probe output stay
under ignored ``roms/``/``research/``/``work/`` paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from core.gba.gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m17_layout import ROM_BASE, source_payload, tokenize_payload  # noqa: E402
from m19_runtime_qa import (  # noqa: E402
    CACHE_CLEAR_LENGTH,
    CACHE_CLEAR_START,
    CODEPAGE_LOOKUP,
    GLYPH_COMPLETE,
    NARROW_GLYPH_ADD,
    NARROW_GLYPH_BYTES,
    TEMP_STACK,
    address,
    expected_row_pixels,
    glyph_bytes_for_unit,
    sha256,
    summarize_bytes,
    writer_pixel_render,
)
from probe_font_resource import (  # noqa: E402
    INITIALIZER,
    INITIALIZER_CALLSITE,
    NARROW_SLOT,
    SLOTS,
    static_resource_metadata,
)


TARGET_OFFSET = 0x080858
ADJACENT_OFFSET = 0x080860
DIRECT_THUMB_INITIALIZER_CALLER = 0x08014E84
NUL_BRANCH = 0x08008770
NUL_RETURN = 0x08008798
NUL_RENDER_EXIT = 0x08008954
NARROW_RESOURCE_SIZE = 0x1980
TILE_OUTPUT_LENGTH = 0x80
WRITER_ENTRY = 0x08008650
WRITER_STORE = 0x08008670
TILE_CALLSITES = (0x08008914, 0x08008926, 0x0800893C)

BASE_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
PATCHED_ROM_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
BPS_SHA256 = "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"
BPS_SIZE = 66


class RuntimeTargetError(RuntimeError):
    """A bounded runtime invariant failed closed."""


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_ledger_hash(path: Path, string_id: int) -> str:
    for row in _read_jsonl(path):
        if int(row.get("string_id", -1)) == string_id:
            value = row.get("source_hash")
            if isinstance(value, str) and len(value) == 64:
                return value
    raise RuntimeTargetError(f"ledger source hash missing for {string_id}")


def _rom_hash(path: Path) -> str:
    return sha256(path.read_bytes())


def _pc(client: GdbClient, target: int) -> None:
    """Write an architectural PC; mGBA rebuilds the mode-specific pipeline."""
    client.write_register(15, target)


def _register_subset(regs: Mapping[str, int], names: Sequence[str]) -> Dict[str, str]:
    return {name: address(int(regs[name])) for name in names}


def _unit_metadata(payload: bytes) -> Tuple[List[int], List[Dict[str, Any]]]:
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        raise RuntimeTargetError("target/adjacent record is not narrow glyph-only")
    units: List[int] = []
    tokens: List[Dict[str, Any]] = []
    for token in tokenization.tokens:
        if token.glyph_class != "narrow" or len(token.raw) != 2:
            raise RuntimeTargetError("record contains non-narrow or malformed token")
        unit = int.from_bytes(token.raw, "little")
        units.append(unit)
        tokens.append(
            {
                "byte_offset": token.raw_offset,
                "code_unit": f"0x{unit:04X}",
                "layout_width": token.layout_width,
                "glyph_class": token.glyph_class,
            }
        )
    return units, tokens


def _record_metadata(rom: bytes, offset: int, role: str, ledger_hash: Optional[str]) -> Dict[str, Any]:
    payload, terminator = source_payload(rom, offset)
    units, tokens = _unit_metadata(payload)
    return {
        "role": role,
        "string_id": offset,
        "source_address": address(ROM_BASE + offset),
        "source_raw_sha256": sha256(payload),
        "source_ledger_sha256": ledger_hash,
        "payload_length": len(payload),
        "unit_count": len(units),
        "line_width": len(units) * 8,
        "terminator": "NUL",
        "terminator_address": address(ROM_BASE + terminator),
        "control_tokens": [],
        "units": tokens,
        "record_end_exclusive": address(ROM_BASE + terminator + 1),
    }


def _slot_values(client: GdbClient) -> Dict[str, int]:
    return {
        name: int.from_bytes(client.read_memory(slot, 4), "little")
        for name, slot in SLOTS.items()
    }


def _capture_initializer(client: GdbClient, rom: bytes, stop_timeout: float) -> Dict[str, Any]:
    """Enter the known Thumb caller without the old ARM-PC adjustment bug."""
    boot_stop = client.continue_and_interrupt(0.4)
    boot_regs = client.read_registers()
    if not (boot_regs["cpsr"] & 0x20):
        raise RuntimeTargetError("corrected direct-Thumb entry requires a Thumb boot state")

    for slot in SLOTS.values():
        client.set_watchpoint(slot, 4, 2)
    client.set_breakpoint(INITIALIZER)
    events: List[Dict[str, Any]] = []
    caller: Optional[Dict[str, Any]] = None
    try:
        # 0x08014e84 is already a Thumb caller which sets the initializer
        # arguments and BLs to 0x080083a0.  Keeping the current Thumb mode
        # avoids the old P19/ARM BX trampoline entirely.
        _pc(client, DIRECT_THUMB_INITIALIZER_CALLER)
        for _ in range(12):
            stop = client.continue_until_stop(stop_timeout)
            kind, watched = parse_stop_watch(stop)
            regs = client.read_registers()
            values = _slot_values(client)
            if kind is None and regs["pc"] == INITIALIZER:
                caller = {
                    "pc": address(regs["pc"]),
                    "lr": address(regs["lr"]),
                    "caller_callsite": address(regs["lr"] - 5),
                    "arguments": _register_subset(regs, ("r0", "r1", "r2", "r3")),
                }
                events.append({"kind": "initializer_entry", **caller})
                continue
            if kind is None or watched not in SLOTS.values():
                raise RuntimeTargetError(
                    f"unexpected initializer stop {stop} at {address(regs['pc'])}"
                )
            slot_name = next(name for name, slot in SLOTS.items() if slot == watched)
            live_pointer = values[slot_name]
            resource = {
                "slot": address(watched),
                "writer_pc": address(max(0, regs["pc"] - 2)),
                "pc": address(regs["pc"]),
                "lr": address(regs["lr"]),
                "pointer": address(live_pointer),
                "pointer_region": "rom" if 0x08000000 <= live_pointer < 0x08800000 else "ram_or_io",
            }
            if live_pointer:
                resource["resource_hash"] = summarize_bytes(
                    client.read_memory(live_pointer, 0x100), live_pointer
                )
            events.append(
                {
                    "kind": "slot_write",
                    "stop": stop,
                    "watch_kind": kind,
                    "watched_address": address(watched),
                    "registers": _register_subset(regs, ("r0", "r1", "r2", "r3", "sp", "lr", "pc")),
                    "resource": resource,
                    "nonzero_slot_count": sum(value != 0 for value in values.values()),
                }
            )
            if all(values.values()):
                break
        values = _slot_values(client)
    finally:
        try:
            client.remove_breakpoint(INITIALIZER)
        finally:
            for slot in SLOTS.values():
                try:
                    client.remove_watchpoint(slot, 4, 2)
                except Exception:
                    pass
    if not all(values.values()):
        raise RuntimeTargetError("initializer did not produce two non-zero font bases")
    return {
        "boot_stop": boot_stop,
        "boot_registers": _register_subset(boot_regs, ("pc", "sp", "cpsr")),
        "entry": address(DIRECT_THUMB_INITIALIZER_CALLER),
        "verified_callsite": address(INITIALIZER_CALLSITE),
        "initializer": address(INITIALIZER),
        "caller": caller,
        "slot_values": {name: address(value) for name, value in values.items()},
        "slot_nonzero": all(values.values()),
        "events": events,
        "static_resource": static_resource_metadata(rom),
    }


def _capture_one_unit(
    client: GdbClient,
    rom: bytes,
    record: Mapping[str, Any],
    unit_index: int,
    slot_values: Mapping[str, int],
) -> Dict[str, Any]:
    units = [int(item["code_unit"], 16) for item in record["units"]]
    byte_offset = int(record["units"][unit_index]["byte_offset"])
    unit = units[unit_index]
    source_pointer = ROM_BASE + int(record["string_id"]) + byte_offset
    nul_address = ROM_BASE + int(record["terminator_address"], 16) - ROM_BASE
    static_glyph = glyph_bytes_for_unit(rom, unit)
    codepage_event: Optional[Dict[str, Any]] = None
    glyph_event: Optional[Dict[str, Any]] = None
    codepage_hit_count = 0
    glyph_hit_count = 0
    writer_calls: List[Dict[str, Any]] = []
    complete: Optional[Dict[str, Any]] = None
    nul_read = False
    breakpoints = (CODEPAGE_LOOKUP, NARROW_GLYPH_ADD, *TILE_CALLSITES, GLYPH_COMPLETE)
    cache_before = client.read_memory(CACHE_CLEAR_START, CACHE_CLEAR_LENGTH)
    for breakpoint in breakpoints:
        client.set_breakpoint(breakpoint)
    client.set_watchpoint(nul_address, 2, 3)
    try:
        client.write_memory(TEMP_STACK, struct.pack("<I", 1))
        client.write_register(0, source_pointer)
        client.write_register(1, 0)
        # 0x080085B0 uses the consumer's third argument as the 4bpp ink
        # nibble.  Zero is a valid transparent colour and would make a
        # renderer proof vacuous; M1.8's fixed glyph contract uses index 1.
        client.write_register(2, 1)
        client.write_register(3, CACHE_CLEAR_START)
        client.write_register(13, TEMP_STACK)
        client.write_register(14, TEMP_STACK | 1)
        _pc(client, 0x08008724)
        for _ in range(96):
            stop = client.continue_until_stop(8.0)
            kind, watched = parse_stop_watch(stop)
            regs = client.read_registers()
            if kind is not None:
                if kind == "rwatch" and watched == nul_address:
                    nul_read = True
                    continue
                raise RuntimeTargetError(
                    f"unexpected consumer watch stop {stop} for {record['role']} unit {unit_index}"
                )
            pc = regs["pc"]
            if pc == CODEPAGE_LOOKUP:
                codepage_hit_count += 1
                observed = regs["r0"] & 0xFFFF
                codepage_event = {
                    "pc": address(pc),
                    "lr": address(regs["lr"]),
                    "callsite": address(regs["lr"] - 5),
                    "source_pointer": address(regs["r5"]),
                    "expected_source_pointer": address(source_pointer),
                    "code_unit": f"0x{observed:04X}",
                    "expected_code_unit": f"0x{unit:04X}",
                    "mode": regs["r1"],
                }
                continue
            if pc == NARROW_GLYPH_ADD:
                glyph_hit_count += 1
                pointer = regs["r0"]
                offset = regs["r4"]
                expected_pointer = slot_values["narrow"] + offset
                if pointer != expected_pointer:
                    raise RuntimeTargetError(
                        f"glyph pointer mismatch {address(pointer)} != {address(expected_pointer)}"
                    )
                live_glyph = client.read_memory(pointer, NARROW_GLYPH_BYTES)
                glyph_event = {
                    "pc": address(pc),
                    "lr": address(regs["lr"]),
                    "base_slot": address(NARROW_SLOT),
                    "initialized_base": address(slot_values["narrow"]),
                    "glyph_offset": f"0x{offset:04X}",
                    "glyph_pointer": address(pointer),
                    "glyph": summarize_bytes(live_glyph, pointer),
                    "static_glyph": static_glyph["summary"],
                    "runtime_static_glyph_match": sha256(live_glyph) == static_glyph["summary"]["sha256"],
                }
                continue
            if pc in TILE_CALLSITES:
                fifth_argument = int.from_bytes(client.read_memory(regs["sp"], 4), "little")
                tile_source_pointer = regs["r6"]
                tile_source_bytes = client.read_memory(tile_source_pointer, 2)
                tile_value = int.from_bytes(tile_source_bytes, "little")
                glyph_source_pointer = regs["r8"]
                glyph_source_byte = client.read_memory(glyph_source_pointer, 1)
                render_buffer_window = client.read_memory(tile_source_pointer, NARROW_GLYPH_BYTES)
                computed_offset = (
                    ((fifth_argument >> 3) << 5)
                    + (regs["r2"] << 2)
                    + (2 if fifth_argument & 7 else 0)
                    + regs["r3"]
                )
                writer_calls.append(
                    {
                        "callsite": address(pc),
                        "writer_pc": address(WRITER_ENTRY),
                        "writer_store_pc": address(WRITER_STORE),
                        "lr": address(regs["lr"]),
                        "writer_base": address(regs["r0"]),
                        "destination": address(regs["r0"] + computed_offset),
                        "tile_value": f"0x{tile_value:04X}",
                        "tile_value_source": "live_memory_at_0x08008908_ldrh_r6",
                        "tile_source_pointer": address(tile_source_pointer),
                        "tile_source_word_sha256": sha256(tile_source_bytes),
                        "pipeline_r1_value": f"0x{regs['r1'] & 0xFFFF:04X}",
                        "pipeline_r1_matches_live_word": (regs["r1"] & 0xFFFF) == tile_value,
                        "glyph_source_pointer": address(glyph_source_pointer),
                        "glyph_source_byte": f"0x{glyph_source_byte[0]:02X}",
                        "glyph_source_byte_sha256": sha256(glyph_source_byte),
                        "render_buffer_window_sha256": sha256(render_buffer_window),
                        "render_buffer_window_nonzero_bytes": sum(value != 0 for value in render_buffer_window),
                        "row": regs["r2"],
                        "tile_offset": f"0x{regs['r3']:04X}",
                        "fifth_argument_pixel_x": fifth_argument,
                        "computed_offset": f"0x{computed_offset:04X}",
                        "strh_bytes": 2,
                        "registers": _register_subset(
                            regs, ("r0", "r1", "r2", "r3", "r6", "r8", "sp", "lr", "pc")
                        ),
                    }
                )
                continue
            if pc == GLYPH_COMPLETE:
                if not writer_calls:
                    raise RuntimeTargetError("glyph completed without tile-writer calls")
                writer_base = min(int(call["writer_base"], 16) for call in writer_calls)
                tile_output = client.read_memory(writer_base, TILE_OUTPUT_LENGTH)
                complete = {
                    "pc": address(pc),
                    "cache_before": summarize_bytes(cache_before, CACHE_CLEAR_START),
                    "cache_after": summarize_bytes(
                        client.read_memory(CACHE_CLEAR_START, CACHE_CLEAR_LENGTH), CACHE_CLEAR_START
                    ),
                    "tile_output_buffer": summarize_bytes(tile_output, writer_base),
                    "tile_output_buffer_role": "bounded post-consumer observation; not the exact render gate",
                    "writer_call_count": len(writer_calls),
                }
                break
            raise RuntimeTargetError(f"unexpected consumer stop {stop} at {address(pc)}")
        else:
            raise RuntimeTargetError("consumer unit stop budget exhausted")
    finally:
        for breakpoint in breakpoints:
            try:
                client.remove_breakpoint(breakpoint)
            except Exception:
                pass
        try:
            client.remove_watchpoint(nul_address, 2, 3)
        except Exception:
            pass
    if codepage_event is None or glyph_event is None or complete is None:
        raise RuntimeTargetError("consumer unit did not produce complete codepage/glyph/writer evidence")
    # The consumer pre-scans from the hijacked source pointer to the record's
    # NUL before rendering.  Therefore unit 0 uses the full remaining record
    # stride (16px here), while a later unit uses the remaining suffix stride.
    # We stop at the first GLYPH_COMPLETE, so later units are expected blank in
    # this bounded per-unit capture rather than silently treated as rendered.
    remaining_units = len(units) - unit_index
    render_width = remaining_units * 8
    expected_glyphs = [static_glyph["glyph"]] + [bytes(NARROW_GLYPH_BYTES)] * (remaining_units - 1)
    expected_pixels = expected_row_pixels(expected_glyphs)
    render = writer_pixel_render(writer_calls, expected_width=render_width)
    render.pop("pixels", None)
    render.update(
        {
            "source": "live_consumer_callsite_arguments_to_0x08008670",
            "layout_width_from_source_suffix": render_width,
            "layout_remaining_unit_count": remaining_units,
            "expected_pixel_nibble_sha256": sha256(expected_pixels),
            "pixel_render_exact_expected": render["pixel_nibble_sha256"] == sha256(expected_pixels),
            "pixels_emitted": False,
        }
    )
    return {
        "unit_index": unit_index,
        "source_byte_offset": byte_offset,
        "source_pointer": address(source_pointer),
        "code_unit": f"0x{unit:04X}",
        "codepage": codepage_event,
        "glyph": glyph_event,
        "writer": {
            "pc": address(WRITER_ENTRY),
            "store_pc": address(WRITER_STORE),
            "calls": writer_calls,
            "destination_first": min(call["destination"] for call in writer_calls),
            "destination_last": max(call["destination"] for call in writer_calls),
            "strh_byte_count": len(writer_calls) * 2,
        },
        "complete": complete,
        "render": render,
        "nul_read_observed_during_unit": nul_read,
        "consumer_event_counts": {
            "codepage_lookup": codepage_hit_count,
            "narrow_glyph_add": glyph_hit_count,
            "tile_writer_callsites": len(writer_calls),
        },
        "controlled_renderer_palette_index": 1,
        "unit_not_truncated": (
            codepage_hit_count == 1
            and glyph_hit_count == 1
            and codepage_event["source_pointer"] == codepage_event["expected_source_pointer"]
            and codepage_event["code_unit"] == codepage_event["expected_code_unit"]
        ),
    }


def _capture_nul(client: GdbClient, record: Mapping[str, Any]) -> Dict[str, Any]:
    nul_address = int(record["terminator_address"], 16)
    breakpoints = (NUL_BRANCH, NUL_RETURN, NUL_RENDER_EXIT)
    for breakpoint in breakpoints:
        client.set_breakpoint(breakpoint)
    try:
        client.write_memory(TEMP_STACK, struct.pack("<I", 1))
        client.write_register(0, nul_address)
        client.write_register(1, 0)
        client.write_register(2, 0)
        client.write_register(3, CACHE_CLEAR_START)
        client.write_register(13, TEMP_STACK)
        client.write_register(14, TEMP_STACK | 1)
        _pc(client, 0x08008724)
        stop = client.continue_until_stop(8.0)
        kind, watched = parse_stop_watch(stop)
        regs = client.read_registers()
        if kind is not None:
            raise RuntimeTargetError(f"unexpected NUL watch stop {stop}")
        return {
            "observed": regs["pc"] in breakpoints,
            "pc": address(regs["pc"]),
            "lr": address(regs["lr"]),
            "source_pointer": address(regs["r5"]),
            "terminator_address": address(nul_address),
            "watch_kind": kind,
            "watched_address": None if watched is None else address(watched),
            "glyph_events_expected": 0,
        }
    finally:
        for breakpoint in breakpoints:
            try:
                client.remove_breakpoint(breakpoint)
            except Exception:
                pass


def _capture_record(
    client: GdbClient,
    rom: bytes,
    record: Dict[str, Any],
    slot_values: Mapping[str, int],
    *,
    capture_nul: bool,
) -> Dict[str, Any]:
    units = [
        _capture_one_unit(client, rom, record, index, slot_values)
        for index in range(int(record["unit_count"]))
    ]
    render_exact = all(bool(unit["render"]["pixel_render_exact_expected"]) for unit in units)
    combined = hashlib.sha256()
    for unit in units:
        combined.update(bytes.fromhex(unit["render"]["pixel_nibble_sha256"]))
    return {
        "record": record,
        "units": units,
        "combined_unit_render_sha256": combined.hexdigest(),
        "layout": {
            "width": int(record["line_width"]),
            "height": 12,
            "tile_columns": math.ceil(int(record["line_width"]) / 8),
            "unit_count": len(units),
            "exact_per_unit": render_exact,
            "controlled_consumer_layout": render_exact and len(units) == int(record["unit_count"]),
        },
        "termination": {
            "terminator": "NUL",
            "record_not_truncated": len(units) == int(record["unit_count"]),
            "unit_count_expected": int(record["unit_count"]),
            "unit_count_observed": len(units),
            "nul_read_during_glyph_units": any(
                bool(unit["nul_read_observed_during_unit"]) for unit in units
            ),
            "nul_branch": _capture_nul(client, record) if capture_nul else None,
        },
    }


def run_probe(args: argparse.Namespace) -> Dict[str, Any]:
    rom = args.rom.read_bytes()
    expected_hash = BASE_ROM_SHA256 if args.label == "base" else PATCHED_ROM_SHA256
    actual_hash = sha256(rom)
    if actual_hash != expected_hash:
        raise RuntimeTargetError(f"{args.label} ROM hash mismatch: {actual_hash}")
    bps = None
    if args.bps:
        data = args.bps.read_bytes()
        bps = {
            "sha256": sha256(data),
            "size": len(data),
            "expected_sha256": BPS_SHA256,
            "expected_size": BPS_SIZE,
            "hash_match": sha256(data) == BPS_SHA256 and len(data) == BPS_SIZE,
        }
        if not bps["hash_match"]:
            raise RuntimeTargetError("BPS hash/size mismatch")

    source_rows = _read_jsonl(args.source_table)
    if not any(
        (int(row.get("string_id", -1), 0) if isinstance(row.get("string_id"), str) else int(row.get("string_id", -1)))
        == TARGET_OFFSET
        for row in source_rows
    ):
        raise RuntimeTargetError("target source record missing")
    target_ledger_hash = _read_ledger_hash(args.ledger, 526424)
    target_payload, _ = source_payload(rom, TARGET_OFFSET)
    adjacent_payload, _ = source_payload(rom, ADJACENT_OFFSET)
    target_record = _record_metadata(rom, TARGET_OFFSET, "target", target_ledger_hash)
    adjacent_record = _record_metadata(rom, ADJACENT_OFFSET, "adjacent_untouched", None)
    static_resources = static_resource_metadata(rom)

    with GdbClient(port=args.port, timeout=max(8.0, args.stop_timeout)) as client:
        initializer = _capture_initializer(client, rom, args.stop_timeout)
        slots = _slot_values(client)
        if any(not value for value in slots.values()):
            raise RuntimeTargetError("font-base nonzero guard failed before consumer")
        target = _capture_record(
            client, rom, target_record, slots, capture_nul=True
        )
        adjacent = _capture_record(
            client, rom, adjacent_record, slots, capture_nul=False
        )

    report = {
        "schema": "super-robot-taisen-d-m130-corrected-runtime-target-v1",
        "milestone": "M1.30",
        "game_code": "A6SJ",
        "label": args.label,
        "rom": {"sha256": actual_hash, "expected_sha256": expected_hash, "hash_match": True},
        "bps": bps,
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "target_string_id": 526424,
            "target_source_offset": address(ROM_BASE + TARGET_OFFSET),
            "target_ledger_source_hash": target_ledger_hash,
            "target_payload_sha256": sha256(target_payload),
            "adjacent_payload_sha256": sha256(adjacent_payload),
        },
        "runtime": {
            "gdb_port": args.port,
            "single_connection": True,
            "fresh_process_required": True,
            "natural_navigation": "not_attempted",
            "controlled_method": "direct verified Thumb initializer caller plus one 0x08008724 call per two-byte unit",
            "pc_write_convention": "architectural instruction address; mGBA rebuilds prefetch",
            "font_slots": {name: address(value) for name, value in slots.items()},
            "static_resources": static_resources,
            "initializer": initializer,
            "target": target,
            "adjacent": adjacent,
        },
        "gate": {
            "rom_hash_match": True,
            "bps_hash_match": None if bps is None else bool(bps["hash_match"]),
            "font_base_nonzero": all(slots.values()),
            "target_two_units_observed": target["termination"]["record_not_truncated"],
            "target_nul_branch_observed": bool(target["termination"]["nul_branch"]["observed"]),
            "target_per_unit_render_exact": bool(target["layout"]["exact_per_unit"]),
            "adjacent_per_unit_render_exact": bool(adjacent["layout"]["exact_per_unit"]),
            "natural_screen_proven": False,
            "translation_status": "ai_draft",
            "release_ready": False,
        },
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"m130_runtime_target=accepted label={args.label} "
        f"target_units={target['termination']['unit_count_observed']} "
        f"nul={target['termination']['nul_branch']['observed']}"
    )
    return report


def compare_reports(base: Mapping[str, Any], patched: Mapping[str, Any]) -> Dict[str, Any]:
    base_target = base["runtime"]["target"]
    patched_target = patched["runtime"]["target"]
    base_adjacent = base["runtime"]["adjacent"]
    patched_adjacent = patched["runtime"]["adjacent"]
    base_adj_hashes = [unit["glyph"]["glyph"]["sha256"] for unit in base_adjacent["units"]]
    patched_adj_hashes = [unit["glyph"]["glyph"]["sha256"] for unit in patched_adjacent["units"]]
    base_adj_render = [unit["render"]["pixel_nibble_sha256"] for unit in base_adjacent["units"]]
    patched_adj_render = [unit["render"]["pixel_nibble_sha256"] for unit in patched_adjacent["units"]]
    return {
        "schema": "super-robot-taisen-d-m130-corrected-runtime-compare-v1",
        "rom_hashes": {
            "base": base["rom"]["sha256"],
            "patched": patched["rom"]["sha256"],
            "bps": patched.get("bps"),
        },
        "target": {
            "string_id": 526424,
            "source_payload_changed": base["source_policy"]["target_payload_sha256"] != patched["source_policy"]["target_payload_sha256"],
            "same_unit_count": base_target["record"]["unit_count"] == patched_target["record"]["unit_count"] == 2,
            "base_units_observed": base_target["termination"]["unit_count_observed"],
            "patched_units_observed": patched_target["termination"]["unit_count_observed"],
            "patched_record_not_truncated": patched_target["termination"]["record_not_truncated"],
            "patched_nul_branch_observed": bool(patched_target["termination"]["nul_branch"]["observed"]),
            "patched_per_unit_render_exact": bool(patched_target["layout"]["exact_per_unit"]),
            "controlled_layout_width": patched_target["layout"]["width"],
            "controlled_layout_height": patched_target["layout"]["height"],
            "runtime_glyph_render_changed": base_target["combined_unit_render_sha256"] != patched_target["combined_unit_render_sha256"],
        },
        "adjacent": {
            "string_id": 526432,
            "payload_sha256_equal": base["source_policy"]["adjacent_payload_sha256"] == patched["source_policy"]["adjacent_payload_sha256"],
            "glyph_hashes_equal": base_adj_hashes == patched_adj_hashes,
            "render_hashes_equal": base_adj_render == patched_adj_render,
            "runtime_untouched": base_adj_hashes == patched_adj_hashes and base_adj_render == patched_adj_render,
        },
        "font_initialization": {
            "slot_values_equal": base["runtime"]["font_slots"] == patched["runtime"]["font_slots"],
            "both_nonzero": base["gate"]["font_base_nonzero"] and patched["gate"]["font_base_nonzero"],
        },
        "gate": {
            "corrected_transport_positive": True,
            "patched_target_controlled_consumer_proven": (
                patched_target["termination"]["record_not_truncated"]
                and patched_target["layout"]["exact_per_unit"]
                and patched_target["termination"]["nul_branch"]["observed"]
            ),
            "adjacent_untouched_runtime_proven": base_adj_hashes == patched_adj_hashes and base_adj_render == patched_adj_render,
            "natural_screen_not_claimed": True,
            "translation_status": "ai_draft",
            "release_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("rom", type=Path)
    run.add_argument("--label", choices=("base", "patched"), required=True)
    run.add_argument("--port", type=int, required=True)
    run.add_argument("--source-table", type=Path, required=True)
    run.add_argument("--ledger", type=Path, required=True)
    run.add_argument("--bps", type=Path)
    run.add_argument("--stop-timeout", type=float, default=8.0)
    run.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--base-report", type=Path, required=True)
    compare.add_argument("--patched-report", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "run":
            run_probe(args)
        else:
            result = compare_reports(
                json.loads(args.base_report.read_text(encoding="utf-8")),
                json.loads(args.patched_report.read_text(encoding="utf-8")),
            )
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print("m130_runtime_compare=accepted")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m130_runtime_rejected={exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
