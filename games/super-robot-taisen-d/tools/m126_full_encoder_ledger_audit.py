#!/usr/bin/env python3
"""Reconcile the A6SJ full-corpus encoder boundary with every tracked ledger.

M1.26 is a coverage audit, not a translation batch.  It re-runs the existing
M1.13 encoder contract, M1.21 capacity join, and M4 full-corpus round-trip
gate from the ignored source/work inputs.  The tracked result contains only
counts, hashes, partitions, and rejection metadata; source text and target
text are never written to the result.

The audit is intentionally fail-closed: the twelve existing narrow static
records may pass, while untranslated narrow records, mixed/wide records,
opaque records, static-only wide identities, and new wide slots remain
rejected.  A passing audit therefore does not mean semantic translation is
complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m113_full_encoder_contract import (  # noqa: E402
    EXPECTED_FONT_LICENSE_SHA256,
    EXPECTED_FONT_SOURCE_SHA256,
    EXPECTED_ROM_SHA256,
    EncoderReject,
    build_report as build_encoder_report,
    hash_ints,
    read_json as read_encoder_json,
    read_ledger_rows,
    sha256,
)
from m121_wide_encoder_capacity import (  # noqa: E402
    build_report as build_capacity_report,
)
from m17_layout import read_source_records  # noqa: E402
from m4_full_corpus_gate import audit as audit_full_corpus  # noqa: E402


EXPECTED_RECORD_COUNT = 2325
EXPECTED_LEDGER_COUNT = 12
EXPECTED_NARROW_ALLOCATION_COUNT = 28
EXPECTED_WIDE_IDENTITY_COUNT = 743
EXPECTED_RUNTIME_WIDE_COUNT = 1
EXPECTED_WIDE_NEW_SLOT_CAPACITY = 0


class FullEncoderAuditReject(ValueError):
    """An input or recomputed contract failed closed."""


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise FullEncoderAuditReject(f"expected_object:{path}")
    return value


def _source_safe_ledger_rows(rows: Sequence[Mapping[str, Any]]) -> List[int]:
    """Validate row shape without returning any source or target text."""

    ids: List[int] = []
    for row in rows:
        if "source" in row or "source_text" in row:
            raise FullEncoderAuditReject("source_text_emitted")
        try:
            string_id = int(row["string_id"])
            source_hash = str(row["source_hash"])
            targets = row["targets"]
            zh_tw = targets["zh-TW"]
            target = zh_tw["text"]
        except (KeyError, TypeError, ValueError) as exc:
            raise FullEncoderAuditReject("ledger_schema_mismatch") from exc
        if len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash):
            raise FullEncoderAuditReject("ledger_source_hash_mismatch")
        if not isinstance(target, str) or not target:
            raise FullEncoderAuditReject("ledger_target_missing")
        ids.append(string_id)
    if len(ids) != len(set(ids)):
        raise FullEncoderAuditReject("duplicate_ledger_id")
    return sorted(ids)


def _hash_pairs(rows: Iterable[Mapping[str, Any]], key: str) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: int(item["string_id"])):
        digest.update(f"{int(row['string_id'])}:{row[key]}\n".encode("ascii"))
    return digest.hexdigest()


def _assert_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise FullEncoderAuditReject(f"{label}_mismatch")


def _recomputed_report_matches(
    computed_encoder: Mapping[str, Any],
    stored_encoder: Mapping[str, Any],
    computed_capacity: Mapping[str, Any],
    stored_capacity: Mapping[str, Any],
    computed_full: Mapping[str, Any],
    stored_full: Mapping[str, Any],
) -> Dict[str, bool]:
    """Compare source-safe report sections, never serializing their inputs."""

    encoder_sections = ("inputs", "source_noop", "translation_ledger", "gate")
    for section in encoder_sections:
        _assert_equal(
            f"m113_{section}",
            computed_encoder.get(section),
            stored_encoder.get(section),
        )
    capacity_sections = (
        "inputs",
        "runtime_confirmed_wide_identity",
        "source_corpus",
        "encoder_contract",
        "gate",
    )
    for section in capacity_sections:
        _assert_equal(
            f"m121_{section}",
            computed_capacity.get(section),
            stored_capacity.get(section),
        )
    full_sections = (
        "source_corpus",
        "structural_partitions",
        "translation_boundary",
        "reinsert",
        "roundtrip",
        "gate",
    )
    for section in full_sections:
        _assert_equal(
            f"m4_{section}",
            computed_full.get(section),
            stored_full.get(section),
        )
    return {
        "m113_stored_report_matches": True,
        "m121_stored_report_matches": True,
        "m4_stored_report_matches": True,
    }


def build_report(
    rom: bytes,
    source_records: Sequence[Mapping[str, Any]],
    narrow_report: Mapping[str, Any],
    wide_report: Mapping[str, Any],
    ledger_rows: Sequence[Mapping[str, Any]],
    stored_encoder: Mapping[str, Any],
    stored_capacity: Mapping[str, Any],
    stored_full: Mapping[str, Any],
    reinsert_report: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
) -> Dict[str, Any]:
    ledger_ids = _source_safe_ledger_rows(ledger_rows)
    if len(ledger_ids) != EXPECTED_LEDGER_COUNT:
        raise FullEncoderAuditReject("ledger_count_mismatch")

    computed_encoder = build_encoder_report(
        rom,
        source_records,
        narrow_report,
        wide_report,
        ledger_rows,
    )
    computed_capacity = build_capacity_report(
        rom,
        source_records,
        narrow_report,
        wide_report,
    )
    computed_full = audit_full_corpus(
        rom,
        source_records,
        set(ledger_ids),
        reinsert_report,
        roundtrip,
    )
    report_matches = _recomputed_report_matches(
        computed_encoder,
        stored_encoder,
        computed_capacity,
        stored_capacity,
        computed_full,
        stored_full,
    )

    encoder_inputs = computed_encoder["inputs"]
    encoder_source = computed_encoder["source_noop"]
    encoder_ledger = computed_encoder["translation_ledger"]
    capacity_inputs = computed_capacity["inputs"]
    capacity_source = computed_capacity["source_corpus"]
    full_boundary = computed_full["translation_boundary"]
    full_roundtrip = computed_full["roundtrip"]

    _assert_equal("rom_hash", encoder_inputs["rom_sha256"], EXPECTED_ROM_SHA256)
    _assert_equal("font_source_hash", capacity_inputs["font_source_sha256"], EXPECTED_FONT_SOURCE_SHA256)
    _assert_equal("font_license_hash", capacity_inputs["font_license_sha256"], EXPECTED_FONT_LICENSE_SHA256)
    _assert_equal("record_count", encoder_source["record_count"], EXPECTED_RECORD_COUNT)
    _assert_equal("source_no_op_count", encoder_source["token_encode_no_op_count"], EXPECTED_RECORD_COUNT)
    _assert_equal("accepted_ledger_count", encoder_ledger["accepted_count"], EXPECTED_LEDGER_COUNT)
    _assert_equal("same_length_count", encoder_ledger["same_length_count"], EXPECTED_LEDGER_COUNT)
    _assert_equal("narrow_allocation_count", encoder_inputs["narrow_allocation_count"], EXPECTED_NARROW_ALLOCATION_COUNT)
    _assert_equal("wide_identity_count", encoder_inputs["wide_existing_identity_count"], EXPECTED_WIDE_IDENTITY_COUNT)
    _assert_equal(
        "runtime_wide_identity_count",
        encoder_inputs["wide_runtime_confirmed_identity_count"],
        EXPECTED_RUNTIME_WIDE_COUNT,
    )
    _assert_equal("wide_new_slot_capacity", encoder_inputs["wide_new_slot_capacity"], EXPECTED_WIDE_NEW_SLOT_CAPACITY)
    _assert_equal("full_source_records", full_roundtrip["source_records"], EXPECTED_RECORD_COUNT)
    _assert_equal("full_target_records", full_roundtrip["target_records"], EXPECTED_LEDGER_COUNT)
    _assert_equal("full_untouched_records", full_roundtrip["untouched_records"], EXPECTED_RECORD_COUNT - EXPECTED_LEDGER_COUNT)

    return {
        "schema": "super-robot-taisen-d-m126-full-encoder-ledger-audit-v1",
        "milestone": "M1.26",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "source_table_read_in_memory_only": True,
            "target_text_emitted": False,
            "rom_modified": False,
            "raw_work_artifacts_tracked": False,
        },
        "inputs": {
            "rom_sha256": encoder_inputs["rom_sha256"],
            "font_source_sha256": capacity_inputs["font_source_sha256"],
            "font_license_sha256": capacity_inputs["font_license_sha256"],
            "narrow_allocation_count": encoder_inputs["narrow_allocation_count"],
            "wide_existing_identity_count": encoder_inputs["wide_existing_identity_count"],
            "wide_runtime_confirmed_identity_count": encoder_inputs["wide_runtime_confirmed_identity_count"],
            "wide_static_only_identity_count": encoder_inputs["wide_static_only_identity_count"],
            "wide_new_slot_capacity": encoder_inputs["wide_new_slot_capacity"],
        },
        "source_corpus": {
            "record_count": encoder_source["record_count"],
            "strict_source_count": encoder_source["strict_source_count"],
            "token_encode_no_op_count": encoder_source["token_encode_no_op_count"],
            "source_record_id_index_sha256": encoder_source["source_record_id_index_sha256"],
            "partition_counts": encoder_source["partition_counts"],
            "record_category_counts": capacity_source["record_category_counts"],
            "record_category_id_index_sha256": capacity_source["record_category_id_index_sha256"],
            "target_identity_record_counts": capacity_source["target_identity_record_counts"],
            "target_identity_record_id_index_sha256": capacity_source["target_identity_record_id_index_sha256"],
            "source_glyph_class_record_counts": capacity_source["source_glyph_class_record_counts"],
            "source_glyph_class_record_id_index_sha256": capacity_source["source_glyph_class_record_id_index_sha256"],
            "target_identity_occurrence_counts": capacity_source["target_identity_occurrence_counts"],
            "source_glyph_class_occurrence_counts": capacity_source["source_glyph_class_occurrence_counts"],
        },
        "translation_ledger": {
            "record_count": encoder_ledger["record_count"],
            "accepted_count": encoder_ledger["accepted_count"],
            "same_length_count": encoder_ledger["same_length_count"],
            "rejected_counts": encoder_ledger["rejected_counts"],
            "encoded_mode_counts": encoder_ledger["encoded_mode_counts"],
            "ledger_id_index_sha256": hash_ints(ledger_ids),
            "source_hash_index_sha256": _hash_pairs(ledger_rows, "source_hash"),
            "source_text_emitted": False,
        },
        "fail_closed_boundary": {
            "translated_narrow_only_count": full_boundary["translated_narrow_only_count"],
            "untranslated_narrow_only_count": full_boundary["untranslated_narrow_only_count"],
            "rejected_mixed_count": full_boundary["rejected_mixed_count"],
            "rejected_wide_count": full_boundary["rejected_wide_count"],
            "rejected_opaque_or_unaligned_count": full_boundary["rejected_opaque_or_unaligned_count"],
            "rejected_total_count": full_boundary["rejected_total_count"],
            "static_only_wide_target_record_count": capacity_source["record_category_counts"].get(
                "reject_static_only_wide", 0
            ),
            "unmapped_source_narrow_target_record_count": capacity_source["record_category_counts"].get(
                "reject_unmapped_source_narrow", 0
            ),
            "wide_static_only_identity_count": encoder_inputs["wide_static_only_identity_count"],
            "wide_new_slot_capacity": encoder_inputs["wide_new_slot_capacity"],
            "policy": "accept only source-safe same-length records in the verified narrow map or bounded runtime-confirmed existing wide identity",
        },
        "reinsert_roundtrip": {
            "record_count": full_roundtrip["target_records"],
            "source_records": full_roundtrip["source_records"],
            "target_exact_matches": full_roundtrip["target_exact_matches"],
            "untouched_records": full_roundtrip["untouched_records"],
            "untouched_exact_matches": full_roundtrip["untouched_exact_matches"],
            "base_source_matches": full_roundtrip["base_source_matches"],
            "rom_outside_allowed_ranges_equal": full_roundtrip["rom_outside_allowed_ranges_equal"],
        },
        "encoder_status": {
            "full_semantic_translation": False,
            "full_encoder_status": "fail_closed_subset_only",
            "variable_length": "reject",
            "opaque_or_control": "reject",
            "missing_glyph": "reject",
            "wide_static_only": "reject_for_target_until_runtime_confirmation",
            "wide_new_slot": "reject_capacity_zero",
        },
        "recomputed_contracts": report_matches,
        "gate": {
            "rom_hash_match": True,
            "font_hashes_match": True,
            "source_records_2325": True,
            "source_no_op_2325": True,
            "ledger_records_12": True,
            "ledger_encoder_accepted_12": True,
            "ledger_same_length_12": True,
            "m113_report_reconciled": True,
            "m121_report_reconciled": True,
            "m4_full_corpus_reconciled": True,
            "roundtrip_target_exact": full_roundtrip["target_exact_matches"] == EXPECTED_LEDGER_COUNT,
            "roundtrip_untouched_exact": full_roundtrip["untouched_exact_matches"] == EXPECTED_RECORD_COUNT - EXPECTED_LEDGER_COUNT,
            "roundtrip_outside_allowed_ranges_equal": bool(full_roundtrip["rom_outside_allowed_ranges_equal"]),
            "wide_new_slot_capacity_zero": True,
            "source_text_emitted": False,
            "target_text_emitted": False,
            "full_semantic_translation": False,
            "release_ready": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--narrow-report", type=Path, required=True)
    parser.add_argument("--wide-report", type=Path, required=True)
    parser.add_argument("--stored-encoder", type=Path, required=True)
    parser.add_argument("--stored-capacity", type=Path, required=True)
    parser.add_argument("--stored-full-corpus", type=Path, required=True)
    parser.add_argument("--reinsert-report", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        ledger_rows = read_ledger_rows(args.ledger)
        result = build_report(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_encoder_json(args.narrow_report),
            read_encoder_json(args.wide_report),
            ledger_rows,
            read_json(args.stored_encoder),
            read_json(args.stored_capacity),
            read_json(args.stored_full_corpus),
            read_json(args.reinsert_report),
            read_json(args.roundtrip),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, EncoderReject, FullEncoderAuditReject, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m126_full_encoder_ledger_audit_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m126_full_encoder_ledger_audit=accepted source={} ledger={}/{} rejected={} roundtrip_targets={}/{}".format(
            result["source_corpus"]["record_count"],
            result["translation_ledger"]["accepted_count"],
            result["translation_ledger"]["record_count"],
            result["fail_closed_boundary"]["rejected_total_count"],
            result["reinsert_roundtrip"]["target_exact_matches"],
            result["reinsert_roundtrip"]["record_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
