#!/usr/bin/env python3
"""Join the full AFEJ hash-only table census with caller receipts.

M1.32 reuses the proven M1.10 worker over the complete 3342-entry pointer
table and adds only runtime loader provenance.  Each successful record keeps
its stable ID, pointer span, source/output hashes, marker counts and original
leaf round-trip result; the 139 decoder-negative entries remain an explicit
failure set.  Natural loader receipts are joined by table index and compared
to the static hashes.

Caller families and route names are evidence labels only.  The report never
turns index adjacency, caller address or a route name into a chapter,
dialogue, support, menu, item, battle or other content category.  It emits no
code-unit bytes, source text, compressed data or Unicode text.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import analyze_m110_corpus as m110


EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)
MAX_LOADER_RECEIPTS_PER_ROUTE = 32


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _as_int(value: object) -> Optional[int]:
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


def _table_digest(census: dict[str, object]) -> str:
    """Hash stable table summaries without copying source/code-unit bytes."""

    records = census.get("records", [])
    failures = census.get("decoder_failures", [])
    if not isinstance(records, list) or not isinstance(failures, list):
        raise ValueError("M1.10 census shape has no record/failure lists")
    stable_rows = []
    for row in records:
        if not isinstance(row, dict):
            continue
        stable_rows.append({
            "table_index": row.get("table_index"),
            "source_pointer": row.get("source_pointer"),
            "source_end": row.get("source_end"),
            "source_hash": row.get("source_hash"),
            "output_hash": row.get("output_hash"),
            "decode_encode_byte_identical": row.get("decode_encode_byte_identical"),
        })
    stable_rows.extend({
        "table_index": row.get("table_index"),
        "failure_kind": row.get("failure_kind"),
    } for row in failures if isinstance(row, dict))
    stable_rows.sort(key=lambda row: (int(row.get("table_index", -1)), str(row.get("failure_kind", ""))))
    return _sha256(json.dumps(stable_rows, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _route_join(path: Path, by_index: dict[int, dict[str, object]]) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    route = report.get("route", {})
    runtime = report.get("runtime", {})
    if not isinstance(route, dict) or not isinstance(runtime, dict):
        raise ValueError(f"unsupported runtime receipt: {path}")
    rows = runtime.get("loader_records", [])
    if not isinstance(rows, list):
        rows = []
    receipts: list[dict[str, object]] = []
    for row in rows[:MAX_LOADER_RECEIPTS_PER_ROUTE]:
        if not isinstance(row, dict):
            continue
        index = _as_int(row.get("loader_index"))
        if index is None:
            continue
        static = by_index.get(index)
        buffer = row.get("buffer", {})
        if not isinstance(buffer, dict):
            buffer = {}
        runtime_source = row.get("source_pointer")
        static_source = static.get("source_pointer") if static else None
        runtime_hash = buffer.get("buffer_sha256")
        static_hash = static.get("output_hash") if static else None
        receipts.append({
            "string_id": static.get("string_id") if static else f"afej.ptr.{index:04d}",
            "table_index": index,
            "caller_callsite": row.get("caller_callsite"),
            "caller_lr": row.get("caller_lr"),
            "runtime_source_pointer": runtime_source,
            "static_source_pointer": static_source,
            "source_pointer_matches_static": bool(static and runtime_source == static_source),
            "runtime_output_hash": runtime_hash,
            "static_output_hash": static_hash,
            "output_hash_matches_static": bool(static and runtime_hash == static_hash),
            "scene_or_content_category": "unknown",
            "category_inferred_from_index_or_route": False,
            "raw_bytes_emitted": False,
        })
    return {
        "report": path.name,
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "loader_receipts": receipts,
        "scene_or_content_category": "unknown",
        "category_inferred_from_index_or_route": False,
        "raw_bytes_emitted": False,
    }


def _caller_groups(routes: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, Any]] = collections.defaultdict(
        lambda: {"indices": set(), "routes": set(), "receipts": []}
    )
    for route in routes:
        receipts = route.get("loader_receipts", [])
        if not isinstance(receipts, list):
            continue
        for receipt in receipts:
            if not isinstance(receipt, dict):
                continue
            caller = str(receipt.get("caller_callsite") or "unknown")
            group = grouped[caller]
            group["indices"].add(receipt.get("table_index"))
            group["routes"].add(route.get("route_name"))
            group["receipts"].append(receipt)
    output = []
    for caller, group in sorted(grouped.items()):
        receipts = group["receipts"]
        output.append({
            "caller_callsite": caller,
            "observed_indices": sorted(index for index in group["indices"] if isinstance(index, int)),
            "route_count": len({route for route in group["routes"] if route is not None}),
            "receipt_count": len(receipts),
            "source_pointer_static_match_count": sum(
                bool(receipt["source_pointer_matches_static"]) for receipt in receipts
            ),
            "output_hash_static_match_count": sum(
                bool(receipt["output_hash_matches_static"]) for receipt in receipts
            ),
            "scene_or_content_category": "unknown",
            "category_inferred_from_caller": False,
            "raw_bytes_emitted": False,
        })
    return output


def build_report(rom_path: Path, runtime_paths: tuple[Path, ...] = ()) -> dict[str, object]:
    rom = m110.load_rom(rom_path)
    game_code = rom.data[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = hashlib.sha256(rom.data).hexdigest()
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")
    census = m110.build_census(rom)
    records = census.get("records", [])
    if not isinstance(records, list):
        raise ValueError("M1.10 census records are not a list")
    by_index = {
        int(row["table_index"]): row
        for row in records
        if isinstance(row, dict) and isinstance(row.get("table_index"), int)
    }
    routes = [_route_join(path, by_index) for path in runtime_paths]
    receipts = [
        receipt
        for route in routes
        for receipt in route["loader_receipts"]
        if isinstance(receipt, dict)
    ]
    observed_indices = sorted({receipt["table_index"] for receipt in receipts})
    observed_callers = sorted({str(receipt.get("caller_callsite") or "unknown") for receipt in receipts})
    category_gate = {
        "table_domain": "[0,3342)",
        "strict_record_count": census["table"]["strictly_supported_record_count"],
        "decoder_failure_count": census["table"]["decoder_failure_count"],
        "natural_route_count": len(routes),
        "natural_loader_receipt_count": len(receipts),
        "natural_unique_table_index_count": len(observed_indices),
        "natural_unique_caller_count": len(observed_callers),
        "natural_indices": observed_indices,
        "natural_callers": observed_callers,
        "caller_or_scene_evidence_present": bool(receipts),
        "content_categories_assigned": [],
        "unassigned_category_reason": "no_independent_scene_or_content_label_receipt",
        "index_adjacency_used_as_category_evidence": False,
        "route_name_used_as_category_evidence": False,
        "translation_ready": False,
        "raw_bytes_emitted": False,
    }
    return {
        "schema": "afej-m132-content-gate-v1",
        "rom": {"game_code": game_code, "size": len(rom.data), "sha256": rom_sha256},
        "table": {
            "pointer_table": census["table"]["pointer_table"],
            "domain_start": census["table"]["domain_start"],
            "domain_end_exclusive": census["table"]["domain_end_exclusive"],
            "record_count": census["table"]["record_count"],
            "strictly_supported_record_count": census["table"]["strictly_supported_record_count"],
            "decoder_failure_count": census["table"]["decoder_failure_count"],
            "all_source_spans_match_next_entry": census["table"]["all_source_spans_match_next_entry"],
            "hash_only_table_digest": _table_digest(census),
            "records": records,
            "decoder_failures": census["decoder_failures"],
            "source_bytes_emitted": False,
            "code_unit_bytes_emitted": False,
        },
        "runtime_input": [str(path) for path in runtime_paths] if runtime_paths else [],
        "runtime": {
            "routes": routes,
            "caller_groups": _caller_groups(routes),
            "natural_loader_receipt_count": len(receipts),
            "source_pointer_static_match_count": sum(
                bool(receipt["source_pointer_matches_static"]) for receipt in receipts
            ),
            "output_hash_static_match_count": sum(
                bool(receipt["output_hash_matches_static"]) for receipt in receipts
            ),
            "scene_or_content_category": "unknown",
            "raw_bytes_emitted": False,
        },
        "category_gate": category_gate,
        "status": {
            "worker": "3203_strict_records_139_explicit_decoder_negative",
            "caller_provenance": "natural_receipts_joined_when_supplied",
            "scene_or_content_category": "unknown",
            "codepage": "shift_jis_candidate_only",
            "unicode_identity_confirmed": False,
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--runtime-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_report(args.rom, tuple(args.runtime_report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"records={result['table']['record_count']}")
    print(f"strict_records={result['table']['strictly_supported_record_count']}")
    print(f"decoder_failures={result['table']['decoder_failure_count']}")
    print(f"natural_receipts={result['runtime']['natural_loader_receipt_count']}")
    print(f"content_categories_assigned={len(result['category_gate']['content_categories_assigned'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
