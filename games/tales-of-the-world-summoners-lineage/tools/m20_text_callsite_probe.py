#!/usr/bin/env python3
"""Metadata-only static caller index for the A9PJ text consumers.

This probe finds Thumb BL callsites to the already identified fixed-count and
null-terminated consumers.  It records caller addresses, simple immediate or
PC-literal argument provenance, bounded stream hashes, and aggregate roles.  A
valid pointer or a NUL terminator is not enough to call a candidate script row;
all candidates remain unclassified until runtime screen context is observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

from m20_text_record_probe import (
    DEFAULT_TARGET_END,
    DEFAULT_TARGET_START,
    EXPECTED_ROM_SHA256,
    FONT_RECORD_FILE_BASE,
    read_halfword_stream,
)


ROM_BASE = 0x08000000
ROM_END = 0x0A000000
NULL_ENTRY = 0x080063E0
FIXED_ENTRY = 0x0800638C
ALT_FIXED_ENTRY = 0x0800644C
DEFAULT_CALLSITE_WINDOW = 0x20


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def thumb_bl_target(data: bytes, file_offset: int) -> int | None:
    """Decode the ARM7TDMI Thumb-1 BL pair at an even ROM offset."""

    if file_offset < 0 or file_offset + 4 > len(data) or file_offset & 1:
        return None
    first, second = struct.unpack_from("<HH", data, file_offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    offset = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if offset & (1 << 22):
        offset -= 1 << 23
    return ROM_BASE + file_offset + 4 + offset


def scan_callsites(data: bytes, target: int) -> list[int]:
    return [
        file_offset
        for file_offset in range(0, max(0, len(data) - 4), 2)
        if thumb_bl_target(data, file_offset) == target
    ]


def _literal_load(data: bytes, file_offset: int) -> dict[str, object] | None:
    if file_offset < 0 or file_offset + 2 > len(data):
        return None
    instruction = struct.unpack_from("<H", data, file_offset)[0]
    if instruction & 0xF800 != 0x4800:
        return None
    register = (instruction >> 8) & 0x7
    literal_offset = ((ROM_BASE + file_offset + 4) & ~3) - ROM_BASE
    literal_offset += (instruction & 0xFF) * 4
    if literal_offset < 0 or literal_offset + 4 > len(data):
        return None
    value = struct.unpack_from("<I", data, literal_offset)[0]
    return {
        "register": f"r{register}",
        "literal_file_offset": f"0x{literal_offset:X}",
        "value": hex32(value),
        "rom_pointer": ROM_BASE <= value < ROM_BASE + len(data),
        "pointer_target_file_offset": None
        if not ROM_BASE <= value < ROM_BASE + len(data)
        else f"0x{value - ROM_BASE:X}",
    }


def _movs_immediate(data: bytes, file_offset: int) -> dict[str, object] | None:
    if file_offset < 0 or file_offset + 2 > len(data):
        return None
    instruction = struct.unpack_from("<H", data, file_offset)[0]
    if instruction & 0xF800 != 0x2000:
        return None
    return {
        "register": f"r{(instruction >> 8) & 0x7}",
        "value": instruction & 0xFF,
    }


def argument_provenance(data: bytes, callsite: int, *, window: int = DEFAULT_CALLSITE_WINDOW) -> dict[str, object]:
    """Summarize simple setup instructions without exporting instruction bytes."""

    start = max(0, callsite - window)
    registers: dict[str, object] = {}
    literals: list[dict[str, object]] = []
    immediates: list[dict[str, object]] = []
    for offset in range(start, callsite, 2):
        literal = _literal_load(data, offset)
        if literal is not None:
            literals.append(literal)
            registers[str(literal["register"])] = literal["value"]
            continue
        immediate = _movs_immediate(data, offset)
        if immediate is not None:
            immediates.append(immediate)
            registers[str(immediate["register"])] = hex32(int(immediate["value"]))
    return {
        "window_file_range": [f"0x{start:X}", f"0x{callsite:X}"],
        "simple_register_values": registers,
        "pc_literal_loads": literals,
        "immediate_loads": immediates,
        "r2_literal_pointer_observed": any(item.get("register") == "r2" for item in literals),
    }


def caller_candidate(data: bytes, callsite: int, *, max_units: int) -> dict[str, object]:
    provenance = argument_provenance(data, callsite)
    r2_value = provenance["simple_register_values"].get("r2")
    stream: dict[str, object] | None = None
    role = "unclassified-callsite-candidate"
    if isinstance(r2_value, str):
        pointer = int(r2_value, 16)
        if ROM_BASE <= pointer < ROM_BASE + len(data):
            target = pointer - ROM_BASE
            stream = read_halfword_stream(data, target, max_units=max_units)
            role = "unclassified-rom-pointer-stream-candidate"
        else:
            role = "unclassified-non-rom-or-runtime-pointer"
    return {
        "callsite_bus_address": hex32(ROM_BASE + callsite),
        "callsite_file_offset": f"0x{callsite:X}",
        "argument_provenance": provenance,
        "stream": stream,
        "role": role,
        "runtime_context": "none",
        "source_text_emitted": False,
    }


def target_profile(data: bytes, target: int, *, max_units: int, limit: int) -> dict[str, object]:
    callsites = scan_callsites(data, target)
    selected = [caller_candidate(data, callsite, max_units=max_units) for callsite in callsites[:limit]]
    roles = Counter(item["role"] for item in selected)
    streams = [item["stream"] for item in selected if isinstance(item["stream"], dict)]
    return {
        "consumer_entry": hex32(target),
        "callsites_found": len(callsites),
        "callsites_profiled": len(selected),
        "role_counts_in_profile": dict(sorted(roles.items())),
        "rom_literal_streams_profiled": len(streams),
        "nul_terminated_streams_in_profile": sum(bool(item["terminated_by_0000"]) for item in streams),
        "control_candidate_streams_in_profile": sum(
            int(item["control_candidate_count"]) > 0 for item in streams
        ),
        "callsites": selected,
        "all_roles": "unclassified-until-runtime-context",
    }


def probe(data: bytes, *, max_units: int = 0x80, limit: int = 256) -> dict[str, object]:
    profiles = [
        target_profile(data, target, max_units=max_units, limit=limit)
        for target in (NULL_ENTRY, FIXED_ENTRY, ALT_FIXED_ENTRY)
    ]
    return {
        "probe_version": "m20-text-callsite-probe-20260816.v1",
        "rom": {
            "sha256": sha256(data),
            "expected_a9pj_sha256_match": sha256(data) == EXPECTED_ROM_SHA256,
            "file_size": len(data),
            "source_text_emitted": False,
        },
        "scope": {
            "rom_scan_file_range": ["0x0", f"0x{len(data):X}"],
            "candidate_target_file_range": [f"0x{DEFAULT_TARGET_START:X}", f"0x{DEFAULT_TARGET_END:X}"],
            "max_units_per_stream": max_units,
            "callsite_profile_limit_per_consumer": limit,
            "bl_decoder": "Thumb-1 BL pair; scan every aligned halfword",
        },
        "consumer_profiles": profiles,
        "classification": {
            "runtime_context_confirmed": False,
            "role_labels": ["plot", "map-event", "character", "battle", "ui-font"],
            "role_status": "all unclassified; static caller/pointer geometry is not scene proof",
        },
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=0x80)
    parser.add_argument("--limit", type=lambda value: int(value, 0), default=256)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_units <= 0 or args.limit < 0:
        parser.error("max-units must be positive and limit must be non-negative")
    rendered = json.dumps(probe(args.rom.read_bytes(), max_units=args.max_units, limit=args.limit), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
