#!/usr/bin/env python3
"""Locate dense regions of strict NUL-terminated Shift-JIS candidates.

This scanner records only counts and byte ranges. It is a way to choose a
bounded extraction window; it does not declare every candidate a game string.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from extract_sjis_strings import extract  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--bucket", type=lambda value: int(value, 0), default=0x1000)
    parser.add_argument("--minimum-bytes", type=int, default=4)
    parser.add_argument("--maximum-bytes", type=int, default=512)
    parser.add_argument("--minimum-script-ratio", type=float, default=0.75)
    parser.add_argument("--top", type=int, default=80)
    args = parser.parse_args()

    data = args.rom.read_bytes()
    buckets = defaultdict(lambda: {"strings": 0, "bytes": 0, "japanese": 0})
    for offset, raw, text in extract(
        data,
        0,
        len(data),
        args.minimum_bytes,
        args.maximum_bytes,
        args.minimum_script_ratio,
    ):
        bucket = offset // args.bucket * args.bucket
        buckets[bucket]["strings"] += 1
        buckets[bucket]["bytes"] += len(raw)
        buckets[bucket]["japanese"] += sum(
            0x3040 <= ord(char) <= 0x30FF or 0x3400 <= ord(char) <= 0x9FFF
            for char in text
        )

    rows = [
        [
            bucket,
            values["strings"],
            values["bytes"],
            values["japanese"],
        ]
        for bucket, values in buckets.items()
    ]
    rows.sort(key=lambda row: (-row[1], -row[2], row[0]))
    print(
        f"buckets={len(rows)} bucket_size=0x{args.bucket:x} "
        f"candidate_count={sum(row[1] for row in rows)}"
    )
    for bucket, strings, byte_count, japanese in rows[: args.top]:
        print(
            f"0x{bucket:06x}-0x{bucket + args.bucket:06x} "
            f"strings={strings} candidate_bytes={byte_count} "
            f"japanese_chars={japanese}"
        )


if __name__ == "__main__":
    main()
