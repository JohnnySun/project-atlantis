#!/usr/bin/env python3
"""Validate the B3CJ committed ledger against the local decoded source table.

The extractor's local rows use ``source_text`` and carry game-specific
provenance.  This validator creates the core-ledger ``text`` adapter only in
a temporary directory, runs the real restore/strip pair, and reports hashes and
counts without printing source text.  No source-bearing file is written under
the repository by this tool.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
RESTORE = REPO_ROOT / "core" / "ledger" / "restore_translations.rb"
STRIP = REPO_ROOT / "core" / "ledger" / "strip_translations.rb"
EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_SOURCE_ROWS = 361
LEDGER_STATUSES = {"untranslated", "ai_draft", "ai_review", "auto_qa", "approved"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            _require(isinstance(value, dict), f"{path}:{line_number} is not a JSON object")
            rows.append(value)
    return rows


def _source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        if "source" in value or "source_text" in value:
            return True
        return any(_contains_forbidden_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False


def _load_source_table(path: pathlib.Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    _require(actual_hash == EXPECTED_SOURCE_TABLE_SHA256, "source table SHA-256 mismatch")
    rows = _load_jsonl(path)
    _require(len(rows) == EXPECTED_SOURCE_ROWS, f"source table has {len(rows)} rows, expected {EXPECTED_SOURCE_ROWS}")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        string_id = row.get("string_id")
        _require(isinstance(string_id, str) and string_id, "source row has no stable string_id")
        _require(string_id not in by_id, f"duplicate source string_id {string_id}")
        _require(row.get("locale") == "ja-JP", f"source locale mismatch for {string_id}")
        _require(isinstance(row.get("source_text"), str), f"source text missing for {string_id}")
        _require(isinstance(row.get("provenance"), dict), f"source provenance missing for {string_id}")
        by_id[string_id] = row
    return rows, by_id


def _validate_ledger_shape(
    ledger_rows: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    required_ids: set[str],
) -> dict[str, Any]:
    _require(ledger_rows, "ledger is empty")
    seen: set[str] = set()
    statuses: collections.Counter[str] = collections.Counter()
    for record in ledger_rows:
        _require(not _contains_forbidden_key(record), "ledger contains source-bearing key")
        string_id = record.get("string_id")
        _require(isinstance(string_id, str) and string_id, "ledger record has no stable string_id")
        _require(string_id not in seen, f"duplicate ledger string_id {string_id}")
        seen.add(string_id)
        _require(record.get("game") == EXPECTED_GAME, f"ledger game mismatch for {string_id}")
        _require(record.get("revision") == EXPECTED_REVISION, f"ledger revision mismatch for {string_id}")
        _require(record.get("source_locale") == "ja-JP", f"ledger source locale mismatch for {string_id}")
        source = source_by_id.get(string_id)
        _require(source is not None, f"ledger string_id is absent from source table: {string_id}")
        expected_hash = _source_hash(str(source["source_text"]))
        _require(record.get("source_hash") == expected_hash, f"source hash mismatch for {string_id}")
        _require(isinstance(record.get("source_hash"), str) and SHA256_RE.fullmatch(record["source_hash"]) is not None, f"malformed source hash for {string_id}")
        targets = record.get("targets")
        _require(isinstance(targets, dict), f"targets missing for {string_id}")
        for locale in ("zh-Hans", "zh-TW"):
            target = targets.get(locale)
            _require(isinstance(target, dict) and isinstance(target.get("text"), str), f"{locale} target missing for {string_id}")
        status = record.get("status")
        _require(status in LEDGER_STATUSES, f"invalid status for {string_id}")
        statuses[str(status)] += 1
    _require(required_ids.issubset(seen), "required ledger string_id is missing")
    return {
        "ledger_records": len(ledger_rows),
        "string_ids": sorted(seen),
        "status_counts": dict(sorted(statuses.items())),
    }


def _make_core_source_adapter(source_rows: Iterable[dict[str, Any]], path: pathlib.Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in source_rows:
            handle.write(
                json.dumps(
                    {
                        "string_id": row["string_id"],
                        "locale": row["locale"],
                        "text": row["source_text"],
                        "provenance": "B3CJ local extractor adapter; source remains temporary",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )


def _verify_core_roundtrip(ledger_path: pathlib.Path, source_rows: list[dict[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="b3cj-ledger-") as temporary:
        root = pathlib.Path(temporary)
        adapter = root / "source-adapter.jsonl"
        working = root / "working.jsonl"
        roundtrip = root / "roundtrip.jsonl"
        _make_core_source_adapter(source_rows, adapter)
        subprocess.run(["ruby", str(RESTORE), str(ledger_path), str(adapter), str(working)], check=True, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["ruby", str(STRIP), str(working), str(roundtrip)], check=True, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        original = _load_jsonl(ledger_path)
        rebuilt = _load_jsonl(roundtrip)
        _require(original == rebuilt, "restore -> strip ledger records are not byte-equivalent by JSON value")


def validate(ledger_path: pathlib.Path, source_path: pathlib.Path, required_ids: set[str] | None = None) -> dict[str, Any]:
    source_rows, source_by_id = _load_source_table(source_path)
    ledger_rows = _load_jsonl(ledger_path)
    shape = _validate_ledger_shape(ledger_rows, source_by_id, required_ids or set())
    _verify_core_roundtrip(ledger_path, source_rows)
    return {
        "validator_version": "m3-ledger-v1",
        "game": EXPECTED_GAME,
        "revision": EXPECTED_REVISION,
        "source_rows": len(source_rows),
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "restore_strip_roundtrip": "json_value_identical",
        **shape,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=pathlib.Path)
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("--require-id", action="append", default=[])
    parser.add_argument("--summary-output", type=pathlib.Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = validate(args.ledger, args.source, set(args.require_id))
        if args.summary_output is not None:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_LEDGER_OK "
            f"records={report['ledger_records']} source_rows={report['source_rows']} "
            f"roundtrip={report['restore_strip_roundtrip']} source_table_sha256={report['source_table_sha256']}"
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"validate_ledger.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
