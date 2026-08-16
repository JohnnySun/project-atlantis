#!/usr/bin/env python3
"""Probe a suspected ROM pointer table without exporting its payloads.

The first reconnaissance pass found a large monotonic table whose targets begin
immediately after the table and often look like GBA compressed-resource headers.
This tool validates that hypothesis at the byte level and reports only aggregate
statistics.  It intentionally does not write decoded assets or print their text.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROM_BASE = 0x08000000
SENTINELS = ("はい", "いいえ", "セーブ", "ロード", "戦闘", "出撃", "召喚", "名前")


def find_all(data: bytes, needle: bytes) -> int:
    count = 0
    start = 0
    while True:
        hit = data.find(needle, start)
        if hit < 0:
            return count
        count += 1
        start = hit + 1


def lz77(data: bytes, offset: int) -> tuple[bytes | None, int | None, str | None]:
    if offset + 4 > len(data) or data[offset] != 0x10:
        return None, None, "not-lz77"
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0:
        return None, None, "empty-output"
    position = offset + 4
    output = bytearray()
    try:
        while len(output) < size:
            flags = data[position]
            position += 1
            # GBA BIOS consumes the flag byte from bit 7 down to bit 0.
            for bit in range(7, -1, -1):
                if len(output) >= size:
                    break
                if flags & (1 << bit):
                    first = data[position]
                    second = data[position + 1]
                    position += 2
                    length = (first >> 4) + 3
                    displacement = ((first & 0x0F) << 8) | second
                    source = len(output) - displacement - 1
                    if source < 0:
                        return None, None, "backreference-before-output"
                    for _ in range(length):
                        output.append(output[source])
                        source += 1
                        if len(output) >= size:
                            break
                else:
                    output.append(data[position])
                    position += 1
    except IndexError:
        return None, None, "input-ended"
    return bytes(output), position, None


def rle(data: bytes, offset: int) -> tuple[bytes | None, int | None, str | None]:
    if offset + 4 > len(data) or data[offset] != 0x30:
        return None, None, "not-rle"
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0:
        return None, None, "empty-output"
    position = offset + 4
    output = bytearray()
    try:
        while len(output) < size:
            control = data[position]
            position += 1
            if control & 0x80:
                count = (control & 0x7F) + 3
                value = data[position]
                position += 1
                output.extend(bytes((value,)) * min(count, size - len(output)))
            else:
                count = (control & 0x7F) + 1
                output.extend(data[position : position + count])
                position += count
                if len(output) > size:
                    return None, None, "literal-overrun"
    except IndexError:
        return None, None, "input-ended"
    return bytes(output), position, None


def ascii_run_count(data: bytes, minimum: int = 8) -> int:
    count = 0
    run = 0
    for value in data + b"\0":
        if 0x20 <= value <= 0x7E:
            run += 1
        else:
            if run >= minimum:
                count += 1
            run = 0
    return count


def probe(path: Path, table_offset: int, count: int) -> dict[str, object]:
    data = path.read_bytes()
    pointers: list[int] = []
    for index in range(count):
        offset = table_offset + index * 4
        if offset + 4 > len(data):
            raise ValueError(f"pointer table exceeds ROM at entry {index}")
        value = int.from_bytes(data[offset : offset + 4], "little")
        if not ROM_BASE <= value < ROM_BASE + len(data):
            raise ValueError(f"entry {index} is not a ROM pointer: 0x{value:08x}")
        pointers.append(value - ROM_BASE)

    tag_counts: Counter[str] = Counter()
    compressed_results: Counter[str] = Counter()
    output_sizes: list[int] = []
    sentinel_hits: Counter[str] = Counter()
    ascii_runs = 0
    valid_payloads = 0
    examples: list[dict[str, object]] = []

    for index, target in enumerate(pointers):
        tag = data[target] if target < len(data) else None
        tag_name = {0x10: "lz77", 0x20: "huffman", 0x30: "rle"}.get(
            tag, f"0x{tag:02x}" if tag is not None else "out-of-range"
        )
        tag_counts[tag_name] += 1
        if tag not in (0x10, 0x30):
            continue

        decoded, end, error = lz77(data, target) if tag == 0x10 else rle(data, target)
        if error:
            compressed_results[error] += 1
            continue
        assert decoded is not None and end is not None
        valid_payloads += 1
        output_sizes.append(len(decoded))
        ascii_runs += ascii_run_count(decoded)
        for sentinel in SENTINELS:
            hits = find_all(decoded, sentinel.encode("shift_jis"))
            if hits:
                sentinel_hits[sentinel] += hits
        if len(examples) < 20:
            examples.append(
                {
                    "entry": index,
                    "target": f"0x{target:x}",
                    "tag": tag_name,
                    "declared_output_size": int.from_bytes(
                        data[target + 1 : target + 4], "little"
                    ),
                    "consumed_bytes": end - target,
                }
            )

    return {
        "rom_path": str(path),
        "table": {
            "file_offset": f"0x{table_offset:x}",
            "entry_count": count,
            "byte_length": count * 4,
            "target_file_range": [
                f"0x{min(pointers):x}",
                f"0x{max(pointers) + 1:x}",
            ],
            "target_monotonic_non_decreasing": all(
                left <= right for left, right in zip(pointers, pointers[1:])
            ),
            "distinct_targets": len(set(pointers)),
        },
        "target_tag_counts": dict(sorted(tag_counts.items())),
        "validated_lz77_or_rle_payloads": valid_payloads,
        "decoder_errors": dict(sorted(compressed_results.items())),
        "decoded_output_size_range": [min(output_sizes), max(output_sizes)]
        if output_sizes
        else None,
        "decoded_ascii_runs_at_least_8": ascii_runs,
        "decoded_shift_jis_sentinel_hits": dict(sorted(sentinel_hits.items())),
        "validated_payload_examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--table-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()
    json.dump(probe(args.rom, args.table_offset, args.count), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
