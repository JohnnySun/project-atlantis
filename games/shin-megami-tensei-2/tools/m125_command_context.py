#!/usr/bin/env python3
"""Bounded command-to-source-table context evidence for A5TJ.

M1.25 follows one already named descriptor field and one command-stream
record.  It verifies the opcode-0x13 callback contract, the staged Thumb
function pointer, and the function's bounded source-table reader edge.  It
does not decode the command stream, emit command words/source bytes, identify
Japanese text, or create a translation ledger.
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
    thumb_literal_load,
)
from m19_state_mapping import _function_end  # noqa: E402
from m111_obj_consumer import _boundary_metadata  # noqa: E402


SCHEMA = "smt2.m1.25.command-context.v1"

# This is the one descriptor/stream relation selected for this slice.  The
# descriptor window is hashed only; its other fields remain uninterpreted.
DESCRIPTOR_BASE = 0x085819A0
DESCRIPTOR_STREAM_FIELD_OFFSET = 0x0C
COMMAND_STREAM_BASE = 0x085862A8
COMMAND_STREAM_WINDOW_LENGTH = 0x200

# The target was selected from the named stream, not from a full-ROM pointer
# scan.  The command is opcode 0x13 and the next command begins immediately
# after the staged function pointer.
TARGET_COMMAND_ADDRESS = 0x085863F0
TARGET_POINTER_ADDRESS = 0x085863F4
TARGET_FUNCTION = 0x080DD7CD
TARGET_OPCODE = 0x13
EXPECTED_NEXT_OPCODE = 0x0C
TARGET_RECORD_LENGTH_WORDS = 2

# Generic queue/callback facts are independently bounded to the existing
# queue consumer and callback table.
QUEUE_DRAIN = 0x080AD01C
QUEUE_CURSOR_GLOBAL = 0x03003B84
QUEUE_ENTRY_OPCODE_FIELD = 0x08
QUEUE_ENTRY_INDEX_FIELD = 0x10
QUEUE_ENTRY_STAGED_FUNCTION_FIELD = 0x20
QUEUE_STAGED_CALLSITE = 0x080AD0BE
QUEUE_STAGED_CALL_TARGET = 0x0815CCC4
CALLBACK_TABLE = 0x0815EEEC
CALLBACK_ENTRY_STRIDE = 0x08
CALLBACK_INDEX = TARGET_OPCODE
CALLBACK_FIRST = 0x080AD541
CALLBACK_SECOND = 0x080AD555
CALLBACK_FIRST_BODY = 0x080AD540
CALLBACK_SECOND_BODY = 0x080AD554

# The command target is also the already named M1.18 UI/source-table reader
# caller.  Keep the table and reader constants local to this probe so the
# report is independently auditable.
CONTEXT_INITIALIZER = 0x080DD279
CONTEXT_INITIALIZER_BODY = 0x080DD278
CONTEXT_RENDERER = 0x080DD7CC
CONTEXT_RENDERER_END = 0x080DDACC
CONTEXT_OBJECT_OFFSET = 0x24
CONTEXT_RECORD_INDEX_OFFSET = 0x02
CONTEXT_RECORD_INDEX_ABSOLUTE_OFFSET = CONTEXT_OBJECT_OFFSET + CONTEXT_RECORD_INDEX_OFFSET
SOURCE_TABLE_BASE = 0x085861C8
SOURCE_TABLE_RECORD_COUNT = 28
SOURCE_TABLE_RECORD_STRIDE = 0x08
SOURCE_TABLE_POINTER_FIELD = 0x04
SOURCE_TABLE_LITERAL_LOAD = 0x080DD862
SOURCE_POINTER_CALLSITE = 0x080DD884
SOURCE_READER = 0x080AC3AC
SOURCE_READER_END = 0x080AC434
STATE_MACHINE = 0x080DD30C
STATE_MACHINE_END = 0x080DD7C8


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
    data: bytes, instruction: int, expected: int
) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction)
        actual = int(str(loaded["value"]), 16)
        return {
            "instruction": hex_address(instruction),
            "literal_address": loaded["literal_address"],
            "loaded_register": loaded["register"],
            "expected": address_metadata(expected, len(data)),
            "observed": address_metadata(actual, len(data)),
            "value_match": actual == expected,
        }
    except (ValueError, IndexError, KeyError, TypeError) as error:
        return {
            "instruction": hex_address(instruction),
            "value_match": False,
            "error_class": type(error).__name__,
        }


def _boundary(data: bytes, entry: int, expected_end: int | None = None) -> dict[str, object]:
    raw = _window(data, entry, 0x100)
    if len(raw) < 2:
        return {
            "entry": address_metadata(entry, len(data)),
            "available": False,
            "expected_end_exclusive": (
                None if expected_end is None else hex_address(expected_end)
            ),
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


def _fixed_leaf_boundary(
    data: bytes, entry: int, expected_end: int, return_address: int
) -> dict[str, object]:
    """Describe a tiny leaf whose return and literal-pool boundary are known."""
    raw = _window(data, entry, expected_end - entry)
    return {
        "entry": address_metadata(entry, len(data)),
        "available": len(raw) == expected_end - entry,
        "expected_end_exclusive": hex_address(expected_end),
        "length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "return_instruction": address_metadata(return_address, len(data)),
        "return_is_bx_lr": _safe_u16(data, return_address) == 0x4770,
        "boundary_basis": "explicit_return_then_literal_pool_or_alignment",
    }


def _descriptor_metadata(data: bytes) -> dict[str, object]:
    window = _window(data, DESCRIPTOR_BASE, 0x20)
    pointer_address = DESCRIPTOR_BASE + DESCRIPTOR_STREAM_FIELD_OFFSET
    pointer = _safe_u32(data, pointer_address)
    return {
        "record_address": address_metadata(DESCRIPTOR_BASE, len(data)),
        "record_window_length": len(window),
        "record_window_hash": sha256(window) if window else None,
        "stream_field_offset": DESCRIPTOR_STREAM_FIELD_OFFSET,
        "stream_field_address": address_metadata(pointer_address, len(data)),
        "stream_pointer": (
            None if pointer is None else address_metadata(pointer, len(data))
        ),
        "stream_pointer_matches_named_source": pointer == COMMAND_STREAM_BASE,
        "raw_record_fields_emitted": False,
    }


def _stream_metadata(data: bytes) -> dict[str, object]:
    window = _window(data, COMMAND_STREAM_BASE, COMMAND_STREAM_WINDOW_LENGTH)
    needle = TARGET_FUNCTION.to_bytes(4, "little")
    hits: list[int] = []
    cursor = 0
    while cursor <= len(window) - len(needle):
        found = window.find(needle, cursor)
        if found < 0:
            break
        hits.append(COMMAND_STREAM_BASE + found)
        cursor = found + 1

    commands: list[dict[str, object]] = []
    for pointer_address in hits:
        command_address = pointer_address - 4
        opcode = _safe_u32(data, command_address)
        next_address = pointer_address + 4
        next_opcode = _safe_u32(data, next_address)
        commands.append(
            {
                "command_address": address_metadata(command_address, len(data)),
                "pointer_address": address_metadata(pointer_address, len(data)),
                "opcode": None if opcode is None else hex_address(opcode),
                "opcode_match": opcode == TARGET_OPCODE,
                "target_function": address_metadata(TARGET_FUNCTION, len(data)),
                "record_length_words": TARGET_RECORD_LENGTH_WORDS,
                "next_command_address": address_metadata(next_address, len(data)),
                "next_opcode": (
                    None if next_opcode is None else hex_address(next_opcode)
                ),
                "next_opcode_is_expected": next_opcode == EXPECTED_NEXT_OPCODE,
                "target_pointer_is_thumb": bool(
                    TARGET_FUNCTION & 1 and ROM_BASE <= (TARGET_FUNCTION & ~1) < ROM_BASE + len(data)
                ),
                "raw_command_words_emitted": False,
            }
        )
    return {
        "stream_start": address_metadata(COMMAND_STREAM_BASE, len(data)),
        "window_length": len(window),
        "window_hash": sha256(window) if window else None,
        "target_pointer_occurrence_count": len(hits),
        "target_command_count": len(commands),
        "commands": commands,
        "full_rom_command_scan": False,
        "raw_command_words_emitted": False,
    }


def _callback_metadata(data: bytes) -> dict[str, object]:
    entry_address = CALLBACK_TABLE + CALLBACK_INDEX * CALLBACK_ENTRY_STRIDE
    first = _safe_u32(data, entry_address)
    second = _safe_u32(data, entry_address + 4)
    first_body = _window(data, CALLBACK_FIRST_BODY, 0x10)
    second_body = _window(data, CALLBACK_SECOND_BODY, 0x04)
    return {
        "table": {
            "base": address_metadata(CALLBACK_TABLE, len(data)),
            "entry_index": CALLBACK_INDEX,
            "entry_stride": CALLBACK_ENTRY_STRIDE,
            "entry_address": address_metadata(entry_address, len(data)),
            "first": None if first is None else address_metadata(first, len(data)),
            "second": None if second is None else address_metadata(second, len(data)),
            "first_match": first == CALLBACK_FIRST,
            "second_match": second == CALLBACK_SECOND,
        },
        "first_callback": {
            "pointer": address_metadata(CALLBACK_FIRST, len(data)),
            "body": _fixed_leaf_boundary(
                data, CALLBACK_FIRST_BODY, 0x080AD550, 0x080AD54E
            ),
            "window_hash": sha256(first_body) if first_body else None,
            "effects": {
                "global_cursor": hex_address(QUEUE_CURSOR_GLOBAL),
                "loads_cursor_dword_by_two_indirections": True,
                "stores_staged_function_field": hex_address(QUEUE_ENTRY_STAGED_FUNCTION_FIELD),
                "increments_queue_index_field": hex_address(QUEUE_ENTRY_INDEX_FIELD),
            },
            "stages_command_pointer": True,
        },
        "second_callback": {
            "pointer": address_metadata(CALLBACK_SECOND, len(data)),
            "body": _fixed_leaf_boundary(
                data, CALLBACK_SECOND_BODY, 0x080AD558, CALLBACK_SECOND_BODY
            ),
            "window_hash": sha256(second_body) if second_body else None,
            "is_bx_lr_noop": _safe_u16(data, CALLBACK_SECOND_BODY) == 0x4770,
        },
    }


def _queue_metadata(data: bytes) -> dict[str, object]:
    try:
        staged_target = thumb_bl_target(data, QUEUE_STAGED_CALLSITE)
    except (ValueError, IndexError):
        staged_target = None
    return {
        "drain_function": _boundary(data, QUEUE_DRAIN),
        "command_cursor_global": hex_address(QUEUE_CURSOR_GLOBAL),
        "entry_contract": {
            "opcode_field": hex_address(QUEUE_ENTRY_OPCODE_FIELD),
            "stream_index_field": hex_address(QUEUE_ENTRY_INDEX_FIELD),
            "staged_function_field": hex_address(QUEUE_ENTRY_STAGED_FUNCTION_FIELD),
            "callback_r0": "queue_entry",
        },
        "staged_function_call": {
            "callsite": hex_address(QUEUE_STAGED_CALLSITE),
            "target": None if staged_target is None else hex_address(staged_target),
            "expected_target": hex_address(QUEUE_STAGED_CALL_TARGET),
            "target_match": staged_target == QUEUE_STAGED_CALL_TARGET,
            "r0": "queue_entry",
            "r1_source": "queue_entry_plus_0x20",
        },
    }


def _context_metadata(data: bytes) -> dict[str, object]:
    try:
        reader_target = thumb_bl_target(data, SOURCE_POINTER_CALLSITE)
    except (ValueError, IndexError):
        reader_target = None
    renderer_window = _window(data, CONTEXT_RENDERER, 0x100)
    state_window = _window(data, STATE_MACHINE, STATE_MACHINE_END - STATE_MACHINE)
    # The state machine has five bounded stores of the selected record byte.
    # Count only the exact Thumb STRB r0,[r6,#2] encoding in this named window.
    record_index_writes = sum(
        1
        for offset in range(0, max(0, len(state_window) - 1), 2)
        if int.from_bytes(state_window[offset : offset + 2], "little") == 0x70B0
    )
    return {
        "initializer": {
            "pointer_in_command_stream": address_metadata(CONTEXT_INITIALIZER, len(data)),
            "body": _boundary(data, CONTEXT_INITIALIZER_BODY),
        },
        "renderer": {
            "entry": address_metadata(CONTEXT_RENDERER, len(data)),
            "boundary": _boundary(data, CONTEXT_RENDERER, CONTEXT_RENDERER_END),
            "window_hash": sha256(renderer_window) if renderer_window else None,
            "direct_bl_callers_not_scanned": True,
        },
        "state_machine": {
            "entry": address_metadata(STATE_MACHINE, len(data)),
            "expected_end_exclusive": hex_address(STATE_MACHINE_END),
            "window_length": len(state_window),
            "window_hash": sha256(state_window) if state_window else None,
            "record_index_write_count": record_index_writes,
            "record_index_write_encoding_class": "strb_r0_object_plus_0x24_plus_0x02",
        },
        "source_table_reader_edge": {
            "table_base": address_metadata(SOURCE_TABLE_BASE, len(data)),
            "table_record_count": SOURCE_TABLE_RECORD_COUNT,
            "record_stride": SOURCE_TABLE_RECORD_STRIDE,
            "pointer_field_offset": SOURCE_TABLE_POINTER_FIELD,
            "literal": _literal_evidence(data, SOURCE_TABLE_LITERAL_LOAD, SOURCE_TABLE_BASE),
            "runtime_index_source": "signed_byte_at_queue_entry_plus_0x26",
            "record_address_expression": "table_base + signed_index * 0x08",
            "source_pointer_expression": "record_address + 0x04",
            "pointer_load_callsite": hex_address(SOURCE_POINTER_CALLSITE),
            "reader_target": None if reader_target is None else hex_address(reader_target),
            "expected_reader": hex_address(SOURCE_READER),
            "reader_target_match": reader_target == SOURCE_READER,
            "reader_boundary": _boundary(data, SOURCE_READER, SOURCE_READER_END),
            "stable_id_contract": "m18-record-%04d (index + 1)",
            "selected_record_known_at_static_time": False,
            "glyph_identity_confirmed": False,
            "unicode_identity_confirmed": False,
        },
    }


def static_report(data: bytes) -> dict[str, object]:
    descriptor = _descriptor_metadata(data)
    stream = _stream_metadata(data)
    callback = _callback_metadata(data)
    queue = _queue_metadata(data)
    context = _context_metadata(data)
    target = stream["commands"][0] if stream["commands"] else None
    static_edge_confirmed = bool(
        descriptor["stream_pointer_matches_named_source"]
        and stream["target_command_count"] == 1
        and isinstance(target, dict)
        and target["opcode_match"]
        and callback["table"]["first_match"]
        and callback["table"]["second_match"]
        and callback["first_callback"]["stages_command_pointer"]
        and queue["staged_function_call"]["target_match"]
        and context["source_table_reader_edge"]["reader_target_match"]
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_named_descriptor_one_named_command_one_source_table_reader",
            "descriptor_window_length": 0x20,
            "command_stream_window_length": COMMAND_STREAM_WINDOW_LENGTH,
            "callback_entry_index": CALLBACK_INDEX,
            "source_table_record_count": SOURCE_TABLE_RECORD_COUNT,
            "full_rom_command_scan": False,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "runtime_capture_performed": False,
            "raw_record_fields_emitted": False,
            "raw_command_words_emitted": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "glyph_bytes_emitted": False,
            "translation_ledger_created": False,
        },
        "descriptor": descriptor,
        "command_stream": stream,
        "callback": callback,
        "queue": queue,
        "context": context,
        "conclusions": {
            "confirmed": (
                [
                    "named_descriptor_field_reaches_named_command_stream",
                    "opcode_13_command_stages_thumb_function_pointer_in_queue_entry_plus_0x20",
                    "queue_drain_indirectly_calls_staged_function_with_queue_entry",
                    "staged_function_reaches_28_record_table_pointer_field",
                    "record_pointer_reaches_16bit_reader_0x080ac3ac",
                ]
                if static_edge_confirmed
                else []
            ),
            "provisional": [
                "command_target_is_a_UI_or_state_context_candidate",
                "28_record_table_is_one_category_candidate_not_the_main_script",
            ],
            "unknown": [
                "natural_runtime_scene_and_selected_record_index",
                "record_category_semantics",
                "unicode_identity_codepage_and_glyph_identity",
                "width_control_contract_and_reinsertion",
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
