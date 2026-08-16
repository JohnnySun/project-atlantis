#!/usr/bin/env python3
"""Bounded A5TJ item-family cross-map from eight external anchors.

M1.28 audits only the first eight records of the caller-bounded
``0x08198b74`` table.  A small, externally sourced Japanese item sequence is
used privately to verify code-unit identity and category, but the report emits
only record addresses, hashes, lengths, counts, and match booleans.  It does
not emit the anchor text, unit values, decoded strings, a full source table,
or a translation ledger.
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


SCHEMA = "smt2.m1.28.item-crossmap.v1"
TABLE_BASE = 0x08198B74
TABLE_STRIDE = 0x24
TABLE_RECORD_COUNT = 0xD0
FIELD_OFFSET = 0x14
FIELD_UNIT_COUNT = 8
ANCHOR_COUNT = 8

# This is a deliberately small identity manifest, not a submitted source
# table.  The Japanese labels are public reference anchors only.  Their unit
# values stay in the private comparison operation and never enter the report.
_ANCHORS = (
    ("item-sequence-00", "アタックナイフ"),
    ("item-sequence-01", "スパイクロッド"),
    ("item-sequence-02", "クィーンビュート"),
    ("item-sequence-03", "バトルハンマー"),
    ("item-sequence-04", "ボロックナイフ"),
    ("item-sequence-05", "スライサー"),
    ("item-sequence-06", "さそりムチ"),
    ("item-sequence-07", "コルセック"),
)

# Confirmed only by the eight bounded anchors.  No attempt is made to claim a
# complete Unicode/codepage map for the rest of the ROM.
_UNIT_MAP = {
    0x001B: "ー",
    0x0130: "さ",
    0x0138: "そ",
    0x0165: "り",
    0x017B: "ア",
    0x017C: "ィ",
    0x017D: "イ",
    0x0188: "ク",
    0x018C: "コ",
    0x018E: "サ",
    0x0192: "ス",
    0x0194: "セ",
    0x0198: "タ",
    0x019A: "チ",
    0x019C: "ッ",
    0x01A1: "ト",
    0x01A2: "ド",
    0x01A3: "ナ",
    0x01A8: "ハ",
    0x01A9: "バ",
    0x01AA: "パ",
    0x01AC: "ビ",
    0x01AE: "フ",
    0x01B5: "ボ",
    0x01B7: "マ",
    0x01BA: "ム",
    0x01BF: "ュ",
    0x01C3: "ラ",
    0x01C5: "ル",
    0x01C7: "ロ",
    0x01CD: "ン",
}

REFERENCE_SOURCES = (
    "https://www.nintendo.co.jp/data/software/manual/WUP-N-JBRJ-JPN.pdf",
    "https://wikiwiki.jp/snes007/%E7%9C%9F%E3%83%BB%E5%A5%B3%E7%A5%9E%E8%BB%A2%E7%94%9F%E2%85%A1%E3%80%80%E5%90%84%E7%A8%AE%E3%83%AA%E3%82%B9%E3%83%88",
)


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _field_units(data: bytes, ordinal: int) -> tuple[list[int], str, int]:
    address = TABLE_BASE + ordinal * TABLE_STRIDE + FIELD_OFFSET
    field = _window(data, address, FIELD_UNIT_COUNT * 2)
    if len(field) != FIELD_UNIT_COUNT * 2:
        return [], "record_out_of_bounds", 0
    units: list[int] = []
    termination = "fixed_width"
    for offset in range(0, len(field), 2):
        unit = read_u16(data, address + offset)
        if unit == 0:
            termination = "zero_0000"
            break
        units.append(unit)
    return units, termination, len(field)


def _anchor_metadata(data: bytes, ordinal: int, reference_id: str, expected: str) -> dict[str, object]:
    record_address = TABLE_BASE + ordinal * TABLE_STRIDE
    field = _window(data, record_address + FIELD_OFFSET, FIELD_UNIT_COUNT * 2)
    units, termination, field_length = _field_units(data, ordinal)
    decoded = "".join(_UNIT_MAP.get(unit, "") for unit in units)
    all_units_mapped = len(decoded) == len(units) and all(unit in _UNIT_MAP for unit in units)
    return {
        "ordinal": ordinal,
        "stable_id": f"m28-item-record-{ordinal:04d}",
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": FIELD_OFFSET,
        "field_length": field_length,
        "field_hash": sha256(field) if field else None,
        "observed_unit_count": len(units),
        "termination": termination,
        "reference_id": reference_id,
        "expected_unit_count": len(expected),
        "all_anchor_units_mapped": all_units_mapped,
        "identity_match": bool(all_units_mapped and decoded == expected),
        "raw_field_emitted": False,
        "raw_units_emitted": False,
        "decoded_text_emitted": False,
    }


def static_report(data: bytes) -> dict[str, object]:
    table_window = _window(data, TABLE_BASE, TABLE_RECORD_COUNT * TABLE_STRIDE)
    anchors = [
        _anchor_metadata(data, ordinal, reference_id, expected)
        for ordinal, (reference_id, expected) in enumerate(_ANCHORS)
    ]
    matched = sum(bool(item["identity_match"]) for item in anchors)
    mapped_units = len(_UNIT_MAP)
    manifest = json.dumps(
        {"units": sorted((f"{unit:04x}", char) for unit, char in _UNIT_MAP.items())},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    table_available = len(table_window) == TABLE_RECORD_COUNT * TABLE_STRIDE
    confirmed = table_available and matched == ANCHOR_COUNT
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "first_eight_records_of_named_caller_bounded_item_candidate",
            "table_base": address_metadata(TABLE_BASE, len(data)),
            "table_record_count": TABLE_RECORD_COUNT,
            "table_record_stride": TABLE_STRIDE,
            "field_offset": FIELD_OFFSET,
            "anchor_count": ANCHOR_COUNT,
            "table_window_length": len(table_window),
            "table_window_hash": sha256(table_window) if table_window else None,
            "external_reference_count": len(REFERENCE_SOURCES),
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "category_crossmap": {
            "candidate_category": "item",
            "bounded_prefix_records": ANCHOR_COUNT,
            "consecutive_identity_matches": matched,
            "prefix_category_status": "confirmed" if confirmed else "unconfirmed",
            "full_table_category_status": "provisional",
            "stable_id_formula": "m28-item-record-{ordinal:04d}",
            "identity_manifest_hash": hashlib.sha256(manifest).hexdigest(),
            "mapped_unit_count": mapped_units,
            "complete_codepage": False,
            "external_reference_urls": list(REFERENCE_SOURCES),
        },
        "anchors": anchors,
        "conclusions": {
            "confirmed": (
                [
                    "eight_consecutive_shared_table_fields_match_external_item_sequence",
                    "bounded_custom_units_have_anchored_identity_for_first_item_prefix",
                    "m28_item_local_ids_are_reproducible_for_caller_bounded_table",
                ]
                if confirmed
                else []
            ),
            "provisional": [
                "full_0x08198b74_table_is_item_family_pending_boundary_crosscheck",
                "anchored_unit_map_is_not_a_complete_game_codepage",
                "external_item_names_are_reference_anchors_not_translation_ledger_entries",
            ],
            "unknown": [
                "records_after_anchor_prefix_semantic_category",
                "item_subcategory_boundaries_and_secondary_0x20_table_relation",
                "Unicode_identity_for_unanchored_units_glyph_width_control_codes",
                "natural_runtime_selector_frequency_and_live_source_pointer",
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
