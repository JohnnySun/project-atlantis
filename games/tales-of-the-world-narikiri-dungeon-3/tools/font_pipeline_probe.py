#!/usr/bin/env python3
"""Verify the bounded B3TJ static font/codepoint pipeline.

This probe follows only already reviewed fixed functions.  It verifies the
format-loop callsites, the ``0x20``-byte asset stride, the parity-selected
transform routines, their fixed IWRAM lookup table, and the two direct callers
of the fixed codepoint lookup.  It emits addresses, bounded span hashes and
table statistics only; it never emits Japanese source, glyph bytes, RAM/VRAM
dumps or OCR output.

The result is deliberately a static contract.  It does not claim that the
asset is the glyph used by a live text record, that the lookup tables are the
complete Japanese codepage, or that the scratch buffer is copied to VRAM.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

FORMAT_ENTRY = 0x080014F4
FONT_MAP_ENTRY = 0x08001414
GLYPH_TRANSFORM_EVEN = 0x080011A8
GLYPH_TRANSFORM_ODD = 0x080012E0
CODEPOINT_LOOKUP_ENTRY = 0x08004D90

FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
FONT_SCRATCH_BASE = 0x03000560
TRANSFORM_LOOKUP_TABLE = 0x03001464

EXPECTED_CALLS = {
    FORMAT_ENTRY: (0x1652, 0x8E16, 0x167A6, 0xA778E, 0xBAC58, 0xC6184),
    FONT_MAP_ENTRY: (0x1556, 0x15F8),
    GLYPH_TRANSFORM_EVEN: (0x1454,),
    GLYPH_TRANSFORM_ODD: (0x1440,),
    CODEPOINT_LOOKUP_ENTRY: (0x15C4, 0x4D60),
}

CODEPOINT_POINTER_POOL = {
    0x741D80: 0x080FFE80,
    0x741D84: 0x080FFF40,
    0x741D88: 0x080FFFBC,
    0x741D8C: 0x080FFFF4,
    0x741D90: 0x08100070,
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


def _read_halfword(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"halfword outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<H", data, offset)[0]


def decode_thumb_bl(data: bytes, offset: int) -> int | None:
    """Decode one Thumb-2 BL at a file offset."""

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
    displacement = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        displacement -= 1 << 25
    return ROM_BASE + offset + 4 + displacement


def find_direct_calls(data: bytes, target: int) -> list[int]:
    """Find only exact direct Thumb BL encodings for one fixed target."""

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


def _table_summary(data: bytes, address: int, window: int = 0x100) -> dict[str, object]:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        raise ValueError(f"table address outside ROM: {_hex(address)}")
    offset = address - ROM_BASE
    if offset + window > len(data):
        raise ValueError("lookup window outside ROM")
    raw = data[offset:offset + window]
    halfwords = [struct.unpack_from("<H", raw, index)[0] for index in range(0, window, 2)]
    return {
        "gba_address": _hex(address),
        "file_offset": _hex(offset, 6),
        "window_bytes": window,
        "halfword_count": len(halfwords),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "nonzero_bytes": sum(value != 0 for value in raw),
        "unique_halfwords": len(set(halfwords)),
        "min_halfword": _hex(min(halfwords), 4),
        "max_halfword": _hex(max(halfwords), 4),
    }


def font_asset_address(codepoint_index: int) -> int:
    if codepoint_index < 0:
        raise ValueError("codepoint index must be non-negative")
    return FONT_ASSET_BASE + codepoint_index * FONT_ASSET_STRIDE


def _direct_call_metadata(data: bytes, target: int) -> dict[str, object]:
    calls = find_direct_calls(data, target)
    expected = list(EXPECTED_CALLS[target])
    if calls != expected:
        raise ValueError(
            f"direct-call set changed for {_hex(target)}: {calls!r} != {expected!r}"
        )
    return {
        "target": _hex(target),
        "count": len(calls),
        "file_offsets": [_hex(offset, 6) for offset in calls],
        "all_direct_targets_match": True,
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    calls = {
        _hex(target): _direct_call_metadata(data, target)
        for target in EXPECTED_CALLS
    }

    literals = {
        "font_asset_base_literal": _read_word(data, 0x1448),
        "font_scratch_base_literal": _read_word(data, 0x144C),
        "transform_lookup_even_literal": _read_word(data, 0x12D8),
        "transform_lookup_odd_literal": _read_word(data, 0x140C),
    }
    expected_literals = {
        "font_asset_base_literal": FONT_ASSET_BASE,
        "font_scratch_base_literal": FONT_SCRATCH_BASE,
        "transform_lookup_even_literal": TRANSFORM_LOOKUP_TABLE,
        "transform_lookup_odd_literal": TRANSFORM_LOOKUP_TABLE,
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
        raise ValueError("font pipeline literal mismatch")

    # The reviewed ``lsls r2,#5`` at the font-map entry is the fixed 0x20
    # asset-stride operation.  The two nearby halfwords also pin the function
    # prologue and keep this check from silently moving to a data pool.
    instruction_checks = {
        "font_map_push": _read_halfword(data, 0x1414) == 0xB510,
        "asset_stride_shift_left_5": _read_halfword(data, 0x1416) == 0x0152,
        "font_map_parity_mask": _read_halfword(data, 0x1436) == 0x4001,
        "even_transform_lookup_mask": _read_halfword(data, 0x11E4) == 0x4038,
        "odd_transform_lookup_mask": _read_halfword(data, 0x1320) == 0x4030,
    }
    if not all(instruction_checks.values()):
        raise ValueError("font pipeline instruction signature mismatch")

    lookup_tables = []
    for slot, address in CODEPOINT_POINTER_POOL.items():
        actual = _read_word(data, slot)
        if actual != address:
            raise ValueError(
                f"codepoint pointer slot mismatch at {_hex(slot, 6)}: "
                f"{_hex(actual)} != {_hex(address)}"
            )
        lookup_tables.append(_table_summary(data, address))

    return {
        "identity": identity,
        "fixed_entries": {
            "format_entry": _hex(FORMAT_ENTRY),
            "font_map_entry": _hex(FONT_MAP_ENTRY),
            "even_transform_entry": _hex(GLYPH_TRANSFORM_EVEN),
            "odd_transform_entry": _hex(GLYPH_TRANSFORM_ODD),
            "codepoint_lookup_entry": _hex(CODEPOINT_LOOKUP_ENTRY),
        },
        "direct_calls": calls,
        "literals": literal_checks,
        "instruction_checks": instruction_checks,
        "font_asset_contract": {
            "base": _hex(FONT_ASSET_BASE),
            "stride_bytes": FONT_ASSET_STRIDE,
            "address_formula": "0x080DDCC4 + codepoint_index*0x20",
            "source_span_per_index_bytes": FONT_ASSET_STRIDE,
            "source_format_status": "static-2-bit-lookup-expansion-candidate",
        },
        "transform_contract": {
            "lookup_table": _hex(TRANSFORM_LOOKUP_TABLE),
            "lookup_mask": "0x03",
            "source_read": "bounded halfword rows with two-bit lookup selection",
            "destination": _hex(FONT_SCRATCH_BASE),
            "parity_dispatch": {
                "even": _hex(GLYPH_TRANSFORM_EVEN),
                "odd": _hex(GLYPH_TRANSFORM_ODD),
            },
            "status": "confirmed-static-transform-shape",
        },
        "codepoint_lookup": {
            "entry": _hex(CODEPOINT_LOOKUP_ENTRY),
            "pointer_slot_count": len(CODEPOINT_POINTER_POOL),
            "tables": lookup_tables,
            "status": "confirmed-static-bounded-table-pool",
        },
        "bounded_spans": [
            _span(data, "font-map-entry", 0x1414, 0x1460),
            _span(data, "glyph-transform-even", 0x11A8, 0x12D4),
            _span(data, "glyph-transform-odd", 0x12E0, 0x1410),
            _span(data, "codepoint-lookup-entry", 0x4D90, 0x4E32),
        ],
        "classification": {
            "asset_stride_and_address_math": "confirmed-static",
            "two_bit_lookup_expansion_shape": "confirmed-static",
            "codepoint_lookup_entry_and_pool": "confirmed-static",
            "complete_japanese_codepage_identity": "unconfirmed",
            "glyph_identity_for_any_strict_record": "unconfirmed",
            "width_semantics": "unconfirmed",
            "live_source_record_to_font_asset": "unconfirmed",
            "scratch_to_glyph_vram": "unconfirmed",
            "capacity_and_roundtrip": "unconfirmed",
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
