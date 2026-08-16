#!/usr/bin/env python3
"""Bounded static record-to-font-asset arithmetic probe for B3TJ.

The reviewed format loop applies one fixed double-byte arithmetic path before
calling the 0x20-byte font-map routine.  Its halfwidth path first calls the
fixed codepoint lookup helper; this probe models that helper only for a
no-control record, then hashes each selected asset slot.  It emits only unit
counts, lookup results, stable hashes, indices and addresses.  It never emits
source text, raw record bytes, glyph bytes, RAM/VRAM data or OCR.

This is a static record-to-asset edge only.  It does not prove that the game
executes this record, that the slot is the displayed glyph, that the lookup
table is a complete codepage, or that the asset reaches VRAM.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import ROM_BASE, strict_records, verify_b3tj  # noqa: E402


EXPECTED_SIZE = 16 * 1024 * 1024
FONT_MAP_ENTRY = 0x08001414
FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
CODEPOINT_LOOKUP_ENTRY = 0x08004D90
CODEPOINT_POINTER_POOL = {
    0x741D80: 0x080FFE80,
    0x741D84: 0x080FFF40,
    0x741D88: 0x080FFFBC,
    0x741D8C: 0x080FFFF4,
    0x741D90: 0x08100070,
}


class StaticPathReject(ValueError):
    """Raised when a bounded static record path cannot be evaluated."""


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def double_byte_index(lead: int, trail: int) -> int:
    """Apply B3TJ's reviewed 0x080014F4 double-byte arithmetic."""

    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
        raise StaticPathReject("lead is outside strict Shift-JIS double-byte range")
    if not 0x40 <= trail <= 0xFC or trail == 0x7F:
        raise StaticPathReject("trail is outside strict Shift-JIS range")
    adjusted = lead - (0x81 if lead <= 0x87 else 0x85)
    return adjusted * 3 * 0x40 + trail - 0x40


def asset_address(index: int, rom_size: int = EXPECTED_SIZE) -> int:
    if index < 0:
        raise StaticPathReject("asset index is negative")
    address = FONT_ASSET_BASE + index * FONT_ASSET_STRIDE
    if not ROM_BASE <= address <= ROM_BASE + rom_size - FONT_ASSET_STRIDE:
        raise StaticPathReject("asset slot is outside ROM")
    return address


def _record_at(records: list[object], offset: int):
    for record in records:
        if record.start == offset:
            return record
    raise StaticPathReject("record offset is not an exact strict record start")


def _asset_slot(data: bytes, index: int) -> dict[str, object]:
    address = asset_address(index, len(data))
    offset = address - ROM_BASE
    slot = data[offset : offset + FONT_ASSET_STRIDE]
    if len(slot) != FONT_ASSET_STRIDE:
        raise StaticPathReject("asset slot is truncated")
    return {
        "asset_index": _hex(index),
        "asset_address": _hex(address),
        "asset_slot_sha256": hashlib.sha256(slot).hexdigest(),
        "asset_slot_bytes": FONT_ASSET_STRIDE,
    }


def _halfwidth_lookup_location(
    value: int, next_value: int, lookup_flag: int = 0
) -> tuple[int, int]:
    """Return (literal-pool slot, halfword index) for the reviewed helper."""

    if not 0xA1 <= value <= 0xDF:
        raise StaticPathReject("halfwidth value is outside lookup range")
    if lookup_flag == 0:
        normal_slot, special_slot = 0x741D84, 0x741D88
    elif lookup_flag != 0:
        normal_slot, special_slot = 0x741D8C, 0x741D90
    if next_value in (0xDE, 0xDF):
        if value == 0xB3:
            return special_slot, 0x19
        if value < 0xB6:
            raise StaticPathReject("special halfwidth lookup has negative table index")
        return special_slot, value - 0xB6
    return normal_slot, value - 0xA1


def _halfwidth_lookup(
    data: bytes, value: int, next_value: int, lookup_flag: int = 0
) -> dict[str, object]:
    slot, halfword_index = _halfwidth_lookup_location(value, next_value, lookup_flag)
    table_address = CODEPOINT_POINTER_POOL[slot]
    table_offset = table_address - ROM_BASE + halfword_index * 2
    if table_offset < 0 or table_offset + 2 > len(data):
        raise StaticPathReject("codepoint lookup halfword is outside ROM")
    lookup_result = struct.unpack_from("<H", data, table_offset)[0]
    result: dict[str, object] = {
        "lookup_flag": lookup_flag,
        "lookup_literal_slot": _hex(slot, 6),
        "lookup_table_address": _hex(table_address),
        "lookup_halfword_index": _hex(halfword_index, 4),
        "lookup_result": _hex(lookup_result, 4),
    }
    if lookup_result == 0:
        result["lookup_result_status"] = "zero-combining-or-skip"
        return result
    lead, trail = lookup_result & 0xFF, lookup_result >> 8
    index = double_byte_index(lead, trail)
    result["lookup_result_status"] = "double-byte-code-unit"
    result.update(_asset_slot(data, index))
    return result


