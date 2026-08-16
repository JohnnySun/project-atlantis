#!/usr/bin/env python3
"""Build a source-safe caller/cohort boundary for A6SJ.

The pointer report used here is an existing ignored artifact from M1.5/M4.
This tool does not rescan the ROM or invent story, branch, battle, unit, or UI
labels.  It joins exact source-target candidates to the already verified
structural token classes, summarizes bounded caller cohorts, and records the
runtime-positive overlap.  Every unproven semantic category remains an
explicit ``unconfirmed`` status.
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


class BoundaryReject(ValueError):
    """An input failed the source-safe bounded join contract."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def address(value: int) -> str:
    return f"0x{value:08X}"


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise BoundaryReject(f"expected_object:{path}")
    return value


def read_ledger_ids(paths: Sequence[Path]) -> set[int]:
    result: set[int] = set()
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise BoundaryReject(f"invalid_ledger_row:{path}:{line_number}")
            if "source" in row:
                raise BoundaryReject(f"source_text_emitted:{path}:{line_number}")
            try:
                result.add(int(row["string_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise BoundaryReject(f"invalid_ledger_id:{path}:{line_number}") from exc
    return result


def read_runtime_ids(path: Path) -> set[int]:
    report = read_json(path)
    ids: set[int] = set()
    for row in report.get("source_contexts", []):
        if not isinstance(row, Mapping):
            raise BoundaryReject("invalid_runtime_context")
        try:
            value = row["string_id"]
            ids.add(int(value, 0) if isinstance(value, str) else int(value))
        except (KeyError, TypeError, ValueError) as exc:
            raise BoundaryReject("invalid_runtime_id") from exc
    return ids


def exact_candidates(pointer_report: Mapping[str, Any], source_offsets: set[int]) -> List[Mapping[str, Any]]:
    candidates: List[Mapping[str, Any]] = []
    for row in pointer_report.get("candidates", []):
        if not isinstance(row, Mapping):
            raise BoundaryReject("invalid_pointer_candidate")
        target = row.get("target_offset")
        if row.get("source_offset_exact") is True and isinstance(target, int) and target in source_offsets:
            candidates.append(row)
    return candidates


def source_partitions(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[int, str]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise BoundaryReject("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise BoundaryReject(f"record_count_mismatch:{len(records)}")
    result: Dict[int, str] = {}
    previous = None
    for row in records:
        offset = int(row["offset"])
        if not SOURCE_START <= offset < SOURCE_END or (previous is not None and offset <= previous):
            raise BoundaryReject("source_offset_order_or_range")
        previous = offset
        try:
            expected = str(row["text"]).encode("shift_jis", errors="strict")
        except UnicodeError as exc:
            raise BoundaryReject(f"source_not_strict_shift_jis:{offset:x}") from exc
        payload, terminator = source_payload(rom, offset)
        if payload != expected or terminator != offset + len(payload):
            raise BoundaryReject(f"source_payload_mismatch:{offset:x}")
        result[offset] = classify_partition(tokenize_payload(payload))
    return result


def _target_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    values = Counter()
    for row in rows:
        for call in row.get("following_calls", []):
            if not isinstance(call, Mapping) or not isinstance(call.get("target"), int):
                continue
            values[address(int(call["target"]))] += 1
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0]))[:8])


def _cohort(key: Any, rows: Sequence[Mapping[str, Any]], partitions: Mapping[int, str]) -> Dict[str, Any]:
    ids = [int(row["target_offset"]) for row in rows]
    confidence = Counter(str(row.get("confidence", "unknown")) for row in rows)
    literal_kind = Counter(str(row.get("literal_kind", "unknown")) for row in rows)
    partition_counts = Counter(partitions[value] for value in ids)
    instruction_offsets = [int(row["instruction_offset"]) for row in rows if isinstance(row.get("instruction_offset"), int)]
    if key is None:
        caller_start = None
        cohort_id = "unanchored"
    else:
        caller_start = address(ROM_BASE + int(key))
        cohort_id = caller_start
    return {
        "cohort_id": cohort_id,
        "caller_function_start": caller_start,
        "anchored_function_start": key is not None,
        "candidate_count": len(rows),
        "record_count": len(set(ids)),
        "record_id_index_sha256": hash_ints(ids),
        "candidate_instruction_index_sha256": hash_ints(instruction_offsets),
        "first_record_offset": address(min(ids)),
        "last_record_offset": address(max(ids)),
        "confidence_counts": dict(sorted(confidence.items())),
        "literal_kind_counts": dict(sorted(literal_kind.items())),
        "structural_partition_counts": dict(sorted(partition_counts.items())),
        "following_call_target_counts": _target_counts(rows),
        "semantic_label": "unclassified",
    }


def build_report(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    pointer_report: Mapping[str, Any],
    runtime_ids: set[int],
    translated_ids: set[int],
    *,
    inventory_report: Mapping[str, Any],
    layout_report: Mapping[str, Any],
    wide_report: Mapping[str, Any],
) -> Dict[str, Any]:
    partitions = source_partitions(rom, records)
    source_offsets = set(partitions)
    if not runtime_ids <= source_offsets or not translated_ids <= source_offsets:
        raise BoundaryReject("runtime_or_ledger_id_outside_source_pool")
    rows = exact_candidates(pointer_report, source_offsets)
    by_caller: Dict[Any, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = row.get("function_start") if isinstance(row.get("function_start"), int) else None
        by_caller[key].append(row)
    cohorts = [_cohort(key, values, partitions) for key, values in by_caller.items()]
    cohorts.sort(key=lambda value: (-int(value["candidate_count"]), str(value["cohort_id"])))
    exact_ids = [int(row["target_offset"]) for row in rows]
    anchored_rows = [row for row in rows if isinstance(row.get("function_start"), int)]
    anchored_ids = [int(row["target_offset"]) for row in anchored_rows]
    exact_partition_counts = Counter(partitions[value] for value in exact_ids)
    runtime_exact_ids = runtime_ids & set(exact_ids)
    return {
        "schema": "super-robot-taisen-d-m112-semantic-caller-boundary-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "rom_rescanned_for_pointers": False,
            "semantic_labels_inferred": False,
        },
        "source_corpus": {
            "record_count": len(records),
            "source_range": {"start": address(ROM_BASE + SOURCE_START), "end_exclusive": address(ROM_BASE + SOURCE_END)},
            "strict_shift_jis_count": len(records),
            "partition_counts": dict(sorted(Counter(partitions.values()).items())),
            "translated_static_record_count": len(translated_ids),
            "translated_static_id_index_sha256": hash_ints(translated_ids),
        },
        "pointer_join": {
            "input_aligned_pointer_refs": int(pointer_report.get("summary", {}).get("aligned_pointer_refs", 0)),
            "input_literal_candidates": int(pointer_report.get("summary", {}).get("literal_candidates", 0)),
            "input_pointer_runs": int(pointer_report.get("summary", {}).get("pointer_runs", 0)),
            "exact_source_candidate_count": len(rows),
            "exact_source_record_count": len(set(exact_ids)),
            "exact_source_record_id_index_sha256": hash_ints(exact_ids),
            "exact_candidate_instruction_index_sha256": hash_ints(
                int(row["instruction_offset"]) for row in rows if isinstance(row.get("instruction_offset"), int)
            ),
            "anchored_candidate_count": len(anchored_rows),
            "anchored_record_count": len(set(anchored_ids)),
            "anchored_record_id_index_sha256": hash_ints(anchored_ids),
            "unanchored_candidate_count": len(rows) - len(anchored_rows),
            "caller_cohort_count": len(cohorts),
            "returned_cohort_limit": COHORT_LIMIT,
            "all_cohort_records_covered": sum(int(value["candidate_count"]) for value in cohorts) == len(rows),
        },
        "bounded_caller_cohorts": cohorts[:COHORT_LIMIT],
        "exact_structural_partition_counts": dict(sorted(exact_partition_counts.items())),
        "runtime_coverage": {
            "controlled_positive_source_record_count": len(runtime_ids),
            "controlled_positive_id_index_sha256": hash_ints(runtime_ids),
            "controlled_positive_exact_pointer_record_count": len(runtime_exact_ids),
            "controlled_positive_exact_pointer_id_index_sha256": hash_ints(runtime_exact_ids),
            "natural_screen_status": "pending",
            "natural_caller_coverage_status": "not_observed",
            "runtime_positive_is_controlled_only": True,
        },
        "layout_and_control_boundary": {
            "consumer_pc": layout_report.get("consumer", {}).get("consumer"),
            "terminator": "NUL",
            "glyph_unit_bytes": 2,
            "glyph_widths": {"narrow": 8, "wide": 12},
            "opaque_token_policy": "preserve_and_reject_for_translation",
            "newline": "unconfirmed_opaque",
            "speaker": "unconfirmed_opaque",
            "branch_semantics": "unconfirmed_opaque",
            "maximum_width": layout_report.get("corpus", {}).get("line_width", {}).get("maximum_pixels"),
            "maximum_width_is_engine_limit": False,
            "observed_exact_partition_counts": dict(sorted(exact_partition_counts.items())),
        },
        "semantic_partition": {
            "story": "unconfirmed",
            "branch": "unconfirmed",
            "battle_dialogue": "unconfirmed",
            "unit_pilot_weapon_spirit": "unconfirmed",
            "ui": "unconfirmed",
            "reason": "exact pointer/caller provenance and structural shape do not prove scene semantics",
            "next_runtime_gate": "natural_or_explicitly_triggered caller context with screen or queue evidence",
        },
        "wide_boundary": {
            "existing_identity_count": wide_report.get("identity_map", {}).get("count"),
            "runtime_confirmed_identity_count": wide_report.get("identity_map", {}).get("runtime_confirmed_identity_count"),
            "new_wide_slot_capacity": 0,
            "policy": "existing-slot identity only; unknown target and expansion reject",
        },
        "gate": {
            "rom_hash_match": sha256(rom) == EXPECTED_ROM_SHA256,
            "record_count_match": len(records) == EXPECTED_RECORD_COUNT,
            "strict_source_identity": True,
            "token_encode_no_op": True,
            "pointer_report_reused_without_rescan": True,
            "semantic_labels_inferred": False,
            "source_text_emitted": False,
            "inventory_schema": inventory_report.get("schema"),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--pointer-report", type=Path, required=True)
    parser.add_argument("--runtime-provenance", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--wide", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_json(args.pointer_report),
            read_runtime_ids(args.runtime_provenance),
            read_ledger_ids(args.ledger),
            inventory_report=read_json(args.inventory),
            layout_report=read_json(args.layout),
            wide_report=read_json(args.wide),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m112_semantic_caller_boundary_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m112_semantic_caller_boundary=accepted records={} exact_candidates={} "
        "cohorts={} runtime_positive={}".format(
            report["source_corpus"]["record_count"],
            report["pointer_join"]["exact_source_candidate_count"],
            report["pointer_join"]["caller_cohort_count"],
            report["runtime_coverage"]["controlled_positive_source_record_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
