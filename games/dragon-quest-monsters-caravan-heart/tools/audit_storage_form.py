#!/usr/bin/env python3
"""Audit the clean A9HJ text storage form without emitting source bytes.

This receipt combines the verified three-level ROM pointer pool with the
normal parser's direct source-byte read.  It identifies the storage observed
so far as a direct ROM pointer pool feeding a mixed-byte stream, while keeping
compression absence and record boundaries explicitly unproven.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
import sys
from collections.abc import Iterable
from typing import Any


TOOLS_DIR = pathlib.Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from audit_control_consumption import audit_signatures  # noqa: E402
from extract_text import (  # noqa: E402
    POINTER_TABLE,
    ROM_BASE,
    ROM_SIZE,
    collect_pointer_tables,
    cpu_to_file,
    pointer_run,
    validate_rom,
)


STATE_POINTER = 0x03002830
PARSER_ENTRY = 0x08012500
NORMAL_SOURCE_READ = 0x08012726
NORMAL_SOURCE_SIGNATURE = bytes.fromhex("1478301c211c01f004f802e0301c01f064fb")
POINTER_LITERAL_SITES = (
    (0x08012374, POINTER_TABLE),
    (0x080124FC, POINTER_TABLE),
)
STATE_LITERAL_SITES = (
    (0x0801236C, STATE_POINTER),
    (0x080124F4, STATE_POINTER),
)
NORMAL_GLYPH_TABLE = 0x082DF3D4
ALTERNATE_GLYPH_POOL = 0x082E0BD4


def read_u32_cpu(data: bytes, address: int) -> int:
    offset = cpu_to_file(address)
    return struct.unpack_from("<I", data, offset)[0]


def signature(data: bytes, address: int, expected: bytes) -> dict[str, str]:
    offset = cpu_to_file(address)
    actual = data[offset:offset + len(expected)]
    if actual != expected:
        raise ValueError(
            f"instruction signature changed at 0x{address:08X}: "
            f"expected {expected.hex()}, got {actual.hex()}"
        )
    return {"address": f"0x{address:08X}", "bytes": expected.hex()}


def summarize_pointer_records(records: Iterable[dict[str, Any]]) -> dict[str, object]:
    rows = list(records)
    targets = [int(row["pointer"]) for row in rows]
    all_in_rom = all(ROM_BASE <= target < ROM_BASE + ROM_SIZE for target in targets)
    return {
        "table_cpu": f"0x{POINTER_TABLE:08X}",
        "groups": sorted({int(row["group"]) for row in rows}),
        "variants": len({(int(row["group"]), int(row["variant"])) for row in rows}),
        "records": len(rows),
        "unique_pointers": len(set(targets)),
        "duplicate_pointer_records": len(rows) - len(set(targets)),
        "all_targets_are_rom": all_in_rom,
        "pointer_encoding": "little-endian CPU addresses into the clean ROM window",
    }


def audit(data: bytes) -> dict[str, object]:
    identity = validate_rom(data)
    records = collect_pointer_tables(data)
    pointer_summary = summarize_pointer_records(records)
    if not pointer_summary["all_targets_are_rom"]:
        raise ValueError("pointer pool contains a target outside the clean ROM window")

    top_table = pointer_run(data, POINTER_TABLE)
    if len(top_table) != 8:
        raise ValueError(f"expected 8 top-level groups, got {len(top_table)}")

    pointer_literals = []
    for address, expected in POINTER_LITERAL_SITES:
        actual = read_u32_cpu(data, address)
        if actual != expected:
            raise ValueError(
                f"pointer-table literal changed at 0x{address:08X}: "
                f"expected 0x{expected:08X}, got 0x{actual:08X}"
            )
        pointer_literals.append({"address": f"0x{address:08X}", "value": f"0x{expected:08X}"})

    state_literals = []
    for address, expected in STATE_LITERAL_SITES:
        actual = read_u32_cpu(data, address)
        if actual != expected:
            raise ValueError(
                f"state literal changed at 0x{address:08X}: "
                f"expected 0x{expected:08X}, got 0x{actual:08X}"
            )
        state_literals.append({"address": f"0x{address:08X}", "value": f"0x{expected:08X}"})

    return {
        "rom": identity,
        "storage_form": "direct-rom-pointer-pool-plus-mixed-byte-stream",
        "pointer_pool": pointer_summary,
        "top_level_pointer_count": len(top_table),
        "parser": {
            "entry": f"0x{PARSER_ENTRY:08X}",
            "state_pointer": f"0x{STATE_POINTER:08X}",
            "source_pointer_field": "state+0x18",
            "normal_source_read": signature(data, NORMAL_SOURCE_READ, NORMAL_SOURCE_SIGNATURE),
            "pointer_table_literals": pointer_literals,
            "state_literals": state_literals,
            "control_read_signature_count": len(audit_signatures(data)),
        },
        "glyph_storage": {
            "normal_table": f"0x{NORMAL_GLYPH_TABLE:08X}",
            "alternate_pool": f"0x{ALTERNATE_GLYPH_POOL:08X}",
        },
        "compression_status": "not-proven-absent",
        "boundary_status": "next-pointer-is-candidate-only",
        "scope_note": "Direct pointers and byte reads are proven; no claim is made about unrelated BIOS compression signatures, control semantics, or final record boundaries.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    args = parser.parse_args()
    try:
        report = audit(args.rom.read_bytes())
    except (OSError, ValueError, struct.error) as error:
        print(f"audit_storage_form: {error}", file=sys.stderr)
        return 2
    print("rom", report["rom"])
    print("storage-form", report["storage_form"])
    print("pointer-pool", report["pointer_pool"])
    print("parser", report["parser"])
    print("glyph-storage", report["glyph_storage"])
    print("compression-status", report["compression_status"])
    print("boundary-status", report["boundary_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