def analyze(data: bytes, record_offset: int) -> dict[str, object]:
    verify_b3tj(data)
    if struct.unpack_from("<I", data, 0x1448)[0] != FONT_ASSET_BASE:
        raise StaticPathReject("font asset base literal changed")
    if struct.unpack_from("<H", data, 0x1416)[0] != 0x0152:
        raise StaticPathReject("font asset stride instruction changed")
    if struct.unpack_from("<H", data, 0x4D90)[0] != 0xB510:
        raise StaticPathReject("codepoint lookup entry signature changed")
    for slot, expected in CODEPOINT_POINTER_POOL.items():
        actual = struct.unpack_from("<I", data, slot)[0]
        if actual != expected:
            raise StaticPathReject(f"codepoint pointer pool changed at {_hex(slot, 6)}")

    record = _record_at(strict_records(data), record_offset)
    if record.control_units or record.newline_units:
        raise StaticPathReject(
            "control/newline-bearing record requires runtime format-state proof"
        )
    payload = data[record.start : record.end]
    units: list[dict[str, object]] = []
    double_byte_count = 0
    lookup_asset_count = 0
    lookup_zero_count = 0
    non_double_byte_counts = {"ascii": 0, "halfwidth": 0}
    cursor = 0
    ordinal = 0
    while cursor < len(payload):
        value = payload[cursor]
        if 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC:
            if cursor + 1 >= len(payload):
                raise StaticPathReject("strict record ends inside a double-byte unit")
            trail = payload[cursor + 1]
            index = double_byte_index(value, trail)
            row = {
                "ordinal": ordinal,
                "kind": "double-byte-static-font-map",
                "unit_sha256": hashlib.sha256(payload[cursor : cursor + 2]).hexdigest(),
            }
            row.update(_asset_slot(data, index))
            units.append(row)
            double_byte_count += 1
            cursor += 2
        elif 0x01 <= value <= 0x1F:
            units.append({"ordinal": ordinal, "kind": "control-or-newline"})
            non_double_byte_counts["control"] += 1
            cursor += 1
        elif 0x20 <= value <= 0x7E:
            units.append({"ordinal": ordinal, "kind": "ascii-codepoint-lookup"})
            non_double_byte_counts["ascii"] += 1
            cursor += 1
        elif 0xA1 <= value <= 0xDF:
            next_value = payload[cursor + 1] if cursor + 1 < len(payload) else 0
            row = {
                "ordinal": ordinal,
                "kind": "halfwidth-codepoint-lookup",
                "unit_sha256": hashlib.sha256(payload[cursor : cursor + 1]).hexdigest(),
            }
            row.update(_halfwidth_lookup(data, value, next_value, lookup_flag=0))
            if "asset_index" in row:
                lookup_asset_count += 1
            elif row.get("lookup_result_status") == "zero-combining-or-skip":
                lookup_zero_count += 1
            units.append(row)
            non_double_byte_counts["halfwidth"] += 1
            cursor += 1
        else:
            raise StaticPathReject("record unit is outside reviewed strict grammar")
        ordinal += 1

    return {
        "mode": "b3tj-static-strict-record-to-font-asset-arithmetic",
        "identity": {
            "size": len(data),
            "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08X}",
            "game_code": data[0xAC:0xB0].decode("ascii", errors="replace"),
        },
        "record": {
            "string_id": f"sjis:0x{record_offset:06X}",
            "file_offset": _hex(record_offset, 6),
            "region": record.region,
            "raw_length": record.raw_length,
            "unit_count": len(units),
        },
        "static_contract": {
            "format_entry": _hex(ROM_BASE + 0x14F4),
            "font_map_entry": _hex(FONT_MAP_ENTRY),
            "asset_base": _hex(FONT_ASSET_BASE),
            "asset_stride_bytes": FONT_ASSET_STRIDE,
            "double_byte_formula": "(lead-adjusted)*3*0x40 + trail - 0x40",
            "lead_boundary": _hex(0x87, 2),
            "codepoint_lookup_entry": _hex(CODEPOINT_LOOKUP_ENTRY),
            "codepoint_pointer_pool": {
                _hex(slot, 6): _hex(address)
                for slot, address in CODEPOINT_POINTER_POOL.items()
            },
            "halfwidth_lookup_flag": 0,
            "font_map_literal_and_stride_signature": True,
        },
        "units": units,
        "counts": {
            "total_units": len(units),
            "double_byte_asset_units": double_byte_count,
            "lookup_asset_units": lookup_asset_count,
            "lookup_zero_units": lookup_zero_count,
            **non_double_byte_counts,
            "unique_asset_indices": len(
                {row["asset_index"] for row in units if "asset_index" in row}
            ),
        },
        "classification": {
            "strict_record_membership": "confirmed-static-extractor-boundary",
            "record_to_asset_arithmetic": "confirmed-static-for-modeled-units",
            "halfwidth_codepoint_lookup": "confirmed-static-table-evaluation",
            "asset_slot_identity_as_glyph": "unconfirmed",
            "live_source_consumer": "unconfirmed",
            "codepage_and_width_semantics": "unconfirmed",
            "asset_to_ram_or_vram_writer": "unconfirmed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--record-offset", type=lambda value: int(value, 0), default=0x146EE0)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.rom.read_bytes(), args.record_offset)
    except (OSError, StaticPathReject, ValueError) as exc:
        parser.error(str(exc))
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(text, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
