#!/usr/bin/env python3
"""Build a bounded cross-caller FE6 source/provenance census.

M1.26 deliberately expands the verified worker across two bounded, disjoint
windows: one around the selector witness and one around the natural generic
caller witnesses.  It records source/output hashes, table spans, marker
offsets and optional natural loader joins.  It does not decode to Unicode,
emit code units, or infer a scene/content category from index adjacency or a
route name.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

from extract_afej_m16 import (
    AfejFormatError,
    BUFFER,
    LOADER_ENTRY,
    POINTER_TABLE,
    WORKER,
    build_codebook,
    decode_record,
    encode_leaves,
    load_rom,
    marker_offsets,
    prove_table_end,
    table_entry,
)


SCHEMA = "afej-m126-cross-caller-provenance-v1"
DEFAULT_RANGES = ((2672, 16), (3080, 16))
MAX_RECORDS = 32


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _parse_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def parse_range(value: str) -> tuple[int, int]:
    """Parse a bounded ``START:COUNT`` command-line range."""

    try:
        start_text, count_text = value.split(":", 1)
        start = int(start_text, 0)
        count = int(count_text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("range must be START:COUNT") from exc
    if start < 0 or count <= 0:
        raise argparse.ArgumentTypeError("range start must be >= 0 and count > 0")
    return start, count


def _selected_indices(ranges: Iterable[tuple[int, int]], table_end: int) -> list[int]:
    selected: set[int] = set()
    for start, count in ranges:
        if count > MAX_RECORDS or start + count > table_end:
            raise ValueError("each range must fit the proven table and 32-record bound")
        selected.update(range(start, start + count))
    if not selected or len(selected) > MAX_RECORDS:
        raise ValueError("census must contain 1..32 unique records")
    return sorted(selected)


def _record_summary(
    rom: Any,
    record: Any,
    table_end: int,
    codebook: dict[bytes, tuple[int, ...]],
    cohort_name: str,
) -> dict[str, object]:
    encoded = encode_leaves(record.leaves, codebook)
    if encoded != record.source_bytes:
        raise AfejFormatError(f"index {record.index} failed original leaf round-trip")
    next_source = table_entry(rom, record.index + 1) if record.index + 1 < table_end else None
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(f"index {record.index} source span does not meet next pointer")
    offsets = marker_offsets(record.output)
    return {
        "string_id": f"afej.ptr.{record.index:04d}",
        "cohort": cohort_name,
        "table_index": record.index,
        "table_entry": _hex(POINTER_TABLE + record.index * 4),
        "source_pointer": _hex(record.source_pointer),
        "source_end": _hex(record.source_end),
        "next_source_pointer": _hex(next_source) if next_source is not None else None,
        "source_span_matches_next_entry": next_source is None or record.source_end == next_source,
        "source_hash": _sha256(record.source_bytes),
        "output_hash": _sha256(record.buffer),
        "source_length": len(record.source_bytes),
        "payload_length": len(record.output),
        "buffer_length": len(record.buffer),
        "control_marker_offsets": offsets,
        "control_marker_counts": {marker: len(values) for marker, values in offsets.items()},
        "decode_encode_byte_identical": True,
        "provenance": {
            "loader_entry": _hex(LOADER_ENTRY),
            "pointer_table": _hex(POINTER_TABLE),
            "worker": _hex(WORKER),
            "destination": _hex(BUFFER),
            "table_domain": f"[0, {table_end})",
        },
        "raw_bytes_emitted": False,
    }


def _route_summary(path: Path, static_by_index: dict[int, dict[str, object]]) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    route = report.get("route", {})
    runtime = report.get("runtime", {})
    if not isinstance(route, dict) or not isinstance(runtime, dict):
        raise ValueError(f"unsupported runtime receipt: {path}")
    loader_rows = runtime.get("loader_records", [])
    if not isinstance(loader_rows, list):
        loader_rows = []
    receipts: list[dict[str, object]] = []
    for row in loader_rows[:32]:
        if not isinstance(row, dict):
            continue
        index = _parse_int(row.get("loader_index"))
        if index is None:
            continue
        static = static_by_index.get(index)
        buffer = row.get("buffer", {})
        if not isinstance(buffer, dict):
            buffer = {}
        static_source = static.get("source_pointer") if static else None
        runtime_source = row.get("source_pointer")
        runtime_hash = buffer.get("buffer_sha256")
        receipts.append({
            "table_index": index,
            "caller_callsite": row.get("caller_callsite"),
            "caller_lr": row.get("caller_lr"),
            "runtime_source_pointer": runtime_source,
            "static_source_pointer": static_source,
            "source_pointer_matches_static": bool(static and runtime_source == static_source),
            "runtime_output_hash": runtime_hash,
            "static_output_hash": static.get("output_hash") if static else None,
            "output_hash_matches_static": bool(static and runtime_hash == static.get("output_hash")),
            "witness_kind": "natural_keyinput_loader_receipt",
        })
    return {
        "report": path.name,
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "input_sequence": route.get("sequence"),
        "loader_receipts": receipts,
        "scene_or_content_category": "unknown",
        "category_inferred_from_route_name": False,
        "raw_bytes_emitted": False,
    }


def _caller_groups(routes: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"indices": set(), "routes": set(), "receipt_count": 0}
    )
    for route in routes:
        for receipt in route["loader_receipts"]:
            assert isinstance(receipt, dict)
            caller = receipt.get("caller_callsite") or "unknown"
            group = grouped[str(caller)]
            group["indices"].add(receipt["table_index"])
            group["routes"].add(route["route_name"])
            group["receipt_count"] += 1
    return [
        {
            "caller_callsite": caller,
            "observed_indices": sorted(group["indices"]),
            "route_count": len(group["routes"]),
            "receipt_count": group["receipt_count"],
            "scene_or_content_category": "unknown",
            "category_inferred_from_caller": False,
        }
        for caller, group in sorted(grouped.items())
    ]


def build_report(
    rom_path: Path,
    *,
    ranges: Optional[Iterable[tuple[int, int]]] = None,
    runtime_paths: Optional[list[Path]] = None,
) -> dict[str, object]:
    rom = load_rom(rom_path)
    table_end = prove_table_end(rom)
    selected_ranges = tuple(ranges or DEFAULT_RANGES)
    indices = _selected_indices(selected_ranges, table_end)
    codebook = build_codebook(rom)
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    range_by_index = {
        index: f"{start}:{count}"
        for start, count in selected_ranges
        for index in range(start, start + count)
    }
    for index in indices:
        try:
            records.append(
                _record_summary(
                    rom,
                    decode_record(rom, index),
                    table_end,
                    codebook,
                    range_by_index[index],
                )
            )
        except AfejFormatError:
            failures.append({
                "table_index": index,
                "failure_kind": "strict_decode_or_original_leaf_round_trip_failure",
            })
    static_by_index = {row["table_index"]: row for row in records}
    routes = [
        _route_summary(path, static_by_index)
        for path in (runtime_paths or [])
    ]
    receipts = [
        receipt
        for route in routes
        for receipt in route["loader_receipts"]
    ]
    matched = [receipt for receipt in receipts if receipt["output_hash_matches_static"]]
    source_matched = [receipt for receipt in receipts if receipt["source_pointer_matches_static"]]
    observed_indices = sorted({receipt["table_index"] for receipt in receipts})
    static_observed_indices = sorted(set(observed_indices) & set(static_by_index))
    return {
        "schema": SCHEMA,
        "rom": {
            "game_code": rom.data[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom.data),
            "sha256": _sha256(rom.data),
        },
        "table": {
            "pointer_table": _hex(POINTER_TABLE),
            "domain": f"[0, {table_end})",
            "selected_ranges": [f"{start}:{count}" for start, count in selected_ranges],
            "selected_indices": indices,
            "selected_record_count": len(records),
            "failure_count": len(failures),
            "all_selected_source_spans_match_next_entry": all(
                bool(row["source_span_matches_next_entry"]) for row in records
            ),
        },
        "records": records,
        "failures": failures,
        "runtime": {
            "route_count": len(routes),
            "routes": routes,
            "loader_receipt_count": len(receipts),
            "observed_indices": observed_indices,
            "observed_indices_in_selected_census": static_observed_indices,
            "all_observed_indices_in_selected_census": set(observed_indices).issubset(static_by_index),
            "source_pointer_match_count": len(source_matched),
            "output_hash_match_count": len(matched),
            "output_hash_mismatch_indices": sorted({
                receipt["table_index"]
                for receipt in receipts
                if receipt["table_index"] in static_by_index and not receipt["output_hash_matches_static"]
            }),
            "source_or_output_mismatch_cause_assigned": False,
            "caller_groups": _caller_groups(routes),
            "scene_or_content_category": "unknown",
            "category_inferred_from_index_caller_or_route": False,
        },
        "cross_caller_comparison": {
            "bounded_windows_are_disjoint": len(indices) == sum(count for _, count in selected_ranges),
            "strict_worker_format_shared": len(records) == len(indices) and not failures,
            "natural_caller_families_observed": sorted({
                str(receipt["caller_callsite"])
                for receipt in receipts
                if receipt.get("caller_callsite") is not None
            }),
            "distinct_natural_caller_family_count": len({
                str(receipt["caller_callsite"])
                for receipt in receipts
                if receipt.get("caller_callsite") is not None
            }),
            "same_content_category_proven": False,
            "scene_or_content_category": "unknown",
        },
        "encode_guard": {
            "decode_encode_byte_identical": len(records) == len(indices) and not failures,
            "scope": "original_decoded_leaf_sequence_only",
            "arbitrary_text_encode_enabled": False,
            "rom_reinsert_enabled": False,
        },
        "status": {
            "source_provenance": "bounded_cross_caller_hash_join",
            "scene_or_content_category": "unknown",
            "unicode_identity_confirmed": False,
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--range",
        dest="ranges",
        action="append",
        type=parse_range,
        help="bounded table window START:COUNT; may be repeated (default: 2672:16 and 3080:16)",
    )
    parser.add_argument("--runtime-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_report(args.rom, ranges=args.ranges, runtime_paths=args.runtime_report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, AfejFormatError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"records={result['table']['selected_record_count']}/{len(result['table']['selected_indices'])}")
    print(f"runtime_receipts={result['runtime']['loader_receipt_count']}")
    print(f"output_hash_matches={result['runtime']['output_hash_match_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
