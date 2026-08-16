#!/usr/bin/env python3
"""Capture a bounded, source-free trace of the M1.9 consumer call.

This diagnostic is intentionally separate from the accepting M1.9 QA probe.
It records every verified breakpoint reached by one controlled consumer call,
including an incomplete unit loop, so a runtime negative cannot be mistaken
for a successful render.  It emits only addresses, registers, counts, and
byte summaries; source text and raw memory dumps stay local to ``work/``.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from core.gba.gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m19_runtime_qa import (  # noqa: E402
    BASE_ROM_SHA256,
    CODEPAGE_LOOKUP,
    CONSUMER,
    GLYPH_COMPLETE,
    NARROW_GLYPH_ADD,
    ROM_BASE,
    TARGET_OFFSET,
    TEMP_STACK,
    TILE_WRITER,
    _registers_metadata,
    address,
    code_units,
    sha256,
    gdb_pc_argument,
    read_payload,
)
from probe_font_resource import (  # noqa: E402
    _assert_initialized,
    capture_initializer,
    write_bounded_memory,
)


PATCHED_ROM_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
STACK_LENGTH = 0x100
CACHE_START = 0x02019010
CACHE_LENGTH = 0x1000
NARROW_GLYPH_LENGTH = 12


class TraceError(RuntimeError):
    """A bounded trace setup or invariant failed."""


def byte_summary(client: GdbClient, start: int, length: int) -> Dict[str, Any]:
    data = client.read_memory(start, length)
    return {
        "address": address(start),
        "length": length,
        "sha256": sha256(data),
        "nonzero_bytes": sum(byte != 0 for byte in data),
    }


def writer_metadata(client: GdbClient, regs: Mapping[str, int]) -> Dict[str, Any]:
    fifth = int.from_bytes(client.read_memory(regs["sp"] + 0x10, 4), "little")
    offset = ((fifth >> 3) << 5) + (regs["r2"] << 2) + (2 if fifth & 7 else 0) + regs["r3"]
    destination = regs["r0"] + offset
    return {
        "pc": address(regs["pc"]),
        "lr": address(regs["lr"]),
        "writer_base": address(regs["r0"]),
        "destination": address(destination),
        "source_tile_value": f"0x{regs['r1'] & 0xFFFF:04X}",
        "row": regs["r2"],
        "tile_offset": f"0x{regs['r3']:04X}",
        "fifth_argument_pixel_x": fifth,
        "computed_offset": f"0x{offset:04X}",
        "strh_bytes": 2,
    }


def classify_trace_events(
    events: Sequence[Mapping[str, Any]],
    *,
    expected_source_pointer: str,
    expected_unit_count: int,
) -> Dict[str, Any]:
    """Classify a trace only when its observed consumer arguments match."""
    codepage = [event for event in events if event.get("kind") == "codepage_lookup"]
    glyphs = [event for event in events if event.get("kind") == "narrow_glyph_add"]
    writers = [event.get("writer") for event in events if event.get("kind") == "tile_writer"]
    observed_source_pointers = sorted(
        {str(event["source_pointer"]) for event in codepage if event.get("source_pointer")}
    )
    observed_code_units = [str(event["code_unit"]) for event in codepage if event.get("code_unit")]
    source_pointer_match = bool(codepage) and all(
        pointer == expected_source_pointer for pointer in observed_source_pointers
    )
    argument_match = source_pointer_match and len(codepage) == expected_unit_count
    complete_event = next((event for event in events if event.get("kind") == "glyph_complete"), None)
    complete_for_requested_record = complete_event is not None and argument_match and (
        len(glyphs) == expected_unit_count
    )
    if complete_for_requested_record and len(codepage) == 2 and len(glyphs) == 2:
        unit_loop_status = "complete_two_unit_candidate"
    elif not argument_match:
        unit_loop_status = "natural_or_unmatched_consumer"
    else:
        unit_loop_status = "partial_or_mismatch"
    return {
        "observed_source_pointers": observed_source_pointers,
        "observed_code_units": observed_code_units,
        "requested_unit_count": expected_unit_count,
        "consumer_argument_match": argument_match,
        "codepage_count": len(codepage),
        "glyph_count": len(glyphs),
        "tile_writer_count": len(writers),
        "complete_observed": complete_for_requested_record,
        "unit_loop_status": unit_loop_status,
    }


def trace_consumer(client: GdbClient, rom: bytes, *, offset: int, max_stops: int) -> Dict[str, Any]:
    initializer = capture_initializer(client, rom, boot_seconds=1.0, stop_timeout=8.0)
    slots = _assert_initialized(client)
    expected_units = code_units(read_payload(rom, offset)[0])
    expected_source_pointer = address(ROM_BASE + offset)
    write_bounded_memory(client, TEMP_STACK, bytes(STACK_LENGTH))
    write_bounded_memory(client, CACHE_START, bytes(CACHE_LENGTH))

    breakpoints = [CODEPAGE_LOOKUP, NARROW_GLYPH_ADD, TILE_WRITER, GLYPH_COMPLETE]
    events: List[Dict[str, Any]] = []
    complete: Optional[Dict[str, Any]] = None
    for breakpoint in breakpoints:
        client.set_breakpoint(breakpoint)
    try:
        client.write_memory(TEMP_STACK, struct.pack("<I", 1))
        client.write_register(0, ROM_BASE + offset)
        client.write_register(1, 0)
        client.write_register(2, 0)
        client.write_register(3, CACHE_START)
        client.write_register(13, TEMP_STACK)
        client.write_register(14, TEMP_STACK | 1)
        client.write_register(15, gdb_pc_argument(CONSUMER, "thumb"))

        for stop_index in range(max_stops):
            stop = client.continue_until_stop(8.0)
            kind, watched = parse_stop_watch(stop)
            if kind is not None:
                events.append({"index": stop_index, "kind": kind, "watched": address(watched or 0)})
                break
            regs = client.read_registers()
            pc = regs["pc"]
            common = {
                "index": stop_index,
                "pc": address(pc),
                "lr": address(regs["lr"]),
                "registers": _registers_metadata(regs),
            }
            if pc == CODEPAGE_LOOKUP:
                events.append(
                    {
                        **common,
                        "kind": "codepage_lookup",
                        "code_unit": f"0x{regs['r0'] & 0xFFFF:04X}",
                        "mode": regs["r1"],
                        "source_pointer": address(regs["r5"]),
                    }
                )
            elif pc == NARROW_GLYPH_ADD:
                pointer = regs["r0"]
                events.append(
                    {
                        **common,
                        "kind": "narrow_glyph_add",
                        "initialized_base": address(slots["narrow"]),
                        "glyph_offset": f"0x{regs['r4']:04X}",
                        "glyph_pointer": address(pointer),
                        "glyph": byte_summary(client, pointer, NARROW_GLYPH_LENGTH),
                    }
                )
            elif pc == TILE_WRITER:
                events.append({**common, "kind": "tile_writer", "writer": writer_metadata(client, regs)})
            elif pc == GLYPH_COMPLETE:
                writer_events = [event["writer"] for event in events if event["kind"] == "tile_writer"]
                if not writer_events:
                    raise TraceError("glyph_complete_without_tile_writer")
                base = min(int(event["writer_base"], 16) for event in writer_events)
                output_length = max(64, math.ceil(16 / 8) * math.ceil(12 / 8) * 32)
                complete = {
                    **common,
                    "kind": "glyph_complete",
                    "tile_cache": byte_summary(client, base, output_length),
                    "cache": byte_summary(client, CACHE_START, CACHE_LENGTH),
                    "writer_count": len(writer_events),
                }
                events.append(complete)
                break
            else:
                events.append({**common, "kind": "unexpected_breakpoint"})
                break
        else:
            raise TraceError("stop_budget_exhausted")
    finally:
        for breakpoint in breakpoints:
            try:
                client.remove_breakpoint(breakpoint)
            except Exception:
                pass

    expected_unit_count = len(expected_units)
    classification = classify_trace_events(
        events,
        expected_source_pointer=expected_source_pointer,
        expected_unit_count=expected_unit_count,
    )
    classification["complete_observed_raw"] = complete is not None
    return {
        "initializer": {
            "slot_values": initializer["slot_values"],
            "event_count": len(initializer["events"]),
            "nonzero_base_guard": all(value != "0x00000000" for value in initializer["slot_values"].values()),
        },
        "controlled_call": {
            "consumer": address(CONSUMER),
            "source_offset": offset,
            "source_pointer": address(ROM_BASE + offset),
            "stack": {"address": address(TEMP_STACK), "length": STACK_LENGTH},
            "cache": {"address": address(CACHE_START), "length": CACHE_LENGTH},
            "requested_source_pointer": expected_source_pointer,
            **classification,
            "breakpoint_set": [address(value) for value in breakpoints],
            "events": events,
            "expected_static_narrow_units": 2 if offset == TARGET_OFFSET else None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--label", choices=("base", "patched"), required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=TARGET_OFFSET)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    rom_hash = sha256(rom)
    expected = BASE_ROM_SHA256 if args.label == "base" else PATCHED_ROM_SHA256
    if rom_hash != expected:
        raise SystemExit(f"rom_hash_mismatch label={args.label} sha256={rom_hash}")
    with GdbClient(port=args.port, timeout=8.0) as client:
        trace = trace_consumer(client, rom, offset=args.offset, max_stops=128)
    report = {
        "schema": "super-robot-taisen-d-m19-runtime-trace-v1",
        "game_code": "A6SJ",
        "label": args.label,
        "rom": {"sha256": rom_hash, "expected_sha256": expected, "hash_match": True},
        "gdb": {"port": args.port, "single_connection": True, "fresh_process_required": True},
        "source_policy": {"source_text_emitted": False, "raw_memory_emitted": False},
        **trace,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"m19_runtime_trace=accepted label={args.label} output={args.output}")


if __name__ == "__main__":
    main()
