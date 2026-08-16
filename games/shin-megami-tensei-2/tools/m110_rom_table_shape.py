#!/usr/bin/env python3
"""Bounded A5TJ ROM-table shape and consumer mapping.

M1.10 follows only the two ROM addresses named by M1.9 caller provenance.
It reports bounded spans, hashes, pointer counts, sentinel offsets, reader
callsites, and small target-window metadata.  It does not emit table keys,
ROM/RAM bytes, strings, glyphs, images, or a translation source table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import (  # noqa: E402
    ROM_BASE,
    ROM_LIMIT,
    address_metadata,
    hex_address,
    read_u32,
    sha256,
)
from m19_state_mapping import (  # noqa: E402
    _address_class,
    _function_metadata,
    _function_start,
    _literal_ref_index,
)


SCHEMA = "smt2.m1.10.rom-table-shape.v1"

TABLE_A = 0x08198A98
TABLE_B = 0x087DF54C
TABLE_A_WINDOW = 0x400
TABLE_B_MAX_WINDOW = 0x2000
TABLE_B_RECORD_STRIDE = 8
TARGET_WINDOW = 0x80
TARGET_LIMIT = 8
SENTINEL = 0x10241224


def _rom_pointer(value: int) -> bool:
    return ROM_BASE <= value < ROM_LIMIT


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + length)]


def _window_metadata(data: bytes, address: int, length: int) -> dict[str, object]:
    raw = _window(data, address, length)
    words = [int.from_bytes(raw[offset : offset + 4], "little") for offset in range(0, max(0, len(raw) - 3), 4)]
    return {
        "address": address_metadata(address, len(data)),
        "length": len(raw),
        "hash": sha256(raw) if raw else None,
        "word_count": len(words),
        "rom_pointer_count": sum(_rom_pointer(value) for value in words),
        "thumb_pointer_count": sum(_rom_pointer(value) and bool(value & 1) for value in words),
        "lz77_header_count": sum((value & 0xFF) == 0x10 for value in words),
    }


def _bounded_table_a(data: bytes) -> dict[str, object]:
    raw = _window(data, TABLE_A, TABLE_A_WINDOW)
    words = [int.from_bytes(raw[offset : offset + 4], "little") for offset in range(0, max(0, len(raw) - 3), 4)]
    sentinels = [offset for offset, value in enumerate(words) if value == SENTINEL]
    first_span = (sentinels[0] + 1) * 4 if sentinels else len(raw)
    first_words = words[: first_span // 4]
    pointer_run_lengths: list[int] = []
    run = 0
    for value in first_words:
        if _rom_pointer(value):
            run += 1
        elif run:
            pointer_run_lengths.append(run)
            run = 0
    if run:
        pointer_run_lengths.append(run)
    return {
        "address": address_metadata(TABLE_A, len(data)),
        "bounded_length": len(raw),
        "bounded_hash": sha256(raw) if raw else None,
        "word_count": len(words),
        "rom_pointer_count": sum(_rom_pointer(value) for value in words),
        "thumb_pointer_count": sum(_rom_pointer(value) and bool(value & 1) for value in words),
        "sentinel": hex_address(SENTINEL),
        "sentinel_offsets": [hex_address(offset * 4) for offset in sentinels],
        "first_sentinel_span": first_span,
        "first_sentinel_rom_pointer_count": sum(_rom_pointer(value) for value in first_words),
        "pointer_run_lengths_before_first_sentinel": pointer_run_lengths,
        "shape": "variable_word_stream_with_sentinels",
        "fixed_stride_status": "not_established",
    }


def _bounded_table_b(data: bytes) -> dict[str, object]:
    records: list[tuple[int, int]] = []
    for offset in range(0, TABLE_B_MAX_WINDOW, TABLE_B_RECORD_STRIDE):
        key_address = TABLE_B + offset
        pointer_address = key_address + 4
        if pointer_address + 4 > ROM_BASE + len(data):
            break
        key = read_u32(data, key_address)
        pointer = read_u32(data, pointer_address)
        if not _rom_pointer(pointer):
            break
        records.append((key, pointer))
    raw = _window(data, TABLE_B, len(records) * TABLE_B_RECORD_STRIDE)
    pointers = [pointer for _, pointer in records]
    return {
        "address": address_metadata(TABLE_B, len(data)),
        "record_count": len(records),
        "record_stride": TABLE_B_RECORD_STRIDE,
        "span_length": len(raw),
        "span_hash": sha256(raw) if raw else None,
        "unique_pointer_count": len(set(pointers)),
        "even_pointer_count": sum(pointer % 2 == 0 for pointer in pointers),
        "odd_pointer_count": sum(pointer % 2 == 1 for pointer in pointers),
        "pointer_region_count": len({_address_class(pointer) for pointer in pointers}),
        "first_break_offset": hex_address(len(records) * TABLE_B_RECORD_STRIDE),
        "shape": "fixed_key_plus_rom_pointer_pairs",
        "source_writer": "ROM_const_data_no_runtime_writer",
    }


def _reader_metadata(data: bytes, refs: dict[int, list[dict[str, object]]], value: int) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for ref in refs.get(value, []):
        instruction = int(str(ref["instruction"]), 16)
        function = _function_start(data, instruction)
        result.append(
            {
                "literal_load": ref,
                "function": _function_metadata(data, function),
                "thumb_boundary_valid": function is not None,
            }
        )
    return result


def _target_windows(data: bytes, pointers: Iterable[int]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[int] = set()
    for pointer in pointers:
        if pointer in seen:
            continue
        seen.add(pointer)
        result.append(_window_metadata(data, pointer, TARGET_WINDOW))
        if len(result) >= TARGET_LIMIT:
            break
    return result


def _first_table_b_pointers(data: bytes) -> list[int]:
    result: list[int] = []
    for offset in range(0, TABLE_B_MAX_WINDOW, TABLE_B_RECORD_STRIDE):
        pointer = read_u32(data, TABLE_B + offset + 4)
        if not _rom_pointer(pointer):
            break
        result.append(pointer)
    return result


def static_report(data: bytes) -> dict[str, object]:
    refs = _literal_ref_index(data, (TABLE_A, TABLE_B))
    table_b_pointers = _first_table_b_pointers(data)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "two tracked ROM table addresses, bounded word/pair shape and reader mapping",
            "glyph_pattern_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "tables": {
            "0x08198a98": _bounded_table_a(data),
            "0x087df54c": _bounded_table_b(data),
        },
        "literal_readers": {
            "0x08198a98": _reader_metadata(data, refs, TABLE_A),
            "0x087df54c": _reader_metadata(data, refs, TABLE_B),
        },
        "bounded_target_windows": {
            "0x087df54c_first_unique_targets": _target_windows(data, table_b_pointers),
        },
        "consumer_edges": {
            "table_a": {
                "reader_callsite": hex_address(0x080BEE40),
                "index_source": "halfword at IWRAM 0x03004550 + 0x62",
                "index_stride": 4,
                "selected_value": "word from 0x08198a98 + index*4",
                "next_consumer": hex_address(0x0813E428),
                "status": "static_provisional_state_pointer",
            },
            "table_b": {
                "reader_callsite": hex_address(0x081534AE),
                "record_pointer_field": "+0x04",
                "next_consumer": hex_address(0x0813E428),
                "status": "static_provisional_resource_pointer",
            },
        },
        "conclusions": {
            "source_writer": "both tracked tables are ROM-resident; no RAM writer was found by this bounded table pass",
            "glyph_provenance": "not established",
            "codepage": "not established",
            "translation_ledger": "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = static_report(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
