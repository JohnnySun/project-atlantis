#!/usr/bin/env python3
"""Metadata-only probe for the A9PJ name-entry keyboard code-unit table.

The name-entry writer at 0x08052B94 indexes a 65-entry row table and stores the
selected halfword into the observed EWRAM name buffer.  This probe verifies the
ROM table arithmetic and the first five known あ-row positions.  It emits only
mapping metadata, record hashes, and bitmap counts; it is not a full source
extractor and never emits record rows or decoded text streams.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m20_text_record_probe import (
    EXPECTED_ROM_SHA256,
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_STRIDE,
    font_record_bus_address,
)


ROM_BASE = 0x08000000
KEYBOARD_TABLE_BUS_BASE = 0x0808884C
KEYBOARD_TABLE_FILE_BASE = KEYBOARD_TABLE_BUS_BASE - ROM_BASE
KEYBOARD_ROW_STRIDE_ENTRIES = 65
KEYBOARD_ENTRY_LENGTH = 2
KEYBOARD_HANDLER_ENTRY = 0x08052B94
KEYBOARD_TABLE_ADD_PC = 0x08052BB6
KEYBOARD_TABLE_READ_PC = 0x08052BB8
KEYBOARD_BUFFER_WRITE_PC = 0x08052BBA

KNOWN_ROW0_LABELS = ("あ", "い", "う", "え", "お")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row_entry_file_offset(row: int, selection: int) -> int:
    if row < 0 or selection < 0:
        raise ValueError("row and selection must be non-negative")
    return KEYBOARD_TABLE_FILE_BASE + KEYBOARD_ENTRY_LENGTH * (
        row * KEYBOARD_ROW_STRIDE_ENTRIES + selection
    )


def row_entry_bus_address(row: int, selection: int) -> int:
    return ROM_BASE + row_entry_file_offset(row, selection)


def read_row(data: bytes, row: int, count: int) -> list[int]:
    if count < 0 or count > KEYBOARD_ROW_STRIDE_ENTRIES:
        raise ValueError("count must fit one keyboard table row")
    result: list[int] = []
    for selection in range(count):
        offset = row_entry_file_offset(row, selection)
        entry = data[offset:offset + KEYBOARD_ENTRY_LENGTH]
        if len(entry) != KEYBOARD_ENTRY_LENGTH:
            raise ValueError("keyboard table entry is outside the ROM")
        result.append(int.from_bytes(entry, "little"))
    return result


def record_bitmap_metadata(data: bytes, code_unit: int) -> dict[str, object]:
    offset = FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE
    record = data[offset:offset + FONT_RECORD_STRIDE]
    if len(record) != FONT_RECORD_STRIDE:
        raise ValueError("font record is outside the ROM")
    rows = [
        int.from_bytes(record[index:index + 2], "little")
        for index in range(0, FONT_RECORD_STRIDE, 2)
    ]
    return {
        "record_bus_address": f"0x{font_record_bus_address(code_unit):08X}",
        "record_file_offset": f"0x{offset:X}",
        "record_sha256": sha256(record),
        "bitmap_width": 16,
        "bitmap_height": len(rows),
        "nonzero_row_count": sum(row != 0 for row in rows),
        "ink_bit_count": sum(bin(row).count("1") for row in rows),
        "rows_emitted": False,
    }


def probe(data: bytes, *, row: int = 0, count: int = 5) -> dict[str, object]:
    rom_hash = sha256(data)
    values = read_row(data, row, count)
    labels = KNOWN_ROW0_LABELS if row == 0 and count == len(KNOWN_ROW0_LABELS) else ()
    mappings: list[dict[str, object]] = []
    for selection, code_unit in enumerate(values):
        item: dict[str, object] = {
            "row": row,
            "selection_index": selection,
            "keyboard_label": labels[selection] if labels else None,
            "code_unit": f"0x{code_unit:04X}",
            "table_entry_bus_address": f"0x{row_entry_bus_address(row, selection):08X}",
            "table_entry_file_offset": f"0x{row_entry_file_offset(row, selection):X}",
            "record": record_bitmap_metadata(data, code_unit),
            "identity_status": (
                "confirmed-system-keyboard-row0"
                if labels
                else "unclassified-keyboard-table-entry"
            ),
        }
        mappings.append(item)

    table_start = row_entry_file_offset(row, 0)
    table_end = row_entry_file_offset(row, KEYBOARD_ROW_STRIDE_ENTRIES - 1) + KEYBOARD_ENTRY_LENGTH
    return {
        "probe_version": "m20-keyboard-codepage-probe-20260816.v1",
        "rom": {
            "sha256": rom_hash,
            "expected_a9pj_sha256_match": rom_hash == EXPECTED_ROM_SHA256,
            "source_text_emitted": False,
        },
        "static_provenance": {
            "handler_entry_pc": f"0x{KEYBOARD_HANDLER_ENTRY:08X}",
            "table_address_add_pc": f"0x{KEYBOARD_TABLE_ADD_PC:08X}",
            "table_read_pc": f"0x{KEYBOARD_TABLE_READ_PC:08X}",
            "buffer_write_pc": f"0x{KEYBOARD_BUFFER_WRITE_PC:08X}",
            "formula": "table_base + 2 * (row * 65 + selection_index)",
            "table_bus_base": f"0x{KEYBOARD_TABLE_BUS_BASE:08X}",
            "table_file_base": f"0x{KEYBOARD_TABLE_FILE_BASE:X}",
            "row_stride_entries": KEYBOARD_ROW_STRIDE_ENTRIES,
            "row_entry_length": KEYBOARD_ENTRY_LENGTH,
        },
        "scope": {
            "row": row,
            "count": count,
            "file_range": [f"0x{table_start:X}", f"0x{table_end:X}"],
            "mapping_status": "confirmed only for row0 first five system-order labels"
            if labels
            else "table arithmetic only",
        },
        "mappings": mappings,
        "codepage": {
            "width_bits": 16,
            "status": "confirmed-for-row0-first-five-only" if labels else "partial-table-only",
            "general_stream_mapping_confirmed": False,
            "control_code_semantics_confirmed": False,
        },
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--row", type=int, default=0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.row < 0 or args.count < 0 or args.count > KEYBOARD_ROW_STRIDE_ENTRIES:
        parser.error("row/count outside keyboard table bounds")
    rendered = json.dumps(
        probe(args.rom.read_bytes(), row=args.row, count=args.count),
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
