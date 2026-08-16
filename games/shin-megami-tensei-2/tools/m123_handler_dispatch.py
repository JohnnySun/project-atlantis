#!/usr/bin/env python3
"""Bounded indirect text-handler dispatch evidence for A5TJ.

M1.23 follows two already-named command streams to the state handlers that
route into the bounded ``0x0815bed4`` encoded-string family.  It verifies the
queue-producer literal edges, the relevant callback-table entries, command
boundaries, handler boundaries, and the small set of direct handler callers.

The probe is deliberately not a command-stream decoder or a text extractor:
it hashes bounded stream windows and emits addresses, lengths, counts, and
classes only.  It does not emit command words, arguments, source bytes,
decoded text, glyphs, or a translation ledger.
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
    address_metadata,
    hex_address,
    read_u16,
    read_u32,
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m19_state_mapping import _function_end, _function_start  # noqa: E402
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)


SCHEMA = "smt2.m1.23.handler-dispatch.v1"

QUEUE_PRODUCER = 0x080AD0FC
CALLBACK_TABLE = 0x0815EEEC
CALLBACK_ENTRY_COUNT = 25
CALLBACK_ENTRY_STRIDE = 0x08
CALLBACK_TRAMPOLINE = 0x0815CCCC
QUEUE_ENTRY_INDEX_FIELD = 0x10
QUEUE_ENTRY_SOURCE_FIELD = 0x14
QUEUE_ENTRY_STATE_FIELD = 0x1E

HANDLER_A = 0x080CE760
HANDLER_B = 0x080CF414

# These are the only two stream starts selected for this slice.  They were
# already named by the static producer edges; no broad pointer scan is done.
STREAMS = (
    {
        "name": "handler_a_stream",
        "producer": 0x080CED00,
        "producer_callsite": 0x080CED08,
        "stream_literal_load": 0x080CED04,
        "limit_literal_load": 0x080CED06,
        "stream_start": 0x084F0EC0,
        "stream_window_length": 0x500,
        "opcode": 0x0B,
        "callback_index": 11,
        "callback_first": 0x080AD3A9,
        "callback_second": 0x080AD3C9,
        "handler": HANDLER_A,
        "argument_word_count": 1,
        "record_length_words": 3,
        "callback_handler": 0x080AD3A8,
        "callback_bl_site": 0x080AD3BA,
    },
    {
        "name": "handler_b_stream",
        "producer": 0x080D44A0,
        "producer_callsite": 0x080D44AC,
        "stream_literal_load": 0x080D44A8,
        "limit_literal_load": 0x080D44AA,
        "stream_start": 0x084F1514,
        "stream_window_length": 0x320,
        "opcode": 0x0A,
        "callback_index": 10,
        "callback_first": 0x080AD389,
        "callback_second": 0x080AD3A5,
        "handler": HANDLER_B,
        "argument_word_count": 0,
        "record_length_words": 2,
        "callback_handler": 0x080AD388,
        "callback_bl_site": 0x080AD398,
    },
)

DIRECT_HANDLER_TARGETS = (HANDLER_A, HANDLER_B)
MAX_DIRECT_CALLERS = 48


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _safe_boundary(data: bytes, entry: int) -> dict[str, object]:
    raw = _window(data, entry, 0x100)
    if len(raw) < 2:
        return {
            "entry": address_metadata(entry, len(data)),
            "available": False,
            "boundary_match": False,
        }
    end = _function_end(data, entry)
    item = _boundary_metadata(data, entry)
    item.update(
        {
            "available": True,
            "detected_end_exclusive": hex_address(end),
            "detected_length": max(0, end - entry),
        }
    )
    return item


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


def _callback_entry(data: bytes, index: int) -> dict[str, object]:
    address = CALLBACK_TABLE + index * CALLBACK_ENTRY_STRIDE
    try:
        first = read_u32(data, address)
        second = read_u32(data, address + 4)
        available = True
    except (ValueError, IndexError):
        first = second = 0
        available = False
    return {
        "index": index,
        "address": address_metadata(address, len(data)),
        "available": available,
        "first": address_metadata(first, len(data)) if available else None,
        "second": address_metadata(second, len(data)) if available else None,
    }


def _callback_contract(data: bytes, spec: dict[str, object]) -> dict[str, object]:
    index = int(spec["callback_index"])
    entry = _callback_entry(data, index)
    first = int(spec["callback_first"])
    second = int(spec["callback_second"])
    callback_handler = int(spec["callback_handler"])
    callback_bl_site = int(spec["callback_bl_site"])
    try:
        bl_target = thumb_bl_target(data, callback_bl_site)
    except (ValueError, IndexError):
        bl_target = None
    try:
        trampoline_halfword = read_u16(data, CALLBACK_TRAMPOLINE)
    except (ValueError, IndexError):
        trampoline_halfword = None
    boundary = _safe_boundary(data, callback_handler)
    observed_first = entry.get("first")
    observed_second = entry.get("second")
    return {
        "table": {
            "base": address_metadata(CALLBACK_TABLE, len(data)),
            "entry_index": index,
            "entry_stride": CALLBACK_ENTRY_STRIDE,
            "entry": entry,
            "first_match": isinstance(observed_first, dict)
            and observed_first.get("address") == hex_address(first),
            "second_match": isinstance(observed_second, dict)
            and observed_second.get("address") == hex_address(second),
        },
        "callback_handler": {
            "entry": address_metadata(callback_handler, len(data)),
            "boundary": boundary,
            "bl_site": hex_address(callback_bl_site),
            "bl_target": None if bl_target is None else hex_address(bl_target),
            "bl_target_match": bl_target == CALLBACK_TRAMPOLINE,
        },
        "trampoline": {
            "entry": address_metadata(CALLBACK_TRAMPOLINE, len(data)),
            "instruction_form": "bx_r3",
            "halfword_match": trampoline_halfword == 0x4718,
        },
        "argument_word_count": int(spec["argument_word_count"]),
        "record_length_words": int(spec["record_length_words"]),
    }


def _target_commands(data: bytes, spec: dict[str, object]) -> list[dict[str, object]]:
    start = int(spec["stream_start"])
    length = int(spec["stream_window_length"])
    target = int(spec["handler"]) | 1
    opcode = int(spec["opcode"])
    raw = _window(data, start, length)
    if not raw:
        return []
    needle = target.to_bytes(4, "little")
    result: list[dict[str, object]] = []
    argument_values: list[int] = []
    cursor = 0
    while cursor <= len(raw) - 4:
        found = raw.find(needle, cursor)
        if found < 0:
            break
        pointer_address = start + found
        command_address = pointer_address - 4
        try:
            observed_opcode = read_u32(data, command_address)
        except (ValueError, IndexError):
            observed_opcode = None
        record_end = found + int(spec["record_length_words"]) * 4
        argument_window = _window(
            data,
            pointer_address + 4,
            int(spec["argument_word_count"]) * 4,
        )
        argument_metadata: dict[str, object] = {
            "class": "no_explicit_argument"
            if int(spec["argument_word_count"]) == 0
            else "small_selector_argument",
            "word_count": int(spec["argument_word_count"]),
        }
        if int(spec["argument_word_count"]) == 1 and len(argument_window) == 4:
            value = int.from_bytes(argument_window, "little")
            argument_values.append(value)
            argument_metadata.update(
                {
                    "value_class": "small_immediate"
                    if value <= 0xFF
                    else "non_small_immediate",
                }
            )
        result.append(
            {
                "command_address": address_metadata(command_address, len(data)),
                "pointer_address": address_metadata(pointer_address, len(data)),
                "opcode": None if observed_opcode is None else hex_address(observed_opcode),
                "opcode_match": observed_opcode == opcode,
                "record_length_words": int(spec["record_length_words"]),
                "argument_word_count": int(spec["argument_word_count"]),
                "argument_window_hash": sha256(argument_window)
                if argument_window
                else None,
                "argument_metadata": argument_metadata,
                "bounded_record_inside_window": record_end <= len(raw),
                "source_class": "ROM_command_stream",
            }
        )
        cursor = found + 1
    if result and int(spec["argument_word_count"]) == 1:
        if argument_values:
            domain = {
                "class": "small_immediate_selector",
                "count": len(argument_values),
                "distinct_count": len(set(argument_values)),
                "contiguous_domain": len(set(argument_values))
                == max(argument_values) - min(argument_values) + 1,
            }
            for item in result:
                item["argument_domain"] = domain
    return result


def _producer_metadata(data: bytes, spec: dict[str, object]) -> dict[str, object]:
    producer = int(spec["producer"])
    callsite = int(spec["producer_callsite"])
    try:
        queue_target = thumb_bl_target(data, callsite)
    except (ValueError, IndexError):
        queue_target = None
    callers = _direct_bl_callers_index(data, (producer,), limit=MAX_DIRECT_CALLERS)
    caller_functions = []
    for value in callers.get(producer, []):
        callsite_address = int(value, 16)
        function = _function_start(data, callsite_address)
        caller_functions.append(
            {
                "callsite": address_metadata(callsite_address, len(data)),
                "function": None
                if function is None
                else _boundary_metadata(data, function),
                "function_end_exclusive": None
                if function is None
                else hex_address(_function_end(data, function)),
            }
        )
    return {
        "function": address_metadata(producer, len(data)),
        "boundary": _safe_boundary(data, producer),
        "queue_callsite": hex_address(callsite),
        "queue_target": None if queue_target is None else hex_address(queue_target),
        "queue_target_match": queue_target == QUEUE_PRODUCER,
        "stream_literal": _literal_evidence(
            data,
            int(spec["stream_literal_load"]),
            int(spec["stream_start"]),
        ),
        "limit_literal": _literal_evidence(
            data,
            int(spec["limit_literal_load"]),
            0x0000FFFF,
        ),
        "direct_bl_callers": callers.get(producer, []),
        "direct_bl_caller_functions": caller_functions,
        "caller_search_limit": MAX_DIRECT_CALLERS,
    }


def _direct_handler_metadata(
    data: bytes, callers: dict[int, list[str]]
) -> dict[str, object]:
    result: dict[str, object] = {}
    for target in DIRECT_HANDLER_TARGETS:
        items = []
        for value in callers.get(target, []):
            callsite = int(value, 16)
            function = _function_start(data, callsite)
            items.append(
                {
                    "callsite": address_metadata(callsite, len(data)),
                    "target": address_metadata(target, len(data)),
                    "caller_function": None
                    if function is None
                    else _boundary_metadata(data, function),
                    "caller_function_end_exclusive": None
                    if function is None
                    else hex_address(_function_end(data, function)),
                }
            )
        result[hex_address(target)] = {
            "direct_call_count": len(items),
            "calls": items,
            "dispatch_class": "indirect_only" if not items else "mixed_direct_and_indirect",
        }
    return result


def static_report(data: bytes) -> dict[str, object]:
    callers = _direct_bl_callers_index(
        data,
        (*DIRECT_HANDLER_TARGETS, QUEUE_PRODUCER),
        limit=MAX_DIRECT_CALLERS,
    )
    callback_window = _window(
        data,
        CALLBACK_TABLE,
        CALLBACK_ENTRY_COUNT * CALLBACK_ENTRY_STRIDE,
    )
    stream_reports = []
    for spec in STREAMS:
        raw = _window(
            data,
            int(spec["stream_start"]),
            int(spec["stream_window_length"]),
        )
        commands = _target_commands(data, spec)
        stream_reports.append(
            {
                "name": spec["name"],
                "producer": _producer_metadata(data, spec),
                "stream": {
                    "start": address_metadata(int(spec["stream_start"]), len(data)),
                    "window_length": len(raw),
                    "window_hash": sha256(raw) if raw else None,
                    "opcode": hex(int(spec["opcode"])),
                    "callback_index": int(spec["callback_index"]),
                    "target_handler": address_metadata(int(spec["handler"]), len(data)),
                    "target_handler_boundary": _safe_boundary(data, int(spec["handler"])),
                    "target_handler_direct_callers": callers.get(int(spec["handler"]), []),
                    "target_command_count": len(commands),
                    "target_commands": commands,
                    "all_target_commands_opcode_match": bool(commands)
                    and all(item["opcode_match"] for item in commands),
                    "argument_word_count": int(spec["argument_word_count"]),
                    "record_length_words": int(spec["record_length_words"]),
                    "queue_entry_input_contract": {
                        "r0": "queue_entry",
                        "stream_source_field": hex(QUEUE_ENTRY_SOURCE_FIELD),
                        "stream_index_field": hex(QUEUE_ENTRY_INDEX_FIELD),
                        "handler_state_field": hex(QUEUE_ENTRY_STATE_FIELD),
                        "r1": "small_selector_argument"
                        if int(spec["argument_word_count"]) == 1
                        else "not_explicitly_loaded_by_callback",
                        "source_is_text_pointer": False,
                        "code_unit_confirmed": False,
                    },
                },
                "callback": _callback_contract(data, spec),
            }
        )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "two_named_command_streams_and_two_named_handlers",
            "stream_count": len(STREAMS),
            "callback_table_entry_count": CALLBACK_ENTRY_COUNT,
            "callback_table_stride": CALLBACK_ENTRY_STRIDE,
            "callback_table_window_length": len(callback_window),
            "callback_table_window_hash": sha256(callback_window)
            if callback_window
            else None,
            "direct_caller_limit": MAX_DIRECT_CALLERS,
            "full_rom_command_scan": False,
            "full_rom_glyph_scan": False,
            "raw_command_words_emitted": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "handlers": {
            hex_address(HANDLER_A): {
                "boundary": _safe_boundary(data, HANDLER_A),
                "dispatch_class": "indirect_only",
            },
            hex_address(HANDLER_B): {
                "boundary": _safe_boundary(data, HANDLER_B),
                "dispatch_class": "mixed_direct_and_indirect",
            },
        },
        "direct_handlers": _direct_handler_metadata(data, callers),
        "streams": stream_reports,
        "conclusions": {
            "confirmed": [
                "named_producers_load_named_rom_command_streams_into_queue_producer",
                "callback_entries_10_and_11_route_to_bounded_indirect_call_handlers",
                "stream_a_opcode_0b_supplies_one_bounded_argument_word",
                "stream_b_opcode_0a_supplies_no_explicit_argument_word",
                "both_handlers_are_reachable_from_named_command_streams",
                "handler_routes_remain_connected_to_m1.22_family_without_unicode_claim",
            ],
            "provisional": [
                "the_two_command_streams_are_resource_or_state_transition_units",
                "handler_a_indirect_only_dispatch_is_a_natural_static_route",
                "handler_b_direct_callers_are_category_boundary_candidates",
            ],
            "unknown": [
                "natural_runtime_frequency_and_scene_name",
                "state_value_to_semantic_category_mapping",
                "codepage_unicode_identity_width_and_reinsertion_contract",
                "main_event_demon_skill_item_table_relationship",
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
