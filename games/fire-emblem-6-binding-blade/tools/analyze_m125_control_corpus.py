#!/usr/bin/env python3
"""Build a bounded, hash-only FE6 control-structure corpus.

M1.25 joins three already reviewed layers without pretending to be a
translation extractor:

* the M1.6 tree worker decodes a bounded set of table entries;
* the M1.19 consumer disassembly supplies exact byte-branch topology; and
* optional ignored natural runtime receipts supply bounded byte-read and hit
  metadata.

The report contains marker offsets, hashes, branch addresses and provenance,
but never source bytes, code-unit bytes, or decoded Japanese text.  The
encode guard is intentionally a no-op guard for the original decoded leaf
sequence only.  It does not claim that arbitrary translated text can yet be
encoded or inserted into a ROM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Optional


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from extract_afej_m16 import (  # noqa: E402
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
import trace_m19_natural  # noqa: E402


SCHEMA = "afej-m125-control-corpus-v1"
DEFAULT_START = 3064
DEFAULT_COUNT = 32
KNOWN_MARKERS = (0x00, 0x01, 0x04, 0xFF)
CONSUMER_BRANCHES = (
    trace_m19_natural.CONSUMER_BYTE_READ,
    trace_m19_natural.CONSUMER_SIGNED_COMPARE_BRANCH,
    trace_m19_natural.CONSUMER_LOW_COMPARE_BRANCH,
    trace_m19_natural.CONSUMER_FOUR_COMPARE_BRANCH,
    trace_m19_natural.CONSUMER_CONTROL_BRANCH,
    trace_m19_natural.CONSUMER_SKIP_LOOP,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _marker_hex(value: int) -> str:
    return f"0x{value:02x}"


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


def _marker_counts(offsets: dict[str, list[int]]) -> dict[str, int]:
    return {marker: len(offsets.get(marker, [])) for marker in offsets}


def _record_summary(rom: Any, record: Any, table_end: int, codebook: dict[bytes, tuple[int, ...]]) -> dict[str, object]:
    encoded = encode_leaves(record.leaves, codebook)
    if encoded != record.source_bytes:
        raise AfejFormatError(f"index {record.index} failed original-leaf encode guard")
    next_source = table_entry(rom, record.index + 1) if record.index + 1 < table_end else None
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(f"index {record.index} source span does not meet next pointer")
    offsets = marker_offsets(record.output)
    return {
        "string_id": f"afej.ptr.{record.index:04d}",
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
        "control_marker_counts": _marker_counts(offsets),
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


def _static_control_gate(rom_data: bytes) -> dict[str, object]:
    gate = trace_m19_natural.static_candidate_report(rom_data)["consumer_branch_gate"]
    # Copy only the stable branch topology.  Keeping this explicit prevents a
    # future static report field from accidentally becoming corpus output.
    return {
        "function_start": gate["function_start"],
        "function_return": gate["function_return"],
        "byte_read_instruction": gate["byte_read_instruction"],
        "branch_rows": gate["branch_rows"],
        "opaque_branch_map": gate["opaque_branch_map"],
        "control_handler_callsite": gate["control_handler_callsite"],
        "semantic_name_assigned": False,
    }


def _runtime_marker_rows(runtime: dict[str, object]) -> list[dict[str, object]]:
    rows = runtime.get("consumer_reads", [])
    if not isinstance(rows, list):
        return []
    result: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _parse_int(row.get("byte_value"))
        if value not in KNOWN_MARKERS:
            continue
        result.append({
            "marker": _marker_hex(value),
            "buffer_offset": row.get("buffer_offset_if_base"),
            "buffer_pointer_register": row.get("buffer_pointer_register"),
            "static_target_for_read": row.get("static_branch_target"),
            "observation": "consumer_byte_read_with_static_branch_target",
            "semantic_name_assigned": False,
        })
    return result


def _runtime_branch_source_pairs(runtime: dict[str, object]) -> list[dict[str, object]]:
    rows = runtime.get("consumer_branch_receipts", [])
    if not isinstance(rows, list):
        return []
    result: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _parse_int(row.get("branch_source_byte"))
        target = _parse_int(row.get("branch_target"))
        if value not in KNOWN_MARKERS or target is None:
            continue
        result.append({
            "marker": _marker_hex(value),
            "branch_target": _hex(target),
            "branch_source_offset": row.get("branch_source_offset_if_base"),
            "semantic_name_assigned": False,
        })
    return result


def _runtime_summary(path: Path, static_by_index: dict[int, dict[str, object]]) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    route = report.get("route", {})
    runtime = report.get("runtime", {})
    if not isinstance(route, dict) or not isinstance(runtime, dict):
        raise ValueError(f"unsupported runtime receipt: {path}")
    loader_rows = runtime.get("loader_records", [])
    if not isinstance(loader_rows, list):
        loader_rows = []
    loader_receipts: list[dict[str, object]] = []
    for row in loader_rows[:32]:
        if not isinstance(row, dict):
            continue
        index = _parse_int(row.get("loader_index"))
        if index is None:
            continue
        buffer = row.get("buffer", {})
        if not isinstance(buffer, dict):
            buffer = {}
        static = static_by_index.get(index)
        loader_receipts.append({
            "table_index": index,
            "caller_callsite": row.get("caller_callsite"),
            "caller_lr": row.get("caller_lr"),
            "source_pointer": row.get("source_pointer"),
            "buffer_hash": buffer.get("buffer_sha256"),
            "static_output_hash": static.get("output_hash") if static else None,
            "buffer_hash_matches_static": bool(static and static.get("output_hash") == buffer.get("buffer_sha256")),
        })
    hit_counts = runtime.get("hit_counts", {})
    if not isinstance(hit_counts, dict):
        hit_counts = {}
    branch_hits = {
        _hex(address): _parse_int(hit_counts.get(_hex(address))) or 0
        for address in CONSUMER_BRANCHES
    }
    marker_reads = _runtime_marker_rows(runtime)
    source_pairs = _runtime_branch_source_pairs(runtime)
    return {
        "report": path.name,
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "input_sequence": route.get("sequence"),
        "loader_indices": [row["table_index"] for row in loader_receipts],
        "loader_receipts": loader_receipts,
        "consumer_branch_hit_counts": branch_hits,
        "marker_reads": marker_reads,
        "dynamic_branch_source_pairs": source_pairs,
        "dynamic_branch_source_pairing_available": bool(source_pairs),
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def _cohort_summary(records: Iterable[dict[str, object]]) -> dict[str, object]:
    rows = list(records)
    total_counts = {f"0x{marker:02x}": 0 for marker in KNOWN_MARKERS}
    record_counts = {f"0x{marker:02x}": 0 for marker in KNOWN_MARKERS}
    for row in rows:
        counts = row["control_marker_counts"]
        assert isinstance(counts, dict)
        for marker in total_counts:
            count = int(counts.get(marker, 0))
            total_counts[marker] += count
            record_counts[marker] += int(count > 0)
    return {
        "record_count": len(rows),
        "marker_total_counts": total_counts,
        "marker_record_counts": record_counts,
        "marker_semantics": "opaque_structural_markers_only",
    }


def build_report(
    rom_path: Path,
    *,
    start: int = DEFAULT_START,
    count: int = DEFAULT_COUNT,
    runtime_paths: Optional[list[Path]] = None,
) -> dict[str, object]:
    rom = load_rom(rom_path)
    table_end = prove_table_end(rom)
    if count <= 0 or count > 32 or start < 0 or start + count > table_end:
        raise ValueError("bounded cohort must contain 1..32 records within proven table")
    codebook = build_codebook(rom)
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for index in range(start, start + count):
        try:
            records.append(_record_summary(rom, decode_record(rom, index), table_end, codebook))
        except AfejFormatError:
            failures.append({
                "table_index": index,
                "failure_kind": "strict_decode_or_original_leaf_encode_failure",
            })
    static_by_index = {row["table_index"]: row for row in records}
    runtime = [
        _runtime_summary(path, static_by_index)
        for path in (runtime_paths or [])
    ]
    all_marker_reads = [
        row
        for route in runtime
        for row in route["marker_reads"]
    ]
    routes_with_dynamic_pairing = sum(
        bool(route["dynamic_branch_source_pairing_available"]) for route in runtime
    )
    return {
        "schema": SCHEMA,
        "rom": {
            "game_code": rom.data[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom.data),
            "sha256": _sha256(rom.data),
        },
        "cohort": {
            "start": start,
            "count_requested": count,
            "count_extracted": len(records),
            "count_failed": len(failures),
            "end_exclusive": start + count,
            "table_domain": f"[0, {table_end})",
            "bounded_max": 32,
            **_cohort_summary(records),
        },
        "records": records,
        "failures": failures,
        "static_consumer_branch_gate": _static_control_gate(rom.data),
        "runtime": {
            "route_count": len(runtime),
            "routes": runtime,
            "marker_read_count": len(all_marker_reads),
            "dynamic_branch_source_pairing_route_count": routes_with_dynamic_pairing,
            "cross_route_behavioral_contrast_observed": False,
            "control_0x01_semantic_name_assigned": False,
        },
        "encode_guard": {
            "decode_encode_byte_identical": len(records) == count and not failures,
            "scope": "original_decoded_leaf_sequence_only",
            "arbitrary_text_encode_enabled": False,
            "control_marker_rewrite_enabled": False,
            "rom_reinsert_enabled": False,
        },
        "status": {
            "control_markers": "opaque_structural_tokens",
            "unicode_identity_confirmed": False,
            "scene_or_content_category": "unknown",
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--runtime-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_report(
            args.rom,
            start=args.start,
            count=args.count,
            runtime_paths=args.runtime_report,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, AfejFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"output={args.output}")
    print(f"records={result['cohort']['count_extracted']}/{result['cohort']['count_requested']}")
    print(f"round_trip={result['encode_guard']['decode_encode_byte_identical']}")
    print(f"runtime_routes={result['runtime']['route_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
