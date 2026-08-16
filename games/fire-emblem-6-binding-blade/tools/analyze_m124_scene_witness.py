#!/usr/bin/env python3
"""Join bounded natural scene receipts to the proven FE6 pointer table.

M1.24 does not infer a scene from pointer adjacency.  It compares two saved
natural KEYINPUT routes: the short selector route and the longer route that
also reached the generic caller family.  Static tree decoding is used only to
verify hashes and marker structure for the observed indices; output remains
hash-only and scene labels stay unconfirmed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from extract_afej_m16 import (
    AfejFormatError,
    BUFFER,
    POINTER_TABLE,
    build_codebook,
    decode_record,
    encode_leaves,
    load_rom,
    marker_offsets,
    prove_table_end,
    table_entry,
)


WATCHED_HITS = (
    "0x08013ad0",
    "0x08098b10",
    "0x08009252",
    "0x08098c78",
    "0x080995a6",
)


def _sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _static_record(rom: Any, codebook: dict[bytes, tuple[int, ...]], table_end: int, index: int) -> dict[str, object]:
    record = decode_record(rom, index)
    if encode_leaves(record.leaves, codebook) != record.source_bytes:
        raise AfejFormatError(f"decode->encode mismatch for {index}")
    next_source = table_entry(rom, index + 1) if index + 1 < table_end else None
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(f"source span mismatch for {index}")
    return {
        "table_index": index,
        "string_id": f"afej.ptr.{index:04d}",
        "table_entry": f"0x{POINTER_TABLE + index * 4:08x}",
        "source_pointer": f"0x{record.source_pointer:08x}",
        "source_end": f"0x{record.source_end:08x}",
        "source_hash": hashlib.sha256(record.source_bytes).hexdigest(),
        "output_hash": hashlib.sha256(record.buffer).hexdigest(),
        "payload_length": record.payload_length,
        "control_marker_offsets": marker_offsets(record.output),
        "decode_encode_byte_identical": True,
        "destination": f"0x{BUFFER:08x}",
        "raw_bytes_emitted": False,
    }


def _route_report(path: Path, static_by_index: dict[int, dict[str, object]]) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    runtime = report.get("runtime")
    route = report.get("route")
    if not isinstance(runtime, dict) or not isinstance(route, dict):
        raise ValueError(f"unsupported runtime report: {path}")
    loader_rows = runtime.get("loader_records", [])
    if not isinstance(loader_rows, list):
        loader_rows = []
    receipts = []
    for row in loader_rows[:32]:
        if not isinstance(row, dict) or not isinstance(row.get("loader_index"), int):
            continue
        index = row["loader_index"]
        static = static_by_index.get(index)
        buffer = row.get("buffer", {})
        if not isinstance(buffer, dict):
            buffer = {}
        receipts.append({
            "table_index": index,
            "caller_callsite": row.get("caller_callsite"),
            "caller_lr": row.get("caller_lr"),
            "source_pointer": row.get("source_pointer"),
            "reachability": row.get("reachability"),
            "buffer_hash": buffer.get("buffer_sha256"),
            "static_output_hash": static.get("output_hash") if static else None,
            "buffer_hash_matches_static": bool(static and static.get("output_hash") == buffer.get("buffer_sha256")),
            "control_marker_offsets": buffer.get("control_marker_offsets"),
        })
    display = runtime.get("final_display_io")
    hit_counts = runtime.get("hit_counts", {})
    if not isinstance(hit_counts, dict):
        hit_counts = {}
    return {
        "report": path.name,
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "sequence": route.get("sequence"),
        "loader_receipts": receipts,
        "loader_indices": [row["table_index"] for row in receipts],
        "caller_callsites": sorted({row["caller_callsite"] for row in receipts if row.get("caller_callsite")}),
        "final_display_io": display,
        "final_display_io_sha256": _sha_json(display),
        "watched_hit_counts": {key: hit_counts.get(key) for key in WATCHED_HITS},
        "scene_context": "route_label_only_unconfirmed",
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_paths: list[Path]) -> dict[str, object]:
    rom = load_rom(rom_path)
    table_end = prove_table_end(rom)
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in runtime_paths]
    indices = sorted({
        row["loader_index"]
        for report in reports
        for row in report.get("runtime", {}).get("loader_records", [])
        if isinstance(row, dict) and isinstance(row.get("loader_index"), int)
    })
    codebook = build_codebook(rom)
    static_by_index = {index: _static_record(rom, codebook, table_end, index) for index in indices}
    routes = [_route_report(path, static_by_index) for path in runtime_paths]
    caller_sets = [set(route["caller_callsites"]) for route in routes]
    index_sets = [set(route["loader_indices"]) for route in routes]
    all_receipts = [receipt for route in routes for receipt in route["loader_receipts"]]
    return {
        "schema": "afej-m124-scene-witness-v1",
        "rom": {
            "game_code": rom.data[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom.data),
            "sha256": hashlib.sha256(rom.data).hexdigest(),
        },
        "table": {
            "pointer_table": f"0x{POINTER_TABLE:08x}",
            "domain": f"[0, {table_end})",
            "observed_index_count": len(indices),
            "observed_indices": indices,
            "static_records": list(static_by_index.values()),
        },
        "routes": routes,
        "comparison": {
            "same_proven_table_domain": all(0 <= index < table_end for index in indices),
            "shared_indices": sorted(set.intersection(*index_sets)) if index_sets else [],
            "shared_caller_families": sorted(set.intersection(*caller_sets)) if caller_sets else [],
            "distinct_caller_families_observed": sorted(set.union(*caller_sets)) if caller_sets else [],
            "different_index_sets_observed": len({tuple(route["loader_indices"]) for route in routes}) > 1,
            "runtime_static_hash_match_count": sum(receipt["buffer_hash_matches_static"] for receipt in all_receipts),
            "runtime_static_hash_mismatch_indices": sorted({
                receipt["table_index"] for receipt in all_receipts if not receipt["buffer_hash_matches_static"]
            }),
            "hash_mismatch_cause_assigned": False,
            "scene_classification_proven": False,
            "control_0x01_semantic_name_assigned": False,
        },
        "status": {
            "scene_or_content_category": "unknown",
            "unicode_identity_confirmed": False,
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("runtime_reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.rom, args.runtime_reports)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
