#!/usr/bin/env python3
"""Probe A9PJ's suspected 16-bit text-pointer regions without exporting text.

The clean ROM contains many little-endian GBA ROM pointers into a dense data
region.  This tool reports pointer geometry and aggregate NUL-terminated
halfword statistics only.  It deliberately never prints code-unit sequences or
decoded source text, so its stdout can be committed as an audit result without
becoming a source-text dump.
"""

from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
from pathlib import Path


ROM_BASE = 0x08000000
DEFAULT_TARGET_START = 0x1F0000
DEFAULT_TARGET_END = 0x2C0000


def format_offset(value: int) -> str:
    return f"0x{value:x}"


def find_references(
    data: bytes,
    scan_start: int,
    scan_end: int,
    target_start: int,
    target_end: int,
    alignment: int,
) -> list[tuple[int, int]]:
    references: list[tuple[int, int]] = []
    upper = min(scan_end, len(data) - 3)
    for offset in range(scan_start, upper, alignment):
        value = struct.unpack_from("<I", data, offset)[0]
        target = value - ROM_BASE
        if target_start <= target < target_end:
            references.append((offset, target))
    return references


def summarize_runs(
    references: list[tuple[int, int]], alignment: int, limit: int = 32
) -> list[dict[str, object]]:
    runs: list[list[tuple[int, int]]] = []
    for reference in references:
        if not runs or reference[0] != runs[-1][-1][0] + alignment:
            runs.append([reference])
        else:
            runs[-1].append(reference)
    runs.sort(key=lambda run: (-len(run), run[0][0]))
    return [
        {
            "file_range": [
                format_offset(run[0][0]),
                format_offset(run[-1][0] + 4),
            ],
            "reference_count": len(run),
            "target_range": [
                format_offset(min(target for _, target in run)),
                format_offset(max(target for _, target in run) + 1),
            ],
            "target_monotonic_non_decreasing": all(
                run[index][1] <= run[index + 1][1]
                for index in range(len(run) - 1)
            ),
        }
        for run in runs[:limit]
    ]


def read_code_units(
    data: bytes, target: int, max_units: int
) -> tuple[int, bool, set[int]]:
    """Return (non-NUL units, terminated, distinct units) for one target."""

    position = target
    distinct: set[int] = set()
    for length in range(max_units):
        if position + 2 > len(data):
            return length, False, distinct
        code_unit = int.from_bytes(data[position : position + 2], "little")
        if code_unit == 0:
            return length, True, distinct
        distinct.add(code_unit)
        position += 2
    return max_units, False, distinct


def code_unit_profile(
    data: bytes, references: list[tuple[int, int]], max_units: int
) -> dict[str, object]:
    unique_targets = sorted({target for _, target in references})
    lengths: list[int] = []
    terminated = 0
    distinct_units: set[int] = set()
    length_buckets: collections.Counter[str] = collections.Counter()
    for target in unique_targets:
        length, has_terminator, units = read_code_units(data, target, max_units)
        lengths.append(length)
        terminated += int(has_terminator)
        distinct_units.update(units)
        if length < 8:
            bucket = "0-7"
        elif length < 16:
            bucket = "8-15"
        elif length < 32:
            bucket = "16-31"
        elif length < 64:
            bucket = "32-63"
        elif length < 128:
            bucket = "64-127"
        else:
            bucket = "128+"
        length_buckets[bucket] += 1

    return {
        "unique_targets_profiled": len(unique_targets),
        "nul_terminated_targets": terminated,
        "unterminated_or_capped_targets": len(unique_targets) - terminated,
        "length_buckets": dict(sorted(length_buckets.items())),
        "maximum_observed_code_unit": format_offset(max(distinct_units))
        if distinct_units
        else None,
        "distinct_nonzero_code_units": len(distinct_units),
        "max_units_per_target": max_units,
    }


def changed_pointer_summary(
    clean: bytes,
    patched: bytes,
    references: list[tuple[int, int]],
    target_start: int,
    target_end: int,
) -> dict[str, object]:
    changed: list[tuple[int, int, int]] = []
    for file_offset, old_target in references:
        if file_offset + 4 > len(patched):
            continue
        old_value = struct.unpack_from("<I", clean, file_offset)[0]
        new_value = struct.unpack_from("<I", patched, file_offset)[0]
        new_target = new_value - ROM_BASE
        if old_value != new_value:
            changed.append((file_offset, old_target, new_target))
    return {
        "changed_references_in_scan": len(changed),
        "changed_new_target_range": [
            format_offset(min(target for _, _, target in changed)),
            format_offset(max(target for _, _, target in changed) + 1),
        ]
        if changed
        else None,
        "note": "This optional comparison is for engineering corroboration; it does not identify text by itself.",
    }


def probe(args: argparse.Namespace) -> dict[str, object]:
    data = args.rom.read_bytes()
    scan_end = min(args.scan_end, len(data))
    references = find_references(
        data,
        args.scan_start,
        scan_end,
        args.target_start,
        args.target_end,
        args.alignment,
    )
    result: dict[str, object] = {
        "rom_path": str(args.rom),
        "scan": {
            "file_range": [format_offset(args.scan_start), format_offset(scan_end)],
            "alignment": args.alignment,
            "target_file_range": [
                format_offset(args.target_start),
                format_offset(args.target_end),
            ],
        },
        "pointer_references": len(references),
        "distinct_pointer_targets": len({target for _, target in references}),
        "reference_runs": summarize_runs(references, args.alignment),
        "code_unit_profile": code_unit_profile(data, references, args.max_units),
    }
    if args.patched_rom:
        result["optional_patch_comparison"] = changed_pointer_summary(
            data,
            args.patched_rom.read_bytes(),
            references,
            args.target_start,
            args.target_end,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--patched-rom", type=Path)
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--scan-end", type=lambda value: int(value, 0), default=0x800000)
    parser.add_argument(
        "--target-start", type=lambda value: int(value, 0), default=DEFAULT_TARGET_START
    )
    parser.add_argument(
        "--target-end", type=lambda value: int(value, 0), default=DEFAULT_TARGET_END
    )
    parser.add_argument("--alignment", type=int, default=4)
    parser.add_argument("--max-units", type=int, default=0x400)
    args = parser.parse_args()
    json.dump(probe(args), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
