#!/usr/bin/env python3
"""Prove the bounded AFEJ font-source initializer and LZ77 contract.

M1.31 follows the composer source base one level upward.  It verifies the
initializer callsite, the ROM source literal, the EWRAM destination literal,
the generic decompression dispatcher and the bounded GBA LZ77 stream.  It
also checks which *mathematical* source-formula inputs fit inside the
decompressed output; map positions outside that range are retained as a
negative result rather than being called font slots.

Only hashes, addresses, instruction assertions and counts are emitted.  The
tool never writes the compressed stream, decompressed source, glyph bytes,
bitmap bytes or decoded text to the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional

import analyze_m129_font_source_formula as m129
from trace_m19_glyph_sink import _capstone_instructions


ROM_BASE = 0x08000000
ROM_SIZE = 0x800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)

INITIALIZER_ENTRY = 0x08099404
INITIALIZER_END = 0x08099418
INITIALIZER_CALLSITE = 0x08098AEE
INITIALIZER_CALLER = 0x08098AD8
DISPATCHER_ENTRY = 0x08013CA4
DISPATCHER_END = 0x08013CDA
DISPATCH_TABLE = 0x085C4D44
DISPATCH_TABLE_LZ77_WRAM_INDEX = 3
DISPATCH_TABLE_LZ77_WRAM_ENTRY = 0x085C4D50
LZ77_WRAM_THUMB_TARGET = 0x0809DCF5
LZ77_WRAM_SVC = 0x11

SOURCE_LITERAL_ADDRESS = 0x08099418
DESTINATION_LITERAL_ADDRESS = 0x0809941C
CONFIG_LITERAL_ADDRESS = 0x08099420
SOURCE_ASSET = 0x0837F478
SOURCE_ASSET_NEXT = 0x08380ECC
SOURCE_BASE = 0x02000000
CONFIG_ADDRESS = 0x02002800
EXPANDED_SOURCE_SIZE = 0x2800
SOURCE_PLANE_OFFSETS = (0x00, 0x40, 0x80, 0xC0)
SOURCE_WORD_SIZE = 4
EXPECTED_COMPRESSED_LENGTH = 0x1A53
EXPECTED_EXPANDED_SHA256 = (
    "141d5ca6563ad2c205a0a050a88332927b40be115db77dade017fd1e559125ff"
)
EXPECTED_COMPRESSED_SHA256 = (
    "37e8c1e254d3156381bf1199dc1ebcef1cf8709125e12556877905c08f194ed6"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:08x}"


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


def _parse_lz77(rom: bytes) -> dict[str, object]:
    """Validate one GBA LZ77 stream without returning its expanded payload."""

    start = SOURCE_ASSET - ROM_BASE
    if start < 0 or start + 4 > len(rom):
        raise ValueError("LZ77 source header is outside the ROM")
    header = rom[start:start + 4]
    if header[0] != 0x10:
        raise ValueError(f"unexpected compression header class: {_hex(header[0])}")
    expanded_size = header[1] | (header[2] << 8) | (header[3] << 16)
    if expanded_size != EXPANDED_SOURCE_SIZE:
        raise ValueError(f"unexpected expanded source size: {_hex(expanded_size)}")

    expanded = bytearray()
    cursor = 4
    while len(expanded) < expanded_size:
        if start + cursor >= len(rom):
            raise ValueError("LZ77 flags exceed ROM")
        flags = rom[start + cursor]
        cursor += 1
        # The GBA BIOS consumes each flag byte most-significant bit first.
        for bit in range(7, -1, -1):
            if len(expanded) >= expanded_size:
                break
            if flags & (1 << bit):
                if start + cursor + 2 > len(rom):
                    raise ValueError("LZ77 back-reference exceeds ROM")
                first = rom[start + cursor]
                second = rom[start + cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8) | second
                if displacement + 1 > len(expanded):
                    raise ValueError("LZ77 back-reference exceeds decoded prefix")
                for _ in range(length):
                    expanded.append(expanded[-displacement - 1])
                    if len(expanded) >= expanded_size:
                        break
            else:
                if start + cursor >= len(rom):
                    raise ValueError("LZ77 literal exceeds ROM")
                expanded.append(rom[start + cursor])
                cursor += 1

    end = SOURCE_ASSET + cursor
    padding_length = SOURCE_ASSET_NEXT - end
    if padding_length != 1:
        raise ValueError(
            "LZ77 source span/padding drifted: "
            f"end={_hex(end)} next={_hex(SOURCE_ASSET_NEXT)}"
        )
    compressed = rom[start:start + cursor]
    return {
        "header_class": _hex(header[0]),
        "expanded_size": expanded_size,
        "compressed_length": cursor,
        "compressed_end_exclusive": _hex(end),
        "next_asset_address": _hex(SOURCE_ASSET_NEXT),
        "alignment_padding_length": padding_length,
        "compressed_span_sha256": _sha256(compressed),
        "expanded_payload_sha256": _sha256(bytes(expanded)),
        "expanded_payload_nonzero_byte_count": sum(value != 0 for value in expanded),
        "expanded_payload_zero_byte_count": expanded.count(0),
        "raw_bytes_emitted": False,
    }


def _initializer_static(rom: bytes) -> dict[str, object]:
    initializer_rows = _capstone_instructions(rom, INITIALIZER_ENTRY, INITIALIZER_END)
    caller_rows = _capstone_instructions(rom, INITIALIZER_CALLER, INITIALIZER_CALLER + 0x20)
    dispatcher_rows = _capstone_instructions(rom, DISPATCHER_ENTRY, DISPATCHER_END)
    expected_initializer = {
        0x08099406: "0x08099406: ldr r0, [pc, #0x10]",
        0x08099408: "0x08099408: ldr r1, [pc, #0x10]",
        0x0809940A: "0x0809940a: bl #0x8013ca4",
        0x0809940E: "0x0809940e: ldr r1, [pc, #0x10]",
        0x08099412: "0x08099412: str r0, [r1]",
    }
    initializer_instructions = {
        _hex(address): _instruction(initializer_rows, address)
        for address in expected_initializer
    }
    if initializer_instructions != {
        _hex(address): text for address, text in expected_initializer.items()
    }:
        raise ValueError("font initializer instruction topology drifted")
    caller_instruction = _instruction(caller_rows, INITIALIZER_CALLSITE)
    if caller_instruction != "0x08098aee: bl #0x8099404":
        raise ValueError("initializer caller BL drifted")

    literal_values = {
        "source_asset": _u32(rom, SOURCE_LITERAL_ADDRESS),
        "destination": _u32(rom, DESTINATION_LITERAL_ADDRESS),
        "config_address": _u32(rom, CONFIG_LITERAL_ADDRESS),
    }
    expected_literals = {
        "source_asset": SOURCE_ASSET,
        "destination": SOURCE_BASE,
        "config_address": CONFIG_ADDRESS,
    }
    if literal_values != expected_literals:
        raise ValueError(f"font initializer literal drifted: {literal_values}")

    dispatch_literals = {
        "destination_limit": _u32(rom, 0x08013CDC),
        "dispatch_table": _u32(rom, 0x08013CE0),
    }
    if dispatch_literals != {"destination_limit": 0x17FFF, "dispatch_table": DISPATCH_TABLE}:
        raise ValueError(f"decompression dispatcher literal drifted: {dispatch_literals}")
    table_entry = _u32(rom, DISPATCH_TABLE_LZ77_WRAM_ENTRY)
    if table_entry != LZ77_WRAM_THUMB_TARGET:
        raise ValueError(f"LZ77 dispatch entry drifted: {_hex(table_entry)}")
    svc_instruction = _instruction(
        _capstone_instructions(rom, 0x0809DCF0, 0x0809DCF8),
        0x0809DCF4,
    )
    if svc_instruction != "0x0809dcf4: svc #0x11":
        raise ValueError("LZ77 WRAM BIOS SVC drifted")
    source_header = rom[SOURCE_ASSET - ROM_BASE:SOURCE_ASSET - ROM_BASE + 4]
    header_class = source_header[0] >> 4
    destination_class = int((SOURCE_BASE + 0xFA000000) > 0x17FFF)
    dispatch_index = ((source_header[0] & 0xF0) >> 3) + destination_class
    if header_class != 1 or dispatch_index != DISPATCH_TABLE_LZ77_WRAM_INDEX:
        raise ValueError("source header does not select the reviewed LZ77 WRAM dispatch row")
    return {
        "initializer_entry": _hex(INITIALIZER_ENTRY),
        "initializer_caller": _hex(INITIALIZER_CALLER),
        "initializer_callsite": caller_instruction,
        "initializer_instructions": initializer_instructions,
        "literal_values": {key: _hex(value) for key, value in literal_values.items()},
        "dispatcher_entry": _hex(DISPATCHER_ENTRY),
        "dispatcher_table": _hex(DISPATCH_TABLE),
        "dispatcher_table_index": dispatch_index,
        "dispatcher_table_entry": _hex(table_entry),
        "dispatcher_svc": svc_instruction,
        "source_header_class": _hex(source_header[0]),
        "source_header_dispatch_class": header_class,
        "destination_class_selector": destination_class,
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def _source_formula_bounds(output_size: int, map_entry_count: int) -> dict[str, object]:
    rows = []
    valid_indices: list[int] = []
    invalid_indices: list[int] = []
    for index in range(map_entry_count):
        offset = m129.source_offset_for_map_index(index)
        last_read_end = offset + max(SOURCE_PLANE_OFFSETS) + SOURCE_WORD_SIZE
        in_bounds = last_read_end <= output_size
        if in_bounds:
            valid_indices.append(index)
        else:
            invalid_indices.append(index)
        rows.append({
            "formula_input": index,
            "source_offset": _hex(offset),
            "source_address": _hex(SOURCE_BASE + offset),
            "last_plane_word_end_offset": _hex(last_read_end),
            "expanded_source_bounds_valid": in_bounds,
            "semantic_name_assigned": False,
        })
    return {
        "input_domain": f"[0,{map_entry_count})",
        "expanded_source_size": output_size,
        "plane_offsets": [_hex(offset) for offset in SOURCE_PLANE_OFFSETS],
        "source_word_size": SOURCE_WORD_SIZE,
        "bounds_valid_count": len(valid_indices),
        "bounds_invalid_count": len(invalid_indices),
        "bounds_valid_input_min": min(valid_indices) if valid_indices else None,
        "bounds_valid_input_max": max(valid_indices) if valid_indices else None,
        "bounds_invalid_input_sha256": _sha256(
            json.dumps(invalid_indices, separators=(",", ":")).encode("ascii")
        ),
        "rows": rows,
        "source_address_bytes_observed": False,
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def _runtime_join(paths: tuple[Path, ...], formula_rows: list[dict[str, object]]) -> dict[str, object]:
    by_index = {row["formula_input"]: row for row in formula_rows}
    routes = []
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        runtime = report.get("runtime", {})
        route = report.get("route", {})
        if not isinstance(runtime, dict) or not isinstance(route, dict):
            raise ValueError(f"unsupported runtime report: {path}")
        lookup_rows = runtime.get("lookup_receipts", [])
        if not isinstance(lookup_rows, list):
            lookup_rows = []
        observed = []
        for lookup in lookup_rows[:32]:
            if not isinstance(lookup, dict):
                continue
            index = lookup.get("map_index")
            row = by_index.get(index) if isinstance(index, int) else None
            if row is None:
                continue
            input_row = lookup.get("input", {})
            if not isinstance(input_row, dict):
                input_row = {}
            observed.append({
                "formula_input": index,
                "glyph_index": lookup.get("glyph_index"),
                "input_pointer": input_row.get("input_pointer"),
                "input_code_unit_sha256": input_row.get("input_code_unit_sha256"),
                "source_formula_address": row["source_address"],
                "expanded_source_bounds_valid": row["expanded_source_bounds_valid"],
                "source_address_bytes_observed": False,
                "semantic_name_assigned": False,
            })
        routes.append({
            "report": path.name,
            "route_name": route.get("name"),
            "natural_reachability": route.get("natural_reachability"),
            "lookup_count_bounded": len(observed),
            "bounds_valid_count": sum(row["expanded_source_bounds_valid"] for row in observed),
            "observed": observed,
            "source_address_bytes_observed": False,
            "scene_or_content_category": "unknown",
            "raw_bytes_emitted": False,
        })
    return {
        "route_count": len(routes),
        "lookup_count_bounded": sum(route["lookup_count_bounded"] for route in routes),
        "bounds_valid_count": sum(route["bounds_valid_count"] for route in routes),
        "source_address_bytes_observed": False,
        "routes": routes,
        "scene_or_content_category": "unknown",
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_paths: tuple[Path, ...] = ()) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    game_code = rom[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = _sha256(rom)
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")
    static = _initializer_static(rom)
    lz77 = _parse_lz77(rom)
    map_static = m129._static_contract(rom)
    formula_bounds = _source_formula_bounds(
        int(lz77["expanded_size"]), int(map_static["map_entry_count"])
    )
    runtime = _runtime_join(runtime_paths, formula_bounds["rows"]) if runtime_paths else None
    return {
        "schema": "afej-m131-font-initializer-v1",
        "rom": {"game_code": game_code, "size": len(rom), "sha256": rom_sha256},
        "static": static,
        "lz77_source": lz77,
        "source_formula_bounds": formula_bounds,
        "runtime_input": [str(path) for path in runtime_paths] if runtime_paths else [],
        "runtime": runtime,
        "status": {
            "initializer_provenance": "static_lz77_wram_path",
            "expanded_source_size_confirmed": True,
            "source_address_bytes_observed": False,
            "font_identity_confirmed": False,
            "unicode_identity_confirmed": False,
            "codepage": "shift_jis_candidate_only",
            "translation_ready": False,
            "scene_or_content_category": "unknown",
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
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"initializer={result['static']['initializer_callsite']}")
    print(f"expanded_source_size=0x{result['lz77_source']['expanded_size']:x}")
    print(f"compressed_length=0x{result['lz77_source']['compressed_length']:x}")
    print(f"formula_bounds_valid={result['source_formula_bounds']['bounds_valid_count']}")
    print(f"formula_bounds_invalid={result['source_formula_bounds']['bounds_invalid_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
