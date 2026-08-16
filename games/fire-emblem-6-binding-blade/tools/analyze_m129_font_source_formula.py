#!/usr/bin/env python3
"""Census the reviewed FE6 map-index to font-source address formula.

The composer computes a source address from the observed glyph/map index.  This
tool re-checks the relevant Thumb literals, resolves that formula for the
bounded 121-entry map domain, and joins only map-index hashes from ignored
runtime receipts.  It does not claim that a computed address is a complete
font pool, and it never emits bitmap/source bytes or Unicode text.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from trace_m19_glyph_sink import _capstone_instructions


ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
MAP_BASE = 0x08691644
MAP_SCAN_LIMIT = 0x800
COMPOSER_ENTRY = 0x08099424
COMPOSER_END = 0x0809946C
SOURCE_BASE_LITERAL_ADDRESS = 0x08099478
DESTINATION_BASE_LITERAL_ADDRESS = 0x08099474
CONFIG_LITERAL_ADDRESS = 0x0809946C
OFFSET_MASK_LITERAL_ADDRESS = 0x08099470
SOURCE_BASE = 0x02000000
DESTINATION_BASE = 0x06010000
CONFIG_ADDRESS = 0x02002800
OFFSET_MASK = 0x3FF
RUNTIME_SOURCE_CANDIDATE = 0x020020C0
RUNTIME_DESTINATION_CANDIDATE = 0x06014000


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


def _u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError(f"ROM address outside image: {_hex(address)}")
    return int.from_bytes(rom[offset:offset + 4], "little")


def _instruction(rows: list[dict[str, object]], address: int) -> str:
    for row in rows:
        if int(row["address"]) == address:
            return f"{_hex(address)}: {row['mnemonic']} {row['op_str']}".rstrip()
    raise ValueError(f"missing instruction at {_hex(address)}")


def _map_count_and_span(rom: bytes) -> tuple[int, int, str]:
    start = MAP_BASE - ROM_BASE
    terminator: Optional[int] = None
    count = 0
    for offset in range(0, MAP_SCAN_LIMIT, 2):
        pair = rom[start + offset:start + offset + 2]
        if len(pair) != 2:
            break
        if pair == b"\x00\x00":
            terminator = MAP_BASE + offset
            break
        count += 1
    if terminator is None:
        raise ValueError("map terminator not found")
    span = rom[start:terminator - ROM_BASE + 2]
    return count, terminator, _sha256(span)


def source_offset_for_map_index(map_index: int) -> int:
    if not 0 <= map_index < 0x100:
        raise ValueError("map index formula is bounded to an 8-bit glyph index")
    packed = (map_index & 0x0F) * 2
    packed += (map_index & 0xF0) << 2
    return (packed & OFFSET_MASK) << 5


def _static_contract(rom: bytes) -> dict[str, object]:
    rows = _capstone_instructions(rom, COMPOSER_ENTRY, COMPOSER_END)
    literal_values = {
        "source_base": _u32(rom, SOURCE_BASE_LITERAL_ADDRESS),
        "destination_base": _u32(rom, DESTINATION_BASE_LITERAL_ADDRESS),
        "config_address": _u32(rom, CONFIG_LITERAL_ADDRESS),
        "offset_mask": _u32(rom, OFFSET_MASK_LITERAL_ADDRESS),
    }
    expected = {
        "source_base": SOURCE_BASE,
        "destination_base": DESTINATION_BASE,
        "config_address": CONFIG_ADDRESS,
        "offset_mask": OFFSET_MASK,
    }
    if literal_values != expected:
        raise ValueError(f"composer literal drift: {literal_values}")
    expected_instructions = {
        0x08099430: "0x08099430: ands r1, r5",
        0x08099436: "0x08099436: ands r0, r4",
        0x08099444: "0x08099444: ands r1, r3",
        0x08099458: "0x08099458: ands r0, r3",
    }
    instruction_rows = {
        _hex(address): _instruction(rows, address)
        for address in expected_instructions
    }
    if instruction_rows != {_hex(address): text for address, text in expected_instructions.items()}:
        raise ValueError("composer map-index address instruction topology drifted")
    count, terminator, span_hash = _map_count_and_span(rom)
    return {
        "composer_entry": _hex(COMPOSER_ENTRY),
        "composer_code_sha256": _sha256(rom[COMPOSER_ENTRY - ROM_BASE:COMPOSER_END - ROM_BASE]),
        "literal_values": {key: _hex(value) for key, value in literal_values.items()},
        "instruction_assertions": instruction_rows,
        "map_base": _hex(MAP_BASE),
        "map_entry_count": count,
        "map_terminator": _hex(terminator),
        "map_span_sha256": span_hash,
        "source_formula": "source_base + ((((index & 0x0f) * 2) + ((index & 0xf0) << 2)) & 0x3ff) << 5",
        "destination_formula": "destination_base + ((config_value_derived & 0x3ff) << 5)",
        "semantic_name_assigned": False,
    }


def _formula_rows(count: int) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        offset = source_offset_for_map_index(index)
        rows.append({
            "map_index": index,
            "source_offset": _hex(offset),
            "source_address": _hex(SOURCE_BASE + offset),
            "semantic_name_assigned": False,
        })
    return rows


def _runtime_summary(path: Path, formula_by_index: dict[int, dict[str, object]]) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    route = report.get("route", {})
    runtime = report.get("runtime", {})
    if not isinstance(route, dict) or not isinstance(runtime, dict):
        raise ValueError(f"unsupported runtime report: {path}")
    lookup_rows = runtime.get("lookup_receipts", [])
    if not isinstance(lookup_rows, list):
        lookup_rows = []
    observed: list[dict[str, object]] = []
    for row in lookup_rows[:32]:
        if not isinstance(row, dict):
            continue
        input_row = row.get("input", {})
        if not isinstance(input_row, dict):
            input_row = {}
        index = _int(row.get("map_index"))
        if index is None or index not in formula_by_index:
            continue
        formula = formula_by_index[index]
        observed.append({
            "input_pointer": input_row.get("input_pointer"),
            "input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
            "map_index": index,
            "glyph_index": row.get("glyph_index"),
            "source_formula_address": formula["source_address"],
            "source_formula_resolved": True,
            "renderer_source_address_observed": False,
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
        "observed_lookup_count": len(observed),
        "observed_map_indices": sorted({row["map_index"] for row in observed}),
        "formula_resolved_count": sum(row["source_formula_resolved"] for row in observed),
        "renderer_entry_count": len(renderer_entries),
        "writer_receipt_count": len(writer_receipts),
        "renderer_source_address_observed": bool(renderer_entries),
        "same_run_writer_pairing_confirmed": bool(writer_receipts),
        "observed": observed,
        "scene_or_content_category": "unknown",
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
    static = _static_contract(rom)
    formula_rows = _formula_rows(int(static["map_entry_count"]))
    formula_by_index = {row["map_index"]: row for row in formula_rows}
    routes = [_runtime_summary(path, formula_by_index) for path in runtime_paths]
    return {
        "schema": "afej-m129-font-source-formula-v1",
        "rom": {"game_code": game_code, "size": len(rom), "sha256": rom_sha256},
        "static": static,
        "font_source_formula_rows": formula_rows,
        "runtime": {
            "route_count": len(routes),
            "routes": routes,
            "observed_lookup_count": sum(route["observed_lookup_count"] for route in routes),
            "formula_resolved_count": sum(route["formula_resolved_count"] for route in routes),
            "renderer_source_address_observed": any(route["renderer_source_address_observed"] for route in routes),
            "same_run_writer_pairing_confirmed": any(route["same_run_writer_pairing_confirmed"] for route in routes),
            "source_address_bytes_observed": False,
            "scene_or_content_category": "unknown",
        },
        "status": {
            "font_source_address_formula": "static_candidate",
            "font_identity_confirmed": False,
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
    print(f"map_entries={result['static']['map_entry_count']}")
    print(f"formula_rows={len(result['font_source_formula_rows'])}")
    print(f"runtime_formula_resolved={result['runtime']['formula_resolved_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
