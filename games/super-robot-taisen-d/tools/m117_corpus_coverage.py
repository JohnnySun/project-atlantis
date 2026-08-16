#!/usr/bin/env python3
"""Join the existing pointer report to the full source corpus safely.

This tool does not rescan ROM pointers and does not infer story, branch,
battle, unit, pilot, weapon, spirit, or UI semantics.  It builds a coverage
matrix from the already reviewed pointer-caller report: exact source records
by structural partition, bounded caller cohorts, and the unresolved natural
runtime boundary.  Reports contain hashes/counts/addresses only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m17_layout import ROM_BASE, read_source_records, source_payload, tokenize_payload  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
SOURCE_START = 0x076000
SOURCE_END = 0x082490
COHORT_LIMIT = 32


class CorpusCoverageReject(ValueError):
    """The existing-pointer/source join failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def address(value: int) -> str:
    return f"0x{value:08X}"


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise CorpusCoverageReject("expected_object")
    return value


def exact_candidates(pointer_report: Mapping[str, Any], source_ids: set[int]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for row in pointer_report.get("candidates", []):
        if not isinstance(row, Mapping):
            raise CorpusCoverageReject("invalid_pointer_candidate")
        target = row.get("target_offset")
        if row.get("source_offset_exact") is True and isinstance(target, int) and target in source_ids:
            rows.append(row)
    return rows


def _caller_key(row: Mapping[str, Any]) -> Any:
    value = row.get("function_start")
    return value if isinstance(value, int) else None


def summarize_coverage(
    partitions: Mapping[int, str],
    candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    total_by_partition: Counter[str] = Counter(partitions.values())
    exact_ids_by_partition: Dict[str, set[int]] = defaultdict(set)
    occurrence_by_partition: Counter[str] = Counter()
    by_caller: Dict[Any, List[Mapping[str, Any]]] = defaultdict(list)
    exact_ids: set[int] = set()
    instruction_ids: List[int] = []
    for row in candidates:
        target = int(row["target_offset"])
        partition = partitions[target]
        exact_ids.add(target)
        exact_ids_by_partition[partition].add(target)
        occurrence_by_partition[partition] += 1
        by_caller[_caller_key(row)].append(row)
        if isinstance(row.get("instruction_offset"), int):
            instruction_ids.append(int(row["instruction_offset"]))

    cohorts: List[Dict[str, Any]] = []
    for caller, rows in by_caller.items():
        ids = [int(row["target_offset"]) for row in rows]
        callsite_ids = [int(row["instruction_offset"]) for row in rows if isinstance(row.get("instruction_offset"), int)]
        partition_counts = Counter(partitions[value] for value in ids)
        cohorts.append(
            {
                "cohort_id": "unanchored" if caller is None else address(ROM_BASE + int(caller)),
                "caller_function_start": None if caller is None else address(ROM_BASE + int(caller)),
                "anchored_function_start": caller is not None,
                "candidate_count": len(rows),
                "record_count": len(set(ids)),
                "record_id_index_sha256": hash_ints(ids),
                "candidate_instruction_index_sha256": hash_ints(callsite_ids),
                "structural_partition_counts": dict(sorted(partition_counts.items())),
                "semantic_label": "unconfirmed",
            }
        )
    cohorts.sort(key=lambda row: (-int(row["candidate_count"]), str(row["cohort_id"])))
    partition_report = {}
    for partition in sorted(total_by_partition):
        exact_ids_for_partition = exact_ids_by_partition[partition]
        partition_report[partition] = {
            "total_record_count": total_by_partition[partition],
            "exact_pointer_record_count": len(exact_ids_for_partition),
            "exact_pointer_occurrence_count": occurrence_by_partition[partition],
            "uncovered_record_count": total_by_partition[partition] - len(exact_ids_for_partition),
            "exact_record_id_index_sha256": hash_ints(exact_ids_for_partition),
        }
    cohort_identity = "\n".join(
        f"{row['cohort_id']}:{row['candidate_count']}:{row['record_id_index_sha256']}"
        for row in cohorts
    ).encode("utf-8")
    return {
        "pointer_join": {
            "exact_source_candidate_count": len(candidates),
            "exact_source_record_count": len(exact_ids),
            "exact_source_record_id_index_sha256": hash_ints(exact_ids),
            "exact_candidate_instruction_index_sha256": hash_ints(instruction_ids),
            "caller_cohort_count": len(cohorts),
            "anchored_candidate_count": sum(row["candidate_count"] for row in cohorts if row["anchored_function_start"]),
            "unanchored_candidate_count": sum(row["candidate_count"] for row in cohorts if not row["anchored_function_start"]),
            "all_cohort_candidates_covered": sum(row["candidate_count"] for row in cohorts) == len(candidates),
            "caller_cohort_index_sha256": sha256(cohort_identity),
        },
        "partition_coverage": partition_report,
        "bounded_caller_cohorts": cohorts[:COHORT_LIMIT],
        "returned_cohort_limit": COHORT_LIMIT,
    }


def build_report(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    pointer_report: Mapping[str, Any],
    *,
    semantic_report: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise CorpusCoverageReject("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise CorpusCoverageReject("record_count_mismatch")
    partitions: Dict[int, str] = {}
    previous = None
    for row in records:
        offset = int(row["offset"])
        if not SOURCE_START <= offset < SOURCE_END or (previous is not None and offset <= previous):
            raise CorpusCoverageReject("source_offset_order_or_range")
        previous = offset
        expected = str(row["text"]).encode("shift_jis", errors="strict")
        payload, terminator = source_payload(rom, offset)
        if payload != expected or terminator != offset + len(payload):
            raise CorpusCoverageReject("source_payload_or_nul_mismatch")
        partitions[offset] = classify_partition(tokenize_payload(payload))
    candidates = exact_candidates(pointer_report, set(partitions))
    coverage = summarize_coverage(partitions, candidates)
    runtime = semantic_report.get("runtime_coverage", {}) if semantic_report else {}
    semantic = {
        "story": "unconfirmed",
        "branch": "unconfirmed",
        "battle_dialogue": "unconfirmed",
        "unit_pilot_weapon_spirit": "unconfirmed",
        "ui": "unconfirmed",
        "natural_caller_coverage": "not_observed",
        "controlled_runtime_positive_is_not_semantic_label": True,
    }
    return {
        "schema": "super-robot-taisen-d-m117-corpus-coverage-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "pointer_report_reused_without_rescan": True,
            "semantic_labels_inferred": False,
        },
        "rom": {"sha256": sha256(rom), "expected_sha256": EXPECTED_ROM_SHA256, "hash_match": True},
        "source_corpus": {
            "record_count": len(records),
            "source_range": {"start": address(ROM_BASE + SOURCE_START), "end_exclusive": address(ROM_BASE + SOURCE_END)},
            "partition_counts": dict(sorted(Counter(partitions.values()).items())),
            "record_id_index_sha256": hash_ints(partitions),
        },
        **coverage,
        "runtime_coverage": {
            "controlled_positive_source_record_count": runtime.get("controlled_positive_source_record_count"),
            "natural_screen_status": "pending",
            "natural_caller_status": "not_observed",
            "target_consumer_runtime_status": "not_proven",
        },
        "semantic_partition": semantic,
        "gate": {
            "rom_hash_match": True,
            "source_record_count_2325": len(records) == EXPECTED_RECORD_COUNT,
            "pointer_report_reused_without_rescan": True,
            "all_exact_candidates_partitioned": coverage["pointer_join"]["all_cohort_candidates_covered"],
            "semantic_translation_complete": False,
            "source_text_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--pointer-report", type=Path, required=True)
    parser.add_argument("--semantic-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_json(args.pointer_report),
            semantic_report=read_json(args.semantic_report) if args.semantic_report else None,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, CorpusCoverageReject, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m117_corpus_coverage_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m117_corpus_coverage=accepted records={} exact_records={} cohorts={}".format(
            report["source_corpus"]["record_count"],
            report["pointer_join"]["exact_source_record_count"],
            report["pointer_join"]["caller_cohort_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
