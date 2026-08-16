#!/usr/bin/env python3
"""Build a small ignored provenance table around the M1.6 source record.

The input is the local, ignored strict Shift-JIS source table.  Output is
metadata-only JSONL under ``work/``: stable source offsets, source hashes,
control-token positions, and bounded pointer/caller provenance.  It does not
copy source text or emit a whole-ROM dump.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from probe_font_resource import (
    ROM_BASE,
    SOURCE_CONTEXTS,
    address,
    load_source_records,
    source_metadata,
    source_record_summary,
)


CENTER = 0x7B3FC
DEFAULT_SIZE = 16
MIN_SIZE = 8
MAX_SIZE = 32


def select_cohort(
    records: Mapping[int, Mapping[str, Any]], center: int = CENTER, size: int = DEFAULT_SIZE
) -> List[Mapping[str, Any]]:
    """Select contiguous records with the exact center record included."""
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError(f"cohort size must be {MIN_SIZE}..{MAX_SIZE}")
    offsets = sorted(records)
    if center not in records:
        raise ValueError(f"cohort center is missing: {address(center)}")
    center_index = offsets.index(center)
    start = max(0, min(center_index - size // 2, len(offsets) - size))
    return [records[offset] for offset in offsets[start : start + size]]


def _hex_value(value: Any, *, base: int = ROM_BASE) -> Optional[str]:
    if value is None:
        return None
    number = int(value)
    if number < base:
        return f"0x{number:06X}"
    return address(number)


def _call_summary(call: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "address": _hex_value(call.get("address")),
        "target": _hex_value(call.get("target")),
        "mnemonic": call.get("mnemonic"),
    }


def bounded_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep only address/shape evidence from a pointer classifier row."""
    fields = (
        "mode",
        "instruction_offset",
        "literal_offset",
        "target_offset",
        "literal_kind",
        "source_offset_exact",
        "pointer_table_start",
        "function_start",
        "confidence",
        "score",
    )
    result: Dict[str, Any] = {}
    for field in fields:
        value = candidate.get(field)
        if field.endswith("_offset") or field in {"literal_offset", "pointer_table_start", "function_start"}:
            result[field] = _hex_value(value, base=0)
        else:
            result[field] = value
    result["following_calls"] = [
        _call_summary(call)
        for call in candidate.get("following_calls", [])
        if isinstance(call, Mapping)
    ]
    return result


def load_pointer_candidates(path: Optional[Path]) -> Dict[int, List[Dict[str, Any]]]:
    if path is None:
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    result: Dict[int, List[Dict[str, Any]]] = {}
    for candidate in report.get("candidates", []):
        offset = int(candidate["target_offset"])
        result.setdefault(offset, []).append(bounded_candidate(candidate))
    return result


def runtime_provenance(offset: int) -> Optional[Dict[str, Any]]:
    if offset != CENTER:
        return None
    return {
        "status": "positive_direct_copy_m1.5",
        "consumer": address(0x08007E04),
        "caller_callsite": address(0x0800F49A),
        "caller_return": address(0x0800F49F),
        "source": address(ROM_BASE + offset),
        "destination": address(0x02000D60),
        "bound": "0x00000010",
    }


def build_rows(
    records: Mapping[int, Mapping[str, Any]],
    candidates: Mapping[int, Sequence[Mapping[str, Any]]],
    *,
    center: int = CENTER,
    size: int = DEFAULT_SIZE,
) -> List[Dict[str, Any]]:
    selected = select_cohort(records, center, size)
    rows: List[Dict[str, Any]] = []
    for index, record in enumerate(selected):
        offset = int(record["offset"])
        metadata = source_metadata(record)
        static = [dict(item) for item in candidates.get(offset, [])]
        runtime = runtime_provenance(offset)
        if runtime is not None:
            status = runtime["status"]
        elif static:
            status = "static_candidate_only"
        else:
            status = "no_bounded_candidate"
        rows.append(
            {
                "cohort_center": address(center),
                "cohort_size": len(selected),
                "cohort_index": index,
                "string_id": address(offset),
                "source_address": address(ROM_BASE + offset),
                **source_record_summary(metadata),
                "pointer_caller_provenance": {
                    "status": status,
                    "runtime": runtime,
                    "static_candidates": static,
                },
                "runtime_identity_status": (
                    "glyph identities are restricted to the separate M1.6 runtime probe"
                    if offset in SOURCE_CONTEXTS
                    else "not independently runtime-identified"
                ),
            }
        )
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--pointer-report", type=Path)
    parser.add_argument("--center", type=lambda value: int(value, 0), default=CENTER)
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = load_source_records(args.source_table)
    candidates = load_pointer_candidates(args.pointer_report)
    rows = build_rows(records, candidates, center=args.center, size=args.size)
    write_jsonl(args.output, rows)
    print(f"cohort_records={len(rows)} center={address(args.center)} output={args.output}")


if __name__ == "__main__":
    main()
