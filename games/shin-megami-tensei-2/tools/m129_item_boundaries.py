#!/usr/bin/env python3
"""Bounded item subcategory boundary anchors for A5TJ.

M1.29 extends the eight-record M1.28 item identity proof with three sparse
records at externally documented equipment transitions.  It deliberately
does not infer every intervening record or decode the unresolved secondary
table.  Only address/hash/length/count/reference and match metadata are
emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import ROM_BASE, address_metadata, read_u16, sha256  # noqa: E402
from m128_item_crossmap import (  # noqa: E402
    FIELD_OFFSET,
    FIELD_UNIT_COUNT,
    REFERENCE_SOURCES,
    TABLE_BASE,
    TABLE_RECORD_COUNT,
    TABLE_STRIDE,
    _UNIT_MAP,
    _window,
)


SCHEMA = "smt2.m1.29.item-boundaries.v1"

# These labels describe the externally documented item sequence positions;
# they are not claims that every intervening ROM record has been semantically
# decoded by this bounded slice.
_BOUNDARY_ANCHORS = (
    (0x58, "item-boundary-58-gun-start", "ベレッタ９２Ｆ"),
    (0x80, "item-boundary-80-headgear-start", "ヘッドギア"),
    (0xC0, "item-boundary-c0-footgear-segment", "ダンシングヒール"),
)

_BOUNDARY_UNIT_MAP = {
    **_UNIT_MAP,
    0x00CE: "２",
    0x00D5: "９",
    0x00E2: "Ｆ",
    0x0187: "ギ",
    0x0189: "グ",
    0x0190: "シ",
    0x0199: "ダ",
    0x01AB: "ヒ",
    0x01B1: "ヘ",
    0x01B2: "ベ",
    0x01C6: "レ",
}


def _anchor(data: bytes, ordinal: int, reference_id: str, expected: str) -> dict[str, object]:
    record_address = TABLE_BASE + ordinal * TABLE_STRIDE
    field_address = record_address + FIELD_OFFSET
    field = _window(data, field_address, FIELD_UNIT_COUNT * 2)
    units: list[int] = []
    termination = "fixed_width"
    if len(field) == FIELD_UNIT_COUNT * 2:
        for offset in range(0, len(field), 2):
            unit = read_u16(data, field_address + offset)
            if unit == 0:
                termination = "zero_0000"
                break
            units.append(unit)
    decoded = "".join(_BOUNDARY_UNIT_MAP.get(unit, "") for unit in units)
    mapped = len(decoded) == len(units) and all(unit in _BOUNDARY_UNIT_MAP for unit in units)
    return {
        "ordinal": ordinal,
        "stable_id": f"m29-item-record-{ordinal:04d}",
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": FIELD_OFFSET,
        "field_length": len(field),
        "field_hash": sha256(field) if field else None,
        "observed_unit_count": len(units),
        "expected_unit_count": len(expected),
        "termination": termination,
        "reference_id": reference_id,
        "all_units_mapped": mapped,
        "identity_match": bool(mapped and decoded == expected),
        "raw_field_emitted": False,
        "raw_units_emitted": False,
        "decoded_text_emitted": False,
    }


def static_report(data: bytes) -> dict[str, object]:
    table_window = _window(data, TABLE_BASE, TABLE_RECORD_COUNT * TABLE_STRIDE)
    anchors = [_anchor(data, *item) for item in _BOUNDARY_ANCHORS]
    matched = sum(bool(item["identity_match"]) for item in anchors)
    manifest = json.dumps(
        {"units": sorted((f"{unit:04x}", char) for unit, char in _BOUNDARY_UNIT_MAP.items())},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    table_available = len(table_window) == TABLE_RECORD_COUNT * TABLE_STRIDE
    confirmed = table_available and matched == len(_BOUNDARY_ANCHORS)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "three_sparse_item_subcategory_boundary_anchors",
            "table_base": address_metadata(TABLE_BASE, len(data)),
            "table_record_count": TABLE_RECORD_COUNT,
            "table_record_stride": TABLE_STRIDE,
            "field_offset": FIELD_OFFSET,
            "anchor_count": len(_BOUNDARY_ANCHORS),
            "table_window_length": len(table_window),
            "table_window_hash": sha256(table_window) if table_window else None,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "subcategory_crossmap": {
            "candidate_family": "item_equipment",
            "boundary_anchor_matches": matched,
            "boundary_anchor_count": len(_BOUNDARY_ANCHORS),
            "boundary_identity_status": "confirmed" if confirmed else "unconfirmed",
            "full_table_category_status": "provisional",
            "stable_id_formula": "m29-item-record-{ordinal:04d}",
            "identity_manifest_hash": hashlib.sha256(manifest).hexdigest(),
            "mapped_unit_count": len(_BOUNDARY_UNIT_MAP),
            "external_reference_urls": list(REFERENCE_SOURCES),
            "secondary_table_decoded": False,
        },
        "anchors": anchors,
        "conclusions": {
            "confirmed": (
                [
                    "0x58_0x80_0xc0_sparse_item_boundary_anchors_match",
                    "item_equipment_subcategory_edges_have_bounded_code_unit_identity",
                ]
                if confirmed
                else []
            ),
            "provisional": [
                "intervening_item_records_and_exact_subcategory_spans_are_not_fully_mapped",
                "0x08198b74_full_table_item_family_label_remains_bounded_provisional",
                "secondary_0x20_accessor_is_not_assigned_to_item_subcategory",
            ],
            "unknown": [
                "special_or_unresolved_item_fields_outside_sparse_anchors",
                "complete_codepage_unicode_glyph_width_and_control_contract",
                "natural_runtime_item_selector_and_live_reader_argument",
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
