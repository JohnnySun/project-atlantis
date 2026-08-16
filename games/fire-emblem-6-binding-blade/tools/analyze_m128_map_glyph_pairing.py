#!/usr/bin/env python3
"""Join bounded FE6 map-index and glyph-field receipts without raw text.

M1.28 uses the two ignored M1.19 natural receipts to make the map-index to
glyph-object relation deterministic and reproducible.  Only code-unit hashes
are retained; the actual two-byte units, source text, bitmap data and RAM
bytes are never emitted.  A missing downstream renderer/writer remains an
explicit negative rather than being inferred from the glyph index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
MAP_BASE = 0x08691644
MAP_SCAN_LIMIT = 0x800
GLYPH_FIELD_OFFSET = 0x4A


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


def _map_info(rom: bytes) -> dict[str, object]:
    start = MAP_BASE - ROM_BASE
    pairs: list[bytes] = []
    terminator: Optional[int] = None
    for offset in range(0, MAP_SCAN_LIMIT, 2):
        pair = rom[start + offset:start + offset + 2]
        if len(pair) != 2:
            break
        if pair == b"\x00\x00":
            terminator = MAP_BASE + offset
            break
        pairs.append(pair)
    if terminator is None:
        raise ValueError("AFEJ map terminator not found")
    span = rom[start:terminator - ROM_BASE + 2]
    return {
        "map_base": _hex(MAP_BASE),
        "entry_count": len(pairs),
        "terminator_address": _hex(terminator),
        "span_length": len(span),
        "span_sha256": _sha256(span),
        "entry_pointer_formula": "map_base + map_index * 2",
        "raw_bytes_emitted": False,
    }


def _lookup_summary(row: dict[str, object]) -> Optional[dict[str, object]]:
    input_row = row.get("input")
    if not isinstance(input_row, dict):
        return None
    map_index = _int(row.get("map_index"))
    glyph_index = _int(row.get("glyph_index"))
    if map_index is None or glyph_index is None:
        return None
    return {
        "input_pointer": input_row.get("input_pointer"),
        "input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
        "map_base": input_row.get("map_base"),
        "map_index": map_index,
        "map_entry_pointer": row.get("map_entry_pointer"),
        "glyph_index": glyph_index,
        "lookup_instruction": row.get("lookup_instruction"),
        "semantic_name_assigned": False,
    }


def _glyph_summary(row: dict[str, object]) -> Optional[dict[str, object]]:
    input_row = row.get("input_lookup")
    if not isinstance(input_row, dict):
        return None
    glyph_index = _int(row.get("glyph_index"))
    if glyph_index is None:
        return None
    return {
        "input_pointer": input_row.get("input_pointer"),
        "input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
        "glyph_index": glyph_index,
        "field_address": row.get("field_address"),
        "field_offset": row.get("field_offset"),
        "object_base_if_layout": row.get("object_base_if_layout"),
        "semantic_name_assigned": False,
    }


def _route_report(path: Path, map_entry_count: int) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    route = report.get("route", {})
    runtime = report.get("runtime", {})
    if not isinstance(route, dict) or not isinstance(runtime, dict):
        raise ValueError(f"unsupported runtime report: {path}")
    lookups = runtime.get("lookup_receipts", [])
    glyphs = runtime.get("glyph_field_receipts", [])
    if not isinstance(lookups, list):
        lookups = []
    if not isinstance(glyphs, list):
        glyphs = []
    lookup_rows = [
        summary
        for row in lookups[:32]
        if isinstance(row, dict)
        for summary in [_lookup_summary(row)]
        if summary is not None
    ]
    glyph_rows = [
        summary
        for row in glyphs[:32]
        if isinstance(row, dict)
        for summary in [_glyph_summary(row)]
        if summary is not None
    ]
    glyph_by_key = {
        (row.get("input_pointer"), row.get("input_code_unit_sha256")): row
        for row in glyph_rows
    }
    pairs: list[dict[str, object]] = []
    for lookup in lookup_rows:
        key = (lookup.get("input_pointer"), lookup.get("input_code_unit_sha256"))
        glyph = glyph_by_key.get(key)
        if glyph is None:
            continue
        map_index = int(lookup["map_index"])
        map_entry = _int(str(lookup.get("map_entry_pointer")))
        expected_entry = MAP_BASE + map_index * 2
        pairs.append({
            "input_pointer": lookup.get("input_pointer"),
            "input_code_unit_sha256": lookup.get("input_code_unit_sha256"),
            "map_index": map_index,
            "map_entry_pointer": lookup.get("map_entry_pointer"),
            "map_entry_pointer_matches_formula": map_entry == expected_entry,
            "glyph_index": lookup["glyph_index"],
            "glyph_index_matches_map_index": lookup["glyph_index"] == glyph["glyph_index"],
            "glyph_field_address": glyph.get("field_address"),
            "glyph_field_offset": glyph.get("field_offset"),
            "object_base_if_layout": glyph.get("object_base_if_layout"),
            "semantic_name_assigned": False,
        })
    renderer_entries = runtime.get("renderer_entries", [])
    if not isinstance(renderer_entries, list):
        renderer_entries = []
    writer_receipts = runtime.get("writer_receipts", [])
    if not isinstance(writer_receipts, list):
        writer_receipts = []
    return {
        "report": path.name,
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "input_sequence": route.get("sequence"),
        "lookup_receipt_count": len(lookup_rows),
        "glyph_field_receipt_count": len(glyph_rows),
        "paired_receipt_count": len(pairs),
        "map_entry_formula_equal_count": sum(row["map_entry_pointer_matches_formula"] for row in pairs),
        "map_glyph_equal_count": sum(row["glyph_index_matches_map_index"] for row in pairs),
        "map_entry_count": map_entry_count,
        "pairs": pairs,
        "renderer_entry_count": len(renderer_entries),
        "writer_receipt_count": len(writer_receipts),
        "font_source_pairing_observed": bool(renderer_entries or writer_receipts),
        "scene_or_content_category": "unknown",
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_paths: list[Path]) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    game_code = rom[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = _sha256(rom)
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")
    static_map = _map_info(rom)
    routes = [_route_report(path, int(static_map["entry_count"])) for path in runtime_paths]
    return {
        "schema": "afej-m128-map-glyph-pairing-v1",
        "rom": {"game_code": game_code, "size": len(rom), "sha256": rom_sha256},
        "static_map": static_map,
        "routes": routes,
        "comparison": {
            "route_count": len(routes),
            "all_routes_have_8_paired_receipts": all(
                route["paired_receipt_count"] == 8 for route in routes
            ),
            "all_paired_map_entries_match_formula": all(
                route["paired_receipt_count"] == route["map_entry_formula_equal_count"]
                for route in routes
            ),
            "all_paired_map_indices_equal_glyph_indices": all(
                route["paired_receipt_count"] == route["map_glyph_equal_count"]
                for route in routes
            ),
            "font_source_pairing_observed": any(
                route["font_source_pairing_observed"] for route in routes
            ),
            "semantic_name_assigned": False,
            "scene_or_content_category": "unknown",
        },
        "status": {
            "map_to_glyph_object": "bounded_runtime_correspondence",
            "codepage": "shift_jis_candidate_only",
            "unicode_identity_confirmed": False,
            "font_identity_confirmed": False,
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
        result = build_report(args.rom, args.runtime_report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"routes={result['comparison']['route_count']}")
    print(f"all_map_glyph_equal={result['comparison']['all_paired_map_indices_equal_glyph_indices']}")
    print(f"font_source_pairing={result['comparison']['font_source_pairing_observed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
