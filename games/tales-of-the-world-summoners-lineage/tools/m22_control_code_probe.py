#!/usr/bin/env python3
"""Metadata-only audit of A9PJ 16-bit stream control candidates.

This is deliberately not a source extractor.  It walks the already bounded
pointer candidates used by M21 and emits aggregate unit counts, hashes and
record-class metadata only.  The parser has static evidence for ``0x0000``
termination and a special ``0xFF70`` branch; this probe keeps the latter as a
candidate and does not assign a translated control-code meaning.  ``0x0001``
is separately identified as an all-zero font record, but its semantic role
(space, blank key, padding, or another sentinel) remains unresolved.

The output is intended for a caller's ignored/private path.  It never writes
stream units, decoded Japanese, glyph rows, or source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Iterable

from m20_text_record_probe import (
    DEFAULT_TARGET_END,
    DEFAULT_TARGET_START,
    EXPECTED_ROM_SHA256,
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_STRIDE,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    find_pointer_references,
)


PROBE_VERSION = "m22-control-code-probe-20260816.v1"
ROM_BASE = 0x08000000
DEFAULT_SCAN_START = 0
DEFAULT_SCAN_END = 0x800000
DEFAULT_MAX_UNITS = 0x400
DEFAULT_TOP_N = 32
BLANK_RECORD_CODE_UNITS = frozenset({0x0001})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex_unit(value: int) -> str:
    return f"0x{value:04X}"


def stream_unit_counts(data: bytes, target: int, *, max_units: int) -> dict[str, object]:
    """Count one bounded halfword stream without returning its units."""

    if not 0 <= target < len(data):
        raise ValueError("stream target is outside the supplied ROM")
    if max_units <= 0:
        raise ValueError("max_units must be positive")

    counts: Counter[int] = Counter()
    position = target
    terminated = False
    units_read = 0
    while units_read < max_units and position + 2 <= len(data):
        unit = int.from_bytes(data[position:position + 2], "little")
        counts[unit] += 1
        position += 2
        units_read += 1
        if unit == NULL_CODE_UNIT:
            terminated = True
            break

    raw = data[target:position]
    return {
        "byte_length": len(raw),
        "unit_count_including_terminator": units_read,
        "terminated_by_0000": terminated,
        "capped_or_truncated": not terminated,
        "unit_count_distinct": len(counts),
        "line_advance_count": counts[LINE_ADVANCE_CODE_UNIT],
        "blank_record_candidate_count": sum(
            counts[unit] for unit in BLANK_RECORD_CODE_UNITS
        ),
        "nonzero_unit_count": units_read - counts[NULL_CODE_UNIT],
        "stream_sha256": sha256(raw),
        "unit_frequency_sha256": sha256(
            json.dumps(
                {hex_unit(unit): count for unit, count in sorted(counts.items())},
                separators=(",", ":"),
            ).encode("ascii")
        ),
        "_counts": counts,
    }


def record_is_blank(data: bytes, code_unit: int) -> bool:
    offset = FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE
    record = data[offset:offset + FONT_RECORD_STRIDE]
    return len(record) == FONT_RECORD_STRIDE and not any(record)


def classify_unit(data: bytes, code_unit: int) -> str:
    if code_unit == NULL_CODE_UNIT:
        return "parser-terminator-0000"
    if code_unit == LINE_ADVANCE_CODE_UNIT:
        return "parser-special-ff70-candidate"
    if record_is_blank(data, code_unit):
        return "blank-font-record-unknown-semantic"
    return "font-record-index"


def audit(
    data: bytes,
    *,
    scan_start: int = DEFAULT_SCAN_START,
    scan_end: int = DEFAULT_SCAN_END,
    target_start: int = DEFAULT_TARGET_START,
    target_end: int = DEFAULT_TARGET_END,
    max_units: int = DEFAULT_MAX_UNITS,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, object]:
    if not 0 <= scan_start <= scan_end <= len(data):
        raise ValueError("scan range is outside ROM")
    if not 0 <= target_start <= target_end <= len(data):
        raise ValueError("target range is outside ROM")
    if max_units <= 0 or top_n < 0:
        raise ValueError("max_units must be positive and top_n non-negative")

    references = find_pointer_references(
        data,
        scan_start=scan_start,
        scan_end=scan_end,
        target_start=target_start,
        target_end=target_end,
    )
    unique_targets = sorted({target for _, target in references})
    total_units: Counter[int] = Counter()
    class_counts: Counter[str] = Counter()
    terminated = 0
    truncated = 0
    line_streams = 0
    blank_streams = 0
    stream_hashes: set[str] = set()
    unit_hashes: set[str] = set()
    for target in unique_targets:
        profile = stream_unit_counts(data, target, max_units=max_units)
        counts = profile.pop("_counts")
        assert isinstance(counts, Counter)
        total_units.update(counts)
        stream_hashes.add(str(profile["stream_sha256"]))
        unit_hashes.add(str(profile["unit_frequency_sha256"]))
        if profile["terminated_by_0000"]:
            terminated += 1
        else:
            truncated += 1
        if profile["line_advance_count"]:
            line_streams += 1
        if profile["blank_record_candidate_count"]:
            blank_streams += 1
        for unit in counts:
            class_counts[classify_unit(data, unit)] += counts[unit]

    top_units = [
        {
            "code_unit": hex_unit(unit),
            "count": count,
            "class": classify_unit(data, unit),
        }
        for unit, count in total_units.most_common(top_n)
    ]
    special_counts = {
        hex_unit(unit): total_units[unit]
        for unit in (NULL_CODE_UNIT, LINE_ADVANCE_CODE_UNIT, *sorted(BLANK_RECORD_CODE_UNITS))
    }
    frequency_payload = {
        hex_unit(unit): count for unit, count in sorted(total_units.items())
    }
    return {
        "probe_version": PROBE_VERSION,
        "rom": {
            "sha256": sha256(data),
            "expected_a9pj_sha256_match": sha256(data) == EXPECTED_ROM_SHA256,
            "file_size": len(data),
            "source_text_emitted": False,
        },
        "scope": {
            "rom_scan_file_range": [f"0x{scan_start:X}", f"0x{scan_end:X}"],
            "candidate_target_file_range": [f"0x{target_start:X}", f"0x{target_end:X}"],
            "pointer_references": len(references),
            "distinct_targets": len(unique_targets),
            "max_units_per_stream": max_units,
        },
        "streams": {
            "terminated_targets": terminated,
            "truncated_targets": truncated,
            "targets_with_ff70": line_streams,
            "targets_with_blank_record_candidate": blank_streams,
            "distinct_stream_sha256": len(stream_hashes),
            "distinct_unit_frequency_sha256": len(unit_hashes),
        },
        "unit_totals": {
            "units_observed": sum(total_units.values()),
            "distinct_units_observed": len(total_units),
            "special_counts": special_counts,
            "class_counts": dict(sorted(class_counts.items())),
            "top_units": top_units,
            "all_frequency_sha256": sha256(
                json.dumps(frequency_payload, separators=(",", ":")).encode("ascii")
            ),
        },
        "interpretation": {
            "terminator": "0x0000 parser branch is statically confirmed; stream counts are static candidates",
            "line_advance": "0xFF70 parser branch is a line-advance candidate; semantic name is unconfirmed",
            "blank_record": "0x0001 is an all-zero record candidate; space/padding/control meaning is unconfirmed",
            "scene_roles": "unclassified; pointer geometry and frequency are not runtime scene proof",
            "runtime_context_confirmed": False,
            "eligible_for_ledger": False,
        },
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=DEFAULT_SCAN_START)
    parser.add_argument("--scan-end", type=lambda value: int(value, 0), default=DEFAULT_SCAN_END)
    parser.add_argument("--target-start", type=lambda value: int(value, 0), default=DEFAULT_TARGET_START)
    parser.add_argument("--target-end", type=lambda value: int(value, 0), default=DEFAULT_TARGET_END)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=DEFAULT_MAX_UNITS)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.top_n < 0:
        parser.error("top-n must be non-negative")
    result = audit(
        args.rom.read_bytes(),
        scan_start=args.scan_start,
        scan_end=args.scan_end,
        target_start=args.target_start,
        target_end=args.target_end,
        max_units=args.max_units,
        top_n=args.top_n,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"probe_version": PROBE_VERSION, "output": str(args.output), "source_text_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
