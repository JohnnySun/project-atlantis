#!/usr/bin/env python3
"""Metadata-only extraction contract for the bounded A5TJ item table.

M1.37 closes the addressable extent of the item-family candidate named by
M1.36.  It reads all 0xd0 records selected by the caller's <= 0xcf branch and
reports only stable IDs, addresses, hashes, lengths, unit counts, termination
classes, and aggregate coverage.  It never emits field bytes, unit values,
decoded names, glyphs, images, or a translation ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import ROM_BASE, address_metadata, read_u16, sha256  # noqa: E402
from m128_item_crossmap import (  # noqa: E402
    REFERENCE_SOURCES as ANCHOR_REFERENCE_SOURCES,
    _UNIT_MAP,
)
from m129_item_boundaries import _BOUNDARY_UNIT_MAP  # noqa: E402


SCHEMA = "smt2.m1.37.item-extent.v1"
TABLE_BASE = 0x08198B74
TABLE_STRIDE = 0x24
TABLE_RECORD_COUNT = 0xD0
FIELD_OFFSET = 0x14
FIELD_UNIT_COUNT = 8
FIELD_BYTE_LENGTH = FIELD_UNIT_COUNT * 2
TABLE_END = TABLE_BASE + TABLE_STRIDE * TABLE_RECORD_COUNT
NEXT_BOUNDED_TABLE = 0x08198EB4

# M1.28's consecutive prefix and M1.29's sparse boundary checks are reused as
# identity evidence.  Their Japanese reference strings remain private to
# those bounded probes and never enter this report.
IDENTITY_ANCHOR_ORDINALS = tuple(range(9)) + (0x58, 0x80, 0xC0)
KNOWN_UNITS = {**_UNIT_MAP, **_BOUNDARY_UNIT_MAP}
CONTROL_UNITS = {0x0300: "line_break", 0x0301: "terminator"}


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _field_metadata(data: bytes, ordinal: int) -> dict[str, object]:
    record_address = TABLE_BASE + ordinal * TABLE_STRIDE
    field_address = record_address + FIELD_OFFSET
    field = _window(data, field_address, FIELD_BYTE_LENGTH)
    units: list[int] = []
    first_zero_slot: int | None = None
    control_counts: Counter[str] = Counter()
    if len(field) == FIELD_BYTE_LENGTH:
        for slot in range(FIELD_UNIT_COUNT):
            unit = read_u16(data, field_address + slot * 2)
            if unit == 0:
                first_zero_slot = slot
                break
            units.append(unit)
            if unit in CONTROL_UNITS:
                control_counts[CONTROL_UNITS[unit]] += 1
    known_count = sum(unit in KNOWN_UNITS for unit in units)
    return {
        "ordinal": ordinal,
        "stable_id": f"m37-item-record-{ordinal:04d}",
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": FIELD_OFFSET,
        "field_length": len(field),
        "field_hash": sha256(field) if field else None,
        "observed_unit_count": len(units),
        "first_zero_slot": first_zero_slot,
        "termination": "zero_0000" if first_zero_slot is not None else "fixed_width",
        "known_anchor_unit_count": known_count,
        "unmapped_unit_count": len(units) - known_count,
        "control_counts": dict(sorted(control_counts.items())),
        "raw_field_emitted": False,
        "raw_units_emitted": False,
        "decoded_text_emitted": False,
    }


def _anchor_metadata(data: bytes) -> dict[str, object]:
    """Re-run only the existing bounded identity checks, without their text."""
    from m128_item_crossmap import _ANCHORS, _anchor_metadata as m28_anchor
    from m129_item_boundaries import _BOUNDARY_ANCHORS, _anchor as m29_anchor

    prefix = [
        m28_anchor(data, ordinal, reference_id, expected)
        for ordinal, (reference_id, expected) in enumerate(_ANCHORS)
    ]
    boundary = [m29_anchor(data, *anchor) for anchor in _BOUNDARY_ANCHORS]
    matches = sum(bool(item["identity_match"]) for item in prefix + boundary)
    return {
        "anchor_ordinals": list(IDENTITY_ANCHOR_ORDINALS),
        "anchor_count": len(prefix) + len(boundary),
        "identity_match_count": matches,
        "identity_status": (
            "confirmed" if matches == len(prefix) + len(boundary) else "unconfirmed"
        ),
        "reference_source_count": len(ANCHOR_REFERENCE_SOURCES),
        "raw_reference_text_emitted": False,
    }


def static_report(data: bytes) -> dict[str, object]:
    table_window = _window(data, TABLE_BASE, TABLE_STRIDE * TABLE_RECORD_COUNT)
    records = [_field_metadata(data, ordinal) for ordinal in range(TABLE_RECORD_COUNT)]
    available = sum(item["field_length"] == FIELD_BYTE_LENGTH for item in records)
    termination = Counter(item["termination"] for item in records)
    lengths = Counter(int(item["observed_unit_count"]) for item in records)
    total_units = sum(int(item["observed_unit_count"]) for item in records)
    known_units = sum(int(item["known_anchor_unit_count"]) for item in records)
    unmapped_units = sum(int(item["unmapped_unit_count"]) for item in records)
    field_bytes = b"".join(
        _window(data, TABLE_BASE + ordinal * TABLE_STRIDE + FIELD_OFFSET, FIELD_BYTE_LENGTH)
        for ordinal in range(TABLE_RECORD_COUNT)
    )
    anchor = _anchor_metadata(data)
    extent_match = len(table_window) == TABLE_STRIDE * TABLE_RECORD_COUNT and available == TABLE_RECORD_COUNT
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "full_caller_bounded_item_table_metadata_extraction",
            "table_base": address_metadata(TABLE_BASE, len(data)),
            "table_end_exclusive": address_metadata(TABLE_END, len(data)),
            "next_bounded_rom_table": address_metadata(NEXT_BOUNDED_TABLE, len(data)),
            "record_count": TABLE_RECORD_COUNT,
            "record_stride": TABLE_STRIDE,
            "field_offset": FIELD_OFFSET,
            "field_unit_width": 2,
            "field_unit_count": FIELD_UNIT_COUNT,
            "table_window_length": len(table_window),
            "table_window_hash": sha256(table_window) if table_window else None,
            "field_window_hash": sha256(field_bytes) if len(field_bytes) == TABLE_RECORD_COUNT * FIELD_BYTE_LENGTH else None,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "graphics_resource_scan": False,
            "runtime_capture_performed": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "extent_contract": {
            "addressable_record_range": "0x00_through_0xcf",
            "caller_threshold_basis": "M1.36 shared accessor branch index <= 0xcf",
            "records_available": available,
            "all_records_available": extent_match,
            "fixed_field_bytes": FIELD_BYTE_LENGTH,
            "fixed_field_little_endian_units": True,
            "field_copy_is_reversible": True,
            "termination_counts": dict(sorted(termination.items())),
            "unit_length_counts": dict(sorted((str(k), v) for k, v in lengths.items())),
            "total_nonzero_units": total_units,
            "known_anchor_unit_occurrences": known_units,
            "unmapped_unit_occurrences": unmapped_units,
            "known_unique_unit_count": len(KNOWN_UNITS),
            "complete_codepage": False,
            "semantic_extent_status": "provisional",
        },
        "identity_crosscheck": anchor,
        "records": records,
        "conclusions": {
            "confirmed": (
                [
                    "caller_bounded_0x08198b74_extent_has_0xd0_available_records",
                    "all_item_fields_are_reextractable_fixed_8_unit_windows",
                    "bounded_item_identity_anchors_remain_11_of_11",
                    "item_field_metadata_contains_no_source_payload",
                ]
                if extent_match and anchor["identity_status"] == "confirmed"
                else []
            ),
            "provisional": [
                "0x08198b74_addressing_extent_is_confirmed_but_semantic_category_extent_is_not",
                "known_anchor_unit_map_is_not_a_complete_game_codepage",
                "fixed_width_fields_with_zero_slots_use_writer_appended_terminator_contract",
            ],
            "unknown": [
                "unicode_identity_for_unmapped_item_units",
                "complete_item_codepage_glyph_width_and_control_contract",
                "natural_runtime_item_selection_and_scene_category",
                "reinserted_item_field_byte_contract",
            ],
            "translation_ledger": "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = static_report(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
