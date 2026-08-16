#!/usr/bin/env python3
"""Audit the source-safe Super Robot Taisen D glossary.

The tracked TSV stores only stable record IDs and hashes.  This bounded audit
joins those hashes against the contributor's ignored local source table without
printing source text.  It intentionally does not translate or alter ROM data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple
from urllib.parse import urlparse


HEADER = (
    "term_key",
    "zh_tw",
    "category",
    "status",
    "source_record_ids",
    "source_raw_sha256s",
    "source_urls",
    "candidates",
    "decision_note",
)
ALLOWED_CATEGORIES = {"character", "unit", "ship", "spirit", "system"}
ALLOWED_STATUSES = {"accepted", "provisional", "deferred_conflict"}
TERM_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
# Reject Japanese kana letters, but allow the middle-dot punctuation used by
# some zh-TW community spellings so a punctuation disagreement can be tracked
# as deferred rather than mistaken for leaked source text.
KANA_RE = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\uff66-\uff9f]")


class GlossaryAuditError(ValueError):
    """A fail-closed glossary validation error."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_source_hashes(path: Path) -> Dict[int, str]:
    """Load record IDs and Shift-JIS raw hashes without exposing source text."""

    records: Dict[int, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                string_id = int(row["string_id"])
                text = row["text"]
                if not isinstance(text, str):
                    raise TypeError("text is not a string")
                raw = text.encode("shift_jis")
            except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
                raise GlossaryAuditError(
                    f"invalid source table row at line {line_number}: {exc}"
                ) from exc
            if string_id in records:
                raise GlossaryAuditError(f"duplicate source record id {string_id}")
            records[string_id] = sha256_bytes(raw)
    return records


def split_nonempty(value: str, separator: str, field: str, row_number: int) -> List[str]:
    parts = [part.strip() for part in value.split(separator) if part.strip()]
    if not parts:
        raise GlossaryAuditError(f"row {row_number}: {field} must not be empty")
    return parts


def parse_ids(value: str, row_number: int) -> List[int]:
    result: List[int] = []
    for item in split_nonempty(value, ",", "source_record_ids", row_number):
        if not item.isdecimal():
            raise GlossaryAuditError(f"row {row_number}: invalid source record id {item!r}")
        result.append(int(item))
    if len(result) != len(set(result)):
        raise GlossaryAuditError(f"row {row_number}: duplicate source record id")
    return result


def validate_url(url: str, row_number: int) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or any(ch.isspace() for ch in url):
        raise GlossaryAuditError(f"row {row_number}: source URL must be an https URL")


def parse_glossary(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != HEADER:
            raise GlossaryAuditError(
                f"unexpected glossary header: {tuple(reader.fieldnames or ())!r}"
            )
        rows: List[Dict[str, Any]] = []
        seen_keys = set()
        for row_number, row in enumerate(reader, 2):
            if not any(value for value in row.values()):
                continue
            if any(value is None for value in row.values()):
                raise GlossaryAuditError(f"row {row_number}: missing TSV field")
            key = row["term_key"]
            if not TERM_KEY_RE.fullmatch(key):
                raise GlossaryAuditError(f"row {row_number}: invalid term_key {key!r}")
            if key in seen_keys:
                raise GlossaryAuditError(f"row {row_number}: duplicate term_key {key!r}")
            seen_keys.add(key)
            category = row["category"]
            if category not in ALLOWED_CATEGORIES:
                raise GlossaryAuditError(f"row {row_number}: invalid category {category!r}")
            status = row["status"]
            if status not in ALLOWED_STATUSES:
                raise GlossaryAuditError(f"row {row_number}: invalid status {status!r}")
            ids = parse_ids(row["source_record_ids"], row_number)
            hashes = split_nonempty(row["source_raw_sha256s"], ",", "source_raw_sha256s", row_number)
            if len(ids) != len(hashes):
                raise GlossaryAuditError(
                    f"row {row_number}: source ID/hash counts differ"
                )
            if any(not HEX64_RE.fullmatch(value) for value in hashes):
                raise GlossaryAuditError(f"row {row_number}: invalid source hash")
            urls = split_nonempty(row["source_urls"], ";", "source_urls", row_number)
            if len(urls) != len(set(urls)):
                raise GlossaryAuditError(f"row {row_number}: duplicate source URL")
            for url in urls:
                validate_url(url, row_number)
            if status in {"accepted", "provisional"}:
                if not row["zh_tw"]:
                    raise GlossaryAuditError(
                        f"row {row_number}: {status} entry needs zh_tw"
                    )
                if len(urls) < 2:
                    raise GlossaryAuditError(
                        f"row {row_number}: accepted/provisional entry needs two sources"
                    )
                if row["candidates"]:
                    raise GlossaryAuditError(
                        f"row {row_number}: accepted entry must not carry candidates"
                    )
            else:
                if row["zh_tw"]:
                    raise GlossaryAuditError(
                        f"row {row_number}: deferred entry must leave zh_tw empty"
                    )
                if not row["candidates"]:
                    raise GlossaryAuditError(
                        f"row {row_number}: deferred entry needs candidate spellings"
                    )
            for field_name, value in row.items():
                if KANA_RE.search(value):
                    raise GlossaryAuditError(
                        f"row {row_number}: Japanese kana is not allowed in {field_name}"
                    )
            rows.append(
                {
                    "row_number": row_number,
                    "term_key": key,
                    "zh_tw": row["zh_tw"],
                    "category": category,
                    "status": status,
                    "source_record_ids": ids,
                    "source_raw_sha256s": hashes,
                    "source_urls": urls,
                    "candidates": row["candidates"],
                    "decision_note": row["decision_note"],
                }
            )
    if not rows:
        raise GlossaryAuditError("glossary has no entries")
    return rows


def audit(glossary: Path, source_table: Path) -> Dict[str, Any]:
    source_hashes = load_source_hashes(source_table)
    rows = parse_glossary(glossary)
    referenced = set()
    for row in rows:
        for record_id, declared_hash in zip(
            row["source_record_ids"], row["source_raw_sha256s"]
        ):
            if record_id not in source_hashes:
                raise GlossaryAuditError(
                    f"row {row['row_number']}: source record {record_id} is missing"
                )
            actual_hash = source_hashes[record_id]
            if actual_hash != declared_hash:
                raise GlossaryAuditError(
                    f"row {row['row_number']}: source hash mismatch for record {record_id}"
                )
            referenced.add(record_id)
    return {
        "schema": "super-robot-taisen-d-m2-glossary-audit-v1",
        "glossary_entries": len(rows),
        "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "source_table_records": len(source_hashes),
        "source_records_referenced": len(referenced),
        "source_hash_matches": sum(len(row["source_record_ids"]) for row in rows),
        "source_text_emitted": False,
        "deferred_terms_fail_closed": all(
            row["status"] == "deferred_conflict" or row["zh_tw"] for row in rows
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glossary", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.parent.name != "work":
        raise SystemExit("refusing non-work output; use games/.../work/*.json")
    try:
        report = audit(args.glossary, args.source_table)
    except GlossaryAuditError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "PASS: entries={glossary_entries} statuses={status_counts} "
        "source_records={source_table_records} referenced={source_records_referenced} "
        "hash_matches={source_hash_matches}".format(**report)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
