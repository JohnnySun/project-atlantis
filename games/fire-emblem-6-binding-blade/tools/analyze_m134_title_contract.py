#!/usr/bin/env python3
"""Join the bounded AFEJ title-text and font-source contracts.

M1.34 is the first content-class gate that is independent of table adjacency.
The eight records at 3080..3087 are the natural reset/start receipt's bounded
intro/title resource.  Their two-byte leaf set is exactly the first 80 valid
entries of the ROM map at 0x08691644.  The same 80 indices are the complete
in-bounds domain of the reviewed 0x2800-byte LZ77-expanded source asset when
the four static plane-word reads are applied.

This report stores only hashes, addresses, counts and runtime provenance.  It
does not store code-unit bytes, decoded Japanese, compressed data, expanded
font bytes or bitmap data.  Shift-JIS remains a bounded candidate; the title
class label is provisional until a visual/title receipt is independently
reviewed.  No arbitrary encoder or ROM insertion is enabled here.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import analyze_m129_font_source_formula as m129
import analyze_m131_font_initializer as m131
import extract_afej_m16 as m16


EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)
TITLE_START = 3080
TITLE_COUNT = 8
MAP_BASE = 0x08691644
MAP_EXPECTED_VALID_PREFIX = 80
SOURCE_PLANE_OFFSETS = (0x00, 0x40, 0x80, 0xC0)
SOURCE_WORD_SIZE = 4
SCHEMA = "afej-m134-title-contract-v1"


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


def _looks_like_strict_sjis_pair(pair: bytes) -> bool:
    if len(pair) != 2:
        return False
    lead, trail = pair
    lead_ok = 0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xEF
    trail_ok = 0x40 <= trail <= 0xFC and trail != 0x7F
    if not (lead_ok and trail_ok):
        return False
    try:
        pair.decode("shift_jis")
    except UnicodeDecodeError:
        return False
    return True


def _expand_lz77(rom: bytes) -> bytes:
    """Expand the reviewed source stream, without exposing it in the report."""

    start = m131.SOURCE_ASSET - m131.ROM_BASE
    header = rom[start:start + 4]
    if header[0] != 0x10:
        raise ValueError("font source is not a GBA LZ77 stream")
    expanded_size = header[1] | (header[2] << 8) | (header[3] << 16)
    if expanded_size != m131.EXPANDED_SOURCE_SIZE:
        raise ValueError("font source expanded size drifted")
    expanded = bytearray()
    cursor = 4
    while len(expanded) < expanded_size:
        flags = rom[start + cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(expanded) >= expanded_size:
                break
            if flags & (1 << bit):
                first = rom[start + cursor]
                second = rom[start + cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8) | second
                if displacement + 1 > len(expanded):
                    raise ValueError("font source back-reference exceeds prefix")
                for _ in range(length):
                    expanded.append(expanded[-displacement - 1])
                    if len(expanded) >= expanded_size:
                        break
            else:
                expanded.append(rom[start + cursor])
                cursor += 1
    parsed = m131._parse_lz77(rom)
    if _sha256(bytes(expanded)) != parsed["expanded_payload_sha256"]:
        raise ValueError("font source expansion hash drifted")
    return bytes(expanded)


def _map_entries(rom: bytes) -> tuple[list[bytes], int, str]:
    count, terminator, span_hash = m129._map_count_and_span(rom)
    entries = [
        rom[MAP_BASE - m129.ROM_BASE + index * 2:MAP_BASE - m129.ROM_BASE + index * 2 + 2]
        for index in range(count)
    ]
    return entries, terminator, span_hash


def _title_records(rom: m16.AfejRom) -> tuple[list[dict[str, object]], list[bytes]]:
    table_end = m16.prove_table_end(rom)
    codebook = m16.build_codebook(rom)
    records: list[dict[str, object]] = []
    units: list[bytes] = []
    for index in range(TITLE_START, TITLE_START + TITLE_COUNT):
        record = m16.decode_record(rom, index)
        if index + 1 < table_end:
            next_source = m16.table_entry(rom, index + 1)
            if record.source_end != next_source:
                raise ValueError(f"title source span drifted at index {index}")
        if m16.encode_leaves(record.leaves, codebook) != record.source_bytes:
            raise ValueError(f"title leaf round-trip drifted at index {index}")
        record_units = [leaf.output for leaf in record.leaves if len(leaf.output) == 2]
        units.extend(record_units)
        try:
            b"".join(record_units).decode("shift_jis")
        except UnicodeDecodeError as exc:
            raise ValueError(f"title record is not strict Shift-JIS candidate: {index}") from exc
        records.append({
            "string_id": f"afej.ptr.{index:04d}",
            "table_index": index,
            "source_pointer": _hex(record.source_pointer),
            "source_end": _hex(record.source_end),
            "source_hash": _sha256(record.source_bytes),
            "payload_hash": _sha256(record.output),
            "buffer_hash": _sha256(record.buffer),
            "payload_length": len(record.output),
            "two_byte_code_unit_count": len(record_units),
            "single_byte_leaf_values": sorted({
                leaf.output[0]
                for leaf in record.leaves
                if len(leaf.output) == 1
            }),
            "strict_shift_jis_candidate": True,
            "decode_encode_byte_identical": True,
            "raw_payload_emitted": False,
        })
    return records, units


def _source_slots(expanded: bytes, slot_count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(slot_count):
        offset = m129.source_offset_for_map_index(index)
        words = []
        for plane_offset in SOURCE_PLANE_OFFSETS:
            begin = offset + plane_offset
            end = begin + SOURCE_WORD_SIZE
            if end > len(expanded):
                raise ValueError(f"source slot {index} exceeds expanded font source")
            words.append(expanded[begin:end])
        composite = b"".join(words)
        rows.append({
            "formula_input": index,
            "source_address": _hex(m131.SOURCE_BASE + offset),
            "source_offset": _hex(offset),
            "plane_word_offsets": [_hex(value) for value in SOURCE_PLANE_OFFSETS],
            "plane_word_hashes": [_sha256(word) for word in words],
            "four_plane_word_composite_sha256": _sha256(composite),
            "expanded_source_bounds_valid": True,
            "raw_source_bytes_emitted": False,
        })
    return rows


def _runtime_join(
    paths: tuple[Path, ...],
    title_by_index: dict[int, dict[str, object]],
    map_entries: list[bytes],
    source_slots: list[dict[str, object]],
) -> dict[str, object]:
    slot_by_index = {row["formula_input"]: row for row in source_slots}
    routes: list[dict[str, object]] = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        route = report.get("route", {})
        runtime = report.get("runtime", {})
        if not isinstance(route, dict) or not isinstance(runtime, dict):
            raise ValueError(f"unsupported runtime report: {path}")
        loader_rows = runtime.get("loader_records", [])
        lookup_rows = runtime.get("lookup_receipts", [])
        if not isinstance(loader_rows, list):
            loader_rows = []
        if not isinstance(lookup_rows, list):
            lookup_rows = []
        title_loaders: list[dict[str, object]] = []
        for row in loader_rows[:32]:
            if not isinstance(row, dict):
                continue
            index = _as_int(row.get("loader_index"))
            static = title_by_index.get(index) if index is not None else None
            if static is None:
                continue
            buffer = row.get("buffer", {})
            if not isinstance(buffer, dict):
                buffer = {}
            title_loaders.append({
                "table_index": index,
                "string_id": static["string_id"],
                "caller_callsite": row.get("caller_callsite"),
                "caller_lr": row.get("caller_lr"),
                "source_pointer": row.get("source_pointer"),
                "static_source_pointer": static["source_pointer"],
                "source_pointer_matches_static": row.get("source_pointer") == static["source_pointer"],
                "runtime_buffer_hash": buffer.get("buffer_sha256"),
                "static_buffer_hash": static["buffer_hash"],
                "buffer_hash_matches_static": buffer.get("buffer_sha256") == static["buffer_hash"],
                "logical_terminator_offset": buffer.get("logical_terminator_offset"),
                "control_marker_offsets": {
                    key: value for key, value in buffer.get("control_marker_offsets", {}).items()
                    if key in {"0x00", "0x01", "0x04", "0xff"}
                } if isinstance(buffer.get("control_marker_offsets", {}), dict) else {},
                "natural_reachability": row.get("reachability") == "natural_keyinput",
                "raw_buffer_emitted": False,
            })
        observed: list[dict[str, object]] = []
        for row in lookup_rows[:32]:
            if not isinstance(row, dict):
                continue
            index = _as_int(row.get("map_index"))
            if index is None or not 0 <= index < len(map_entries):
                continue
            input_row = row.get("input", {})
            if not isinstance(input_row, dict):
                input_row = {}
            expected_hash = _sha256(map_entries[index])
            formula = slot_by_index.get(index)
            observed.append({
                "map_index": index,
                "glyph_index": row.get("glyph_index"),
                "map_index_equals_glyph_index": row.get("glyph_index") == index,
                "map_entry_sha256": expected_hash,
                "runtime_input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
                "runtime_input_hash_matches_map": input_row.get("input_code_unit_sha256") == expected_hash,
                "source_formula_address": formula["source_address"] if formula else None,
                "source_four_plane_word_composite_sha256": (
                    formula["four_plane_word_composite_sha256"] if formula else None
                ),
                "font_source_bounds_valid": formula is not None,
                "raw_code_unit_emitted": False,
            })
        display = runtime.get("final_display_io", {})
        routes.append({
            "report": path.name,
            "route_name": route.get("name"),
            "natural_reachability": bool(route.get("natural_reachability")),
            "key_sequence": route.get("sequence", []),
            "title_loader_receipt_count": len(title_loaders),
            "title_loader_receipts": title_loaders,
            "lookup_count_bounded": len(observed),
            "lookup_rows": observed,
            "display_registers_present": isinstance(display, dict) and bool(display),
            "display_registers": display if isinstance(display, dict) else {},
            "renderer_source_bytes_observed": False,
            "writer_receipts_observed": False,
            "scene_or_content_category": "title_splash_bounded_candidate",
            "category_is_provisional": True,
            "raw_payload_emitted": False,
        })
    return {
        "route_count": len(routes),
        "natural_title_loader_receipt_count": sum(
            route["title_loader_receipt_count"]
            for route in routes
            if route["natural_reachability"]
        ),
        "title_loader_source_pointer_match_count": sum(
            receipt["source_pointer_matches_static"]
            for route in routes
            for receipt in route["title_loader_receipts"]
        ),
        "title_loader_buffer_hash_match_count": sum(
            receipt["buffer_hash_matches_static"]
            for route in routes
            for receipt in route["title_loader_receipts"]
        ),
        "lookup_count_bounded": sum(route["lookup_count_bounded"] for route in routes),
        "lookup_map_hash_match_count": sum(
            row["runtime_input_hash_matches_map"]
            for route in routes
            for row in route["lookup_rows"]
        ),
        "lookup_glyph_index_match_count": sum(
            row["map_index_equals_glyph_index"]
            for route in routes
            for row in route["lookup_rows"]
        ),
        "routes": routes,
        "renderer_source_bytes_observed": False,
        "writer_receipts_observed": False,
        "raw_payload_emitted": False,
    }


def build_report(rom_path: Path, runtime_paths: tuple[Path, ...] = ()) -> dict[str, object]:
    rom = m16.load_rom(rom_path)
    title_records, title_units = _title_records(rom)
    map_entries, terminator, map_span_hash = _map_entries(rom.data)
    valid_prefix = 0
    while valid_prefix < len(map_entries) and _looks_like_strict_sjis_pair(map_entries[valid_prefix]):
        valid_prefix += 1
    if valid_prefix != MAP_EXPECTED_VALID_PREFIX:
        raise ValueError(f"title map valid prefix drifted: {valid_prefix}")
    map_prefix = map_entries[:valid_prefix]
    if set(map_prefix) != set(title_units):
        raise ValueError("title code-unit set no longer matches map prefix")
    expanded = _expand_lz77(rom.data)
    source_slots = _source_slots(expanded, valid_prefix)
    static_lz77 = m131._parse_lz77(rom.data)
    title_by_index = {row["table_index"]: row for row in title_records}
    runtime = _runtime_join(runtime_paths, title_by_index, map_entries, source_slots) if runtime_paths else None
    source_stride_histogram = collections.Counter(
        m129.source_offset_for_map_index(index + 1) - m129.source_offset_for_map_index(index)
        for index in range(valid_prefix - 1)
    )
    decoded_utf8_hash = _sha256(
        b"".join(title_units).decode("shift_jis").encode("utf-8")
    )
    return {
        "schema": SCHEMA,
        "rom": {
            "game_code": rom.data[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom.data),
            "sha256": _sha256(rom.data),
        },
        "content_class_gate": {
            "label": "title_splash_bounded_candidate",
            "basis": [
                "natural_start_a_loader_receipt_for_index_3087",
                "bounded_records_3080_3087_strict_shift_jis_candidate",
                "map_prefix_set_equals_all_bounded_code_units",
                "map_prefix_is_complete_in_bounds_font_source_domain",
            ],
            "category_assigned": True,
            "category_is_provisional": True,
            "index_adjacency_used_as_category_evidence": False,
            "decoded_source_emitted": False,
        },
        "title_records": {
            "table_domain": "[3080,3088)",
            "records": title_records,
            "record_count": len(title_records),
            "strict_shift_jis_candidate_count": len(title_records),
            "two_byte_code_unit_count": len(title_units),
            "unique_code_unit_count": len(set(title_units)),
            "decoded_utf8_sha256": decoded_utf8_hash,
            "map_prefix_set_equal": True,
            "single_byte_leaf_values": sorted({
                value
                for row in title_records
                for value in row["single_byte_leaf_values"]
            }),
            "raw_code_units_emitted": False,
            "decoded_source_emitted": False,
        },
        "map_contract": {
            "base": _hex(MAP_BASE),
            "terminator": _hex(terminator),
            "full_span_sha256": map_span_hash,
            "full_entry_count": len(map_entries),
            "valid_sjis_prefix_count": valid_prefix,
            "prefix_sha256": _sha256(b"".join(map_prefix)),
            "prefix_unique_entry_count": len(set(map_prefix)),
            "prefix_set_equals_title_code_units": True,
            "match_runtime_lookup_at": "0x080992f6",
            "runtime_input_bytes_emitted": False,
        },
        "font_source_contract": {
            "initializer": "0x08098aee -> 0x08099404",
            "source_asset": _hex(m131.SOURCE_ASSET),
            "destination_base": _hex(m131.SOURCE_BASE),
            "expanded_size": static_lz77["expanded_size"],
            "expanded_payload_sha256": static_lz77["expanded_payload_sha256"],
            "source_plane_offsets": [_hex(value) for value in SOURCE_PLANE_OFFSETS],
            "source_word_size": SOURCE_WORD_SIZE,
            "formula_input_domain": f"[0,{valid_prefix})",
            "formula_input_bounds_valid_count": len(source_slots),
            "formula_input_bounds_invalid_count": 0,
            "source_offset_stride_histogram": {
                _hex(stride): count for stride, count in sorted(source_stride_histogram.items())
            },
            "source_slots": source_slots,
            "unique_four_plane_composite_hash_count": len({
                row["four_plane_word_composite_sha256"] for row in source_slots
            }),
            "source_bytes_emitted": False,
            "raw_bitmap_emitted": False,
        },
        "runtime": runtime,
        "status": {
            "title_class": "bounded_provisional",
            "font_source_contract": "80_in_bounds_four_plane_word_slots",
            "font_identity_confirmed": False,
            "unicode_identity_confirmed": False,
            "codepage": "shift_jis_bounded_title_candidate",
            "control_semantics": "opaque",
            "translation_ready": False,
            "arbitrary_text_encode_enabled": False,
            "rom_insertion_enabled": False,
            "raw_payload_emitted": False,
        },
        "raw_payload_emitted": False,
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
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"title_records={result['title_records']['record_count']}")
    print(f"title_code_units={result['title_records']['two_byte_code_unit_count']}")
    print(f"map_valid_prefix={result['map_contract']['valid_sjis_prefix_count']}")
    print(f"font_source_slots={len(result['font_source_contract']['source_slots'])}")
    if result["runtime"] is not None:
        print(f"natural_title_loaders={result['runtime']['natural_title_loader_receipt_count']}")
        print(f"runtime_lookup_hash_matches={result['runtime']['lookup_map_hash_match_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
