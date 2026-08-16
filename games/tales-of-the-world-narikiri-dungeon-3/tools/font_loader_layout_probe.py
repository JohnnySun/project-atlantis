#!/usr/bin/env python3
"""Verify the bounded static output geometry of B3TJ's font loader.

The reviewed loader at ``0x080021A8`` consumes the 32-byte slot selected from
``0x080DDCC4`` and writes four 32-byte groups into the caller context.  This
probe checks only the fixed instruction signatures, literal addresses and the
bounded output formula.  It does not decode source text, identify glyphs,
read RAM/VRAM, or claim that the loader is a live text consumer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from font_record_consumer_probe import (  # noqa: E402
    EXPECTED_CRC32,
    EXPECTED_GAME_CODE,
    EXPECTED_MAKER_CODE,
    EXPECTED_SIZE,
    EXPECTED_TITLE,
    FONT_ASSET_BASE,
    FONT_ASSET_STRIDE,
    ROM_BASE,
    find_direct_calls,
    verify_identity,
)


FONT_LOADER_ENTRY = 0x080021A8
FONT_LOADER_CALLSITE = 0x15C26
FONT_LOOKUP_BASE = 0x03001464
FONT_INIT_ENTRY = 0x08002100

OUTPUT_GROUP_OFFSETS = (0x00, 0x20, 0x40, 0x60)
OUTPUT_GROUP_BYTES = 0x20
OUTPUT_TOTAL_BYTES = len(OUTPUT_GROUP_OFFSETS) * OUTPUT_GROUP_BYTES
ASSET_HALF_OFFSETS = (0x00, 0x10)
LOADER_SPAN = (0x21A8, 0x2310)


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def _read_halfword(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"halfword outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<H", data, offset)[0]


def _read_word(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"word outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<I", data, offset)[0]


def output_geometry(context_address: int) -> dict[str, object]:
    """Return the static four-group output formula without reading memory."""

    if context_address < 0 or context_address > 0xFFFFFFFF:
        raise ValueError("context address must be a 32-bit unsigned value")
    return {
        "context_base": _hex(context_address),
        "group_count": len(OUTPUT_GROUP_OFFSETS),
        "group_bytes": OUTPUT_GROUP_BYTES,
        "total_bytes": OUTPUT_TOTAL_BYTES,
        "group_offsets": [_hex(offset, 2) for offset in OUTPUT_GROUP_OFFSETS],
        "group_addresses": [
            _hex(context_address + offset) for offset in OUTPUT_GROUP_OFFSETS
        ],
        "status": "confirmed-static-output-geometry",
    }


def asset_read_geometry(asset_address: int) -> dict[str, object]:
    """Return the fixed 32-byte asset/half layout without reading bytes."""

    if asset_address < 0 or asset_address > 0xFFFFFFFF:
        raise ValueError("asset address must be a 32-bit unsigned value")
    return {
        "asset_base": _hex(asset_address),
        "asset_bytes": FONT_ASSET_STRIDE,
        "half_bytes": 0x10,
        "half_offsets": [_hex(offset, 2) for offset in ASSET_HALF_OFFSETS],
        "status": "confirmed-static-input-geometry",
    }


def _span(data: bytes) -> dict[str, object]:
    start, end = LOADER_SPAN
    value = data[start:end]
    return {
        "file_start": _hex(start, 6),
        "file_end_exclusive": _hex(end, 6),
        "byte_length": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    calls = find_direct_calls(data, FONT_LOADER_ENTRY)
    if calls != [FONT_LOADER_CALLSITE]:
        raise ValueError(f"unexpected loader direct calls: {calls!r}")

    instruction_checks = {
        "entry_copies_r0_to_context_r4": _read_halfword(data, 0x21B4) == 0x1C04,
        "first_source_uses_r8": _read_halfword(data, 0x21E8) == 0x4640,
        "second_source_uses_r8": _read_halfword(data, 0x21FE) == 0x4641,
        "source_second_half_add_0x10": _read_halfword(data, 0x2200) == 0x3110,
        "output_group_0_store": _read_halfword(data, 0x2230) == 0x601C,
        "output_group_1_store": _read_halfword(data, 0x2272) == 0x603B,
        "output_group_2_store": _read_halfword(data, 0x22AE) == 0x602B,
        "output_group_3_store": _read_halfword(data, 0x22F0) == 0x603A,
        "lookup_table_literally_loaded": _read_word(data, 0x2318) == FONT_LOOKUP_BASE,
        "asset_base_literally_loaded": _read_word(data, 0x2310) == FONT_ASSET_BASE,
        "font_init_called_before_expansion": find_direct_calls(data, FONT_INIT_ENTRY)
        == [0x2146, 0x2174, 0x21E2, 0x22FC],
    }
    if not all(instruction_checks.values()):
        raise ValueError("font loader layout signature mismatch")

    return {
        "identity": identity,
        "fixed_entries": {
            "font_loader": _hex(FONT_LOADER_ENTRY),
            "font_loader_callsite": _hex(FONT_LOADER_CALLSITE, 6),
            "font_init": _hex(FONT_INIT_ENTRY),
            "asset_base": _hex(FONT_ASSET_BASE),
            "lookup_base": _hex(FONT_LOOKUP_BASE),
        },
        "direct_calls": {
            "font_loader": {
                "count": 1,
                "file_offsets": [_hex(FONT_LOADER_CALLSITE, 6)],
                "all_direct_targets_match": True,
            },
            "font_init": {
                "count": 4,
                "file_offsets": [_hex(offset, 6) for offset in (0x2146, 0x2174, 0x21E2, 0x22FC)],
                "all_direct_targets_match": True,
            },
        },
        "input_geometry": asset_read_geometry(FONT_ASSET_BASE),
        "output_geometry": output_geometry(0),
        "lookup_geometry": {
            "table_base": _hex(FONT_LOOKUP_BASE),
            "index_shape": "packed-value-and-0x03-then-ldrb",
            "status": "confirmed-static-lookup-shape",
        },
        "instruction_checks": instruction_checks,
        "bounded_span": _span(data),
        "classification": {
            "asset_to_context_byte_geometry": "confirmed-static",
            "asset_input_size": "confirmed-static-0x20",
            "expanded_output_size": "confirmed-static-0x80",
            "glyph_format_semantics": "unconfirmed",
            "codepage_identity": "unconfirmed",
            "live_source_consumer": "unconfirmed",
            "context_to_vram": "unconfirmed",
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
