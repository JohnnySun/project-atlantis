#!/usr/bin/env python3
"""Reconcile structural caller coverage with the A6SJ wide encoder boundary.

This slice deliberately keeps scene labels separate from structural evidence.
It reuses M1.24's verified caller windows and M1.21's source-safe wide map;
there is no pointer rescan, source text output, new translation, or bitmap
identity inference.  The result states exactly which release gates are
closed and which remain unconfirmed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
EXPECTED_CALLER_CANDIDATES = 609
EXPECTED_CALLER_RECORDS = 370
EXPECTED_COHORTS = 123
EXPECTED_CALLSITES = 5
EXPECTED_WIDE_IDENTITIES = 743
EXPECTED_RUNTIME_WIDE = 1
EXPECTED_STATIC_WIDE = 742
EXPECTED_WIDE_NEW_SLOTS = 0


class SceneWideBoundaryReject(ValueError):
    """A reused structural or wide-identity report drifted or leaked text."""


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SceneWideBoundaryReject(f"expected_object:{path}")
    return value


def _source_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        if "text" in value or "targets" in value:
            raise SceneWideBoundaryReject(f"source_or_target_text_key:{path}")
        for key, child in value.items():
            _source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _source_safe(child, f"{path}[{index}]")


def _equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise SceneWideBoundaryReject(f"{label}_mismatch")


def build_report(
    m124: Mapping[str, Any],
    m121: Mapping[str, Any],
    m128: Mapping[str, Any],
) -> Dict[str, Any]:
    _source_safe(m124, "m124")
    _source_safe(m121, "m121")
    _source_safe(m128, "m128")
    _equal("m124_rom_hash", m124.get("rom", {}).get("sha256"), EXPECTED_ROM_SHA256)
    _equal("m121_rom_hash", m121.get("inputs", {}).get("rom_sha256"), EXPECTED_ROM_SHA256)
    _equal("m128_rom_hash", m128.get("gate", {}).get("rom_hash_match"), True)

    corpus = m124.get("full_corpus")
    inventory = m124.get("consumer_callsite_inventory")
    scene = m124.get("semantic_scene_partition")
    runtime = m124.get("runtime_coverage")
    if not all(isinstance(item, Mapping) for item in (corpus, inventory, scene, runtime)):
        raise SceneWideBoundaryReject("m124_sections_missing")
    assert isinstance(corpus, Mapping)
    assert isinstance(inventory, Mapping)
    assert isinstance(scene, Mapping)
    assert isinstance(runtime, Mapping)
    _equal("corpus_record_count", int(corpus.get("record_count", -1)), EXPECTED_RECORD_COUNT)
    _equal("exact_pointer_candidates", int(corpus.get("exact_pointer_candidate_count", -1)), EXPECTED_CALLER_CANDIDATES)
    _equal("exact_pointer_records", int(corpus.get("exact_pointer_record_count", -1)), EXPECTED_CALLER_RECORDS)
    _equal("caller_cohorts", int(corpus.get("caller_cohort_count", -1)), EXPECTED_COHORTS)
    _equal("consumer_callsites", int(inventory.get("candidate_count", -1)), EXPECTED_CALLSITES)
    _equal("consumer_address", inventory.get("consumer"), "0x08008724")
    _equal("consumer_semantic_label", inventory.get("semantic_label"), "unconfirmed")
    if any(value != "unconfirmed" for value in scene.values() if isinstance(value, str) and value != scene.get("reason")):
        raise SceneWideBoundaryReject("scene_semantic_label_inferred")
    if runtime.get("natural_caller_coverage") != "not_observed":
        raise SceneWideBoundaryReject("natural_caller_status_changed")

    m121_inputs = m121.get("inputs")
    m121_source = m121.get("source_corpus")
    m121_identity = m121.get("runtime_confirmed_wide_identity")
    if not all(isinstance(item, Mapping) for item in (m121_inputs, m121_source, m121_identity)):
        raise SceneWideBoundaryReject("m121_sections_missing")
    assert isinstance(m121_inputs, Mapping)
    assert isinstance(m121_source, Mapping)
    assert isinstance(m121_identity, Mapping)
    _equal("wide_identity_count", int(m121_inputs.get("wide_existing_identity_count", -1)), EXPECTED_WIDE_IDENTITIES)
    _equal("runtime_wide_count", int(m121_inputs.get("wide_runtime_confirmed_identity_count", -1)), EXPECTED_RUNTIME_WIDE)
    _equal("static_wide_count", int(m121_inputs.get("wide_static_only_identity_count", -1)), EXPECTED_STATIC_WIDE)
    _equal("wide_new_slot_capacity", int(m121_inputs.get("wide_new_slot_capacity", -1)), EXPECTED_WIDE_NEW_SLOTS)
    _equal("wide_resource_new_slot_capacity", int(m121_inputs.get("wide_resource", {}).get("new_slot_capacity", -1)), EXPECTED_WIDE_NEW_SLOTS)
    _equal("m121_source_record_count", int(m121_source.get("record_count", -1)), EXPECTED_RECORD_COUNT)
    _equal("runtime_identity_status", m121_identity.get("identity_basis"), "strict_shift_jis_source_context_plus_bounded_runtime_confirmation")
    _equal("m128_target_admissible", int(m128.get("corpus_boundary", {}).get("target_encoder_admissible_count", -1)), 12)

    partition_coverage = corpus.get("partition_coverage")
    if not isinstance(partition_coverage, Mapping):
        raise SceneWideBoundaryReject("partition_coverage_missing")
    structural_coverage = {}
    for partition, item in sorted(partition_coverage.items()):
        if not isinstance(item, Mapping):
            raise SceneWideBoundaryReject(f"partition_coverage_invalid:{partition}")
        structural_coverage[str(partition)] = {
            "total_record_count": int(item["total_record_count"]),
            "exact_pointer_record_count": int(item["exact_pointer_record_count"]),
            "uncovered_record_count": int(item["uncovered_record_count"]),
            "exact_record_id_index_sha256": str(item["exact_record_id_index_sha256"]),
        }

    target_cross = m121_source.get("target_source_class_cross_counts", {})
    if not isinstance(target_cross, Mapping):
        raise SceneWideBoundaryReject("target_source_cross_counts_missing")
    return {
        "schema": "super-robot-taisen-d-m129-scene-wide-release-boundary-v1",
        "milestone": "M1.29",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "target_text_emitted": False,
            "raw_memory_emitted": False,
            "pointer_report_rescanned": False,
            "bitmap_identity_inferred": False,
            "translation_started": False,
        },
        "structural_caller_coverage": {
            "record_count": EXPECTED_RECORD_COUNT,
            "exact_pointer_candidate_count": EXPECTED_CALLER_CANDIDATES,
            "exact_pointer_record_count": EXPECTED_CALLER_RECORDS,
            "caller_cohort_count": EXPECTED_COHORTS,
            "direct_consumer_callsite_count": EXPECTED_CALLSITES,
            "consumer": inventory["consumer"],
            "semantic_label": "unconfirmed",
            "structural_class_counts": inventory["structural_class_counts"],
            "partition_coverage": structural_coverage,
            "translated_ledger_pointer_overlap": m124["translated_ledger_overlap"],
        },
        "scene_semantics": {
            "story": "unconfirmed",
            "branch": "unconfirmed",
            "battle_dialogue": "unconfirmed",
            "unit_pilot_weapon_spirit": "unconfirmed",
            "ui": "unconfirmed",
            "speaker": "unconfirmed",
            "newline": "unconfirmed",
            "reason": "source-pointer provenance and structural callsites do not prove scene semantics",
            "natural_caller_coverage": "not_observed",
            "natural_screen_coverage": "not_observed",
        },
        "wide_encoder_strategy": {
            "resource": m121_inputs["wide_resource"],
            "existing_identity_count": EXPECTED_WIDE_IDENTITIES,
            "runtime_confirmed_identity_count": EXPECTED_RUNTIME_WIDE,
            "static_only_identity_count": EXPECTED_STATIC_WIDE,
            "new_slot_capacity": EXPECTED_WIDE_NEW_SLOTS,
            "source_wide_occurrence_count": m121_source["source_glyph_class_occurrence_counts"]["source_wide"],
            "source_wide_record_count": m121_source["source_glyph_class_record_counts"]["source_wide"],
            "target_static_only_wide_occurrence_count": m121_source["target_identity_occurrence_counts"]["target_wide_static_only"],
            "target_static_only_wide_record_count": m121_source["target_identity_record_counts"]["target_wide_static_only"],
            "source_wide_to_target_narrow_occurrence_count": target_cross.get("target_narrow_known|source_wide", 0),
            "policy": "reuse only an existing identity with bounded runtime confirmation; reject static-only and new wide slots",
            "status": "runtime_confirmed_existing_identity_only",
        },
        "release_boundary": {
            "target_encoder_admissible_records": 12,
            "full_semantic_translation": False,
            "scene_classification_complete": False,
            "wide_encoder_complete": False,
            "natural_caller_coverage_proven": False,
            "runtime_target_screen_proven": False,
            "release_ready": False,
            "next_required_evidence": [
                "producer_or_queue context binding exact source record to a verified callsite",
                "scene semantics from natural or controlled screen/layout evidence",
                "runtime confirmation for any additional wide identity or a reversible resource expansion",
                "full-corpus ledger and translation only after all fail-closed gates pass",
            ],
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": True,
            "structural_caller_reports_reconciled": True,
            "scene_semantic_labels_unconfirmed": True,
            "pointer_report_reused_without_rescan": True,
            "wide_identity_743": True,
            "runtime_wide_identity_1": True,
            "wide_static_only_742_rejected": True,
            "wide_new_slot_capacity_zero": True,
            "source_wide_target_narrow_edge_preserved": True,
            "translation_started": False,
            "full_semantic_translation": False,
            "release_ready": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m124-report", type=Path, required=True)
    parser.add_argument("--m121-report", type=Path, required=True)
    parser.add_argument("--m128-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(read_json(args.m124_report), read_json(args.m121_report), read_json(args.m128_report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, SceneWideBoundaryReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m129_scene_wide_release_boundary_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m129_scene_wide_release_boundary=accepted records={} caller_records={} wide_static_only={} new_wide_slots=0".format(
            report["structural_caller_coverage"]["record_count"],
            report["structural_caller_coverage"]["exact_pointer_record_count"],
            report["wide_encoder_strategy"]["static_only_identity_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
