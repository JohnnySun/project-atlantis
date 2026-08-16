#!/usr/bin/env python3
"""Audit the complete A6SJ source pool with a fail-closed encoder boundary.

The source pool is fully re-read and no-op encoded, but only source-safe
ledger records whose verified shape is narrow-only may enter the bounded
static reinsertor.  Mixed, wide, opaque, and untranslated records remain
explicitly rejected; this tool does not claim a complete semantic translator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m17_layout import read_source_records, source_payload, tokenize_payload  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325


class FullCorpusReject(ValueError):
    """The full-corpus fail-closed audit rejected an input."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Sequence[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise FullCorpusReject(f"invalid_jsonl_record:{path}:{line_number}")
        rows.append(row)
    return rows


def read_ledger_ids(paths: Sequence[Path]) -> set[int]:
    result: set[int] = set()
    for path in paths:
        for row in read_jsonl(path):
            if "source" in row:
                raise FullCorpusReject(f"source_text_emitted:{path}")
            try:
                result.add(int(row["string_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise FullCorpusReject(f"invalid_ledger_id:{path}") from exc
    return result


def audit(
    rom: bytes,
    source_records: Sequence[Mapping[str, Any]],
    translated_ids: set[int],
    reinsert_report: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
) -> Dict[str, Any]:
    if sha256(rom) != ROM_SHA256:
        raise FullCorpusReject("rom_hash_mismatch")
    if len(source_records) != EXPECTED_RECORD_COUNT:
        raise FullCorpusReject("record_count_mismatch")
    source_ids = {int(row["offset"]) for row in source_records}
    if len(source_ids) != len(source_records):
        raise FullCorpusReject("duplicate_source_id")
    if not translated_ids.issubset(source_ids):
        raise FullCorpusReject("ledger_id_outside_source_pool")

    partitions: Counter[str] = Counter()
    partition_ids: Dict[str, list[int]] = {}
    no_op_count = 0
    nul_count = 0
    translated_by_partition: Counter[str] = Counter()
    translated_rejects: list[int] = []
    for row in source_records:
        source_id = int(row["offset"])
        text = str(row["text"])
        try:
            expected_payload = text.encode("shift_jis", errors="strict")
        except UnicodeEncodeError as exc:
            raise FullCorpusReject(f"source_not_shift_jis:{source_id}") from exc
        payload, terminator = source_payload(rom, source_id)
        if payload != expected_payload:
            raise FullCorpusReject(f"source_payload_mismatch:{source_id}")
        tokenization = tokenize_payload(payload)
        if terminator != source_id + len(payload):
            raise FullCorpusReject(f"nul_boundary_mismatch:{source_id}")
        partition = classify_partition(tokenization)
        partitions[partition] += 1
        partition_ids.setdefault(partition, []).append(source_id)
        nul_count += 1
        no_op_count += int(b"".join(token.raw for token in tokenization.tokens) + b"\x00" == payload + b"\x00")
        if source_id in translated_ids:
            translated_by_partition[partition] += 1
            if partition != "glyph_only_narrow":
                translated_rejects.append(source_id)
    if translated_rejects:
        raise FullCorpusReject("translated_record_outside_narrow_contract")

    report_ids = {int(row["string_id"]) for row in reinsert_report.get("records", [])}
    if report_ids != translated_ids:
        raise FullCorpusReject("reinsert_translation_set_mismatch")
    if int(reinsert_report.get("allocator", {}).get("wide_new_slots", -1)) != 0:
        raise FullCorpusReject("wide_new_slots_nonzero")
    if any(not bool(row.get("same_length")) for row in reinsert_report.get("records", [])):
        raise FullCorpusReject("reinsert_variable_length")

    partition_report = {}
    for partition in sorted(partitions):
        partition_report[partition] = {
            "record_count": partitions[partition],
            "record_id_index_sha256": hash_ints(partition_ids[partition]),
            "translated_record_count": translated_by_partition[partition],
        }
    rejected_count = EXPECTED_RECORD_COUNT - len(translated_ids)
    return {
        "schema": "super-robot-taisen-d-m4-full-corpus-gate-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "semantic_translation_complete": False,
        },
        "source_corpus": {
            "record_count": len(source_records),
            "strict_shift_jis_count": len(source_records),
            "nul_terminated_count": nul_count,
            "token_encode_noop_count": no_op_count,
            "partition_counts": dict(sorted(partitions.items())),
        },
        "structural_partitions": partition_report,
        "translation_boundary": {
            "ledger_record_count": len(translated_ids),
            "ledger_id_index_sha256": hash_ints(list(translated_ids)),
            "translated_narrow_only_count": translated_by_partition["glyph_only_narrow"],
            "untranslated_narrow_only_count": partitions["glyph_only_narrow"] - translated_by_partition["glyph_only_narrow"],
            "rejected_mixed_count": partitions["glyph_only_mixed"],
            "rejected_wide_count": partitions["glyph_only_wide"],
            "rejected_opaque_or_unaligned_count": partitions["opaque_or_unaligned"],
            "rejected_total_count": rejected_count,
            "policy": "only translated narrow-only records enter static reinsert; all other records fail closed",
        },
        "reinsert": {
            "record_count": int(reinsert_report["record_count"]),
            "wide_new_slots": int(reinsert_report["allocator"]["wide_new_slots"]),
            "same_length": bool(reinsert_report["allocator"]["same_length"]),
            "source_hash_matches": bool(reinsert_report["allocator"]["source_hash_matches"]),
        },
        "roundtrip": {
            "source_records": int(roundtrip["source_records"]),
            "base_source_matches": int(roundtrip["base_source_matches"]),
            "target_records": int(roundtrip["target_records"]),
            "target_exact_matches": int(roundtrip["target_exact_matches"]),
            "untouched_records": int(roundtrip["untouched_records"]),
            "untouched_exact_matches": int(roundtrip["untouched_exact_matches"]),
            "rom_outside_allowed_ranges_equal": bool(roundtrip["rom_outside_allowed_ranges_equal"]),
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": len(source_records) == EXPECTED_RECORD_COUNT,
            "strict_source_2325": no_op_count == EXPECTED_RECORD_COUNT,
            "nul_2325": nul_count == EXPECTED_RECORD_COUNT,
            "translated_set_matches_reinsert": True,
            "wide_new_slots_zero": True,
            "full_semantic_translation": False,
            "full_encoder_status": "fail_closed_subset_only",
            "source_text_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--reinsert-report", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_ledger_ids(args.ledger),
            json.loads(args.reinsert_report.read_text(encoding="utf-8")),
            json.loads(args.roundtrip.read_text(encoding="utf-8")),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m4_full_corpus_rejected={exc}", file=sys.stderr)
        return 2
    print(
        f"m4_full_corpus=accepted source={result['source_corpus']['record_count']} "
        f"translated={result['translation_boundary']['ledger_record_count']} "
        f"rejected={result['translation_boundary']['rejected_total_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
