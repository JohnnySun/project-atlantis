#!/usr/bin/env python3
"""Source-safe M1.10 record-boundary and opaque-token audit for A6SJ.

The audit reads the contributor's ignored source table and clean ROM, but the
report contains only offsets, hashes, lengths, counts, and bounded token
metadata.  It does not name an opaque value as a control code or newline.  A
glyph-only record is eligible for the proven no-op contract; an opaque or
unaligned record is preserved for extraction statistics but rejected by the
translation contract.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from m17_layout import (
    ROM_BASE,
    Tokenization,
    encode_tokens,
    hash_ints,
    read_source_records,
    select_cohort,
    sha256,
    source_payload,
    tokenize_payload,
)


class BoundaryAuditError(RuntimeError):
    """A source or record-boundary invariant failed closed."""


SOURCE_START = 0x76000
SOURCE_END = 0x82490
SOURCE_CENTER = 0x7B3FC
COHORT_SIZE = 16


def address(value: int) -> str:
    return f"0x{value:08X}"


def _strict_source_bytes(record: Mapping[str, Any]) -> bytes:
    try:
        return str(record["text"]).encode("shift_jis", errors="strict")
    except UnicodeEncodeError as exc:
        raise BoundaryAuditError(f"source is not strict Shift-JIS at {record['offset']!r}") from exc


def _signature_hash(tokenization: Tokenization) -> str:
    signature = json.dumps(
        tokenization.signature(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return sha256(signature)


def _token_metadata(tokenization: Tokenization) -> Dict[str, Any]:
    token_kinds = Counter(token.kind for token in tokenization.tokens)
    glyph_classes = Counter(
        token.glyph_class for token in tokenization.tokens if token.is_glyph
    )
    opaque_reasons = Counter(
        token.reason for token in tokenization.tokens if not token.is_glyph and token.reason
    )
    return {
        "status": "glyph_only" if tokenization.supported else "opaque_or_unaligned",
        "token_count": len(tokenization.tokens),
        "token_kind_counts": dict(sorted(token_kinds.items())),
        "glyph_class_counts": dict(sorted(glyph_classes.items())),
        "opaque_reason_counts": dict(sorted(opaque_reasons.items())),
        "token_signature_sha256": _signature_hash(tokenization),
        "line_width": tokenization.line_width if tokenization.supported else None,
    }


def audit_record(rom: bytes, record: Mapping[str, Any]) -> Dict[str, Any]:
    offset = int(record["offset"])
    payload, terminator = source_payload(rom, offset)
    encoded_source = _strict_source_bytes(record)
    if encoded_source != payload:
        raise BoundaryAuditError(f"source table differs from ROM at {address(ROM_BASE + offset)}")
    tokenization = tokenize_payload(payload)
    encoded = encode_tokens(tokenization, include_terminator=True)
    if encoded != payload + b"\x00":
        raise BoundaryAuditError(f"token no-op mismatch at {address(ROM_BASE + offset)}")
    metadata = _token_metadata(tokenization)
    return {
        "string_id": offset,
        "source_address": address(ROM_BASE + offset),
        "source_hash": sha256(payload),
        "payload_length": len(payload),
        "terminator": "NUL",
        "terminator_address": address(ROM_BASE + terminator),
        "record_end_exclusive": address(ROM_BASE + terminator + 1),
        "embedded_nul_count": payload.count(0),
        "byte_identity_no_op": encoded == payload + b"\x00",
        "contract_eligible": tokenization.supported,
        **metadata,
    }


def _counter_to_strings(counter: Counter[int]) -> Dict[str, int]:
    return {str(key): int(value) for key, value in sorted(counter.items())}


def _cohort_metadata(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "record_count": len(rows),
        "offset_index_sha256": hash_ints(sorted(int(row["string_id"]) for row in rows)),
        "source_hashes": [row["source_hash"] for row in rows],
        "status_counts": dict(sorted(Counter(str(row["status"]) for row in rows).items())),
        "byte_identity_no_op_count": sum(bool(row["byte_identity_no_op"]) for row in rows),
        "contract_eligible_count": sum(bool(row["contract_eligible"]) for row in rows),
        "rows": [
            {
                key: row[key]
                for key in (
                    "string_id",
                    "source_address",
                    "source_hash",
                    "payload_length",
                    "terminator",
                    "terminator_address",
                    "status",
                    "token_count",
                    "token_kind_counts",
                    "glyph_class_counts",
                    "opaque_reason_counts",
                    "token_signature_sha256",
                    "line_width",
                    "byte_identity_no_op",
                    "contract_eligible",
                )
            }
            for row in rows
        ],
    }


def build_report(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    *,
    source_start: int = SOURCE_START,
    source_end: int = SOURCE_END,
    center: int = SOURCE_CENTER,
    cohort_size: int = COHORT_SIZE,
) -> Dict[str, Any]:
    if not records:
        raise BoundaryAuditError("source table is empty")
    if not source_start <= source_end <= len(rom):
        raise BoundaryAuditError("source audit range is outside ROM")
    rows = [audit_record(rom, record) for record in records]
    offsets = [int(row["string_id"]) for row in rows]
    if offsets != sorted(offsets) or len(set(offsets)) != len(offsets):
        raise BoundaryAuditError("source records are not strictly ordered")

    overlap_count = 0
    gap_lengths: Counter[int] = Counter()
    for previous, current in zip(rows, rows[1:]):
        previous_end = ROM_BASE + int(previous["string_id"]) + int(previous["payload_length"]) + 1
        current_start = ROM_BASE + int(current["string_id"])
        if current_start < previous_end:
            overlap_count += 1
        else:
            gap_lengths[current_start - previous_end] += 1

    statuses = Counter(str(row["status"]) for row in rows)
    token_kinds: Counter[str] = Counter()
    glyph_classes: Counter[str] = Counter()
    opaque_reasons: Counter[str] = Counter()
    widths: List[int] = []
    for row in rows:
        token_kinds.update(row["token_kind_counts"])
        glyph_classes.update(row["glyph_class_counts"])
        opaque_reasons.update(row["opaque_reason_counts"])
        if row["line_width"] is not None:
            widths.append(int(row["line_width"]))

    cohort_source_rows = select_cohort(records, center, cohort_size)
    cohort_offsets = {int(row["offset"]) for row in cohort_source_rows}
    cohort_rows = [row for row in rows if int(row["string_id"]) in cohort_offsets]
    if len(cohort_rows) != cohort_size:
        raise BoundaryAuditError("bounded cohort selection changed unexpectedly")

    digest_material = "".join(
        f"{row['string_id']}:{row['source_hash']}:{row['payload_length']}\n" for row in rows
    ).encode("ascii")
    supported_no_op = sum(
        bool(row["byte_identity_no_op"]) and bool(row["contract_eligible"]) for row in rows
    )
    opaque_count = sum(not bool(row["contract_eligible"]) for row in rows)
    return {
        "schema": "super-robot-taisen-d-m110-boundary-audit-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "decoder": "strict Shift-JIS source table plus NUL-bounded ROM equality",
            "opaque_values": "preserve for statistics; reject for translation contract",
            "newline_semantics": "unconfirmed_opaque; no numeric token naming",
        },
        "source_range": {
            "start": address(ROM_BASE + source_start),
            "end_exclusive": address(ROM_BASE + source_end),
            "record_count": len(rows),
            "first_record_address": rows[0]["source_address"],
            "last_record_address": rows[-1]["source_address"],
            "last_terminator_address": rows[-1]["terminator_address"],
            "source_corpus_digest": sha256(digest_material),
        },
        "record_boundaries": {
            "strictly_ordered": offsets == sorted(offsets),
            "duplicate_offset_count": len(offsets) - len(set(offsets)),
            "overlap_count": overlap_count,
            "gap_count": sum(gap_lengths.values()),
            "gap_length_counts": _counter_to_strings(gap_lengths),
            "terminator_kind_counts": {"NUL": len(rows)},
            "embedded_nul_count": sum(int(row["embedded_nul_count"]) for row in rows),
            "record_end_in_source_range": all(
                source_start <= int(row["string_id"]) < source_end
                and int(row["terminator_address"], 0) - ROM_BASE < source_end
                for row in rows
            ),
            "rom_source_byte_identity_count": len(rows),
        },
        "tokenization": {
            "status_counts": dict(sorted(statuses.items())),
            "token_kind_counts": dict(sorted(token_kinds.items())),
            "glyph_class_counts": dict(sorted(glyph_classes.items())),
            "opaque_reason_counts": dict(sorted(opaque_reasons.items())),
            "consumer_newline_branch": False,
            "newline_candidate_count": int(opaque_reasons.get("consumer_has_no_dedicated_newline_branch", 0)),
            "unknown_token_policy": "opaque",
        },
        "layout": {
            "contract_eligible_record_count": len(widths),
            "opaque_or_unaligned_record_count": opaque_count,
            "line_width_minimum": min(widths) if widths else None,
            "line_width_maximum": max(widths) if widths else None,
            "line_width_distinct_count": len(set(widths)),
            "line_width_values_sha256": hash_ints(sorted(widths)),
        },
        "no_op": {
            "all_record_byte_identity_count": sum(bool(row["byte_identity_no_op"]) for row in rows),
            "all_record_count": len(rows),
            "contract_eligible_count": len(widths),
            "contract_eligible_byte_identity_count": supported_no_op,
            "opaque_rejected_count": opaque_count,
            "fail_closed": True,
        },
        "cohort": _cohort_metadata(cohort_rows),
        "gate": {
            "record_count_expected": 2325,
            "record_count_match": len(rows) == 2325,
            "rom_source_identity_complete": len(rows) == 2325,
            "all_nul_terminated": all(row["terminator"] == "NUL" for row in rows),
            "no_overlap": overlap_count == 0,
            "supported_no_op_complete": supported_no_op == len(widths),
            "opaque_not_named_as_control": True,
            "translation_started": False,
        },
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--start", type=lambda value: int(value, 0), default=SOURCE_START)
    parser.add_argument("--end", type=lambda value: int(value, 0), default=SOURCE_END)
    parser.add_argument("--center", type=lambda value: int(value, 0), default=SOURCE_CENTER)
    parser.add_argument("--cohort-size", type=int, default=COHORT_SIZE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    records = read_source_records(args.source_table)
    report = build_report(
        rom,
        records,
        source_start=args.start,
        source_end=args.end,
        center=args.center,
        cohort_size=args.cohort_size,
    )
    write_report(args.output, report)
    print(
        f"m110_boundary=accepted records={report['source_range']['record_count']} "
        f"status={report['tokenization']['status_counts']} "
        f"contract_noop={report['no_op']['contract_eligible_byte_identity_count']}/"
        f"{report['no_op']['contract_eligible_count']} "
        f"opaque_rejected={report['no_op']['opaque_rejected_count']} output={args.output}"
    )


if __name__ == "__main__":
    main()
