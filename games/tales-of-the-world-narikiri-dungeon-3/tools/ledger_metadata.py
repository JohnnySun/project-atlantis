#!/usr/bin/env python3
"""Build and verify a source-separated B3TJ localization ledger.

The input is the ignored local source table produced by ``extract_strings.py``.
The committed output contains only stable IDs, source hashes, structural
metadata, and empty translation targets.  It never copies ``source.text``.

This tool deliberately does not call a Shift-JIS decoder itself.  The decoder
version and source hashes come from the local source table, so a changed
decoder or a moved record is detected by ``--verify`` instead of silently
re-pairing a translation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator


GAME = "tales-of-the-world-narikiri-dungeon-3"
REVISION = "B3TJ-rev00"
STRING_ID_RE = re.compile(r"^sjis:0x[0-9A-F]{6}$")
CONTROL_RE = re.compile(r"\{([0-9A-F]{2})\}|%([0-9A-Za-z]+)")
DECODER_VERSION = "tow-nd3-sjis-nul-v1"


class LedgerError(ValueError):
    """Raised when the local source table cannot safely form a ledger."""


def source_hash(text: str) -> str:
    """Match ``core/ledger/ledger_codec.rb``'s canonical source hash."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterator[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise LedgerError(f"{path}:{line_number}: record is not an object")
            yield value


def _required_string(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise LedgerError(f"record {record.get('string_id')!r}: {key} is required")
    return value


def _record_controls(text: str) -> Counter[str]:
    controls: Counter[str] = Counter()
    for match in CONTROL_RE.finditer(text):
        controls[match.group(0)] += 1
    return controls


def _source_record_metadata(record: dict[str, object]) -> tuple[str, str, dict[str, object]]:
    string_id = _required_string(record, "string_id")
    if not STRING_ID_RE.fullmatch(string_id):
        raise LedgerError(f"record {string_id!r}: unstable string_id format")
    if record.get("locale") != "ja":
        raise LedgerError(f"record {string_id}: source locale is not ja")
    text = record.get("text")
    if not isinstance(text, str):
        raise LedgerError(f"record {string_id}: source text is missing")
    decoder_version = _required_string(record, "decoder_version")
    region = _required_string(record, "region")
    raw_length = record.get("raw_length")
    if not isinstance(raw_length, int) or raw_length < 1:
        raise LedgerError(f"record {string_id}: invalid raw_length")

    controls = _record_controls(text)
    return string_id, decoder_version, {
        "region": region,
        "raw_length": raw_length,
        "newline_count": text.count("\n"),
        "control_tokens": dict(sorted(controls.items())),
        "source_hash": source_hash(text),
    }


def ledger_record(
    source_record: dict[str, object], *, decoder_version: str
) -> tuple[dict[str, object], dict[str, object]]:
    """Return (safe ledger record, metadata-only row) for one source row."""

    string_id, row_decoder, metadata = _source_record_metadata(source_record)
    if row_decoder != decoder_version:
        raise LedgerError(
            f"record {string_id}: decoder version {row_decoder!r} differs from {decoder_version!r}"
        )
    controls = metadata["control_tokens"]
    assert isinstance(controls, dict)
    control_names = sorted(controls)
    safe = {
        "game": GAME,
        "revision": REVISION,
        "string_id": string_id,
        "source_locale": "ja",
        "source_hash": metadata["source_hash"],
        "decoder_version": decoder_version,
        "targets": {"zh-Hans": {"text": ""}, "zh-TW": {"text": ""}},
        "context": {
            "scene": str(metadata["region"]),
            "control_codes": control_names,
        },
        "terms": [],
        "status": "untranslated",
        "review_notes": (
            "Strict static candidate scaffold; source is local-only. "
            "Awaiting live text-consumer, codepage, glyph and capacity proof."
        ),
    }
    metadata_row = {
        "string_id": string_id,
        "region": metadata["region"],
        "raw_length": metadata["raw_length"],
        "newline_count": metadata["newline_count"],
        "control_tokens": controls,
        "source_hash": metadata["source_hash"],
    }
    return safe, metadata_row


def build_records(
    source_records: Iterable[dict[str, object]], *, decoder_version: str = DECODER_VERSION
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    ledger: list[dict[str, object]] = []
    metadata: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in source_records:
        safe, row = ledger_record(record, decoder_version=decoder_version)
        string_id = str(safe["string_id"])
        if string_id in seen:
            raise LedgerError(f"duplicate string_id {string_id}")
        seen.add(string_id)
        ledger.append(safe)
        metadata.append(row)
    if not ledger:
        raise LedgerError("source table has no records")
    return ledger, metadata


def summary(metadata: Iterable[dict[str, object]], decoder_version: str) -> dict[str, object]:
    rows = list(metadata)
    regions = Counter(str(row["region"]) for row in rows)
    controls: Counter[str] = Counter()
    newline_records = 0
    lengths = [int(row["raw_length"]) for row in rows]
    for row in rows:
        token_map = row["control_tokens"]
        assert isinstance(token_map, dict)
        controls.update({str(k): int(v) for k, v in token_map.items()})
        if int(row["newline_count"]) > 0:
            newline_records += 1
    return {
        "game": GAME,
        "revision": REVISION,
        "decoder_version": decoder_version,
        "record_count": len(rows),
        "region_counts": dict(sorted(regions.items())),
        "records_with_newline": newline_records,
        "control_token_counts": dict(sorted(controls.items())),
        "raw_length": {
            "min": min(lengths),
            "max": max(lengths),
            "total": sum(lengths),
        },
        "source_text_committed": False,
        "translation_targets_initialized": False,
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def verify_ledger(
    source_records: Iterable[dict[str, object]],
    ledger_records: Iterable[dict[str, object]],
    *,
    decoder_version: str = DECODER_VERSION,
) -> dict[str, object]:
    expected, metadata = build_records(source_records, decoder_version=decoder_version)
    actual = list(ledger_records)
    if actual != expected:
        if len(actual) != len(expected):
            raise LedgerError(f"ledger count {len(actual)} != source count {len(expected)}")
        for index, (want, got) in enumerate(zip(expected, actual)):
            if want != got:
                raise LedgerError(f"ledger mismatch at record index {index} ({want['string_id']})")
    for row in actual:
        if "source" in row:
            raise LedgerError(f"unsafe source field in {row.get('string_id')}")
    result = summary(metadata, decoder_version)
    result["ledger_matches_source_hashes"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_table", type=Path, help="ignored local decoded JSONL")
    parser.add_argument("--ledger-out", type=Path, required=True)
    parser.add_argument("--metadata-out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--decoder-version", default=DECODER_VERSION)
    args = parser.parse_args(argv)

    source_records = list(iter_jsonl(args.source_table))
    ledger, metadata = build_records(
        source_records, decoder_version=args.decoder_version
    )
    if args.verify:
        existing = list(iter_jsonl(args.ledger_out))
        result = verify_ledger(
            source_records, existing, decoder_version=args.decoder_version
        )
    else:
        write_jsonl(args.ledger_out, ledger)
        result = summary(metadata, args.decoder_version)
        result["ledger_matches_source_hashes"] = False
    write_jsonl(args.metadata_out, [result])
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LedgerError as exc:
        print(f"ledger_metadata: {exc}", file=sys.stderr)
        raise SystemExit(2)
