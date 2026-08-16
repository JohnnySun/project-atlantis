#!/usr/bin/env python3
"""Find pointer-referenced Shift-JIS record candidates without emitting text.

This is a reconnaissance helper, not a decoder.  It follows aligned 32-bit
absolute GBA pointers, validates a bounded NUL-terminated payload as strict
Shift-JIS, and reports only offsets, lengths, hashes and control statistics.
The known reviewed pools can be excluded so that new story/event candidates
are easier to audit.  It never writes source text, ROM bytes or glyph data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROM_BASE = 0x08000000
DEFAULT_MAX_BYTES = 0x200
DEFAULT_MIN_BYTES = 8
DEFAULT_MIN_DOUBLE_BYTE_UNITS = 2
KNOWN_TARGET_WINDOWS = (
    (0x075A80, 0x077101),
    (0x078528, 0x07870C),
    (0x07880C, 0x078849),
    (0x079764, 0x0797E5),
)


def _inside_known_window(offset: int) -> bool:
    return any(start <= offset < end for start, end in KNOWN_TARGET_WINDOWS)


def _double_byte_units(payload: bytes) -> int:
    encoded = payload.decode("shift_jis")
    units = 0
    cursor = 0
    while cursor < len(payload):
        value = payload[cursor]
        if value <= 0x7F or 0xA1 <= value <= 0xDF:
            cursor += 1
            continue
        if cursor + 1 >= len(payload):
            raise ValueError("truncated Shift-JIS pair")
        units += 1
        cursor += 2
    if not encoded:
        raise ValueError("empty decoded string")
    return units


def _format_counts(payload: bytes) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for index, value in enumerate(payload[:-1]):
        if value == 0x25 and payload[index + 1] in b"sdu%":
            counts[f"%{chr(payload[index + 1])}"] += 1
    return dict(sorted(counts.items()))


def candidate_record(data: bytes, target: int, *, max_bytes: int, min_bytes: int, min_units: int) -> dict[str, object] | None:
    if target < 0 or target >= len(data):
        return None
    terminator = data.find(b"\0", target, min(len(data), target + max_bytes))
    if terminator < 0:
        return None
    payload = data[target:terminator]
    if len(payload) < min_bytes or any(value < 0x20 and value not in (0x0A, 0x09) for value in payload):
        return None
    try:
        unit_count = _double_byte_units(payload)
    except (UnicodeDecodeError, ValueError):
        return None
    if unit_count < min_units:
        return None
    return {
        "target_file_offset": f"0x{target:06X}",
        "target_gba_address": f"0x{ROM_BASE + target:08X}",
        "payload_length": len(payload),
        "source_hash": hashlib.sha256(payload).hexdigest(),
        "shift_jis_double_byte_unit_count": unit_count,
        "line_feed_count": payload.count(b"\n"),
        "format_counts": _format_counts(payload),
        "terminator": "0x00",
    }


def discover(
    data: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    min_bytes: int = DEFAULT_MIN_BYTES,
    min_units: int = DEFAULT_MIN_DOUBLE_BYTE_UNITS,
    exclude_known: bool = True,
) -> list[dict[str, object]]:
    """Return unique pointer-referenced candidates, metadata only."""

    references: defaultdict[int, list[int]] = defaultdict(list)
    for pointer_offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, pointer_offset)[0]
        if ROM_BASE <= value < ROM_BASE + len(data):
            target = value - ROM_BASE
            if not exclude_known or not _inside_known_window(target):
                references[target].append(pointer_offset)

    candidates = []
    for target, pointer_offsets in references.items():
        row = candidate_record(
            data,
            target,
            max_bytes=max_bytes,
            min_bytes=min_bytes,
            min_units=min_units,
        )
        if row is None:
            continue
        row["pointer_reference_count"] = len(pointer_offsets)
        row["pointer_reference_file_offsets"] = [
            f"0x{offset:06X}" for offset in pointer_offsets[:16]
        ]
        row["pointer_reference_truncated"] = len(pointer_offsets) > 16
        candidates.append(row)
    return sorted(candidates, key=lambda row: int(str(row["target_file_offset"]), 16))


def summarize(candidates: list[dict[str, object]], *, excluded_known: bool) -> dict[str, object]:
    by_region: Counter[str] = Counter()
    for row in candidates:
        offset = int(str(row["target_file_offset"]), 16)
        by_region[f"0x{offset // 0x10000:02X}"] += 1
    return {
        "read_only": True,
        "candidate_count": len(candidates),
        "excluded_known_target_windows": excluded_known,
        "region_counts": dict(sorted(by_region.items())),
        "candidates": candidates,
        "note": "Metadata only; source text and raw payload bytes are intentionally omitted.",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    parser.add_argument("--min-units", type=int, default=DEFAULT_MIN_DOUBLE_BYTE_UNITS)
    parser.add_argument("--include-known", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.max_bytes <= 0 or args.min_bytes <= 0 or args.min_units <= 0:
        parser.error("bounds must be positive")
    candidates = discover(
        args.rom.read_bytes(),
        max_bytes=args.max_bytes,
        min_bytes=args.min_bytes,
        min_units=args.min_units,
        exclude_known=not args.include_known,
    )
    report = summarize(candidates, excluded_known=not args.include_known)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("read_only", "candidate_count", "excluded_known_target_windows")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
