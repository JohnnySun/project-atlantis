#!/usr/bin/env python3
"""Count pointer rewrites made by a local engineering-reference patch.

This is deliberately a diff summary: it reports file buckets and pointer
target ranges, never the pointed-to source bytes.  The patch is an external
reference artifact and must stay outside the repository.
"""

from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
from pathlib import Path


ROM_BASE = 0x08000000


def fmt(value: int) -> str:
    return f"0x{value:x}"


def probe(
    clean_path: Path,
    patched_path: Path,
    old_end: int,
    new_start: int,
    new_end: int,
) -> dict[str, object]:
    clean = clean_path.read_bytes()
    patched = patched_path.read_bytes()
    limit = min(len(clean), len(patched)) - 3
    rewrites: list[tuple[int, int, int]] = []
    for offset in range(0, max(0, limit), 4):
        old_value = struct.unpack_from("<I", clean, offset)[0]
        new_value = struct.unpack_from("<I", patched, offset)[0]
        if (
            old_value != new_value
            and ROM_BASE <= old_value < old_end
            and new_start <= new_value < new_end
        ):
            rewrites.append((offset, old_value - ROM_BASE, new_value - ROM_BASE))

    bucket_counts: collections.Counter[str] = collections.Counter()
    for offset, _, _ in rewrites:
        bucket_counts[f"0x{offset // 0x100000:x}00000"] += 1

    return {
        "clean_rom": str(clean_path),
        "patched_rom": str(patched_path),
        "filter": {
            "old_pointer_range": [fmt(ROM_BASE), fmt(old_end)],
            "new_pointer_range": [fmt(new_start), fmt(new_end)],
            "word_alignment": 4,
        },
        "rewritten_pointer_count": len(rewrites),
        "source_file_bucket_counts": dict(sorted(bucket_counts.items())),
        "old_target_file_range": [
            fmt(min(old for _, old, _ in rewrites)),
            fmt(max(old for _, old, _ in rewrites) + 1),
        ]
        if rewrites
        else None,
        "new_target_file_range": [
            fmt(min(new for _, _, new in rewrites)),
            fmt(max(new for _, _, new in rewrites) + 1),
        ]
        if rewrites
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean_rom", type=Path)
    parser.add_argument("patched_rom", type=Path)
    parser.add_argument(
        "--old-end", type=lambda value: int(value, 0), default=0x08800000
    )
    parser.add_argument(
        "--new-start", type=lambda value: int(value, 0), default=0x08800000
    )
    parser.add_argument(
        "--new-end", type=lambda value: int(value, 0), default=0x09000000
    )
    args = parser.parse_args()
    json.dump(
        probe(args.clean_rom, args.patched_rom, args.old_end, args.new_start, args.new_end),
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
