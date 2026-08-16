#!/usr/bin/env python3
"""Bounded source-table and reversible code-unit metadata for A5TJ.

M1.24 audits only the 28-record pointer table already selected in M1.18.
It gives each record a stable ordinal/record-id contract, verifies the
record stride and pointer field, hashes the bounded 16-bit unit stream, and
records control-code and font-bank metadata.  It deliberately does not emit
unit values, source bytes, decoded text, glyph data, or a translation ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import (  # noqa: E402
    ROM_BASE,
    address_metadata,
    hex_address,
    read_u16,
    read_u32,
    sha256,
)
from m118_codeunit_font import (  # noqa: E402
    CODE_UNIT_LINE_BREAK,
    CODE_UNIT_TERMINATOR,
    FONT_BANK_POINTER_BOUND,
    FONT_BANK_POINTER_TABLE,
    SOURCE_TABLE_BASE,
    SOURCE_TABLE_POINTER_FIELD,
    SOURCE_TABLE_RECORD_COUNT,
    SOURCE_TABLE_RECORD_STRIDE,
    _unit_class,
)


SCHEMA = "smt2.m1.24.source-table.v1"
MAX_SOURCE_SCAN_BYTES = 0x100
FIELD_BYTES = 4


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _source_metadata(data: bytes, pointer: int) -> dict[str, object]:
    if not ROM_BASE <= pointer < ROM_BASE + len(data):
        return {
            "available": False,
            "pointer": address_metadata(pointer, len(data)),
            "termination": "pointer_out_of_bounds",
            "raw_source_emitted": False,
        }
    raw = _window(data, pointer, MAX_SOURCE_SCAN_BYTES)
    units: list[int] = []
    termination = "not_found_within_bounded_window"
    terminator_offset: int | None = None
    for offset in range(0, len(raw) - 1, 2):
        unit = read_u16(data, pointer + offset)
        units.append(unit)
        if unit == CODE_UNIT_LINE_BREAK:
            continue
        if unit == CODE_UNIT_TERMINATOR:
            termination = "terminator_0301"
            terminator_offset = offset
            break
        if unit == 0:
            termination = "zero_0000"
            terminator_offset = offset
            break
    consumed = (
        raw[: terminator_offset + 2]
        if terminator_offset is not None
        else raw
    )
    bank_counts = Counter()
    for unit in units:
        if unit in (0, CODE_UNIT_LINE_BREAK, CODE_UNIT_TERMINATOR):
            continue
        bank = unit >> 8
        bank_counts[str(bank) if bank < FONT_BANK_POINTER_BOUND else "out_of_table"] += 1
    classes = Counter(_unit_class(unit) for unit in units)
    return {
        "available": bool(raw),
        "pointer": address_metadata(pointer, len(data)),
        "window_length": len(raw),
        "length": len(consumed),
        "unit_count": len(units),
        "unit_stream_hash": sha256(consumed) if consumed else None,
        "termination": termination,
        "terminator_offset": terminator_offset,
        "line_break_count": units.count(CODE_UNIT_LINE_BREAK),
        "terminator_count": units.count(CODE_UNIT_TERMINATOR),
        "zero_unit_count": units.count(0),
        "unit_class_counts": dict(sorted(classes.items())),
        "font_bank_counts": dict(sorted(bank_counts.items())),
        "raw_source_emitted": False,
        "decoded_text_emitted": False,
    }


def _record(data: bytes, ordinal: int) -> dict[str, object]:
    address = SOURCE_TABLE_BASE + ordinal * SOURCE_TABLE_RECORD_STRIDE
    try:
        field0 = read_u32(data, address)
        pointer = read_u32(data, address + SOURCE_TABLE_POINTER_FIELD)
        available = True
    except (ValueError, IndexError):
        field0 = pointer = 0
        available = False
    field_bytes = [((field0 >> (8 * i)) & 0xFF) for i in range(FIELD_BYTES)]
    stored_id = field_bytes[0]
    source = _source_metadata(data, pointer) if available else {
        "available": False,
        "termination": "record_out_of_bounds",
        "raw_source_emitted": False,
    }
    return {
        "ordinal": ordinal,
        "stable_id": f"m18-record-{ordinal + 1:04d}",
        "record_address": address_metadata(address, len(data)),
        "record_stride": SOURCE_TABLE_RECORD_STRIDE,
        "stored_record_id": stored_id,
        "stored_id_matches_ordinal": stored_id == ordinal + 1,
        "record_metadata_bytes": field_bytes,
        "pointer_field_offset": SOURCE_TABLE_POINTER_FIELD,
        "source": source,
        "font_addressing": {
            "expression": "bank[unit>>8] + ((low>>4)<<10) + ((low&0xf)<<5)",
            "bank_table": address_metadata(FONT_BANK_POINTER_TABLE, len(data)),
            "bank_table_entry_stride": 0x08,
            "glyph_block_bytes": 0x20,
            "source_address_recoverable": bool(
                source.get("available") and source.get("termination") in
                ("terminator_0301", "zero_0000")
            ),
        },
    }


def static_report(data: bytes) -> dict[str, object]:
    table_length = SOURCE_TABLE_RECORD_COUNT * SOURCE_TABLE_RECORD_STRIDE
    table_window = _window(data, SOURCE_TABLE_BASE, table_length)
    records = [_record(data, ordinal) for ordinal in range(SOURCE_TABLE_RECORD_COUNT)]
    pointer_count = sum(
        bool(record["source"].get("available")) for record in records
    )
    id_matches = sum(bool(record["stored_id_matches_ordinal"]) for record in records)
    terminator_count = sum(
        record["source"].get("termination") == "terminator_0301"
        for record in records
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_named_28_record_pointer_table",
            "table_base": address_metadata(SOURCE_TABLE_BASE, len(data)),
            "table_window_length": len(table_window),
            "table_window_hash": sha256(table_window) if table_window else None,
            "record_count": SOURCE_TABLE_RECORD_COUNT,
            "record_stride": SOURCE_TABLE_RECORD_STRIDE,
            "pointer_field_offset": SOURCE_TABLE_POINTER_FIELD,
            "per_source_probe_limit": MAX_SOURCE_SCAN_BYTES,
            "font_bank_pointer_bound": FONT_BANK_POINTER_BOUND,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "source_table": {
            "addressing_contract": {
                "record_address": "base + ordinal * stride",
                "pointer_address": "record_address + pointer_field_offset",
                "stable_id": "m18-record-%04d",
                "stored_id_field": "record_field0.byte0",
                "record_metadata_fields_uninterpreted": True,
                "record_id_matches_ordinal_count": id_matches,
                "pointer_available_count": pointer_count,
                "terminator_0301_count": terminator_count,
            },
            "records": records,
            "control_contract": {
                "line_break": hex_address(CODE_UNIT_LINE_BREAK),
                "terminator": hex_address(CODE_UNIT_TERMINATOR),
                "zero_unit_is_not_text_terminator": True,
                "width_rule_confirmed": False,
                "unicode_identity_confirmed": False,
            },
        },
        "conclusions": {
            "confirmed": [
                "28_records_have_bounded_stable_ordinal_contract",
                "record_stride_and_pointer_field_are_reextractable",
                "16_bit_unit_stream_hash_and_control_counts_are_reextractable",
                "font_bank_address_expression_is_reversible_for_bounded_units",
            ],
            "provisional": [
                "records_are_one_encoded_string_family_candidate",
                "stored_record_id_is_a_local_stable_id_not_a_scene_semantic_id",
            ],
            "unknown": [
                "unicode_identity_and_codepage",
                "record_category_and_natural_scene_selection",
                "width_rule_and_zh_tw_encoder_font_contract",
                "relationship_to_main_event_demon_skill_item_system_tables",
            ],
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
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
