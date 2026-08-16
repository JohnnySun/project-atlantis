#!/usr/bin/env python3
"""Unify the verified consumer grammar and full-corpus layout boundary.

The report names only behavior proven by the bounded consumer disassembly:
NUL termination, two-byte glyph loads, narrow/wide width classes, and an
opaque policy for every other unit.  It deliberately does not assign meaning
to numeric tokens or mode branches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m17_layout import read_source_records, source_payload, tokenize_payload  # noqa: E402
from m111_layout_contract import verify_consumer_contract  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325


class ControlLayoutReject(ValueError):
    """The unified control/layout gate rejected an input."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def token_policy(token: Any) -> str:
    """Return a structural policy name without assigning semantic meaning."""
    if token.kind == "glyph":
        return f"glyph_{token.glyph_class}"
    if token.kind == "opaque_newline_candidate":
        return "opaque_newline_candidate"
    if token.kind == "opaque_ascii_or_format":
        return "opaque_ascii_or_format"
    if token.kind == "opaque_unaligned_tail":
        return "opaque_unaligned_tail"
    return "opaque_unit"


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ControlLayoutReject("expected_object")
    return value


def audit(rom: bytes, records: Sequence[Mapping[str, Any]], layout_safe: Mapping[str, Any]) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise ControlLayoutReject("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ControlLayoutReject("record_count_mismatch")
    consumer = verify_consumer_contract(rom)
    if consumer["line_layout"]["newline_branch"] is not False:
        raise ControlLayoutReject("newline_branch_gate_changed")
    token_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    glyph_counts: Counter[str] = Counter()
    widths: list[int] = []
    record_ids: list[int] = []
    no_op_count = 0
    nul_count = 0
    for row in records:
        offset = int(row["offset"])
        text = str(row["text"])
        expected = text.encode("shift_jis", errors="strict")
        payload, terminator = source_payload(rom, offset)
        if payload != expected or terminator != offset + len(payload):
            raise ControlLayoutReject("source_payload_or_nul_mismatch")
        tokenization = tokenize_payload(payload)
        partition_counts[classify_partition(tokenization)] += 1
        widths.append(tokenization.line_width)
        record_ids.append(offset)
        nul_count += 1
        no_op_count += int(b"".join(token.raw for token in tokenization.tokens) == payload)
        for token in tokenization.tokens:
            token_counts[token_policy(token)] += 1
            if token.is_glyph:
                glyph_counts[str(token.glyph_class)] += 1
    if no_op_count != EXPECTED_RECORD_COUNT or nul_count != EXPECTED_RECORD_COUNT:
        raise ControlLayoutReject("source_noop_or_nul_gate_failed")
    safe_gate = layout_safe.get("gate")
    safe_classification = layout_safe.get("classification")
    if not isinstance(safe_gate, Mapping) or not isinstance(safe_classification, Mapping):
        raise ControlLayoutReject("layout_safe_report_shape_invalid")
    if safe_gate.get("accepted_subset_is_single_line_narrow") is not True:
        raise ControlLayoutReject("layout_safe_subset_gate_failed")
    return {
        "schema": "super-robot-taisen-d-m118-control-layout-contract-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "source_safe_hashes_only": True},
        "rom": {"sha256": sha256(rom), "expected_sha256": EXPECTED_ROM_SHA256, "hash_match": True},
        "consumer": {
            "consumer": consumer["consumer"],
            "code_sha256": consumer["code_sha256"],
            "terminator": consumer["terminator"],
            "glyph_units": consumer["glyph_units"],
            "line_layout": consumer["line_layout"],
            "final_mode_branch": consumer["final_mode_branch"],
            "unknown_semantics": consumer["unknown_semantics"],
        },
        "source_corpus": {
            "record_count": len(records),
            "nul_terminated_count": nul_count,
            "token_encode_no_op_count": no_op_count,
            "record_id_index_sha256": hash_ints(record_ids),
            "partition_counts": dict(sorted(partition_counts.items())),
            "observed_width_minimum": min(widths),
            "observed_width_maximum": max(widths),
        },
        "token_policy": {
            "known": ["NUL terminator", "two-byte narrow glyph", "two-byte wide glyph"],
            "opaque_counts": dict(sorted((key, value) for key, value in token_counts.items() if key.startswith("opaque_"))),
            "glyph_counts": dict(sorted(glyph_counts.items())),
            "all_other_units": "opaque_and_reject",
            "newline_semantics": "unconfirmed",
            "speaker_semantics": "unconfirmed",
            "branch_semantics": "unconfirmed",
        },
        "layout_safe_subset": {
            "accepted_record_count": safe_classification.get("accepted_record_count"),
            "accepted_id_index_sha256": safe_classification.get("accepted_id_index_sha256"),
            "width_cap_pixels": layout_safe.get("contract", {}).get("width_cap_pixels"),
            "width_cap_is_engine_limit": False,
            "max_lines": 1,
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": len(records) == EXPECTED_RECORD_COUNT,
            "nul_2325": nul_count == EXPECTED_RECORD_COUNT,
            "token_encode_no_op_2325": no_op_count == EXPECTED_RECORD_COUNT,
            "static_no_newline_branch": consumer["line_layout"]["newline_branch"] is False,
            "unknown_tokens_fail_closed": True,
            "engine_width_limit_proven": False,
            "semantic_translation_complete": False,
            "source_text_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--layout-safe-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_json(args.layout_safe_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ControlLayoutReject, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m118_control_layout_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m118_control_layout=accepted source={} opaque_kinds={} static_no_newline_branch={}".format(
            report["source_corpus"]["record_count"],
            len(report["token_policy"]["opaque_counts"]),
            report["gate"]["static_no_newline_branch"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
