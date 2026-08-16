#!/usr/bin/env python3
"""Census the reviewed AFEJ source-address layout and code-unit gate.

M1.30 keeps two questions separate:

* the already proven map-index formula has a deterministic address layout;
* the bounded worker cohort is structurally round-trippable and strictly
  compatible with a Shift-JIS decoder candidate.

The first result is an address-only formula census, not a font-byte proof.
The second is a readiness gate for opaque code units, not Unicode identity.
The report never emits source bytes, decoded Japanese, bitmap bytes, or a
translation ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

import analyze_m129_font_source_formula as m129
import extract_m123_bounded_corpus as m123


ROM_SIZE = 0x800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)
DEFAULT_WINDOWS = ((2672, 16), (3080, 16))
MAX_WINDOW_COUNT = 32
MAX_RUNTIME_LOOKUPS = 32


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _int(value: object) -> Optional[int]:
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


def _parse_window(value: str) -> tuple[int, int]:
    try:
        start_text, count_text = value.split(":", 1)
        start = int(start_text, 0)
        count = int(count_text, 0)
    except (TypeError, ValueError):
        raise ValueError(f"window must be START:COUNT, got {value!r}") from None
    if start < 0 or count <= 0 or count > MAX_WINDOW_COUNT:
        raise ValueError("window must be non-empty and contain at most 32 records")
    return start, count


def _record_sequence_hash(records: Iterable[dict[str, object]]) -> str:
    sequence = [
        {
            "table_index": record.get("table_index"),
            "source_hash": record.get("source_hash"),
            "output_hash": record.get("output_hash"),
        }
        for record in records
    ]
    return _sha256(json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _formula_layout(map_entry_count: int) -> dict[str, object]:
    rows = []
    offsets: list[int] = []
    for index in range(map_entry_count):
        offset = m129.source_offset_for_map_index(index)
        offsets.append(offset)
        rows.append({
            "map_index": index,
            "formula_bank": index >> 4,
            "formula_slot": index & 0x0F,
            "source_offset": _hex(offset),
            "source_address": _hex(m129.SOURCE_BASE + offset),
            "semantic_name_assigned": False,
        })

    collisions: dict[int, list[int]] = defaultdict(list)
    for index, offset in enumerate(offsets):
        collisions[offset].append(index)
    collision_groups = [
        {"source_offset": _hex(offset), "map_indices": indices}
        for offset, indices in sorted(collisions.items())
        if len(indices) > 1
    ]

    consecutive_strides = Counter(
        right - left for left, right in zip(offsets, offsets[1:])
    )
    banks: list[dict[str, object]] = []
    for bank in sorted({index >> 4 for index in range(map_entry_count)}):
        bank_rows = [row for row in rows if row["formula_bank"] == bank]
        bank_offsets = [int(row["source_offset"], 16) for row in bank_rows]
        banks.append({
            "formula_bank": bank,
            "map_index_start": bank_rows[0]["map_index"],
            "map_index_end_inclusive": bank_rows[-1]["map_index"],
            "slot_count": len(bank_rows),
            "source_offset_start": _hex(min(bank_offsets)),
            "source_offset_end": _hex(max(bank_offsets)),
            "source_address_start": _hex(m129.SOURCE_BASE + min(bank_offsets)),
            "source_address_end": _hex(m129.SOURCE_BASE + max(bank_offsets)),
            "within_bank_stride_counts": dict(Counter(
                right - left for left, right in zip(bank_offsets, bank_offsets[1:])
            )),
            "semantic_name_assigned": False,
        })

    return {
        "map_entry_count": map_entry_count,
        "source_base": _hex(m129.SOURCE_BASE),
        "source_offset_min": _hex(min(offsets)) if offsets else None,
        "source_offset_max": _hex(max(offsets)) if offsets else None,
        "unique_source_address_count": len(set(offsets)),
        "source_address_collision_group_count": len(collision_groups),
        "source_address_collision_groups": collision_groups,
        "consecutive_source_offset_stride_counts": {
            _hex(stride): count for stride, count in sorted(consecutive_strides.items())
        },
        "formula_bank_count": len(banks),
        "formula_banks": banks,
        "rows": rows,
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def _code_unit_gate(rom_path: Path, windows: tuple[tuple[int, int], ...]) -> dict[str, object]:
    window_reports: list[dict[str, object]] = []
    all_records: list[dict[str, object]] = []
    seen_indices: set[int] = set()
    for start, count in windows:
        if seen_indices.intersection(range(start, start + count)):
            raise ValueError("code-unit windows must be disjoint")
        report = m123.build_report(rom_path, start=start, count=count)
        cohort = report["cohort"]
        records = report["records"]
        failures = report["failures"]
        seen_indices.update(range(start, start + count))
        all_records.extend(records)
        strict_count = sum(
            bool(record["codepage_candidate"]["strict_decode"])
            for record in records
        )
        roundtrip_count = sum(
            bool(record["decode_encode_byte_identical"])
            for record in records
        )
        marker_occurrence_counts = Counter()
        marker_record_counts = Counter()
        for record in records:
            for marker, offsets in record["control_marker_offsets"].items():
                marker_occurrence_counts[marker] += len(offsets)
                marker_record_counts[marker] += bool(offsets)
        window_reports.append({
            "start": start,
            "count_requested": count,
            "count_extracted": cohort["count_extracted"],
            "count_failed": cohort["count_failed"],
            "strict_shift_jis_candidate_record_count": strict_count,
            "decode_encode_byte_identical_count": roundtrip_count,
            "total_code_unit_count": sum(
                record["codepage_candidate"]["code_unit_count"]
                for record in records
            ),
            "record_sequence_sha256": _record_sequence_hash(records),
            "marker_occurrence_counts": {
                marker: marker_occurrence_counts[marker]
                for marker in ("0x00", "0x01", "0x04", "0xff")
            },
            "marker_record_counts": {
                marker: marker_record_counts[marker]
                for marker in ("0x00", "0x01", "0x04", "0xff")
            },
            "strict_shift_jis_candidate_all_records": strict_count == len(records) and not failures,
            "decode_encode_all_records": roundtrip_count == len(records) and not failures,
            "scene_or_content_category": "unknown",
            "raw_bytes_emitted": False,
        })

    return {
        "windows": window_reports,
        "unique_record_count": len(all_records),
        "strict_shift_jis_candidate_record_count": sum(
            bool(record["codepage_candidate"]["strict_decode"])
            for record in all_records
        ),
        "decode_encode_byte_identical_count": sum(
            bool(record["decode_encode_byte_identical"])
            for record in all_records
        ),
        "total_code_unit_count": sum(
            record["codepage_candidate"]["code_unit_count"]
            for record in all_records
        ),
        "strict_shift_jis_candidate_all_records": all(
            bool(record["codepage_candidate"]["strict_decode"])
            for record in all_records
        ),
        "decode_encode_all_records": all(
            bool(record["decode_encode_byte_identical"])
            for record in all_records
        ),
        "unicode_identity_confirmed": False,
        "translation_ready": False,
        "raw_bytes_emitted": False,
    }


def _runtime_join(
    runtime_paths: Iterable[Path],
    rows_by_index: dict[int, dict[str, object]],
) -> dict[str, object]:
    reports: list[dict[str, object]] = []
    for path in runtime_paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        runtime = report.get("runtime", {})
        route = report.get("route", {})
        if not isinstance(runtime, dict) or not isinstance(route, dict):
            raise ValueError(f"unsupported runtime report: {path}")
        lookups = runtime.get("lookup_receipts", [])
        if not isinstance(lookups, list):
            lookups = []
        observed = []
        for lookup in lookups[:MAX_RUNTIME_LOOKUPS]:
            if not isinstance(lookup, dict):
                continue
            index = _int(lookup.get("map_index"))
            row = rows_by_index.get(index) if index is not None else None
            if row is None:
                continue
            input_row = lookup.get("input", {})
            if not isinstance(input_row, dict):
                input_row = {}
            observed.append({
                "map_index": index,
                "glyph_index": lookup.get("glyph_index"),
                "input_pointer": input_row.get("input_pointer"),
                "input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
                "formula_bank": row["formula_bank"],
                "formula_slot": row["formula_slot"],
                "source_formula_address": row["source_address"],
                "source_formula_resolved": True,
                "source_address_bytes_observed": False,
                "semantic_name_assigned": False,
            })
        renderer_entries = runtime.get("renderer_entries", [])
        writer_receipts = runtime.get("writer_receipts", [])
        reports.append({
            "report": path.name,
            "route_name": route.get("name"),
            "natural_reachability": route.get("natural_reachability"),
            "lookup_count_bounded": len(observed),
            "formula_resolved_count": sum(
                bool(row["source_formula_resolved"]) for row in observed
            ),
            "observed_formula_banks": sorted({row["formula_bank"] for row in observed}),
            "observed": observed,
            "renderer_entry_count": len(renderer_entries) if isinstance(renderer_entries, list) else 0,
            "writer_receipt_count": len(writer_receipts) if isinstance(writer_receipts, list) else 0,
            "source_address_bytes_observed": False,
            "same_run_writer_pairing_confirmed": False,
            "scene_or_content_category": "unknown",
            "raw_bytes_emitted": False,
        })
    return {
        "route_count": len(reports),
        "lookup_count_bounded": sum(row["lookup_count_bounded"] for row in reports),
        "formula_resolved_count": sum(row["formula_resolved_count"] for row in reports),
        "source_address_bytes_observed": False,
        "same_run_writer_pairing_confirmed": False,
        "routes": reports,
        "scene_or_content_category": "unknown",
        "raw_bytes_emitted": False,
    }


def build_report(
    rom_path: Path,
    *,
    windows: tuple[tuple[int, int], ...] = DEFAULT_WINDOWS,
    runtime_paths: tuple[Path, ...] = (),
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    game_code = rom[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = _sha256(rom)
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")

    static = m129._static_contract(rom)
    layout = _formula_layout(int(static["map_entry_count"]))
    rows_by_index = {row["map_index"]: row for row in layout["rows"]}
    gate = _code_unit_gate(rom_path, windows)
    runtime = _runtime_join(runtime_paths, rows_by_index) if runtime_paths else None
    return {
        "schema": "afej-m130-source-layout-v1",
        "rom": {
            "game_code": game_code,
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "static": {
            "map_base": static["map_base"],
            "map_entry_count": static["map_entry_count"],
            "map_terminator": static["map_terminator"],
            "map_span_sha256": static["map_span_sha256"],
            "source_formula": static["source_formula"],
            "literal_values": static["literal_values"],
            "layout": layout,
            "source_address_bytes_observed": False,
        },
        "code_unit_gate": gate,
        "runtime_input": [str(path) for path in runtime_paths] if runtime_paths else [],
        "runtime": runtime,
        "status": {
            "source_address_layout": "static_formula_census",
            "font_pool_bytes_observed": False,
            "font_identity_confirmed": False,
            "codepage": "shift_jis_candidate_only",
            "unicode_identity_confirmed": False,
            "translation_ready": False,
            "scene_or_content_category": "unknown",
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--window",
        action="append",
        default=[],
        help="bounded worker window START:COUNT; defaults to 2672:16 and 3080:16",
    )
    parser.add_argument("--runtime-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        windows = tuple(_parse_window(value) for value in args.window) or DEFAULT_WINDOWS
        result = build_report(
            args.rom,
            windows=windows,
            runtime_paths=tuple(args.runtime_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"map_entries={result['static']['map_entry_count']}")
    print(f"source_address_collisions={result['static']['layout']['source_address_collision_group_count']}")
    print(f"strict_candidate_records={result['code_unit_gate']['strict_shift_jis_candidate_record_count']}")
    print(f"roundtrip_records={result['code_unit_gate']['decode_encode_byte_identical_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
