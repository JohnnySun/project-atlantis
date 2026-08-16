#!/usr/bin/env python3
"""Verify the bounded B3TJ parser-to-renderer static chain.

This probe follows only direct calls to the already reviewed parser entry
``0x080025CC``.  It checks the four direct callsites, the one stack-buffer
callsite that hands formatted bytes to ``0x08001DBC``, and the fixed literals
used by the adjacent Shift-JIS-like index and tilemap routines.

The result is static metadata only: addresses, literal values, bounded span
hashes and counts.  It does not emit source text, glyph bytes, VRAM dumps or
OCR.  Runtime execution, exact codepage identity, glyph identity and a
record-level source edge remain separate claims.
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

PARSER_ENTRY = 0x080025CC
PARSER_CALLSITES = (0x164C, 0x1D92, 0x1E26, 0x281C)
EXPECTED_NEXT_CALLS = {
    0x164C: (0x06, 0x080014F4),
    0x1D92: (0x08, 0x08001A10),
    0x1E26: (0x0A, 0x08001DBC),
}
FORMATTED_BUFFER = 0x03001468
PARSER_CURSOR = 0x03001588

FORMAT_ENTRY = 0x14F4
FONT_MAP_ENTRY = 0x1414
GLYPH_TRANSFORM_A = 0x11A8
GLYPH_TRANSFORM_B = 0x12E0
RAM_TILEMAP_WRITER_ENTRY = 0x1DBC
CODEPOINT_LOOKUP_ENTRY = 0x4D90

FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
FONT_SCRATCH_BASE = 0x03000560
GLYPH_LOOKUP_TABLE = 0x03001464
RAM_TILEMAP_BASE = 0x03000060
TILEMAP_ROW_STRIDE = 0x40
TILEMAP_ENTRY_SIZE = 2
RAM_TILEMAP_WRITER_FLAGS = 0x03001461
TILE_ATTRIBUTE = 0xFFFFE000


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


def decode_thumb_bl(data: bytes, offset: int) -> int | None:
    """Decode one Thumb-2 BL at a file offset, returning its GBA target."""

    if offset < 0 or offset + 4 > len(data) or offset % 2:
        return None
    first, second = struct.unpack_from("<HH", data, offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    offset_value = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        offset_value -= 1 << 25
    return ROM_BASE + offset + 4 + offset_value


def find_direct_calls(data: bytes, target: int) -> list[int]:
    """Find only direct Thumb BL encodings for one fixed target."""

    return [
        offset
        for offset in range(0, len(data) - 4, 2)
        if decode_thumb_bl(data, offset) == target
    ]


def _span(data: bytes, name: str, start: int, end: int) -> dict[str, object]:
    if start < 0 or end <= start or end > len(data):
        raise ValueError(f"invalid span {name}")
    value = data[start:end]
    return {
        "name": name,
        "file_start": _hex(start, 6),
        "file_end_exclusive": _hex(end, 6),
        "byte_length": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def _callsite_metadata(data: bytes, offset: int) -> dict[str, object]:
    target = decode_thumb_bl(data, offset)
    if target != PARSER_ENTRY:
        raise ValueError(f"unexpected parser callsite at {_hex(offset, 6)}")
    row: dict[str, object] = {
        "file_offset": _hex(offset, 6),
        "gba_address": _hex(ROM_BASE + offset),
        "parser_target": _hex(target),
    }
    next_call = EXPECTED_NEXT_CALLS.get(offset)
    if next_call is not None:
        delta, next_target = next_call
        following = decode_thumb_bl(data, offset + delta)
        if following != next_target:
            raise ValueError(f"unexpected post-parser call at {_hex(offset + delta, 6)}")
        row["post_parser_call"] = _hex(following)
    else:
        row["post_parser_call"] = "return-wrapper"
    if offset == 0x1E26:
        row["output_buffer"] = "stack+0x00 (bounded 0x20-byte caller frame)"
        row["renderer_consumer"] = _hex(0x08001DBC)
    elif offset in (0x164C, 0x1D92):
        row["output_buffer"] = _hex(FORMATTED_BUFFER)
    else:
        row["output_buffer"] = "caller-provided"
    return row


def double_byte_index(lead: int, trail: int) -> int:
    """Apply the fixed arithmetic in 0x080014F4 for a double-byte pair."""

    if not 0x81 <= lead <= 0xDF:
        raise ValueError("lead outside reviewed double-byte branch")
    if not 0x40 <= trail <= 0xFC or trail == 0x7F:
        raise ValueError("trail outside reviewed double-byte branch")
    adjusted = lead - (0x81 if lead <= 0x87 else 0x85)
    return adjusted * 3 * 0x40 + trail - 0x40


def tilemap_address(x: int, y: int) -> int:
    if x < 0 or y < 0:
        raise ValueError("tilemap coordinates must be non-negative")
    return RAM_TILEMAP_BASE + y * TILEMAP_ROW_STRIDE + x * TILEMAP_ENTRY_SIZE


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    calls = find_direct_calls(data, PARSER_ENTRY)
    expected = list(PARSER_CALLSITES)
    if calls != expected:
        raise ValueError(f"parser direct-call set changed: {calls!r}")

    literals = {
        "formatted_buffer_literal_1646": _read_word(data, 0x165C),
        "formatted_buffer_literal_1D8E": _read_word(data, 0x1DA4),
        "font_asset_base_literal": _read_word(data, 0x1448),
        "font_scratch_literal": _read_word(data, 0x144C),
        "glyph_lookup_table_literal": _read_word(data, 0x12D8),
        "format_state_literal": _read_word(data, 0x1520),
        "ram_tilemap_base_literal": _read_word(data, 0x1DEC),
        "ram_tilemap_writer_flags_literal": _read_word(data, 0x1DE8),
        "tile_attribute_literal": _read_word(data, 0x1DF0),
    }
    expected_literals = {
        "formatted_buffer_literal_1646": FORMATTED_BUFFER,
        "formatted_buffer_literal_1D8E": FORMATTED_BUFFER,
        "font_asset_base_literal": FONT_ASSET_BASE,
        "font_scratch_literal": FONT_SCRATCH_BASE,
        "glyph_lookup_table_literal": GLYPH_LOOKUP_TABLE,
        "format_state_literal": 0x03000040,
        "ram_tilemap_base_literal": RAM_TILEMAP_BASE,
        "ram_tilemap_writer_flags_literal": RAM_TILEMAP_WRITER_FLAGS,
        "tile_attribute_literal": TILE_ATTRIBUTE,
    }
    literal_checks = {
        name: {
            "value": _hex(value),
            "expected": _hex(expected_literals[name]),
            "matches": value == expected_literals[name],
        }
        for name, value in literals.items()
    }
    if not all(row["matches"] for row in literal_checks.values()):
        raise ValueError("renderer-chain literal mismatch")

    return {
        "identity": identity,
        "parser_callsites": {
            "target": _hex(PARSER_ENTRY),
            "count": len(calls),
            "all_direct_targets_match": True,
            "rows": [_callsite_metadata(data, offset) for offset in calls],
        },
        "static_chain": {
            "formatted_buffer": _hex(FORMATTED_BUFFER),
            "parser_cursor_global": _hex(PARSER_CURSOR),
            "stack_buffer_to_ram_tilemap_writer": {
                "parser_callsite": _hex(ROM_BASE + 0x1E26),
                "consumer": _hex(ROM_BASE + RAM_TILEMAP_WRITER_ENTRY),
                "buffer_size_bytes": 0x20,
                "ram_tilemap_base": _hex(RAM_TILEMAP_BASE),
                "row_stride_bytes": TILEMAP_ROW_STRIDE,
                "entry_size_bytes": TILEMAP_ENTRY_SIZE,
                "address_formula": "0x03000060 + y*0x40 + x*2",
                "writer_status": "confirmed-static-IWRAM-writer",
            },
            "sjis_like_format_path": {
                "format_entry": _hex(ROM_BASE + FORMAT_ENTRY),
                "font_map_entry": _hex(ROM_BASE + FONT_MAP_ENTRY),
                "font_asset_base": _hex(FONT_ASSET_BASE),
                "font_asset_stride_bytes": FONT_ASSET_STRIDE,
                "font_scratch_base": _hex(FONT_SCRATCH_BASE),
                "double_byte_index_formula": "(lead-adjusted)*3*0x40 + trail - 0x40",
                "lead_adjustment_boundary": _hex(0x87, 2),
                "asset_status": "static-glyph-source-candidate",
            },
            "glyph_transform": {
                "transform_entries": [
                    _hex(ROM_BASE + GLYPH_TRANSFORM_A),
                    _hex(ROM_BASE + GLYPH_TRANSFORM_B),
                ],
                "lookup_table": _hex(GLYPH_LOOKUP_TABLE),
                "interpretation": "static-packed-glyph-to-IWRAM-candidate",
            },
            "codepoint_lookup": {
                "entry": _hex(ROM_BASE + CODEPOINT_LOOKUP_ENTRY),
                "interpretation": "static-character-index-candidate",
            },
            "literal_checks": literal_checks,
            "bounded_spans": [
                _span(data, "format-loop", 0x14F4, 0x1636),
                _span(data, "font-map", 0x1414, 0x1460),
                _span(data, "glyph-transform-a", 0x11A8, 0x1200),
                _span(data, "glyph-transform-b", 0x12E0, 0x1410),
                _span(data, "ram-tilemap-writer", 0x1DBC, 0x1E16),
                _span(data, "codepoint-lookup", 0x4D90, 0x4E32),
            ],
        },
        "classification": {
            "parser_to_stack_buffer": "confirmed-static",
            "stack_buffer_to_ram_tilemap_writer": "confirmed-static",
            "sjis_like_double_byte_arithmetic": "confirmed-static",
            "font_asset_identity": "unconfirmed",
            "runtime_source_record_edge": "unconfirmed",
            "runtime_glyph_vram_edge": "unconfirmed",
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
