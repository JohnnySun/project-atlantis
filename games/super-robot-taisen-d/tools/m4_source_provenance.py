#!/usr/bin/env python3
"""Summarize existing A6SJ pointer-caller evidence without source text.

This is a bounded join over the already-created ignored pointer-caller report;
it does not rescan the ROM or infer story/UI semantics.  Its output contains
only structural partitions, caller/literal confidence counts, ID hashes, and
coverage counts so that exact pointer provenance is not confused with a full
semantic text partition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m17_layout import ROM_BASE, read_source_records, source_payload, tokenize_payload  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
SOURCE_START = 0x076000
SOURCE_END = 0x082490


class ProvenanceReject(ValueError):
    """An input failed the source-safe provenance contract."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ProvenanceReject(f"invalid_jsonl_record:{path}:{line_number}")
        rows.append(row)
    return rows


def read_ledger_ids(paths: Sequence[Path]) -> set[int]:
    ids: set[int] = set()
    for path in paths:
        for row in read_jsonl(path):
            if "source" in row:
                raise ProvenanceReject(f"source_text_emitted:{path}")
            try:
                ids.add(int(row["string_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ProvenanceReject(f"invalid_ledger_id:{path}") from exc
    return ids


def read_runtime_ids(path: Path) -> set[int]:
    report = json.loads(path.read_text(encoding="utf-8"))
    result: set[int] = set()
    for row in report.get("source_contexts", []):
        try:
            result.add(int(str(row["string_id"]), 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise ProvenanceReject("invalid_runtime_source_context") from exc
    return result


def exact_candidate_rows(pointer_report: Mapping[str, Any], source_offsets: set[int]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for row in pointer_report.get("candidates", []):
        if not isinstance(row, Mapping):
            raise ProvenanceReject("invalid_pointer_candidate")
        target_offset = row.get("target_offset")
        if bool(row.get("source_offset_exact")) and isinstance(target_offset, int) and target_offset in source_offsets:
            rows.append(row)
    return rows


def inventory(
    rom: bytes,
    source_records: Sequence[Mapping[str, Any]],
    pointer_report: Mapping[str, Any],
    translated_ids: set[int],
    runtime_ids: set[int],
) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise ProvenanceReject("rom_hash_mismatch")
    if len(source_records) != EXPECTED_RECORD_COUNT:
        raise ProvenanceReject("record_count_mismatch")
    source_offsets = {int(row["offset"]) for row in source_records}
    if len(source_offsets) != len(source_records):
        raise ProvenanceReject("duplicate_source_offset")
    unknown_translated = translated_ids - source_offsets
    if unknown_translated:
        raise ProvenanceReject("ledger_id_outside_source_pool")
    unknown_runtime = runtime_ids - source_offsets
    if unknown_runtime:
        raise ProvenanceReject("runtime_id_outside_source_pool")

    exact_rows = exact_candidate_rows(pointer_report, source_offsets)
    exact_by_offset: Dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in exact_rows:
        exact_by_offset[int(row["target_offset"])].append(row)

    partitions: Counter[str] = Counter()
    record_ids_by_partition: Dict[str, list[int]] = defaultdict(list)
    exact_record_ids_by_partition: Dict[str, list[int]] = defaultdict(list)
    exact_occurrences_by_partition: Counter[str] = Counter()
    translated_by_partition: Counter[str] = Counter()
    runtime_by_partition: Counter[str] = Counter()
    records_with_exact = 0
    source_noop = 0

    for row in source_records:
        offset = int(row["offset"])
        if not SOURCE_START <= offset < SOURCE_END:
            raise ProvenanceReject("source_offset_out_of_range")
        text = str(row["text"])
        try:
            expected = text.encode("shift_jis", errors="strict")
        except UnicodeEncodeError as exc:
            raise ProvenanceReject("source_not_shift_jis") from exc
        payload, terminator = source_payload(rom, offset)
        if payload != expected or terminator != offset + len(payload):
            raise ProvenanceReject("source_payload_mismatch")
        tokenization = tokenize_payload(payload)
        partition = classify_partition(tokenization)
        partitions[partition] += 1
        record_ids_by_partition[partition].append(offset)
        source_noop += int(b"".join(token.raw for token in tokenization.tokens) + b"\x00" == payload + b"\x00")
        exact_rows_for_record = exact_by_offset.get(offset, [])
        exact_occurrences_by_partition[partition] += len(exact_rows_for_record)
        if exact_rows_for_record:
            records_with_exact += 1
            exact_record_ids_by_partition[partition].append(offset)
        translated_by_partition[partition] += int(offset in translated_ids)
        runtime_by_partition[partition] += int(offset in runtime_ids)

    if source_noop != EXPECTED_RECORD_COUNT:
        raise ProvenanceReject("source_token_noop_mismatch")

    confidence = Counter(str(row.get("confidence", "unknown")) for row in exact_rows)
    literal_kind = Counter(str(row.get("literal_kind", "unknown")) for row in exact_rows)
    caller_functions = [int(row["function_start"]) for row in exact_rows if isinstance(row.get("function_start"), int)]
    call_targets = [
        int(call["target"])
        for row in exact_rows
        for call in row.get("following_calls", [])
        if isinstance(call, Mapping) and isinstance(call.get("target"), int)
    ]
    partition_report = {}
    for partition in sorted(partitions):
        partition_report[partition] = {
            "record_count": partitions[partition],
            "record_id_index_sha256": hash_ints(record_ids_by_partition[partition]),
            "exact_pointer_record_count": len(exact_record_ids_by_partition[partition]),
            "exact_pointer_record_id_index_sha256": hash_ints(exact_record_ids_by_partition[partition]),
            "exact_pointer_occurrences": exact_occurrences_by_partition[partition],
            "translated_static_record_count": translated_by_partition[partition],
            "runtime_identity_record_count": runtime_by_partition[partition],
        }
    return {
        "schema": "super-robot-taisen-d-m4-source-provenance-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "semantic_labels_inferred": False,
        },
        "source_corpus": {
            "record_count": len(source_records),
            "source_range": {"start": f"0x{SOURCE_START:06X}", "end_exclusive": f"0x{SOURCE_END:06X}"},
            "strict_shift_jis_count": len(source_records),
            "token_encode_noop_count": source_noop,
            "translated_static_record_count": len(translated_ids),
            "translated_static_id_index_sha256": hash_ints(translated_ids),
            "runtime_identity_record_count": len(runtime_ids),
            "runtime_identity_id_index_sha256": hash_ints(runtime_ids),
        },
        "pointer_report": {
            "aligned_pointer_refs": int(pointer_report.get("summary", {}).get("aligned_pointer_refs", 0)),
            "literal_candidates": int(pointer_report.get("summary", {}).get("literal_candidates", 0)),
            "pointer_runs": int(pointer_report.get("summary", {}).get("pointer_runs", 0)),
            "exact_source_candidate_count": len(exact_rows),
            "exact_source_record_count": records_with_exact,
            "exact_source_record_id_index_sha256": hash_ints(exact_by_offset),
            "exact_candidate_confidence": dict(sorted(confidence.items())),
            "exact_candidate_literal_kind": dict(sorted(literal_kind.items())),
            "exact_caller_function_index_sha256": hash_ints(caller_functions),
            "exact_call_target_index_sha256": hash_ints(call_targets),
        },
        "structural_partitions": partition_report,
        "semantic_boundary": {
            "caller_provenance_status": "bounded_exact_pointer_only",
            "semantic_partition_status": "unclassified",
            "natural_runtime_screen_status": "pending",
            "unknown_pointer_and_pool_outside_status": "unconfirmed",
            "next_gate": "natural_or_controlled caller context before naming story/UI/branch partitions",
        },
        "gate": {
            "rom_hash_match": True,
            "record_count_match": len(source_records) == EXPECTED_RECORD_COUNT,
            "strict_source_identity": True,
            "token_encode_noop": source_noop == EXPECTED_RECORD_COUNT,
            "pointer_report_joined": True,
            "source_text_emitted": False,
            "semantic_labels_inferred": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--pointer-report", type=Path, required=True)
    parser.add_argument("--runtime-provenance", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        pointer_report = json.loads(args.pointer_report.read_text(encoding="utf-8"))
        result = inventory(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            pointer_report,
            read_ledger_ids(args.ledger),
            read_runtime_ids(args.runtime_provenance),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m4_source_provenance_rejected={exc}", file=sys.stderr)
        return 2
    print(
        f"m4_source_provenance=accepted records={result['source_corpus']['record_count']} "
        f"exact_records={result['pointer_report']['exact_source_record_count']} "
        f"exact_candidates={result['pointer_report']['exact_source_candidate_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
