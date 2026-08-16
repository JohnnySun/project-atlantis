#!/usr/bin/env python3
"""Strict local-only Shift-JIS/NUL string extractor for B3TJ.

This is intentionally narrower than ``recon_rom.py``.  It only examines
explicit, hand-reviewed data windows where the first pass found plausible
NUL-terminated text.  A record must start at a NUL boundary (or the beginning
of a declared window), contain only decodable Shift-JIS/ASCII/control units,
and end at a NUL terminator.  Invalid bytes, unterminated runs and
ASCII-only runs are rejected rather than being emitted as source text.

The output is a *local source table* for the ledger workflow.  It contains
Japanese source text and is therefore expected to be written to the ignored
``research/*-decoded.jsonl`` path; it must not be committed.  The default
stdout output is a summary only and never prints decoded source text.

No pointer, control-code or font semantics are inferred here.  Low control
bytes are preserved as ``{HH}``, and LF (0x0A) is kept as a newline so a future
renderer can distinguish bytes without losing them.
"""

from __future__ import annotations

import argparse
import binascii
import json
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
DECODER_VERSION = "tow-nd3-sjis-nul-v1"


@dataclass(frozen=True)
class RangeSpec:
    name: str
    start: int
    end: int


DEFAULT_RANGES = (
    RangeSpec("kana-and-names", 0x100000, 0x103000),
    RangeSpec("names-and-ui", 0x105000, 0x10D400),
    RangeSpec("battle-and-enemy-tables", 0x111000, 0x114000),
    RangeSpec("text-pool", 0x140000, 0x1C4000),
    RangeSpec("list-data-provisional", 0x1C8000, 0x1CC000),
)


@dataclass
class ParsedString:
    region: str
    start: int
    end: int
    raw_length: int
    units: int
    double_byte_units: int
    halfwidth_units: int
    ascii_units: int
    newline_units: int
    control_units: int
    text: str
    pointer_refs: int = 0

    @property
    def quality(self) -> str:
        if self.pointer_refs or self.newline_units or self.control_units:
            return "high"
        if self.region == "text-pool" and self.double_byte_units >= 2:
            return "high"
        return "candidate"


def sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def sjis_trail(value: int) -> bool:
    return (0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC) and value != 0x7F


def _decode_pair(first: int, second: int) -> str | None:
    if not sjis_lead(first) or not sjis_trail(second):
        return None
    try:
        decoded = bytes((first, second)).decode("shift_jis")
    except UnicodeDecodeError:
        return None
    return decoded if decoded else None


def parse_nul_string(
    data: bytes, start: int, limit: int, region: str, max_raw_bytes: int = 512
) -> ParsedString | None:
    """Parse one strict NUL-terminated record, returning None on any ambiguity."""

    i = start
    tokens: list[str] = []
    units = 0
    double_byte_units = 0
    halfwidth_units = 0
    ascii_units = 0
    newline_units = 0
    control_units = 0

    while i < limit and i - start <= max_raw_bytes:
        value = data[i]
        if value == 0x00:
            if units < 2:
                return None
            if double_byte_units == 0 and halfwidth_units < 3:
                return None
            return ParsedString(
                region=region,
                start=start,
                end=i,
                raw_length=i - start,
                units=units,
                double_byte_units=double_byte_units,
                halfwidth_units=halfwidth_units,
                ascii_units=ascii_units,
                newline_units=newline_units,
                control_units=control_units,
                text="".join(tokens),
            )

        if value == 0xFF:
            return None

        if value == 0x0A:
            tokens.append("\n")
            newline_units += 1
            units += 1
            i += 1
            continue

        if 0x01 <= value <= 0x1F:
            tokens.append(f"{{{value:02X}}}")
            control_units += 1
            units += 1
            i += 1
            continue

        if 0x20 <= value <= 0x7E:
            tokens.append(chr(value))
            ascii_units += 1
            units += 1
            i += 1
            continue

        if 0xA1 <= value <= 0xDF:
            try:
                decoded = bytes((value,)).decode("shift_jis")
            except UnicodeDecodeError:
                return None
            tokens.append(decoded)
            halfwidth_units += 1
            units += 1
            i += 1
            continue

        if sjis_lead(value) and i + 1 < limit:
            decoded = _decode_pair(value, data[i + 1])
            if decoded is None:
                return None
            tokens.append(decoded)
            double_byte_units += 1
            units += 1
            i += 2
            continue

        # Bytes outside the strict Shift-JIS/ASCII/control grammar are not
        # guessed as a private codepage.  That is a future, separately
        # evidenced decoder boundary.
        return None

    # No terminator inside the declared window/record bound.
    return None


