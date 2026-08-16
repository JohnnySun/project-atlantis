#!/usr/bin/env python3
"""Extract clean A9HJ script-pointer records for local research only.

This is deliberately a byte/token extractor, not a translation decoder.  It
follows the three-level pointer selection used by the text initializer:

    ROM[0x08266240 + state[0] * 4]
      -> table[state[1]]
      -> table[state_u16_2]

The parser evidence currently proves 0x92/0x93 lead bytes consume a second
byte through the glyph combiner, and 0xE0/0xE1 consume one parameter byte for
the alternate glyph pool.  Other bytes are kept as single-byte tokens or
control candidates; their semantic names are not guessed here.  Output
contains source-bearing raw hex and must remain under an ignored local path
(`research/*-decoded.jsonl` or a private temporary directory).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Iterable


ROM_SIZE = 0x800000
ROM_BASE = 0x08000000
ROM_LIMIT = ROM_BASE + ROM_SIZE
POINTER_TABLE = 0x08266240
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
PAIR_LEADS = {0x92, 0x93}
ALT_GLYPH_LEADS = {0xE0, 0xE1}
CONTROL_MIN = 0xDF
DEFAULT_MAX_SPAN = 0x10000


def cpu_to_file(address: int) -> int:
    if not ROM_BASE <= address < ROM_LIMIT:
        raise ValueError(f"ROM pointer outside clean address window: 0x{address:08X}")
    return address - ROM_BASE


def read_u32(data: bytes, cpu_address: int) -> int:
    offset = cpu_to_file(cpu_address)
    return struct.unpack_from("<I", data, offset)[0]


def pointer_run(data: bytes, cpu_address: int, limit: int = 0x1000) -> list[int]:
    """Read a contiguous ROM-pointer table until its first non-pointer word."""

    values: list[int] = []
    for index in range(limit):
        try:
            value = read_u32(data, cpu_address + index * 4)
        except (struct.error, ValueError):
            break
        if not ROM_BASE <= value < ROM_LIMIT:
            break
        values.append(value)
    return values


def validate_rom(data: bytes) -> dict[str, str | int]:
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(
            "refusing non-clean A9HJ ROM: "
            f"CRC32={crc32:08X}, SHA256={sha256}"
        )
    return {"size": len(data), "crc32": f"{crc32:08X}", "sha256": sha256}


def tokenise(data: bytes, start: int, end: int) -> tuple[list[dict[str, object]], bool]:
    tokens: list[dict[str, object]] = []
    offset = start
    truncated_pair = False
    while offset < end:
        value = data[offset]
        if value in PAIR_LEADS:
            if offset + 1 >= end:
                truncated_pair = True
                tokens.append({"kind": "pair-truncated", "offset": offset - start, "lead": value})
                break
            tokens.append(
                {
                    "kind": "pair",
                    "offset": offset - start,
                    "lead": value,
                    "trail": data[offset + 1],
                }
            )
            offset += 2
        elif value in ALT_GLYPH_LEADS:
            if offset + 1 >= end:
                truncated_pair = True
                tokens.append({"kind": "alt-glyph-truncated", "offset": offset - start, "lead": value})
                break
            tokens.append(
                {
                    "kind": "alt-glyph",
                    "offset": offset - start,
                    "lead": value,
                    "value": data[offset + 1],
                }
            )
            offset += 2
        elif value >= CONTROL_MIN:
            tokens.append({"kind": "control-candidate", "offset": offset - start, "value": value})
            offset += 1
        else:
            tokens.append({"kind": "single-byte-candidate", "offset": offset - start, "value": value})
            offset += 1
    return tokens, truncated_pair


def next_greater(values: Iterable[int], current: int) -> int | None:
    greater = [value for value in values if value > current]
    return min(greater) if greater else None


def collect_pointer_tables(data: bytes) -> list[dict[str, object]]:
    """Collect (state[0], state[1], state_u16[2]) pointer records."""

    top = pointer_run(data, POINTER_TABLE)
    records: list[dict[str, object]] = []
    for group, second_table in enumerate(top):
        second = pointer_run(data, second_table)
        for variant, third_table in enumerate(second):
            message_pointers = pointer_run(data, third_table)
            for message_index, pointer in enumerate(message_pointers):
                records.append(
                    {
                        "group": group,
                        "variant": variant,
                        "message_index": message_index,
                        "second_table": second_table,
                        "third_table": third_table,
                        "pointer": pointer,
                    }
                )
    return records


def enrich_records(data: bytes, records: list[dict[str, object]], max_span: int) -> list[dict[str, object]]:
    all_pointers = [int(record["pointer"]) for record in records]
    by_table: dict[int, list[int]] = {}
    for record in records:
        by_table.setdefault(int(record["third_table"]), []).append(int(record["pointer"]))

    enriched: list[dict[str, object]] = []
    for record in records:
        pointer = int(record["pointer"])
        start = cpu_to_file(pointer)
        table_pointers = by_table[int(record["third_table"])]
        next_pointer = next_greater(table_pointers, pointer)
        boundary = "next-pointer-in-table"
        if next_pointer is None:
            next_pointer = next_greater(all_pointers, pointer)
            boundary = "next-pointer-global-candidate" if next_pointer is not None else "max-span"
        candidate_end = cpu_to_file(next_pointer) if next_pointer is not None else len(data)
        end = min(len(data), start + max_span, candidate_end)
        tokens, truncated_pair = tokenise(data, start, end)
        raw = data[start:end]
        enriched.append(
            {
                "schema": "dqmch-clean-script-bytes-v1",
                "rom_sha256": EXPECTED_SHA256,
                "group": record["group"],
                "variant": record["variant"],
                "message_index": record["message_index"],
                "second_table": f"0x{int(record['second_table']):08X}",
                "third_table": f"0x{int(record['third_table']):08X}",
                "pointer_cpu": f"0x{pointer:08X}",
                "pointer_file": f"0x{start:06X}",
                "span_end_file": f"0x{end:06X}",
                "boundary": boundary,
                "raw_hex": raw.hex(),
                "tokens": tokens,
                "pair_count": sum(token["kind"] == "pair" for token in tokens),
                "alt_glyph_count": sum(token["kind"] == "alt-glyph" for token in tokens),
                "control_values": [token["value"] for token in tokens if token["kind"] == "control-candidate"],
                "truncated_pair": truncated_pair,
            }
        )
    return enriched


def summary(records: list[dict[str, object]]) -> dict[str, object]:
    pointers = {record["pointer_cpu"] for record in records}
    pairs = sum(int(record["pair_count"]) for record in records)
    alt_glyphs = sum(int(record.get("alt_glyph_count", 0)) for record in records)
    controls = sum(len(record["control_values"]) for record in records)
    return {
        "records": len(records),
        "unique_pointers": len(pointers),
        "pair_tokens": pairs,
        "alt_glyph_tokens": alt_glyphs,
        "control_candidates": controls,
        "groups": sorted({record["group"] for record in records}),
        "variants": len({(record["group"], record["variant"]) for record in records}),
        "truncated_pairs": sum(bool(record["truncated_pair"]) for record in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="ignored local JSONL output")
    parser.add_argument("--max-span", type=lambda value: int(value, 0), default=DEFAULT_MAX_SPAN)
    args = parser.parse_args()

    try:
        data = args.rom.read_bytes()
        identity = validate_rom(data)
        raw_records = collect_pointer_tables(data)
        records = enrich_records(data, raw_records, args.max_span)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, ValueError, struct.error) as error:
        print(f"extract_text: {error}", file=sys.stderr)
        return 2

    print("rom", identity)
    print("pointer-table", f"0x{POINTER_TABLE:08X}")
    print("summary", summary(records))
    print("output", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
