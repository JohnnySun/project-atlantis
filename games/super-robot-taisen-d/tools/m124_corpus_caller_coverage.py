#!/usr/bin/env python3
"""Reconcile A6SJ source cohorts, consumer callsites, and runtime coverage.

M1.24 reuses the reviewed M1.17/M1.20 reports and the ignored pointer-caller
report.  It does not rescan ROM pointers, read the local source table, or turn
structural caller names into story/branch/battle/unit/UI semantics.  The
output contains only hashes, offsets, counts, callsite metadata, and explicit
unconfirmed statuses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
EXPECTED_EXACT_CANDIDATES = 609
EXPECTED_EXACT_RECORDS = 370
EXPECTED_CALLER_COHORTS = 123
EXPECTED_CONSUMER_CALLSITES = 5


class CoverageReconcileReject(ValueError):
    """A source-safe coverage join failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def address(value: int) -> str:
    return f"0x{value:08X}"


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise CoverageReconcileReject(f"expected_object:{path}")
    return value


def _assert_source_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        if "text" in value:
            raise CoverageReconcileReject(f"source_text_key:{path}")
        for key, child in value.items():
            _assert_source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_source_safe(child, f"{path}[{index}]")


def read_ledger_ids(paths: Sequence[Path]) -> Set[int]:
    ids: Set[int] = set()
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping) or "source" in row:
                raise CoverageReconcileReject(f"ledger_source_or_shape:{path}:{line_number}")
            try:
                ids.add(int(row["string_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise CoverageReconcileReject(f"ledger_id:{path}:{line_number}") from exc
    return ids


def _exact_pointer_ids(pointer_report: Mapping[str, Any]) -> Set[int]:
    result: Set[int] = set()
    for row in pointer_report.get("candidates", []):
        if not isinstance(row, Mapping):
            raise CoverageReconcileReject("pointer_candidate_shape")
        if row.get("source_offset_exact") is True:
            target = row.get("target_offset")
            if not isinstance(target, int):
                raise CoverageReconcileReject("exact_candidate_offset_shape")
            result.add(target)
    return result


def _callsite_inventory(callsite_report: Mapping[str, Any]) -> Dict[str, Any]:
    calls = callsite_report.get("consumer_callsites")
    if not isinstance(calls, Mapping):
        raise CoverageReconcileReject("consumer_callsite_report_missing")
    entries = calls.get("entries")
    if not isinstance(entries, list) or len(entries) != EXPECTED_CONSUMER_CALLSITES:
        raise CoverageReconcileReject("consumer_callsite_count_mismatch")
    result: List[Dict[str, Any]] = []
    classes: Counter[str] = Counter()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise CoverageReconcileReject("consumer_callsite_entry_shape")
        static = entry.get("static")
        if not isinstance(static, Mapping) or static.get("status") != "verified":
            raise CoverageReconcileReject("unverified_consumer_callsite")
        classes[str(static.get("structural_class", "opaque"))] += 1
        window = static.get("instruction_window")
        if not isinstance(window, Mapping):
            raise CoverageReconcileReject("consumer_callsite_window_missing")
        result.append(
            {
                "callsite": entry.get("callsite"),
                "consumer": entry.get("consumer"),
                "structural_class": static.get("structural_class"),
                "trigger_condition": static.get("trigger_condition"),
                "instruction_window_sha256": window.get("sha256"),
                "instruction_pcs_sha256": window.get("instruction_pcs_sha256"),
                "semantic_label": "unconfirmed",
            }
        )
    return {
        "consumer": calls.get("consumer"),
        "candidate_count": int(calls.get("candidate_count", -1)),
        "candidate_instruction_index_sha256": calls.get("candidate_instruction_index_sha256"),
        "verified_entries": result,
        "structural_class_counts": dict(sorted(classes.items())),
        "semantic_label": "unconfirmed",
    }


def _runtime_boundary(
    m119_report: Mapping[str, Any], m122_report: Mapping[str, Any]
) -> Dict[str, Any]:
    m119_runtime = m119_report.get("runtime_caller")
    m119_gate = m119_report.get("gate")
    m119_gdb = m119_report.get("gdb")
    if not isinstance(m119_runtime, Mapping) or not isinstance(m119_gate, Mapping) or not isinstance(m119_gdb, Mapping):
        raise CoverageReconcileReject("m119_runtime_shape")
    m122_runtime = m122_report.get("runtime_attempt")
    m122_gate = m122_report.get("gate")
    if not isinstance(m122_runtime, Mapping) or not isinstance(m122_gate, Mapping):
        raise CoverageReconcileReject("m122_runtime_shape")
    if m122_runtime.get("result") != "transport_negative":
        raise CoverageReconcileReject("m122_transport_status_changed")
    return {
        "m119_natural_consumer": {
            "fresh_process": m119_gdb.get("fresh_process_required"),
            "port": m119_gdb.get("port"),
            "single_connection": m119_gdb.get("single_connection"),
            "consumer": m119_runtime.get("consumer"),
            "caller_callsite": m119_runtime.get("caller_callsite"),
            "lr": m119_runtime.get("lr"),
            "source_pointer": m119_runtime.get("source_pointer"),
            "source_pointer_region": m119_runtime.get("source_pointer_region"),
            "target_pointer_match": m119_runtime.get("target_pointer_match"),
            "consumer_entry_observed": m119_runtime.get("status") == "consumer_entry_observed",
            "natural_screen_proven": m119_gate.get("natural_screen_proven"),
            "target_render_proven": m119_gate.get("target_render_proven"),
        },
        "m122_transport": {
            "fresh_process": m122_runtime.get("fresh_process"),
            "port": m122_runtime.get("dedicated_port"),
            "single_connection_attempt": m122_runtime.get("single_gdb_connection_attempt"),
            "natural_paths_attempted": m122_runtime.get("natural_paths_attempted"),
            "controlled_consumer_attempted": m122_runtime.get("controlled_consumer_attempted"),
            "listener_observed": m122_runtime.get("listener_observed"),
            "connection_established": m122_runtime.get("connection_established"),
            "result": m122_runtime.get("result"),
            "coverage": m122_runtime.get("coverage"),
            "rom_or_translation_failure": m122_runtime.get("rom_or_translation_failure"),
            "target_screen": m122_gate.get("target_runtime_screen"),
        },
        "natural_caller_coverage": "not_observed",
        "semantic_scene_coverage": "unconfirmed",
    }


def build_report(
    rom: bytes,
    coverage_report: Mapping[str, Any],
    pointer_report: Mapping[str, Any],
    callsite_report: Mapping[str, Any],
    m119_report: Mapping[str, Any],
    m122_report: Mapping[str, Any],
    full_corpus_report: Mapping[str, Any],
    ledger_ids: Set[int],
) -> Dict[str, Any]:
    for name, report in (
        ("coverage", coverage_report),
        ("pointer", pointer_report),
        ("callsite", callsite_report),
        ("m119", m119_report),
        ("m122", m122_report),
        ("full_corpus", full_corpus_report),
    ):
        _assert_source_safe(report, name)
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise CoverageReconcileReject("rom_hash_mismatch")
    source = coverage_report.get("source_corpus")
    pointer_join = coverage_report.get("pointer_join")
    if not isinstance(source, Mapping) or not isinstance(pointer_join, Mapping):
        raise CoverageReconcileReject("coverage_report_shape")
    if int(source.get("record_count", -1)) != EXPECTED_RECORD_COUNT:
        raise CoverageReconcileReject("source_record_count_mismatch")
    exact_ids = _exact_pointer_ids(pointer_report)
    if len(exact_ids) != EXPECTED_EXACT_RECORDS:
        raise CoverageReconcileReject("exact_record_count_mismatch")
    if int(pointer_report.get("summary", {}).get("exact_source_targets", -1)) != EXPECTED_EXACT_CANDIDATES:
        raise CoverageReconcileReject("exact_candidate_count_mismatch")
    if int(pointer_join.get("exact_source_candidate_count", -1)) != EXPECTED_EXACT_CANDIDATES:
        raise CoverageReconcileReject("coverage_exact_candidate_count_mismatch")
    if int(pointer_join.get("exact_source_record_count", -1)) != EXPECTED_EXACT_RECORDS:
        raise CoverageReconcileReject("coverage_exact_record_count_mismatch")
    if int(pointer_join.get("caller_cohort_count", -1)) != EXPECTED_CALLER_COHORTS:
        raise CoverageReconcileReject("caller_cohort_count_mismatch")
    expected_hash = pointer_join.get("exact_source_record_id_index_sha256")
    if expected_hash != hash_ints(exact_ids):
        raise CoverageReconcileReject("exact_record_hash_mismatch")
    callsites = _callsite_inventory(callsite_report)
    if callsites["candidate_count"] != EXPECTED_CONSUMER_CALLSITES:
        raise CoverageReconcileReject("direct_callsite_count_mismatch")
    if len(ledger_ids) != 12:
        raise CoverageReconcileReject("ledger_count_mismatch")
    if not ledger_ids <= exact_ids:
        raise CoverageReconcileReject("ledger_pointer_overlap_mismatch")
    translation_boundary = full_corpus_report.get("translation_boundary")
    if not isinstance(translation_boundary, Mapping):
        raise CoverageReconcileReject("full_corpus_translation_boundary_missing")
    if int(translation_boundary.get("ledger_record_count", -1)) != len(ledger_ids):
        raise CoverageReconcileReject("full_corpus_ledger_count_mismatch")
    runtime = _runtime_boundary(m119_report, m122_report)
    partition_coverage = coverage_report.get("partition_coverage")
    if not isinstance(partition_coverage, Mapping):
        raise CoverageReconcileReject("partition_coverage_missing")
    semantic_status = {
        "story": "unconfirmed",
        "branch": "unconfirmed",
        "battle_dialogue": "unconfirmed",
        "unit_pilot_weapon_spirit": "unconfirmed",
        "ui": "unconfirmed",
        "speaker": "unconfirmed",
        "newline": "unconfirmed",
        "reason": "source-pointer provenance and structural callsites do not prove scene semantics",
    }
    return {
        "schema": "super-robot-taisen-d-m124-corpus-caller-coverage-v1",
        "milestone": "M1.24",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "pointer_report_reused_without_rescan": True,
            "semantic_labels_inferred": False,
        },
        "rom": {
            "sha256": sha256(rom),
            "expected_sha256": EXPECTED_ROM_SHA256,
            "hash_match": True,
        },
        "full_corpus": {
            "record_count": EXPECTED_RECORD_COUNT,
            "partition_counts": source.get("partition_counts"),
            "exact_pointer_candidate_count": EXPECTED_EXACT_CANDIDATES,
            "exact_pointer_record_count": EXPECTED_EXACT_RECORDS,
            "caller_cohort_count": EXPECTED_CALLER_COHORTS,
            "anchored_candidate_count": pointer_join.get("anchored_candidate_count"),
            "unanchored_candidate_count": pointer_join.get("unanchored_candidate_count"),
            "partition_coverage": partition_coverage,
        },
        "translated_ledger_overlap": {
            "ledger_record_count": len(ledger_ids),
            "ledger_id_index_sha256": hash_ints(ledger_ids),
            "exact_pointer_record_count": len(ledger_ids & exact_ids),
            "exact_pointer_id_index_sha256": hash_ints(ledger_ids & exact_ids),
            "all_ledger_records_have_exact_pointer_candidate": ledger_ids <= exact_ids,
            "structural_translation_boundary": "narrow_only_static_subset; semantic scene unconfirmed",
        },
        "consumer_callsite_inventory": callsites,
        "runtime_coverage": runtime,
        "semantic_scene_partition": semantic_status,
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": True,
            "pointer_report_reused_without_rescan": True,
            "exact_pointer_candidates_609": True,
            "exact_pointer_records_370": True,
            "caller_cohorts_123": True,
            "direct_consumer_callsites_5": True,
            "ledger_records_12": True,
            "ledger_pointer_overlap_12": True,
            "natural_caller_coverage_proven": False,
            "semantic_scene_labels_proven": False,
            "translation_complete": False,
            "source_text_emitted": False,
        },
        "next_condition": (
            "capture a producer/queue context that binds one exact source record to a verified consumer callsite "
            "and screen/layout state; do not treat the 12 static ledger records or 609 pointer candidates as scene coverage"
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--coverage-report", type=Path, required=True)
    parser.add_argument("--pointer-report", type=Path, required=True)
    parser.add_argument("--callsite-report", type=Path, required=True)
    parser.add_argument("--m119-report", type=Path, required=True)
    parser.add_argument("--m122-report", type=Path, required=True)
    parser.add_argument("--full-corpus-report", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_json(args.coverage_report),
            read_json(args.pointer_report),
            read_json(args.callsite_report),
            read_json(args.m119_report),
            read_json(args.m122_report),
            read_json(args.full_corpus_report),
            read_ledger_ids(args.ledger),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, CoverageReconcileReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m124_corpus_caller_coverage_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m124_corpus_caller_coverage=accepted source={} exact_records={} ledger={} runtime={}".format(
            report["full_corpus"]["record_count"],
            report["full_corpus"]["exact_pointer_record_count"],
            report["translated_ledger_overlap"]["ledger_record_count"],
            report["runtime_coverage"]["m122_transport"]["result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
