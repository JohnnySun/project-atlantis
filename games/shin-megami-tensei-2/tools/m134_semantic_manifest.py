#!/usr/bin/env python3
"""Build a bounded metadata-only semantic manifest for named A5TJ families.

M1.34 composes the already audited item, demon, and skill anchor probes.  It
does not scan a new table, infer an extent, or emit unit values/text.  The
manifest records only stable-id namespace, ordinal/address, field hash,
length/count, termination class, identity status, and the existing private
identity-manifest hashes.  It is an auditable anchor index, not a complete
source table or translation ledger.
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

from m16_queue_probe import sha256  # noqa: E402
import m128_item_crossmap as m128  # noqa: E402
import m129_item_boundaries as m129  # noqa: E402
import m130_demon_crossmap as m130  # noqa: E402
import m131_skill_crossmap as m131  # noqa: E402


SCHEMA = "smt2.m1.34.semantic-manifest.v1"


def _safe_anchor(item: dict[str, Any], family: str) -> dict[str, Any]:
    """Keep only non-payload metadata from an existing family report."""
    keys = (
        "ordinal",
        "stable_id",
        "record_address",
        "field_offset",
        "field_length",
        "field_hash",
        "observed_unit_count",
        "expected_unit_count",
        "termination",
        "reference_id",
        "identity_match",
    )
    result = {key: item.get(key) for key in keys if key in item}
    result["family"] = family
    result["raw_field_emitted"] = False
    result["raw_units_emitted"] = False
    result["decoded_text_emitted"] = False
    return result


def _family_metadata(data: bytes, family: str, module: Any) -> dict[str, Any]:
    report = module.static_report(data)
    if family == "item":
        crossmap = report["category_crossmap"]
        anchors = report["anchors"]
    elif family == "item-boundary":
        crossmap = report["subcategory_crossmap"]
        anchors = report["anchors"]
    elif family == "demon":
        crossmap = report["category_crossmap"]
        anchors = report["anchors"]
    else:
        crossmap = report["category_crossmap"]
        anchors = report["anchors"]
    safe_anchors = [_safe_anchor(item, family) for item in anchors]
    return {
        "family": family,
        "table_base": crossmap.get("table_base")
        or report["scan_scope"].get("table_base"),
        "record_stride": report["scan_scope"].get("table_record_stride")
        or report["scan_scope"].get("table_stride"),
        "field_offset": report["scan_scope"].get("field_offset"),
        "bounded_anchor_count": len(safe_anchors),
        "identity_match_count": sum(
            bool(item.get("identity_match")) for item in safe_anchors
        ),
        "identity_manifest_hash": crossmap.get("identity_manifest_hash"),
        "stable_id_formula": crossmap.get("stable_id_formula"),
        "table_extent_proven": bool(report["scan_scope"].get("table_extent_proven", False)),
        "complete_codepage": bool(crossmap.get("complete_codepage", False)),
        "anchors": safe_anchors,
        "external_reference_urls": list(crossmap.get("external_reference_urls", [])),
    }


def _manifest_hash(families: list[dict[str, Any]]) -> str:
    normalized = []
    for family in families:
        normalized.append(
            {
                "family": family["family"],
                "table_base": family["table_base"],
                "record_stride": family["record_stride"],
                "field_offset": family["field_offset"],
                "identity_manifest_hash": family["identity_manifest_hash"],
                "anchors": [
                    {
                        key: item.get(key)
                        for key in (
                            "family",
                            "stable_id",
                            "ordinal",
                            "record_address",
                            "field_offset",
                            "field_length",
                            "field_hash",
                            "observed_unit_count",
                            "termination",
                            "identity_match",
                        )
                    }
                    for item in family["anchors"]
                ],
            }
        )
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def static_report(data: bytes) -> dict[str, Any]:
    families = [
        _family_metadata(data, "item", m128),
        _family_metadata(data, "item-boundary", m129),
        _family_metadata(data, "demon", m130),
        _family_metadata(data, "skill", m131),
    ]
    anchor_count = sum(int(item["bounded_anchor_count"]) for item in families)
    matched_count = sum(int(item["identity_match_count"]) for item in families)
    reference_urls = sorted(
        {
            url
            for family in families
            for url in family["external_reference_urls"]
        }
    )
    manifest_hash = _manifest_hash(families)
    all_bounded_matches = anchor_count > 0 and matched_count == anchor_count
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "compose_existing_bounded_item_demon_skill_anchor_metadata",
            "family_count": len(families),
            "anchor_count": anchor_count,
            "identity_match_count": matched_count,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "new_table_scan": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "families": families,
        "semantic_manifest": {
            "manifest_hash": manifest_hash,
            "stable_id_status": "bounded_anchor_ids_confirmed"
            if all_bounded_matches
            else "unconfirmed",
            "bounded_anchor_count": anchor_count,
            "identity_match_count": matched_count,
            "family_anchor_counts": {
                family["family"]: family["bounded_anchor_count"]
                for family in families
            },
            "source_table_complete": False,
            "complete_codepage": False,
            "complete_unicode_identity": False,
            "external_reference_urls": reference_urls,
        },
        "conclusions": {
            "confirmed": (
                [
                    "bounded_item_item_boundary_demon_skill_anchor_ids_are_reextractable",
                    "all_bounded_family_identity_matches_survive_composed_manifest",
                    "field_hashes_and_namespace_form_a_stable_metadata_only_manifest",
                ]
                if all_bounded_matches
                else []
            ),
            "provisional": [
                "manifest_covers_only_existing_named_anchor_cohorts",
                "same_code_unit_across_families_is_not_a_complete_codepage_proof",
                "table_extent_and_intervening_record_semantics_remain_unproven",
            ],
            "unknown": [
                "main_script_event_system_source_table_and_record_extent",
                "unanchored_unicode_identity_glyph_width_and_control_semantics",
                "natural_runtime_selection_frequency_and_live_source_pointer",
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
