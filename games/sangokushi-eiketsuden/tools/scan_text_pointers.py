#!/usr/bin/env python3
"""Summarize verified B3EJ pointer-table candidates without decoding text.

The report contains table offsets, counts, and ROM target ranges only.  It
never emits bytes from the original script and never modifies the ROM.  The
default tables are bounded candidates recorded in ``research/recon-ledger.md``;
use ``--table OFFSET:COUNT`` to inspect another explicitly reviewed range.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


ROM_BASE = 0x08000000
MAX_REPORTED_TARGETS = 16

DEFAULT_TABLES = (
    ("system_item_class_candidate", 0x0CBC54, 183),
    ("menu_battle_candidate_a", 0x0D1FFC, 44),
    ("menu_battle_candidate_b", 0x0D20D8, 4),
    ("event_system_candidate", 0x0D4D00, 28),
)


def parse_table_spec(spec: str) -> tuple[int, int]:
    try:
        offset_text, count_text = spec.split(":", 1)
        offset = int(offset_text, 0)
        count = int(count_text, 0)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"table must be OFFSET:COUNT, got {spec!r}") from exc
    if offset < 0 or offset % 4:
        raise ValueError(f"table offset must be a non-negative 4-byte offset: {spec!r}")
    if count <= 0:
        raise ValueError(f"table count must be positive: {spec!r}")
    return offset, count


def summarize_table(data: bytes, offset: int, count: int) -> dict[str, object]:
    end = offset + count * 4
    if end > len(data):
        raise ValueError(f"table 0x{offset:06x}:{count} exceeds ROM size")

    targets: list[int] = []
    outside_rom = 0
    for index in range(count):
        value = int.from_bytes(data[offset + index * 4 : offset + index * 4 + 4], "little")
        if ROM_BASE <= value < ROM_BASE + len(data):
            targets.append(value - ROM_BASE)
        else:
            outside_rom += 1

    return {
        "table_file_offset": f"0x{offset:06x}",
        "entry_count": count,
        "table_end_file_offset_exclusive": f"0x{end:06x}",
        "rom_pointer_count": len(targets),
        "outside_rom_pointer_count": outside_rom,
        "unique_target_count": len(set(targets)),
        "target_file_offset_min": f"0x{min(targets):06x}" if targets else None,
        "target_file_offset_max": f"0x{max(targets):06x}" if targets else None,
        "first_target_file_offsets": [f"0x{target:06x}" for target in targets[:MAX_REPORTED_TARGETS]],
        "targets_monotonic_non_decreasing": all(
            left <= right for left, right in zip(targets, targets[1:])
        ),
        "note": "Pointer-table candidate only; target bytes are intentionally not decoded.",
    }


def inspect(path: Path, tables: Iterable[tuple[str, int, int]]) -> dict[str, object]:
    data = path.read_bytes()
    reports = []
    for name, offset, count in tables:
        report = summarize_table(data, offset, count)
        report["label"] = name
        reports.append(report)
    return {
        "path": str(path),
        "read_only": True,
        "size_bytes": len(data),
        "rom_base": f"0x{ROM_BASE:08x}",
        "tables": reports,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--table",
        action="append",
        metavar="OFFSET:COUNT",
        help="replace defaults with an explicit file-offset table range",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        if args.table:
            tables = [
                (f"explicit_{index}", *parse_table_spec(spec))
                for index, spec in enumerate(args.table)
            ]
        else:
            tables = list(DEFAULT_TABLES)
        report = inspect(args.rom, tables)
    except (OSError, ValueError) as exc:
        print(f"scan_text_pointers.py: {exc}")
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
