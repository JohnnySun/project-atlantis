#!/usr/bin/env python3
"""Classify B3TJ string-record references without emitting source text.

The strict extractor supplies candidate record boundaries.  This tool then
cross-references those boundaries against:

* direct absolute 32-bit GBA pointers (any byte alignment);
* exact 16/24/32-bit file-relative values; and
* provisional self-relative 16/32-bit values, where the pointer location or
  the byte after the word is the inferred base.

Only direct absolute references are promoted to ``confirmed``.  Relative
matches are reported as ``provisional`` because a relocation base cannot be
proven from bytes alone.  Adjacent direct pointers are grouped into a table
span so a runtime probe can watch a concrete record instead of a whole data
window.  Output contains offsets and counts, never decoded source text.
"""

from __future__ import annotations

import argparse
import binascii
import json
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import (  # noqa: E402
    DEFAULT_RANGES,
    ROM_BASE,
    EXPECTED_CRC32,
    EXPECTED_SIZE,
    ParsedString,
    strict_records,
)


@dataclass(frozen=True)
class Reference:
    kind: str
    location: int
    base: int | None = None


def verify_b3tj(data: bytes) -> None:
    if len(data) != EXPECTED_SIZE or (binascii.crc32(data) & 0xFFFFFFFF) != EXPECTED_CRC32:
        raise ValueError("ROM identity mismatch; expected B3TJ CRC32 1867CCEF")


def scan_references(
    data: bytes, records: list[ParsedString]
) -> dict[int, list[Reference]]:
    starts = {row.start for row in records}
    refs: dict[int, list[Reference]] = defaultdict(list)

    for location in range(0, len(data) - 3):
        word = struct.unpack_from("<I", data, location)[0]
        direct_absolute = False
        if ROM_BASE <= word < ROM_BASE + len(data):
            target = word - ROM_BASE
            if target in starts:
                refs[target].append(Reference("absolute32", location))
                direct_absolute = True

        # The low 24/16 bits of a direct GBA pointer naturally equal its file
        # offset.  Do not count those overlapping bytes as an independent
        # relative encoding.
        if not direct_absolute and location + 3 <= len(data):
            rel24 = int.from_bytes(data[location : location + 3], "little")
            if rel24 in starts:
                refs[rel24].append(Reference("relative24-exact", location))

        halfword = struct.unpack_from("<H", data, location)[0]
        if not direct_absolute and halfword in starts:
            refs[halfword].append(Reference("relative16-exact", location))

        if 0 < word < len(data):
            for base in (location, location + 4):
                target = base + word
                if target in starts:
                    refs[target].append(Reference("relative32-self", location, base))

        if 0 < halfword < len(data):
            for base in (location, location + 2):
                target = base + halfword
                if target in starts:
                    refs[target].append(Reference("relative16-self", location, base))

    return refs


def absolute_table_span(
    data: bytes, location: int, records_by_start: dict[int, ParsedString]
) -> dict[str, object]:
    """Return the contiguous aligned run of direct pointers around location."""

    if location % 4:
        return {"start": location, "end": location + 4, "words": 1}

    start = location
    while start >= 4:
        value = struct.unpack_from("<I", data, start - 4)[0]
        if value < ROM_BASE or value >= ROM_BASE + len(data):
            break
        if value - ROM_BASE not in records_by_start:
            break
        start -= 4

    end = location + 4
    while end + 4 <= len(data):
        value = struct.unpack_from("<I", data, end)[0]
        if value < ROM_BASE or value >= ROM_BASE + len(data):
            break
        if value - ROM_BASE not in records_by_start:
            break
        end += 4

    return {
        "start": start,
        "end": end,
        "words": (end - start) // 4,
        "targets": [
            struct.unpack_from("<I", data, offset)[0] - ROM_BASE
            for offset in range(start, end, 4)
        ],
    }


def build_report(data: bytes) -> dict[str, object]:
    records = strict_records(data, DEFAULT_RANGES)
    by_start = {row.start: row for row in records}
    refs = scan_references(data, records)
    rows: list[dict[str, object]] = []
    table_cache: dict[int, dict[str, object]] = {}

    for row in records:
        row_refs = refs.get(row.start, [])
        absolute = [ref for ref in row_refs if ref.kind == "absolute32"]
        relative = [ref for ref in row_refs if ref.kind != "absolute32"]
        tables = []
        for ref in absolute:
            table = table_cache.setdefault(
                ref.location, absolute_table_span(data, ref.location, by_start)
            )
            tables.append(table)
        if absolute:
            classification = "confirmed-absolute"
        elif relative:
            classification = "provisional-relative"
        else:
            classification = "unreferenced-by-tested-encodings"
        rows.append(
            {
                "string_id": f"sjis:0x{row.start:06X}",
                "region": row.region,
                "file_offset": f"0x{row.start:06X}",
                "raw_length": row.raw_length,
                "classification": classification,
                "absolute32": [
                    {"location": f"0x{ref.location:06X}"}
                    for ref in absolute[:16]
                ],
                "relative": [
                    {
                        "kind": ref.kind,
                        "location": f"0x{ref.location:06X}",
                        "base": None if ref.base is None else f"0x{ref.base:06X}",
                    }
                    for ref in relative[:16]
                ],
                "absolute_tables": [
                    {
                        "start": f"0x{int(table['start']):06X}",
                        "end": f"0x{int(table['end']):06X}",
                        "words": table["words"],
                    }
                    for table in tables[:4]
                ],
            }
        )

    region_summary: dict[str, dict[str, int]] = {}
    for row in rows:
        region = str(row["region"])
        summary = region_summary.setdefault(
            region,
            {"records": 0, "absolute_records": 0, "relative_records": 0},
        )
        summary["records"] += 1
        if row["classification"] == "confirmed-absolute":
            summary["absolute_records"] += 1
        elif row["classification"] == "provisional-relative":
            summary["relative_records"] += 1

    return {
        "mode": "absolute-and-relative-pointer-cross-classification",
        "rom_size": len(data),
        "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08X}",
        "tested_encodings": [
            "absolute32-any-alignment",
            "relative24-exact-file-offset",
            "relative16-exact-file-offset",
            "relative32-self-or-after-word",
            "relative16-self-or-after-halfword",
        ],
        "record_count": len(rows),
        "region_summary": region_summary,
        "confirmed_absolute_record_count": sum(
            row["classification"] == "confirmed-absolute" for row in rows
        ),
        "provisional_relative_record_count": sum(
            row["classification"] == "provisional-relative" for row in rows
        ),
        "records": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    data = args.rom.read_bytes()
    verify_b3tj(data)
    report = build_report(data)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2, sort_keys=True))
        print(f"wrote {args.out}")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
