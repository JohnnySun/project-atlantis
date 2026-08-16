#!/usr/bin/env python3
"""Bounded A5TJ 16-bit text consumer and font-bank provenance probe.

M1.18 follows the first code-unit reader that has an independently confirmed
ROM pointer table.  It records function boundaries, literal references,
pointer-table shape, source-record hashes, control-code counts, and addressing
expressions.  It never emits source bytes, decoded text, glyph data, images,
or a translation ledger.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import Counter
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
    read_u16,
    read_u32,
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m19_state_mapping import (  # noqa: E402
    _function_end,
    _function_start,
    _literal_ref_index,
)
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)


SCHEMA = "smt2.m1.18.codeunit-font.v1"

# Named code-unit/font path.  These addresses are deliberately kept separate
# from the M1.17 ASCII/map-label path.
FONT_BUILD = 0x080ABF24
FONT_MAP_INSERT = 0x080AC124
FONT_MAP_INIT = 0x080AC198
FONT_MAP_LOOKUP = 0x080AC1DC
CODEUNIT_RENDER_SMALL = 0x080AC218
CODEUNIT_RENDER_LARGE = 0x080AC2A0
CODEUNIT_STRING_SMALL = 0x080AC334
CODEUNIT_STRING_LARGE = 0x080AC3AC

FONT_BANK_POINTER_TABLE = 0x0815ED88
FONT_BANK_POINTER_ENTRY_STRIDE = 0x08
FONT_BANK_POINTER_BOUND = 18
FONT_SCRATCH_SMALL = 0x020391E0
FONT_SCRATCH_LARGE = 0x020395E0
FONT_MAP_GLOBAL = 0x020360DC
FONT_DESCRIPTOR = 0x0815EE18

# This is an audited, bounded table selected from the direct callsite at
# 0x080dd884.  The next data at the same ROM area belongs to another record
# family, so the probe intentionally does not infer a larger table.
SOURCE_TABLE_BASE = 0x085861C8
SOURCE_TABLE_RECORD_STRIDE = 0x08
SOURCE_TABLE_RECORD_COUNT = 28
SOURCE_TABLE_POINTER_FIELD = 0x04
SOURCE_CALLER = 0x080DD7CC
SOURCE_TABLE_LITERAL_LOAD = 0x080DD862
SOURCE_POINTER_CALLSITE = 0x080DD884
SOURCE_RECORD_INDEX_FIELD = 0x02

CODE_UNIT_LINE_BREAK = 0x0300
CODE_UNIT_TERMINATOR = 0x0301
MAX_SOURCE_SCAN_BYTES = 0x100
MAX_CALLERS = 48


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _safe_u16(data: bytes, address: int) -> int | None:
    try:
        return read_u16(data, address)
    except (ValueError, IndexError):
        return None


def _safe_u32(data: bytes, address: int) -> int | None:
    try:
        return read_u32(data, address)
    except (ValueError, IndexError):
        return None


def _literal_evidence(
    data: bytes, instruction_address: int, expected_value: int
) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction_address)
        actual = int(str(loaded["value"]), 16)
        return {
            "instruction": hex_address(instruction_address),
            "literal_address": loaded["literal_address"],
            "loaded_register": loaded["register"],
            "value": address_metadata(actual, len(data)),
            "expected_value": address_metadata(expected_value, len(data)),
            "value_match": actual == expected_value,
        }
    except (ValueError, IndexError) as error:
        return {
            "instruction": hex_address(instruction_address),
            "error_class": type(error).__name__,
            "value_match": False,
        }


def _safe_boundary(
    data: bytes, entry: int, expected_return: int, expected_end: int
) -> dict[str, object]:
    raw = _window(data, entry, 0x100)
    if len(raw) < 2:
        return {
            "entry": address_metadata(entry, len(data)),
            "available": False,
            "expected_return": hex_address(expected_return),
            "expected_end_exclusive": hex_address(expected_end),
            "boundary_match": False,
        }
    item = _boundary_metadata(data, entry)
    detected_end = _function_end(data, entry)
    item.update(
        {
            "available": True,
            "expected_return": hex_address(expected_return),
            "expected_end_exclusive": hex_address(expected_end),
            "boundary_match": detected_end == expected_end,
        }
    )
    return item


def _address_class(value: int, rom_size: int) -> str:
    if ROM_BASE <= value < ROM_BASE + rom_size:
        return "rom_pointer"
    if 0x02000000 <= value < 0x02400000:
        return "ewram_address"
    if 0x03000000 <= value < 0x03008000:
        return "iwram_address"
    if 0x04000000 <= value < 0x04000400:
        return "io_address"
    return "constant"


def _unit_class(unit: int) -> str:
    if unit == CODE_UNIT_TERMINATOR:
        return "terminator_0301"
    if unit == CODE_UNIT_LINE_BREAK:
        return "line_break_0300"
    if unit == 0:
        return "zero_unit"
    if unit < 0x100:
        return "single_byte_page_unit"
    return "multi_byte_code_unit"


def font_source_address(code_unit: int, bank_pointer: int) -> int:
    """Return the ROM glyph source address expression used by FONT_BUILD."""
    low = code_unit & 0xFF
    return bank_pointer + ((low >> 4) << 10) + ((low & 0x0F) << 5)


def _scan_code_units(
    data: bytes, pointer: int, upper_bound: int
) -> dict[str, object]:
    if not ROM_BASE <= pointer < ROM_BASE + len(data):
        return {
            "available": False,
            "source_pointer": address_metadata(pointer, len(data)),
            "termination": "pointer_out_of_bounds",
        }
    if upper_bound <= pointer:
        upper_bound = min(ROM_BASE + len(data), pointer + MAX_SOURCE_SCAN_BYTES)
    upper_bound = min(upper_bound, pointer + MAX_SOURCE_SCAN_BYTES)
    raw = _window(data, pointer, upper_bound - pointer)
    units: list[int] = []
    terminator_offset: int | None = None
    for offset in range(0, len(raw) - 1, 2):
        unit = struct.unpack_from("<H", raw, offset)[0]
        units.append(unit)
        if unit == CODE_UNIT_TERMINATOR:
            terminator_offset = offset
            break
    if terminator_offset is None:
        consumed = raw
        termination = "not_found_within_bounded_window"
    else:
        consumed = raw[: terminator_offset + 2]
        termination = "terminator_0301"
    classes = Counter(_unit_class(unit) for unit in units)
    return {
        "available": bool(raw),
        "source_pointer": address_metadata(pointer, len(data)),
        "window_length": len(raw),
        "length": len(consumed),
        "unit_count": len(units),
        "hash": sha256(consumed) if consumed else None,
        "termination": termination,
        "terminator_offset": terminator_offset,
        "line_break_count": units.count(CODE_UNIT_LINE_BREAK),
        "terminator_count": units.count(CODE_UNIT_TERMINATOR),
        "zero_unit_count": units.count(0),
        "unit_class_counts": dict(sorted(classes.items())),
        "odd_window_length": len(raw) % 2 == 1,
        "raw_source_emitted": False,
        "decoded_text_emitted": False,
    }


def _source_record_metadata(
    data: bytes, index: int, next_pointer: int | None
) -> dict[str, object]:
    record_address = SOURCE_TABLE_BASE + index * SOURCE_TABLE_RECORD_STRIDE
    word = _safe_u32(data, record_address)
    pointer = _safe_u32(data, record_address + SOURCE_TABLE_POINTER_FIELD)
    result: dict[str, object] = {
        "record_index": index,
        "record_address": address_metadata(record_address, len(data)),
        "record_available": word is not None and pointer is not None,
        "record_id": None if word is None else word & 0xFFFF,
        "pointer_field_offset": SOURCE_TABLE_POINTER_FIELD,
        "source": None,
    }
    if pointer is None:
        return result
    if next_pointer is not None and next_pointer > pointer:
        upper_bound = next_pointer
        result["pointer_delta"] = next_pointer - pointer
    else:
        upper_bound = pointer + MAX_SOURCE_SCAN_BYTES
        result["pointer_delta"] = None
    result["source"] = _scan_code_units(data, pointer, upper_bound)
    return result


def bounded_source_table_metadata(data: bytes) -> dict[str, object]:
    """Describe only the audited 28-record Japanese code-unit table."""
    pointers: list[int | None] = []
    for index in range(SOURCE_TABLE_RECORD_COUNT):
        pointer = _safe_u32(
            data,
            SOURCE_TABLE_BASE
            + index * SOURCE_TABLE_RECORD_STRIDE
            + SOURCE_TABLE_POINTER_FIELD,
        )
        pointers.append(pointer)
    records = [
        _source_record_metadata(
            data,
            index,
            pointers[index + 1] if index + 1 < len(pointers) else None,
        )
        for index in range(SOURCE_TABLE_RECORD_COUNT)
    ]
    ids = [
        int(record["record_id"])
        for record in records
        if record["record_id"] is not None
    ]
    source_items = [
        record["source"]
        for record in records
        if isinstance(record.get("source"), dict)
    ]
    deltas = [
        int(record["pointer_delta"])
        for record in records
        if record.get("pointer_delta") is not None
    ]
    span = _window(
        data,
        SOURCE_TABLE_BASE,
        SOURCE_TABLE_RECORD_COUNT * SOURCE_TABLE_RECORD_STRIDE,
    )
    return {
        "base": address_metadata(SOURCE_TABLE_BASE, len(data)),
        "record_stride": SOURCE_TABLE_RECORD_STRIDE,
        "bounded_record_count": SOURCE_TABLE_RECORD_COUNT,
        "available_record_count": sum(
            int(bool(record["record_available"])) for record in records
        ),
        "record_id_unique": len(ids) == len(set(ids)),
        "record_id_contiguous_1_to_28": ids == list(
            range(1, SOURCE_TABLE_RECORD_COUNT + 1)
        ),
        "pointer_region_counts": dict(
            sorted(
                Counter(
                    "rom_pointer"
                    if pointer is not None
                    and ROM_BASE <= pointer < ROM_BASE + len(data)
                    else "unavailable"
                    for pointer in pointers
                ).items()
            )
        ),
        "pointer_delta_counts": dict(sorted(Counter(deltas).items())),
        "source_terminated_record_count": sum(
            int(
                isinstance(item, dict)
                and item.get("termination") == "terminator_0301"
            )
            for item in source_items
        ),
        "source_unit_count_total": sum(
            int(item.get("unit_count", 0))
            for item in source_items
            if isinstance(item, dict)
        ),
        "line_break_count_total": sum(
            int(item.get("line_break_count", 0))
            for item in source_items
            if isinstance(item, dict)
        ),
        "terminator_count_total": sum(
            int(item.get("terminator_count", 0))
            for item in source_items
            if isinstance(item, dict)
        ),
        "table_span": {
            "length": len(span),
            "hash": sha256(span) if span else None,
        },
        "records": records,
        "category": "bounded_japanese_16bit_string_candidate",
        "raw_source_emitted": False,
        "decoded_text_emitted": False,
    }


def _font_bank_metadata(data: bytes) -> dict[str, object]:
    pointers: list[int] = []
    for index in range(FONT_BANK_POINTER_BOUND):
        value = _safe_u32(
            data, FONT_BANK_POINTER_TABLE + index * FONT_BANK_POINTER_ENTRY_STRIDE
        )
        if value is None:
            break
        pointers.append(value)
    span = _window(
        data,
        FONT_BANK_POINTER_TABLE,
        FONT_BANK_POINTER_BOUND * FONT_BANK_POINTER_ENTRY_STRIDE,
    )
    first = pointers[0] if pointers else None
    last = pointers[-1] if pointers else None
    return {
        "table": address_metadata(FONT_BANK_POINTER_TABLE, len(data)),
        "entry_stride": FONT_BANK_POINTER_ENTRY_STRIDE,
        "bounded_pointer_entry_count": FONT_BANK_POINTER_BOUND,
        "rom_pointer_run_count": sum(
            int(ROM_BASE <= value < ROM_BASE + len(data)) for value in pointers
        ),
        "unique_rom_pointer_count": len(
            {
                value
                for value in pointers
                if ROM_BASE <= value < ROM_BASE + len(data)
            }
        ),
        "first_pointer": (
            None
            if first is None
            else {
                **address_metadata(first, len(data)),
                "class": _address_class(first, len(data)),
            }
        ),
        "last_pointer": (
            None
            if last is None
            else {
                **address_metadata(last, len(data)),
                "class": _address_class(last, len(data)),
            }
        ),
        "table_window": {"length": len(span), "hash": sha256(span) if span else None},
        "break_after_bounded_run": "not_classified_beyond_entry_17",
        "raw_font_bytes_emitted": False,
    }


def _caller_index(
    data: bytes, targets: Iterable[int]
) -> dict[int, list[str]]:
    return _direct_bl_callers_index(data, targets, limit=MAX_CALLERS)


def static_report(data: bytes) -> dict[str, object]:
    targets = (
        FONT_BUILD,
        FONT_MAP_INSERT,
        FONT_MAP_INIT,
        FONT_MAP_LOOKUP,
        CODEUNIT_RENDER_SMALL,
        CODEUNIT_RENDER_LARGE,
        CODEUNIT_STRING_SMALL,
        CODEUNIT_STRING_LARGE,
    )
    callers = _caller_index(data, targets)
    boundaries = {
        "font_build": _safe_boundary(data, FONT_BUILD, 0x080AC0D0, 0x080AC0D2),
        "map_insert": _safe_boundary(data, FONT_MAP_INSERT, 0x080AC18C, 0x080AC18E),
        "map_init": _safe_boundary(data, FONT_MAP_INIT, 0x080AC1C8, 0x080AC1CC),
        "map_lookup": _safe_boundary(data, FONT_MAP_LOOKUP, 0x080AC214, 0x080AC216),
        "render_small": _safe_boundary(
            data, CODEUNIT_RENDER_SMALL, 0x080AC294, 0x080AC296
        ),
        "render_large": _safe_boundary(
            data, CODEUNIT_RENDER_LARGE, 0x080AC328, 0x080AC32A
        ),
        "string_small": _safe_boundary(
            data, CODEUNIT_STRING_SMALL, 0x080AC3A6, 0x080AC3A8
        ),
        "string_large": _safe_boundary(
            data, CODEUNIT_STRING_LARGE, 0x080AC432, 0x080AC434
        ),
        "source_caller": _safe_boundary(data, SOURCE_CALLER, 0x080DDACA, 0x080DDACC),
    }
    try:
        dispatch_target = thumb_bl_target(data, SOURCE_POINTER_CALLSITE)
    except (ValueError, IndexError):
        dispatch_target = None
    table_refs = _literal_ref_index(data, (FONT_BANK_POINTER_TABLE, FONT_DESCRIPTOR))
    source_table = bounded_source_table_metadata(data)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "named_16bit_codeunit_reader_font_bank_and_bounded_pointer_table",
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "raw_font_bytes_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "functions": boundaries,
        "literal_edges": {
            "font_bank_table": _literal_evidence(
                data, 0x080ABF34, FONT_BANK_POINTER_TABLE
            ),
            "font_scratch_small": _literal_evidence(
                data, 0x080ABF54, FONT_SCRATCH_SMALL
            ),
            "font_scratch_large": _literal_evidence(
                data, 0x080AC0BE, FONT_SCRATCH_LARGE
            ),
            "map_global_small_path": _literal_evidence(
                data, 0x080AC25E, FONT_MAP_GLOBAL
            ),
            "descriptor_small_path": _literal_evidence(
                data, 0x080AC274, FONT_DESCRIPTOR
            ),
            "map_global_large_path": _literal_evidence(
                data, 0x080AC2F0, FONT_MAP_GLOBAL
            ),
            "descriptor_large_path": _literal_evidence(
                data, 0x080AC306, FONT_DESCRIPTOR
            ),
            "terminator_literal": _literal_evidence(
                data, 0x080AC41E, CODE_UNIT_TERMINATOR
            ),
            "source_table": _literal_evidence(
                data, SOURCE_TABLE_LITERAL_LOAD, SOURCE_TABLE_BASE
            ),
        },
        "font_banks": _font_bank_metadata(data),
        "source_table": source_table,
        "source_dispatch": {
            "table_base": address_metadata(SOURCE_TABLE_BASE, len(data)),
            "record_index_source": "caller_object_byte_field_plus_0x02_signed",
            "record_addressing": "table_base_plus_index_times_0x08_plus_0x04_pointer_field",
            "pointer_load_callsite": hex_address(SOURCE_POINTER_CALLSITE),
            "pointer_load_to_string_reader": (
                None if dispatch_target is None else hex_address(dispatch_target)
            ),
            "expected_string_reader": hex_address(CODEUNIT_STRING_LARGE),
            "dispatch_target_match": dispatch_target == CODEUNIT_STRING_LARGE,
            "caller_direct_bl_callers": callers.get(SOURCE_CALLER, []),
        },
        "code_unit_path": {
            "unit_width": 16,
            "reader_load": "ldrh",
            "reader_advance_bytes": 2,
            "line_break_unit": hex_address(CODE_UNIT_LINE_BREAK),
            "terminator_unit": hex_address(CODE_UNIT_TERMINATOR),
            "font_bank_selector": "code_unit_high_byte",
            "font_bank_pointer_stride": FONT_BANK_POINTER_ENTRY_STRIDE,
            "font_glyph_offset": "((low_byte >> 4) << 10) + ((low_byte & 0x0f) << 5)",
            "font_transform_outputs": [
                address_metadata(FONT_SCRATCH_SMALL, len(data)),
                address_metadata(FONT_SCRATCH_LARGE, len(data)),
            ],
            "map_cache_global": address_metadata(FONT_MAP_GLOBAL, len(data)),
            "descriptor": address_metadata(FONT_DESCRIPTOR, len(data)),
            "glyph_identity_confirmed": False,
        },
        "callers": {
            hex_address(target): callers.get(target, []) for target in targets
        },
        "conclusions": {
            "confirmed": [
                "0x080ac3ac_reads_16bit_units_and_advances_by_two_bytes",
                "0x080ac3ac_handles_line_break_0x0300_and_terminator_0x0301",
                "0x080abf24_selects_font_bank_from_code_unit_high_byte",
                "0x080abf24_uses_0x0815ed88_and_two_ewram_font_scratch_buffers",
                "font_renderers_dispatch_to_0x0815ee18_and_oam_writer_family",
                "0x085861c8_has_a_bounded_28_record_pointer_table_with_ids_1_to_28",
                "0x080dd884_loads_a_table_record_pointer_and_calls_0x080ac3ac",
            ],
            "provisional": [
                "bounded_0x085861c8_records_are_a_japanese_name_or_ui_category",
                "font_bank_table_is_the_runtime_codepage_source_for_this_consumer",
            ],
            "unknown": [
                "category_semantics_for_ids_1_to_28",
                "full_main_script_table_and_bank_selection",
                "unicode_identity_for_code_units",
                "control_codes_beyond_0x0300_and_0x0301",
                "runtime_scene_to_source_record_selection",
                "translated_width_budget_and_reinsert_contract",
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
