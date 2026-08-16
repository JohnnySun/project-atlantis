#!/usr/bin/env python3
"""Bounded context-index initializer evidence for A5TJ.

M1.26 follows only the initializer and selection-array writer already reached
by M1.25's named command stream.  It establishes the runtime-object field
contract and bounded ordinal domain without assigning scene/category meaning.
No source bytes, unit values, glyphs, decoded text, or translation ledger are
emitted.
"""

from __future__ import annotations

import argparse
import json
import sys
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
    thumb_bl_target,
)
from m19_state_mapping import _function_end  # noqa: E402
from m111_obj_consumer import _boundary_metadata  # noqa: E402


SCHEMA = "smt2.m1.26.context-index.v1"

COMMAND_STREAM_BASE = 0x085862A8
COMMAND_STREAM_WINDOW_LENGTH = 0x200
INITIALIZER_OPCODE = 0x0A
INITIALIZER_COMMAND_ADDRESS = COMMAND_STREAM_BASE
INITIALIZER_POINTER_ADDRESS = COMMAND_STREAM_BASE + 4
INITIALIZER_FUNCTION = 0x080DD279

INITIALIZER_BODY = 0x080DD278
INITIALIZER_END = 0x080DD2C0
CONTEXT_OFFSET = 0x24
RECORD_INDEX_FIELD_OFFSET = 0x02
RECORD_INDEX_ENTRY_OFFSET = CONTEXT_OFFSET + RECORD_INDEX_FIELD_OFFSET
DEFAULT_RECORD_INDEX = 1
STATE_ARRAY_OFFSET = 0x15
STATE_ARRAY_COUNT = 0x1B
STATE_ARRAY_MIN = 1
STATE_ARRAY_MAX = 0x1B
STATE_ARRAY_WRITER = 0x080DDE2C
STATE_ARRAY_WRITER_END = 0x080DDEC6
STATE_MACHINE = 0x080DD30C
STATE_MACHINE_END = 0x080DD7C8
INIT_RESOURCE_CALLSITE = 0x080DD2AC
INIT_RESOURCE_TARGET = 0x080E3158
INIT_ARRAY_CALLSITE = 0x080DD2B6
INIT_ARRAY_TARGET = 0x080DDE2C

SOURCE_TABLE_BASE = 0x085861C8
SOURCE_TABLE_RECORD_COUNT = 28
SOURCE_TABLE_RECORD_STRIDE = 0x08
SOURCE_TABLE_POINTER_FIELD = 0x04


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


def _boundary(data: bytes, entry: int, expected_end: int | None = None) -> dict[str, object]:
    raw = _window(data, entry, 0x100)
    if len(raw) < 2:
        return {
            "entry": address_metadata(entry, len(data)),
            "available": False,
            "boundary_match": False,
        }
    detected = _function_end(data, entry)
    result = _boundary_metadata(data, entry)
    result.update(
        {
            "available": True,
            "detected_end_exclusive": hex_address(detected),
            "expected_end_exclusive": (
                None if expected_end is None else hex_address(expected_end)
            ),
            "boundary_match": expected_end is None or detected == expected_end,
        }
    )
    return result


def _bl_evidence(data: bytes, callsite: int, expected: int) -> dict[str, object]:
    try:
        observed = thumb_bl_target(data, callsite)
    except (ValueError, IndexError):
        observed = None
    return {
        "callsite": hex_address(callsite),
        "expected_target": hex_address(expected),
        "observed_target": None if observed is None else hex_address(observed),
        "target_match": observed == expected,
    }


def _initializer_metadata(data: bytes) -> dict[str, object]:
    stream_window = _window(data, COMMAND_STREAM_BASE, COMMAND_STREAM_WINDOW_LENGTH)
    opcode = _safe_u32(data, INITIALIZER_COMMAND_ADDRESS)
    pointer = _safe_u32(data, INITIALIZER_POINTER_ADDRESS)
    # The prologue is intentionally checked by instruction class only; raw
    # halfwords are not included in the report.
    instruction_contract = {
        "context_add_instruction": _safe_u16(data, 0x080DD27C) == 0x3024,
        "load_one_instruction": _safe_u16(data, 0x080DD282) == 0x2101,
        "store_index_byte_instruction": _safe_u16(data, 0x080DD286) == 0x7081,
        "context_offset": CONTEXT_OFFSET,
        "record_index_field_offset": RECORD_INDEX_FIELD_OFFSET,
    }
    return {
        "command": {
            "stream_start": address_metadata(COMMAND_STREAM_BASE, len(data)),
            "stream_window_length": len(stream_window),
            "stream_window_hash": sha256(stream_window) if stream_window else None,
            "command_address": address_metadata(INITIALIZER_COMMAND_ADDRESS, len(data)),
            "opcode": None if opcode is None else hex_address(opcode),
            "opcode_match": opcode == INITIALIZER_OPCODE,
            "pointer_address": address_metadata(INITIALIZER_POINTER_ADDRESS, len(data)),
            "pointer": None if pointer is None else address_metadata(pointer, len(data)),
            "pointer_match": pointer == INITIALIZER_FUNCTION,
            "record_length_words": 2,
            "raw_command_words_emitted": False,
        },
        "function": {
            "pointer": address_metadata(INITIALIZER_FUNCTION, len(data)),
            "body": _boundary(data, INITIALIZER_BODY, INITIALIZER_END),
            "instruction_contract": instruction_contract,
            "default_record_index": DEFAULT_RECORD_INDEX,
            "default_index_is_runtime_capture": False,
        },
        "calls": {
            "resource_initializer": _bl_evidence(
                data, INIT_RESOURCE_CALLSITE, INIT_RESOURCE_TARGET
            ),
            "selection_array_initializer": _bl_evidence(
                data, INIT_ARRAY_CALLSITE, INIT_ARRAY_TARGET
            ),
        },
    }


