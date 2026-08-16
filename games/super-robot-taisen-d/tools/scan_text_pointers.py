#!/usr/bin/env python3
"""Find aligned absolute ROM pointers into a bounded Shift-JIS text bank.

The output is structural only (pointer locations and target ranges), so it
does not reproduce the source strings. Pointer clusters are hypotheses until
the surrounding code/data and target boundaries are checked.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct


def pointer_runs(data: bytes, low: int, high: int, minimum: int):
    refs = []
    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if low <= value < high:
            refs.append((offset, value))

    runs = []
    if not refs:
        return refs, runs
    start = 0
    for index in range(1, len(refs) + 1):
        split = index == len(refs) or refs[index][0] != refs[index - 1][0] + 4
        if not split:
            continue
        group = refs[start:index]
        if len(group) >= minimum:
            runs.append(
                (
                    group[0][0],
                    len(group),
                    min(value for _, value in group),
                    max(value for _, value in group),
                    all(group[n][1] <= group[n + 1][1] for n in range(len(group) - 1)),
                )
            )
        start = index
    return refs, sorted(runs, key=lambda row: (-row[1], row[0]))


def source_offsets(path: pathlib.Path) -> set[int]:
    offsets = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                offsets.add(int(json.loads(line)["string_id"]))
    return offsets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--target-start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--target-end", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--minimum-run", type=int, default=4)
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--source-table", type=pathlib.Path)
    args = parser.parse_args()

    data = args.rom.read_bytes()
    refs, runs = pointer_runs(data, 0x08000000 + args.target_start, 0x08000000 + args.target_end, args.minimum_run)
    exact = source_offsets(args.source_table) if args.source_table else set()
    exact_refs = sum((value - 0x08000000) in exact for _, value in refs)
    print(
        f"target=file 0x{args.target_start:06x}..0x{args.target_end:06x} "
        f"absolute=0x{0x08000000 + args.target_start:08x}..0x{0x08000000 + args.target_end:08x} "
        f"aligned_refs={len(refs)} clusters={len(runs)}"
        + (f" exact_source_offsets={exact_refs}" if args.source_table else "")
    )
    for offset, length, low, high, ascending in runs[: args.top]:
        print(
            f"  ref=0x{offset:06x} words={length} "
            f"targets=0x{low - 0x08000000:06x}..0x{high - 0x08000000:06x} "
            f"ascending={ascending}"
        )


if __name__ == "__main__":
    main()
