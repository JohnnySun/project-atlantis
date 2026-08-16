#!/usr/bin/env python3
"""Build a full-corpus, fail-closed single-line narrow layout boundary.

This contract is intentionally conservative: it accepts only strict NUL-
terminated records whose tokenization is glyph-only narrow and whose observed
width is at most 64 pixels.  The width is a POC allocation cap, not a claim
about the engine's maximum line width.  Mixed, wide, opaque, unaligned,
newline-looking, and over-cap records remain rejected.
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

from m17_layout import ROM_BASE, read_source_records, source_payload, tokenize_payload  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
OBSERVED_SINGLE_LINE_WIDTH_CAP = 64


class LayoutSafeReject(ValueError):
    """A full-corpus layout-safe contract invariant failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def evaluate_tokenization(tokenization: Any, *, width_cap: int = OBSERVED_SINGLE_LINE_WIDTH_CAP) -> Dict[str, Any]:
    width = int(tokenization.line_width)
    partition = classify_partition(tokenization)
    if partition != "glyph_only_narrow":
        return {"accepted": False, "reason": partition, "width": width}
    if width > width_cap:
        return {"accepted": False, "reason": "width_over_observed_cap", "width": width}
    return {"accepted": True, "reason": "single_line_narrow", "width": width}


def audit(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise LayoutSafeReject("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise LayoutSafeReject("record_count_mismatch")
    statuses: Counter[str] = Counter()
    widths: Counter[int] = Counter()
    accepted_ids: list[int] = []
    all_ids: list[int] = []
    token_kinds: Counter[str] = Counter()
    no_op_count = 0
    nul_count = 0
    strict_count = 0
    for row in records:
        offset = int(row["offset"])
        text = str(row["text"])
        expected = text.encode("shift_jis", errors="strict")
        payload, terminator = source_payload(rom, offset)
        if payload != expected:
            raise LayoutSafeReject(f"source_payload_mismatch:{offset:x}")
        if terminator != offset + len(payload):
            raise LayoutSafeReject(f"nul_boundary_mismatch:{offset:x}")
        tokenization = tokenize_payload(payload)
        decision = evaluate_tokenization(tokenization)
        statuses[decision["reason"]] += 1
        widths[int(decision["width"])] += 1
        for token in tokenization.tokens:
            token_kinds[token.kind] += 1
        all_ids.append(offset)
        strict_count += 1
        nul_count += 1
        no_op_count += int(b"".join(token.raw for token in tokenization.tokens) == payload)
        if decision["accepted"]:
            accepted_ids.append(offset)
    return {
        "schema": "super-robot-taisen-d-m116-layout-safe-contract-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "source_safe_hashes_only": True},
        "rom": {"sha256": sha256(rom), "expected_sha256": EXPECTED_ROM_SHA256, "hash_match": True},
        "source_corpus": {
            "record_count": len(records),
            "strict_source_count": strict_count,
            "nul_terminated_count": nul_count,
            "token_encode_no_op_count": no_op_count,
            "record_id_index_sha256": hash_ints(all_ids),
        },
        "contract": {
            "accepted_shape": "glyph_only_narrow",
            "terminator": "NUL",
            "newline_policy": "opaque_and_reject",
            "speaker_policy": "opaque_and_reject",
            "branch_policy": "opaque_and_reject",
            "max_lines": 1,
            "width_cap_pixels": OBSERVED_SINGLE_LINE_WIDTH_CAP,
            "width_cap_is_engine_limit": False,
            "variable_length": "reject",
            "wide_new_slot_capacity": 0,
        },
        "classification": {
            "decision_counts": dict(sorted(statuses.items())),
            "accepted_record_count": len(accepted_ids),
            "accepted_id_index_sha256": hash_ints(accepted_ids),
            "width_histogram": {str(width): widths[width] for width in sorted(widths)},
            "token_kind_counts": dict(sorted(token_kinds.items())),
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": strict_count == EXPECTED_RECORD_COUNT,
            "nul_2325": nul_count == EXPECTED_RECORD_COUNT,
            "token_encode_no_op_2325": no_op_count == EXPECTED_RECORD_COUNT,
            "accepted_subset_is_single_line_narrow": True,
            "engine_width_limit_proven": False,
            "semantic_translation_complete": False,
            "source_text_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit(args.rom.read_bytes(), read_source_records(args.source_table))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, LayoutSafeReject, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"m116_layout_safe_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m116_layout_safe=accepted source={} accepted={} rejected={}".format(
            report["source_corpus"]["record_count"],
            report["classification"]["accepted_record_count"],
            report["source_corpus"]["record_count"] - report["classification"]["accepted_record_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