def _array_writer_metadata(data: bytes) -> dict[str, object]:
    window = _window(data, STATE_ARRAY_WRITER, STATE_ARRAY_WRITER_END - STATE_ARRAY_WRITER)
    instruction_contract = {
        "context_add_instruction": _safe_u16(data, 0x080DDE32) == 0x3524,
        "array_add_instruction": _safe_u16(data, 0x080DDE3E) == 0x3739,
        "ordinal_plus_one_instruction": _safe_u16(data, 0x080DDE44) == 0x1C60,
        "array_store_instruction": _safe_u16(data, 0x080DDE46) == 0x7008,
        "loop_increment_instruction": _safe_u16(data, 0x080DDE4A) == 0x0E04,
        "loop_bound_instruction": _safe_u16(data, 0x080DDE4C) == 0x2C1A,
    }
    return {
        "function": {
            "entry": address_metadata(STATE_ARRAY_WRITER, len(data)),
            "boundary": _boundary(data, STATE_ARRAY_WRITER, STATE_ARRAY_WRITER_END),
            "window_length": len(window),
            "window_hash": sha256(window) if window else None,
            "instruction_contract": instruction_contract,
        },
        "array_contract": {
            "object_context_offset": CONTEXT_OFFSET,
            "array_offset_from_context": STATE_ARRAY_OFFSET,
            "array_count": STATE_ARRAY_COUNT,
            "array_end_offset_exclusive": STATE_ARRAY_OFFSET + STATE_ARRAY_COUNT,
            "value_class": "ordinal_plus_one",
            "value_min": STATE_ARRAY_MIN,
            "value_max": STATE_ARRAY_MAX,
            "raw_array_values_emitted": False,
        },
    }


def _state_machine_metadata(data: bytes) -> dict[str, object]:
    window = _window(data, STATE_MACHINE, STATE_MACHINE_END - STATE_MACHINE)
    # Exact STRB r0,[r6,#2] encoding in the named state-machine window.
    writer_count = sum(
        1
        for offset in range(0, max(0, len(window) - 1), 2)
        if int.from_bytes(window[offset : offset + 2], "little") == 0x70B0
    )
    return {
        "entry": address_metadata(STATE_MACHINE, len(data)),
        "expected_end_exclusive": hex_address(STATE_MACHINE_END),
        "window_length": len(window),
        "window_hash": sha256(window) if window else None,
        "record_index_write_count": writer_count,
        "record_index_source": "context_plus_0x14_selector_through_context_plus_0x15_array",
        "record_index_field": hex_address(RECORD_INDEX_ENTRY_OFFSET),
    }


def static_report(data: bytes) -> dict[str, object]:
    initializer = _initializer_metadata(data)
    array_writer = _array_writer_metadata(data)
    state_machine = _state_machine_metadata(data)
    contract = initializer["function"]["instruction_contract"]
    array_contract = array_writer["array_contract"]
    confirmed = bool(
        initializer["command"]["opcode_match"]
        and initializer["command"]["pointer_match"]
        and all(contract.values())
        and initializer["calls"]["resource_initializer"]["target_match"]
        and initializer["calls"]["selection_array_initializer"]["target_match"]
        and all(array_writer["function"]["instruction_contract"].values())
        and array_contract["array_count"] == 0x1B
        and array_contract["value_min"] == 1
        and array_contract["value_max"] == 0x1B
        and state_machine["record_index_write_count"] == 5
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_named_initializer_one_selection_array_one_state_machine",
            "command_stream_window_length": COMMAND_STREAM_WINDOW_LENGTH,
            "state_array_count": STATE_ARRAY_COUNT,
            "state_machine_window_length": STATE_MACHINE_END - STATE_MACHINE,
            "full_rom_command_scan": False,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "runtime_capture_performed": False,
            "raw_command_words_emitted": False,
            "raw_array_values_emitted": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "glyph_bytes_emitted": False,
            "translation_ledger_created": False,
        },
        "initializer": initializer,
        "selection_array_writer": array_writer,
        "state_machine": state_machine,
        "source_table_contract": {
            "table_base": address_metadata(SOURCE_TABLE_BASE, len(data)),
            "record_count": SOURCE_TABLE_RECORD_COUNT,
            "record_stride": SOURCE_TABLE_RECORD_STRIDE,
            "pointer_field_offset": SOURCE_TABLE_POINTER_FIELD,
            "index_domain_class": "bounded_ordinal_plus_one_1_to_27",
            "stable_id_formula": "m18-record-(table_index + 1)",
            "semantic_category_confirmed": False,
        },
        "conclusions": {
            "confirmed": (
                [
                    "command_stream_opcode_0a_reaches_context_initializer",
                    "initializer_sets_entry_plus_0x26_default_to_one",
                    "selection_array_has_27_ordinal_plus_one_slots",
                    "state_machine_writes_selected_array_value_to_record_index",
                    "bounded_index_domain_is_one_through_27_not_a_unicode_codepoint",
                ]
                if confirmed
                else []
            ),
            "provisional": [
                "initializer_and_array_writer_are_one_UI_or_state_context_candidate",
                "bounded_index_domain_can_address_m18_record_ids_0002_through_0028",
            ],
            "unknown": [
                "natural_runtime_scene_and_selected_index_frequency",
                "semantic_category_of_records_and_array_slots",
                "unicode_identity_codepage_glyph_identity_and_width",
                "full_source_table_scope_and_reinsertion_contract",
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
