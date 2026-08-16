#!/usr/bin/env python3
"""Verify a local Shift-JIS source table against the clean ROM.

The source table is intentionally kept under ``research/`` and ignored by
Git. This checker proves that each local record still points at the bytes it
claims to represent without printing the source text or creating a tracked
artifact.
"""

from __future__ import annotations

import argparse
import json
import pathlib


def read_source_table(path: pathlib.Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON: {exc}") from exc
            yield line_number, record


def decode_at(data: bytes, offset: int) -> tuple[str, int]:
    if offset < 0 or offset >= len(data):
        raise ValueError("offset is outside the ROM")
    terminator = data.find(b"\x00", offset)
    if terminator < 0:
        raise ValueError("missing NUL terminator")
    payload = data[offset:terminator]
    try:
        text = payload.decode("shift_jis", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid strict Shift-JIS bytes: {exc}") from exc
    return text, terminator - offset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("source_table", type=pathlib.Path)
    parser.add_argument("--start", type=lambda value: int(value, 0))
    parser.add_argument("--end", type=lambda value: int(value, 0))
    parser.add_argument("--expected-count", type=int)
    parser.add_argument("--max-errors", type=int, default=8)
    args = parser.parse_args()

    data = args.rom.read_bytes()
    records = list(read_source_table(args.source_table))
    if args.expected_count is not None and len(records) != args.expected_count:
        raise SystemExit(
            f"expected {args.expected_count} records, found {len(records)}"
        )

    seen: set[int] = set()
    errors: list[str] = []
    verified = 0
    for line_number, record in records:
        try:
            offset = int(record["string_id"])
            if offset in seen:
                raise ValueError("duplicate string_id")
            seen.add(offset)
            if record.get("locale") != "ja":
                raise ValueError("locale is not ja")
            expected = record["text"]
            if not isinstance(expected, str):
                raise ValueError("text is not a string")
            if args.start is not None and offset < args.start:
                raise ValueError("offset is before --start")
            if args.end is not None and offset >= args.end:
                raise ValueError("offset is at or after --end")
            actual, _ = decode_at(data, offset)
            if actual != expected:
                raise ValueError("decoded text differs from source record")
            verified += 1
        except (KeyError, TypeError, ValueError) as exc:
            if len(errors) < args.max_errors:
                errors.append(f"line {line_number}: {exc}")

    if errors:
        for error in errors:
            print(f"ERROR {error}")
        raise SystemExit(f"verification failed: {len(errors)} error(s) shown")

    bounds = ""
    if args.start is not None or args.end is not None:
        bounds = f" range=0x{args.start or 0:06x}..0x{args.end or len(data):06x}"
    print(
        f"source_records={len(records)} verified={verified}"
        f" rom_bytes={len(data)}{bounds}"
    )


if __name__ == "__main__":
    main()
