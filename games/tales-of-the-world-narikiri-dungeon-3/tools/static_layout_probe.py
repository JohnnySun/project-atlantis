#!/usr/bin/env python3
"""Verify the bounded B3TJ layout-table evidence without emitting source.

The offsets in this probe are hypotheses isolated from the M1.8 disassembly:
five code literals point at a small table immediately before a later data
region, and a nearby dispatcher has 19 bounded cases.  The probe verifies
those exact literals and reports hashes/counts only.  It is not a codepage
decoder, a pointer scanner, or a claim that the table is the Japanese text
font.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

# This is the small table referenced by the bounded C8F7C/C9058 layout helper.
WIDTH_TABLE_START = 0x1BE31C
WIDTH_TABLE_END = 0x1BE3A0
WIDTH_TABLE_POINTER = ROM_BASE + WIDTH_TABLE_START

# Exact literal-pool locations observed in the bounded code window.
WIDTH_LITERAL_REFS = {
    0x0C8F90: 0x0C8F7E,
    0x0C9038: 0x0C8FF0,
    0x0C9098: 0x0C9074,
    0x0C92DC: 0x0C92D0,
    0x0C92F0: 0x0C92E0,
}

LAYOUT_SWITCH_TABLE = 0x0C9118
LAYOUT_CASE_COUNT = 0x13


def verify_identity(data: bytes) -> dict[str, object]:
    crc32 = binascii.crc32(data) & 0xFFFFFFFF
    title = data[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = data[0xAC:0xB0]
    maker_code = data[0xB0:0xB2]
    result = {
        "size": len(data),
        "crc32": f"{crc32:08X}",
        "title_ascii": title.decode("ascii", errors="replace"),
        "game_code": game_code.decode("ascii", errors="replace"),
        "maker_code": maker_code.decode("ascii", errors="replace"),
    }
    if (
        len(data) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != EXPECTED_TITLE
        or game_code != EXPECTED_GAME_CODE
        or maker_code != EXPECTED_MAKER_CODE
    ):
        raise ValueError(f"ROM identity mismatch: {result}")
    return result


def summarize_pairs(data: bytes) -> dict[str, object]:
    """Summarize the bounded table as pairs, never return its raw bytes."""

    if len(data) == 0 or len(data) % 2:
        raise ValueError("width table must contain a non-empty even number of bytes")
    pairs = [tuple(data[index : index + 2]) for index in range(0, len(data), 2)]
    return {
        "byte_length": len(data),
        "pair_count": len(pairs),
        "sha256": hashlib.sha256(data).hexdigest(),
        "nonzero_bytes": sum(value != 0 for value in data),
        "unique_pair_count": len(set(pairs)),
        "first_byte_counts": dict(sorted(Counter(pair[0] for pair in pairs).items())),
        "second_byte_counts": dict(sorted(Counter(pair[1] for pair in pairs).items())),
    }


def _read_word(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"word outside ROM at 0x{offset:06X}")
    return struct.unpack_from("<I", data, offset)[0]


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    table = data[WIDTH_TABLE_START:WIDTH_TABLE_END]
    if len(table) != WIDTH_TABLE_END - WIDTH_TABLE_START:
        raise ValueError("bounded width table is truncated")

    literal_checks = []
    for literal_offset, code_offset in sorted(WIDTH_LITERAL_REFS.items()):
        value = _read_word(data, literal_offset)
        literal_checks.append(
            {
                "literal_file_offset": f"0x{literal_offset:06X}",
                "code_file_offset": f"0x{code_offset:06X}",
                "value": f"0x{value:08X}",
                "matches_width_table": value == WIDTH_TABLE_POINTER,
            }
        )

    switch_targets = [
        _read_word(data, LAYOUT_SWITCH_TABLE + index * 4)
        for index in range(LAYOUT_CASE_COUNT)
    ]
    return {
        "identity": identity,
        "bounded_layout": {
            "width_table_file_offset": f"0x{WIDTH_TABLE_START:06X}",
            "width_table_end_file_offset": f"0x{WIDTH_TABLE_END:06X}",
            "width_table_gba_address": f"0x{WIDTH_TABLE_POINTER:08X}",
            "width_table": summarize_pairs(table),
            "literal_reference_count": len(literal_checks),
            "literal_references": literal_checks,
            "all_literal_references_match": all(
                row["matches_width_table"] for row in literal_checks
            ),
            "layout_dispatcher_file_offset": f"0x{0x0C90F8:06X}",
            "layout_dispatch_case_count": LAYOUT_CASE_COUNT,
            "layout_dispatch_target_count": len(switch_targets),
            "layout_dispatch_unique_targets": len(set(switch_targets)),
            "layout_dispatch_target_hash": hashlib.sha256(
                struct.pack(f"<{len(switch_targets)}I", *switch_targets)
            ).hexdigest(),
        },
        "classification": {
            "width_table": "provisional-layout-table",
            "japanese_codepage": "unconfirmed",
            "glyph_identity": "unconfirmed",
            "runtime_text_consumer": "unconfirmed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze(args.rom.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(text, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
