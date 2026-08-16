#!/usr/bin/env python3
"""Bounded adjacent-record identity/shape probe for A5TJ text families.

M1.35 checks one record immediately after each existing named prefix:
item ordinal 8, demon ordinal 16, and skill ordinal 32.  Public Japanese
labels are private comparison anchors only.  The report emits record and
field addresses, hashes, lengths/counts, termination class, stable-ID
candidate metadata, and match booleans; it never emits unit values, names,
raw fields, decoded text, glyphs, or a translation ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import ROM_BASE, address_metadata, read_u16, sha256  # noqa: E402
import m128_item_crossmap as item  # noqa: E402
import m129_item_boundaries as item_boundary  # noqa: E402
import m130_demon_crossmap as demon  # noqa: E402
import m131_skill_crossmap as skill  # noqa: E402


SCHEMA = "smt2.m1.35.adjacent-records.v1"
FIELD_UNIT_COUNT = 8
FIELD_BYTES = FIELD_UNIT_COUNT * 2

# These names are comparison-only references.  They never enter the report.
_ADJACENT = (
    {
        "family": "item",
        "ordinal": 8,
        "reference_id": "item-adjacent-0008",
        "expected": "ギロチンアクス",
        "table_base": item.TABLE_BASE,
        "record_stride": item.TABLE_STRIDE,
        "field_offset": item.FIELD_OFFSET,
        "unit_map": item_boundary._BOUNDARY_UNIT_MAP,
        "preceding_stable_id": "m28-item-record-0007",
        "stable_id_candidate": "m28-item-record-0008",
        "reference_urls": (
            "https://wikiwiki.jp/snes007/%E7%9C%9F%E3%83%BB%E5%A5%B3%E7%A5%9E%E8%BB%A2%E7%94%9F%E2%85%A1%E3%80%80%E5%90%84%E7%A8%AE%E3%83%AA%E3%82%B9%E3%83%88",
            "https://ifs.nog.cc/fool-est.hp.infoseek.co.jp/shin_dds2/data/sword.html",
            "https://ore-game.com/dds2/equipment/sword/",
        ),
    },
    {
        "family": "demon",
        "ordinal": 16,
        "reference_id": "demon-adjacent-0016",
        "expected": "アメノトリフネ",
        "table_base": demon.TABLE_BASE,
        "record_stride": demon.TABLE_STRIDE,
        "field_offset": demon.FIELD_OFFSET,
        "unit_map": demon._DEMON_UNIT_MAP,
        "preceding_stable_id": "m30-demon-record-0015",
        "stable_id_candidate": "m30-demon-record-0016",
        "reference_urls": (
            "https://w.atwiki.jp/shinmegamitensei2/pages/527.html",
            "https://gameha.com/works/kaizou/kaizou/code/1999005/SFC_SHVC-ZE_04.html",
            "https://wikiwiki.jp/snes007/%E7%9C%9F%E3%83%BB%E5%A5%B3%E7%A5%9E%E8%BB%A2%E7%94%9F%E2%85%A1%E3%80%80%E5%90%84%E7%A8%AE%E3%83%AA%E3%82%B9%E3%83%88",
        ),
    },
    {
        "family": "skill",
        "ordinal": 32,
        "reference_id": "skill-adjacent-0032",
        "expected": "エルトラ",
        "table_base": skill.TABLE_BASE,
        "record_stride": skill.TABLE_STRIDE,
        "field_offset": skill.FIELD_OFFSET,
        "unit_map": {**skill._SKILL_UNIT_MAP, 0x0181: "エ", 0x01A1: "ト"},
        "preceding_stable_id": "m31-skill-record-0031",
        "stable_id_candidate": "m31-skill-record-0032",
        "reference_urls": (
            "https://w.atwiki.jp/shinmegamitensei2/pages/87.html",
            "https://daisanhinanjo.nobody.jp/%E7%AC%AC%E4%B8%89%E9%81%BF%E9%9B%A3%E6%89%80.jp/shin_megaten2/shin2_basic029.html",
            "https://www.gamingalexandria.com/highquality/snes/Shin%20Megami%20Tensei%20II/Shin%20Megami%20Tensei%20II%20-%20Manual%20%28Searchable%29.pdf",
        ),
    },
)


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _record(data: bytes, spec: dict[str, Any]) -> dict[str, Any]:
    record_address = int(spec["table_base"]) + int(spec["ordinal"]) * int(
        spec["record_stride"]
    )
    field_address = record_address + int(spec["field_offset"])
    field = _window(data, field_address, FIELD_BYTES)
    units: list[int] = []
    termination = "fixed_width"
    if len(field) != FIELD_BYTES:
        termination = "field_out_of_bounds"
    else:
        for offset in range(0, FIELD_BYTES, 2):
            unit = read_u16(data, field_address + offset)
            if unit == 0:
                termination = "zero_0000"
                break
            units.append(unit)
    unit_map = spec["unit_map"]
    mapped = bool(field) and all(unit in unit_map for unit in units)
    decoded = "".join(unit_map.get(unit, "") for unit in units)
    identity_match = bool(
        mapped and termination == "zero_0000" and decoded == spec["expected"]
    )
    return {
        "family": spec["family"],
        "ordinal": int(spec["ordinal"]),
        "reference_id": spec["reference_id"],
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": int(spec["field_offset"]),
        "field_length": len(field),
        "field_hash": sha256(field) if field else None,
        "observed_unit_count": len(units),
        "termination": termination,
        "mapped_unit_count": len(units) if mapped else 0,
        "identity_match": identity_match,
        "preceding_stable_id": spec["preceding_stable_id"],
        "stable_id_candidate": spec["stable_id_candidate"],
        "stable_id_status": "confirmed_for_adjacent_record"
        if identity_match
        else "unconfirmed",
        "raw_field_emitted": False,
        "raw_units_emitted": False,
        "decoded_text_emitted": False,
    }


def _manifest_hash(records: list[dict[str, Any]]) -> str:
    normalized = [
        {
            key: record.get(key)
            for key in (
                "family",
                "ordinal",
                "reference_id",
                "record_address",
                "field_offset",
                "field_length",
                "field_hash",
                "observed_unit_count",
                "termination",
                "identity_match",
                "preceding_stable_id",
                "stable_id_candidate",
            )
        }
        for record in records
    ]
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def static_report(data: bytes) -> dict[str, Any]:
    records = [_record(data, spec) for spec in _ADJACENT]
    matched = sum(bool(record["identity_match"]) for record in records)
    all_matched = matched == len(records)
    references = sorted(
        {url for spec in _ADJACENT for url in spec["reference_urls"]}
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_adjacent_record_after_each_named_item_demon_skill_prefix",
            "family_count": len(_ADJACENT),
            "record_count": len(records),
            "field_unit_count": FIELD_UNIT_COUNT,
            "field_bytes": FIELD_BYTES,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "new_table_extent_scan": False,
            "runtime_capture_performed": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "records": records,
        "adjacency_contract": {
            "all_three_identity_matches": all_matched,
            "identity_match_count": matched,
            "record_manifest_hash": _manifest_hash(records),
            "reference_urls": references,
            "table_extent_proven": False,
            "complete_codepage": False,
            "stable_id_scope": "three_adjacent_records_only",
        },
        "conclusions": {
            "confirmed": (
                [
                    "item_ordinal_8_matches_external_adjacent_identity",
                    "demon_ordinal_16_matches_external_adjacent_identity",
                    "skill_ordinal_32_matches_external_adjacent_identity",
                    "all_three_fields_have_zero_termination_within_eight_units",
                    "stable_id_candidates_are_reextractable_for_three_adjacent_records",
                ]
                if all_matched
                else []
            ),
            "provisional": [
                "adjacency_is_confirmed_only_at_three_selected_ordinals",
                "record_shape_does_not_prove_full_family_extent_or_intervening_semantics",
                "skill_adjacent_identity_extends_private_anchor_alphabet_by_two_units",
            ],
            "unknown": [
                "main_script_event_system_source_table_and_family_extent",
                "unanchored_unicode_identity_complete_codepage_glyph_width_and_controls",
                "natural_runtime_selection_and_live_writer_arguments",
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