def iter_parsed_strings(
    data: bytes, ranges: Iterable[RangeSpec] = DEFAULT_RANGES
) -> Iterator[ParsedString]:
    """Yield only boundary-aligned, strictly parsed records in declared ranges."""

    for spec in ranges:
        if spec.start < 0 or spec.end > len(data) or spec.start >= spec.end:
            raise ValueError(f"invalid range {spec}")
        i = spec.start
        while i < spec.end:
            if data[i] == 0x00:
                i += 1
                continue
            if i != spec.start and data[i - 1] != 0x00:
                i += 1
                continue
            parsed = parse_nul_string(data, i, spec.end, spec.name)
            if parsed is None:
                i += 1
                continue
            yield parsed
            i = parsed.end + 1


def pointer_reference_counts(data: bytes, starts: set[int]) -> Counter[int]:
    """Count aligned absolute GBA pointers to candidate starts.

    The alignment restriction is deliberate: it is a reproducible signal,
    not a claim that all game references are aligned or direct.
    """

    counts: Counter[int] = Counter()
    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if ROM_BASE <= value < ROM_BASE + len(data):
            target = value - ROM_BASE
            if target in starts:
                counts[target] += 1
    return counts


def strict_records(
    data: bytes, ranges: Iterable[RangeSpec] = DEFAULT_RANGES
) -> list[ParsedString]:
    parsed = list(iter_parsed_strings(data, ranges))
    refs = pointer_reference_counts(data, {row.start for row in parsed})
    for row in parsed:
        row.pointer_refs = refs.get(row.start, 0)
    return parsed


def record_json(row: ParsedString) -> dict[str, object]:
    return {
        "string_id": f"sjis:0x{row.start:06X}",
        "locale": "ja",
        "text": row.text,
        "provenance": (
            "TOWND3-B3TJ-rev00; strict Shift-JIS + NUL extraction; "
            f"ROM file offset 0x{row.start:06X}"
        ),
        "decoder_version": DECODER_VERSION,
        "region": row.region,
        "quality": row.quality,
        "raw_length": row.raw_length,
        "pointer_refs_aligned": row.pointer_refs,
    }


def summary(records: Iterable[ParsedString]) -> dict[str, object]:
    rows = list(records)
    by_region = Counter(row.region for row in rows)
    by_quality = Counter(row.quality for row in rows)
    return {
        "decoder_version": DECODER_VERSION,
        "mode": "strict-boundary-sjis-nul",
        "record_count": len(rows),
        "quality_counts": dict(sorted(by_quality.items())),
        "region_counts": dict(sorted(by_region.items())),
        "offsets": {
            "first": min((row.start for row in rows), default=None),
            "last": max((row.start for row in rows), default=None),
        },
    }


def verify_b3tj(data: bytes) -> None:
    crc32 = binascii.crc32(data) & 0xFFFFFFFF
    title = data[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = data[0xAC:0xB0]
    maker_code = data[0xB0:0xB2]
    if (
        len(data) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != b"TOWNARIKIRI3"
        or game_code != b"B3TJ"
        or maker_code != b"AF"
    ):
        raise ValueError(
            "ROM identity mismatch; expected B3TJ/TOWNARIKIRI3/AF/16MiB/CRC32 "
            f"{EXPECTED_CRC32:08X}, got size={len(data)} crc32={crc32:08X}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--out",
        type=Path,
        help="ignored local source-table JSONL, normally research/*-decoded.jsonl",
    )
    parser.add_argument(
        "--skip-identity-check",
        action="store_true",
        help="only for synthetic tests; never use for B3TJ research output",
    )
    args = parser.parse_args()

    data = args.rom.read_bytes()
    if not args.skip_identity_check:
        verify_b3tj(data)
    records = strict_records(data)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            for row in records:
                handle.write(json.dumps(record_json(row), ensure_ascii=False) + "\n")

    result = summary(records)
    result["rom"] = str(args.rom)
    result["output"] = str(args.out) if args.out else None
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
