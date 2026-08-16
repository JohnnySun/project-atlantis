#!/usr/bin/env python3
"""Build a hash-only AFEJ map/font-pool structural census.

This tool deliberately stops before Unicode identification.  It proves the
ROM-side two-byte lookup span and the wrapper's indexed-byte window, then can
consume an ignored runtime receipt to summarize EWRAM glyph-source and VRAM
destination strides.  It never writes or emits a complete Japanese string,
ROM slice, RAM dump or bitmap.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from trace_m19_glyph_sink import (
    COMPOSER_CALL,
    MAP_BASE,
    MAP_LOOKUP_ENTRY,
    MAP_LOOKUP_FALLBACK,
    MAP_LOOKUP_FIRST_BYTE,
    MAP_LOOKUP_MATCH,
    MAP_LOOKUP_WRAPPER,
    RENDERER_ENTRY,
    RENDERER_KERNEL,
    RENDERER_WRITE,
    _capstone_instructions,
    hex32,
)


ROM_BASE = 0x08000000
MAP_SCAN_LIMIT = 0x800
LOOKUP_INDEX_BYTE_BASE = 0x086916E5
GLYPH_SOURCE_CANDIDATE = 0x020020C0
VRAM_DESTINATION_CANDIDATE = 0x06014000
GLYPH_PLANE_OFFSETS = (0x00, 0x40, 0x80, 0xC0)


def _u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset:offset + 4], "little")


def _instruction_text(rows: Iterable[dict[str, object]], address: int) -> str:
    for row in rows:
        if int(row["address"]) == address:
            return f"{hex32(address)}: {row['mnemonic']} {row['op_str']}".rstrip()
    raise ValueError(f"missing disassembly at {hex32(address)}")


def _map_census(rom: bytes) -> dict[str, object]:
    start = MAP_BASE - ROM_BASE
    pairs: list[bytes] = []
    terminator_address: Optional[int] = None
    for offset in range(0, MAP_SCAN_LIMIT, 2):
        pair = rom[start + offset:start + offset + 2]
        if len(pair) != 2:
            break
        if pair == bytes((0, 0)):
            terminator_address = MAP_BASE + offset
            break
        pairs.append(pair)
    if terminator_address is None:
        raise ValueError("two-byte map terminator not found in bounded scan")
    span = rom[start:terminator_address - ROM_BASE + 2]
    unique = len(set(pairs))
    return {
        "map_base": hex32(MAP_BASE),
        "entry_count": len(pairs),
        "terminator_address": hex32(terminator_address),
        "next_data_address": hex32(terminator_address + 2),
        "span_length": len(span),
        "span_sha256": hashlib.sha256(span).hexdigest(),
        "pair_data_sha256": hashlib.sha256(b"".join(pairs)).hexdigest(),
        "unique_pair_count": unique,
        "duplicate_pair_count": len(pairs) - unique,
        "raw_bytes_emitted": False,
    }


def _indexed_byte_window(rom: bytes, entry_count: int) -> dict[str, object]:
    start = LOOKUP_INDEX_BYTE_BASE - ROM_BASE
    window = rom[start:start + entry_count]
    if len(window) != entry_count:
        raise ValueError("indexed-byte window falls outside ROM")
    histogram = collections.Counter(window)
    return {
        "base": hex32(LOOKUP_INDEX_BYTE_BASE),
        "length": len(window),
        "sha256": hashlib.sha256(window).hexdigest(),
        "nonzero_count": sum(value != 0 for value in window),
        "min_value": min(window),
        "max_value": max(window),
        "value_histogram": {hex(value): histogram[value] for value in sorted(histogram)},
        "role": "lookup_result_indexed_byte_window",
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def _static_census(rom: bytes) -> dict[str, object]:
    map_rows = _capstone_instructions(rom, MAP_LOOKUP_ENTRY, MAP_LOOKUP_WRAPPER + 0x12)
    wrapper_rows = _capstone_instructions(rom, MAP_LOOKUP_WRAPPER, MAP_LOOKUP_WRAPPER + 0x12)
    composer_rows = _capstone_instructions(rom, COMPOSER_CALL - 0x3E, COMPOSER_CALL + 4)
    renderer_rows = _capstone_instructions(rom, RENDERER_ENTRY, RENDERER_ENTRY + 2)
    kernel_rows = renderer_rows + _capstone_instructions(rom, RENDERER_KERNEL, RENDERER_WRITE + 4)
    map_info = _map_census(rom)
    indexed_window = _indexed_byte_window(rom, int(map_info["entry_count"]))
    literal_address = 0x08099324
    literal_value = _u32(rom, literal_address)
    return {
        "map": map_info,
        "lookup_wrapper": {
            "entry": hex32(MAP_LOOKUP_WRAPPER),
            "lookup_call": _instruction_text(wrapper_rows, 0x08099316),
            "indexed_byte_load": _instruction_text(wrapper_rows, 0x0809931E),
            "literal_address": hex32(literal_address),
            "literal_value": hex32(literal_value),
            "literal_matches_indexed_window": literal_value == LOOKUP_INDEX_BYTE_BASE,
            "semantic_name_assigned": False,
        },
        "indexed_byte_window": indexed_window,
        "glyph_composer": {
            "entry": hex32(0x08099424),
            "call_instruction": _instruction_text(composer_rows, COMPOSER_CALL),
            "renderer_entry": _instruction_text(kernel_rows, RENDERER_ENTRY),
            "kernel_entry": _instruction_text(kernel_rows, RENDERER_KERNEL),
            "writer_instruction": _instruction_text(kernel_rows, RENDERER_WRITE),
            "plane_offsets": [hex32(value) for value in GLYPH_PLANE_OFFSETS],
            "source_candidate": hex32(GLYPH_SOURCE_CANDIDATE),
            "vram_destination_candidate": hex32(VRAM_DESTINATION_CANDIDATE),
            "semantic_name_assigned": False,
        },
        "static_map_rows_recorded": len(map_rows),
        "raw_bytes_emitted": False,
        "unicode_identity_confirmed": False,
    }


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            return None
    return None


def _stride_values(addresses: list[int]) -> list[str]:
    unique = sorted(set(addresses))
    return sorted({hex32(right - left) for left, right in zip(unique, unique[1:]) if right > left})


def _ordered_stride_histogram(addresses: list[int]) -> dict[str, int]:
    counts = collections.Counter(
        hex32(right - left)
        for left, right in zip(addresses, addresses[1:])
        if right > left
    )
    return {key: counts[key] for key in sorted(counts)}


def _renderer_rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = runtime.get("renderer_entries")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    rows = runtime.get("renderer_events")
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows
        if isinstance(row, dict) and row.get("pc") == hex32(RENDERER_ENTRY)
    ]


def _composer_rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = runtime.get("composer_receipts")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    rows = runtime.get("renderer_events")
    if not isinstance(rows, list):
        return []
    return [
        row for row in rows
        if isinstance(row, dict) and row.get("pc") == hex32(0x08099424)
    ]


def _runtime_census(report: dict[str, Any]) -> dict[str, object]:
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime report has no runtime object")
    renderers = _renderer_rows(runtime)
    composers = _composer_rows(runtime)
    sources = [
        value for value in (_as_int(row.get("source_register_r0")) for row in renderers)
        if value is not None
    ]
    destinations = [
        value for value in (_as_int(row.get("destination_register_r1")) for row in renderers)
        if value is not None
    ]
    source_hashes = [
        row.get("source_hash_window", {}).get("sha256")
        for row in renderers
        if isinstance(row.get("source_hash_window"), dict)
        and row["source_hash_window"].get("sha256")
    ]
    groups: list[dict[str, object]] = []
    if composers and len(renderers) >= len(composers) * 3:
        for index, composer in enumerate(composers[:32]):
            group = renderers[index * 3:(index + 1) * 3]
            group_sources = [
                value for value in (_as_int(row.get("source_register_r0")) for row in group)
                if value is not None
            ]
            group_destinations = [
                value for value in (_as_int(row.get("destination_register_r1")) for row in group)
                if value is not None
            ]
            groups.append({
                "group_index": index,
                "opaque_input_glyph_index": composer.get("source_register_r0"),
                "renderer_call_count_observed": len(group),
                "source_base": hex32(group_sources[0]) if group_sources else None,
                "destination_base": hex32(group_destinations[0]) if group_destinations else None,
                "source_addresses_unique": [hex32(value) for value in sorted(set(group_sources))],
                "destination_addresses_unique": [hex32(value) for value in sorted(set(group_destinations))],
            })
    source_bases = [
        value for value in (_as_int(group.get("source_base")) for group in groups)
        if value is not None
    ]
    destination_bases = [
        value for value in (_as_int(group.get("destination_base")) for group in groups)
        if value is not None
    ]
    writer_rows = runtime.get("writer_receipts")
    writer_count = len(writer_rows) if isinstance(writer_rows, list) else 0
    return {
        "renderer_entry_count": len(renderers),
        "composer_entry_count": len(composers),
        "source_address_count": len(set(sources)),
        "destination_address_count": len(set(destinations)),
        "source_addresses": [hex32(value) for value in sorted(set(sources))],
        "destination_addresses": [hex32(value) for value in sorted(set(destinations))],
        "source_stride_values": _stride_values(sources),
        "destination_stride_values": _stride_values(destinations),
        "source_020020c0_observed": GLYPH_SOURCE_CANDIDATE in sources,
        "destination_06014000_observed": VRAM_DESTINATION_CANDIDATE in destinations,
        "source_hash_receipt_count": len(source_hashes),
        "writer_receipt_count": writer_count,
        "grouped_renderer_receipts": groups,
        "source_base_stride_values": _stride_values(source_bases),
        "destination_base_stride_values": _stride_values(destination_bases),
        "source_base_stride_histogram": _ordered_stride_histogram(source_bases),
        "destination_base_stride_histogram": _ordered_stride_histogram(destination_bases),
        "plane_offsets_static": [hex32(value) for value in GLYPH_PLANE_OFFSETS],
        "semantic_name_assigned": False,
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_path: Optional[Path] = None) -> dict[str, object]:
    rom = rom_path.read_bytes()
    report: dict[str, object] = {
        "schema": "afej-m120-font-pool-census-v1",
        "rom": {
            "game_code": rom[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "static": _static_census(rom),
        "runtime_input": None,
        "runtime": None,
        "raw_bytes_emitted": False,
    }
    if runtime_path is not None:
        runtime_report = json.loads(runtime_path.read_text(encoding="utf-8"))
        report["runtime_input"] = str(runtime_path)
        report["runtime"] = _runtime_census(runtime_report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.rom, args.runtime_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
