#!/usr/bin/env python3
"""Audit a private A9PJ decoded JSONL without printing source text.

M28 validates the local source-row contract needed before a ledger batch can
be made: stable ID, decoder version, provenance, UTF-8 source hash and the
explicit runtime/role/eligibility gates.  It accepts ignored local JSONL only
and reports IDs/counts/hashes, never row text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


PROBE_VERSION = "m28-source-checksum-probe-20260816.v1"
REQUIRED_FIELDS = {
    "string_id",
    "locale",
    "text",
    "source_text_sha256",
    "provenance",
    "decoder_version",
    "runtime_context",
    "scene_role",
    "eligible_for_ledger",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def audit_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    missing: Counter[str] = Counter()
    hash_mismatches: list[str] = []
    duplicate_ids: list[str] = []
    seen_ids: set[str] = set()
    eligible_rows = 0
    runtime_rows = 0
    unclassified_rows = 0
    for row in rows:
        row_id = str(row.get("string_id", "<missing>"))
        if row_id in seen_ids:
            duplicate_ids.append(row_id)
        seen_ids.add(row_id)
        for field in sorted(REQUIRED_FIELDS - row.keys()):
            missing[field] += 1
        text = row.get("text")
        expected = row.get("source_text_sha256")
        if isinstance(text, str) and isinstance(expected, str) and sha256_text(text) != expected:
            hash_mismatches.append(row_id)
        if row.get("eligible_for_ledger") is True:
            eligible_rows += 1
        if row.get("runtime_context") is True:
            runtime_rows += 1
        if row.get("scene_role") == "unclassified":
            unclassified_rows += 1
    return {
        "probe_version": PROBE_VERSION,
        "rows_checked": len(rows),
        "required_field_missing_counts": dict(sorted(missing.items())),
        "source_hash_mismatch_count": len(hash_mismatches),
        "source_hash_mismatch_ids": hash_mismatches,
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_ids": duplicate_ids,
        "runtime_context_rows": runtime_rows,
        "unclassified_rows": unclassified_rows,
        "eligible_rows": eligible_rows,
        "ledger_gate": {
            "schema_complete": not missing,
            "source_hashes_match": not hash_mismatches,
            "unique_ids": not duplicate_ids,
            "runtime_context_present": runtime_rows > 0,
            "unclassified_rows_present": unclassified_rows > 0,
            "eligible_for_ledger": eligible_rows > 0,
            "open": bool(rows)
            and not missing
            and not hash_mismatches
            and not duplicate_ids
            and eligible_rows > 0,
        },
        "source_text_emitted": False,
    }


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            rows.append(value)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_jsonl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_rows(load_rows(args.source_jsonl))
    result["input"] = str(args.source_jsonl)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("probe_version", "rows_checked", "ledger_gate", "source_text_emitted")}, sort_keys=True))


if __name__ == "__main__":
    main()
