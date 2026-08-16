#!/usr/bin/env python3
"""Verify the bounded B3TJ text/control parser edge without emitting source.

The fixed THUMB span at ``0x080025CC`` was isolated from the game's own
code, not from a broad byte-pattern scan.  It copies ordinary input bytes to
an IWRAM cursor, treats ``%`` as a command introducer, normalizes the command
byte to a 0x54-entry jump table, and terminates the output with NUL.  This
probe checks only that bounded static contract and the adjacent width helpers.

It intentionally does not claim that the parser has been reached by a live
text record, that its input is Japanese Shift-JIS, or that its width helpers
identify the glyph ROM.  It emits addresses, signatures, hashes and counts;
it never prints or stores ROM/source bytes.
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

PARSER_ENTRY = 0x25CC
PARSER_WRAPPER_ENTRY = 0x2814
PARSER_LOOP = 0x27F2
PARSER_NONCONTROL_COPY = 0x27E4
PARSER_TERMINATOR = 0x27FA
PARSER_DISPATCH_LITERAL = 0x262C
PARSER_DISPATCH_TABLE = 0x2630
PARSER_DISPATCH_MIN = 0x25
PARSER_DISPATCH_MAX = 0x78
PARSER_DISPATCH_COUNT = PARSER_DISPATCH_MAX - PARSER_DISPATCH_MIN + 1
PARSER_CASE_START = 0x2780
PARSER_CASE_END = PARSER_LOOP
PARSER_CURSOR_GLOBAL = 0x03001588

WIDTH_COUNTER_ENTRY = 0x2828
WIDTH_HELPER_ENTRY = 0x2844
WIDTH_HELPER_ALT_ENTRY = 0x28B0
WIDTH_TABLE_GLOBAL = 0x080FFD86

# These are short instruction signatures at reviewed offsets.  They are
# deliberately structural: no disassembly listing or raw code is emitted.
BYTE_SIGNATURES = {
    "parser_push": (PARSER_ENTRY, bytes.fromhex("f0b5")),
    "cursor_global_load": (0x25D6, bytes.fromhex("0148")),
    "cursor_global_store": (0x25D8, bytes.fromhex("0760")),
    "percent_trigger": (0x25E0, bytes.fromhex("2528")),
    "dispatch_subtract": (0x2618, bytes.fromhex("2538")),
    "dispatch_bound": (0x261A, bytes.fromhex("5328")),
    "dispatch_index_shift": (0x2620, bytes.fromhex("8000")),
    "noncontrol_copy": (PARSER_NONCONTROL_COPY, bytes.fromhex("22780134")),
    "parser_loop_read": (PARSER_LOOP, bytes.fromhex("20780028")),
    "parser_nul_terminator": (PARSER_TERMINATOR, bytes.fromhex("0022")),
    "wrapper_push": (PARSER_WRAPPER_ENTRY, bytes.fromhex("0eb4")),
    "width_counter_push": (WIDTH_COUNTER_ENTRY, bytes.fromhex("00b5")),
    "width_helper_push": (WIDTH_HELPER_ENTRY, bytes.fromhex("00b5")),
    "width_helper_alt_push": (WIDTH_HELPER_ALT_ENTRY, bytes.fromhex("00b5")),
}


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


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


def _read_word(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"word outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<I", data, offset)[0]


def _check_signatures(data: bytes) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for name, (offset, expected) in BYTE_SIGNATURES.items():
        actual = data[offset : offset + len(expected)]
        checks[name] = actual == expected
        if not checks[name]:
            raise ValueError(
                f"signature mismatch for {name} at {_hex(offset, 6)}"
            )
    return checks


def parse_dispatch_table(
    data: bytes,
    *,
    table_offset: int = PARSER_DISPATCH_TABLE,
    count: int = PARSER_DISPATCH_COUNT,
) -> dict[str, object]:
    """Summarize one reviewed jump table; never return its raw words."""

    if count <= 0:
        raise ValueError("dispatch table count must be positive")
    end = table_offset + count * 4
    if table_offset < 0 or end > len(data):
        raise ValueError("dispatch table is outside ROM")
    targets = [
        _read_word(data, table_offset + index * 4) for index in range(count)
    ]
    invalid = [
        target
        for target in targets
        if target & 1
        or target < ROM_BASE + PARSER_CASE_START
        or target > ROM_BASE + PARSER_CASE_END
    ]
    if invalid:
        raise ValueError("dispatch target escaped the reviewed parser case span")

    histogram = Counter(targets)
    return {
        "file_offset": _hex(table_offset, 6),
        "gba_address": _hex(ROM_BASE + table_offset),
        "entry_count": count,
        "command_byte_min": _hex(PARSER_DISPATCH_MIN, 2),
        "command_byte_max": _hex(PARSER_DISPATCH_MAX, 2),
        "target_count": len(targets),
        "unique_target_count": len(histogram),
        "target_histogram": {
            _hex(target): histogram[target] for target in sorted(histogram)
        },
        "fallthrough_target": _hex(ROM_BASE + PARSER_LOOP),
        "fallthrough_case_count": histogram.get(ROM_BASE + PARSER_LOOP, 0),
        "special_case_count": count - histogram.get(ROM_BASE + PARSER_LOOP, 0),
        "target_sha256": hashlib.sha256(
            struct.pack(f"<{len(targets)}I", *targets)
        ).hexdigest(),
    }


def _span_metadata(data: bytes, name: str, start: int, end: int) -> dict[str, object]:
    if start < 0 or end <= start or end > len(data):
        raise ValueError(f"invalid bounded span {name}")
    span = data[start:end]
    return {
        "name": name,
        "file_start": _hex(start, 6),
        "file_end_exclusive": _hex(end, 6),
        "byte_length": len(span),
        "sha256": hashlib.sha256(span).hexdigest(),
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    signatures = _check_signatures(data)

    table_pointer = _read_word(data, PARSER_DISPATCH_LITERAL)
    expected_table_pointer = ROM_BASE + PARSER_DISPATCH_TABLE
    if table_pointer != expected_table_pointer:
        raise ValueError("parser dispatch literal does not point to reviewed table")

    cursor_literal = _read_word(data, 0x25DC)
    output_cursor_literal = _read_word(data, 0x2810)
    if cursor_literal != PARSER_CURSOR_GLOBAL or output_cursor_literal != PARSER_CURSOR_GLOBAL:
        raise ValueError("parser cursor literals do not agree")

    table = parse_dispatch_table(data)
    return {
        "identity": identity,
        "bounded_parser": {
            "parser_entry": _hex(ROM_BASE + PARSER_ENTRY),
            "wrapper_entry": _hex(ROM_BASE + PARSER_WRAPPER_ENTRY),
            "parser_loop": _hex(ROM_BASE + PARSER_LOOP),
            "noncontrol_copy_entry": _hex(ROM_BASE + PARSER_NONCONTROL_COPY),
            "nul_terminator_entry": _hex(ROM_BASE + PARSER_TERMINATOR),
            "percent_trigger_byte": _hex(0x25, 2),
            "command_dispatch": {
                "subtract_byte": _hex(0x25, 2),
                "maximum_delta": _hex(0x53, 2),
                "entry_count": PARSER_DISPATCH_COUNT,
                "command_byte_range": [_hex(PARSER_DISPATCH_MIN, 2), _hex(PARSER_DISPATCH_MAX, 2)],
                "literal_file_offset": _hex(PARSER_DISPATCH_LITERAL, 6),
                "literal_value": _hex(table_pointer),
                "literal_matches_table": True,
                "table": table,
            },
            "cursor": {
                "global_gba_address": _hex(PARSER_CURSOR_GLOBAL),
                "region": "IWRAM",
                "entry_literal_matches": cursor_literal == PARSER_CURSOR_GLOBAL,
                "output_literal_matches": output_cursor_literal == PARSER_CURSOR_GLOBAL,
            },
            "static_operations": {
                "ordinary_input_byte_copied_to_cursor": True,
                "percent_introduces_dispatch": True,
                "output_terminated_with_nul": True,
                "optional_zero_prefix_marker": _hex(0x30, 2),
            },
            "bounded_spans": [
                _span_metadata(data, "parser-and-cases", PARSER_ENTRY, 0x2810),
                _span_metadata(data, "wrapper", PARSER_WRAPPER_ENTRY, 0x2826),
                _span_metadata(data, "width-counter", WIDTH_COUNTER_ENTRY, 0x2842),
                _span_metadata(data, "width-helper", WIDTH_HELPER_ENTRY, 0x28B0),
                _span_metadata(data, "width-helper-alt", WIDTH_HELPER_ALT_ENTRY, 0x2912),
            ],
            "width_helpers": {
                "counter_entry": _hex(ROM_BASE + WIDTH_COUNTER_ENTRY),
                "signed_width_entry": _hex(ROM_BASE + WIDTH_HELPER_ENTRY),
                "signed_width_alt_entry": _hex(ROM_BASE + WIDTH_HELPER_ALT_ENTRY),
                "shared_table_literal": _hex(WIDTH_TABLE_GLOBAL),
                "interpretation": "static-width-helper-candidate",
            },
            "signature_checks": signatures,
        },
        "classification": {
            "static_control_parser": "confirmed-static",
            "source_buffer_edge": "provisional-static",
            "runtime_text_consumer": "unconfirmed",
            "japanese_codepage": "unconfirmed",
            "glyph_identity": "unconfirmed",
            "roundtrip_insertion": "unconfirmed",
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
