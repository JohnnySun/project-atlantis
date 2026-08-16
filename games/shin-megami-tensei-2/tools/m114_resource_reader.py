#!/usr/bin/env python3
"""Bounded A5TJ descriptor-reader to staging-writer provenance mapper.

M1.14 follows one already identified state-dispatch path and the opcode 0x0c
reader.  It reports callback/source addresses, argument classes, function
boundaries, hashes, and counts only.  It does not emit descriptor bytes,
source payloads, strings, glyphs, or a translation source table.
"""

from __future__ import annotations

import argparse
import json
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
    thumb_literal_load,
)
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)
from m113_staging_resource_map import (  # noqa: E402
    RESOURCE_RECORDS_PER_GROUP,
    RESOURCE_RECORD_STRIDE,
    STAGING_WRITER,
    STAGING_WRITER_THUMB,
    _groups_from_positions,
    _pointer_positions,
    _region,
)


SCHEMA = "smt2.m1.14.resource-reader.v1"

DESCRIPTOR_BASE = 0x08794E24
DESCRIPTOR_OPCODE = 0x0C
OPCODE_HANDLER = 0x080AD3CC
OPCODE_HANDLER_THUMB = OPCODE_HANDLER | 1
OPCODE_HANDLER_TABLE_INDEX = 12
CALLBACK_TRAMPOLINE = 0x0815CCCC
QUEUE_DRAIN = 0x080AD01C
QUEUE_PRODUCER = 0x080AD0FC
QUEUE_ENTRY_SOURCE_OFFSET = 0x14
QUEUE_ENTRY_INDEX_OFFSET = 0x10
CALLBACK_TABLE = 0x0815EEEC
CALLBACK_TABLE_STRIDE = 8
CALLBACK_TABLE_ENTRIES = 25

STATE_DISPATCH = 0x0813EF40
STATE_DISPATCH_THUMB = STATE_DISPATCH | 1
STATE_GLOBAL = 0x0203B554
STATE_TABLE = 0x0879243C
STATE_TABLE_ENTRIES = 8
STATE_HANDLER = 0x0813F22C
STATE_HANDLER_THUMB = STATE_HANDLER | 1
STATE_HANDLER_STATE_INDEX = 5
STATE_HANDLER_PRODUCER_CALLSITE = 0x0813F242

STAGING_INTERMEDIATE = 0x0200AFC8
STAGING_BASE = 0x02001000
HUFF_WRAPPER = 0x0815CAFC
LZ77_WRAPPER = 0x0815CB00

MAX_LONG_FUNCTION_WINDOW = 0x1200

KNOWN_FUNCTION_ENDS = {
    OPCODE_HANDLER: 0x080AD3EE,
    QUEUE_DRAIN: 0x080AD0D2,
    QUEUE_PRODUCER: 0x080AD14E,
    STATE_DISPATCH: 0x0813EF5C,
    STAGING_WRITER: 0x0813EF86,
}


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    start = address - ROM_BASE
    return data[start : min(len(data), start + length)]


def _long_return_addresses(data: bytes, entry: int) -> list[int]:
    result: list[int] = []
    end = min(ROM_BASE + len(data), entry + MAX_LONG_FUNCTION_WINDOW)
    for address in range(entry + 0x20, end - 1, 2):
        if read_u16(data, address) & 0xFF87 == 0x4700:
            result.append(address)
            if len(result) >= 8:
                break
    return result


def _function_metadata(data: bytes, entry: int, *, long_boundary: bool = False) -> dict[str, object]:
    metadata = _boundary_metadata(data, entry)
    if not long_boundary:
        known_end = KNOWN_FUNCTION_ENDS.get(entry)
        if known_end is None:
            return metadata
        raw = _window(data, entry, known_end - entry)
        metadata.update(
            {
                "length": known_end - entry,
                "window_length": len(raw),
                "window_hash": sha256(raw),
                "return_candidates": [hex_address(known_end - 2)],
            }
        )
        return metadata
    returns = _long_return_addresses(data, entry)
    end = returns[0] + 2 if returns else entry + MAX_LONG_FUNCTION_WINDOW
    raw = _window(data, entry, end - entry)
    metadata.update(
        {
            "length": end - entry,
            "window_length": len(_window(data, entry, 0x100)),
            "window_hash": sha256(_window(data, entry, 0x100)),
            "full_span_length": len(raw),
            "full_span_hash": sha256(raw) if raw else None,
            "return_candidates": [hex_address(value) for value in returns],
        }
    )
    return metadata


def _literal_metadata(data: bytes, address: int) -> dict[str, object] | None:
    try:
        item = thumb_literal_load(data, address)
    except (IndexError, ValueError):
        return None
    return {
        "load_address": hex_address(address),
        "literal_address": item["literal_address"],
        "value": item["value"],
    }


def _address_field(value: int, rom_size: int) -> dict[str, object]:
    return {**address_metadata(value, rom_size), "region_class": _region(value)}


def _source_sample(data: bytes, value: int) -> dict[str, object]:
    raw = _window(data, value, 0x20)
    return {
        "address": _address_field(value, len(data)),
        "bounded_window_length": len(raw),
        "bounded_window_hash": sha256(raw) if raw else None,
    }


def _callback_table_metadata(data: bytes) -> dict[str, object]:
    span = _window(data, CALLBACK_TABLE, CALLBACK_TABLE_ENTRIES * CALLBACK_TABLE_STRIDE)
    entry_value = read_u32(data, CALLBACK_TABLE + OPCODE_HANDLER_TABLE_INDEX * CALLBACK_TABLE_STRIDE)
    return {
        "address": _address_field(CALLBACK_TABLE, len(data)),
        "entry_count": CALLBACK_TABLE_ENTRIES,
        "entry_stride": CALLBACK_TABLE_STRIDE,
        "span_length": len(span),
        "span_hash": sha256(span),
        "selected_opcode": DESCRIPTOR_OPCODE,
        "selected_entry_address": hex_address(
            CALLBACK_TABLE + OPCODE_HANDLER_TABLE_INDEX * CALLBACK_TABLE_STRIDE
        ),
        "selected_callback": _address_field(entry_value, len(data)),
        "selected_callback_matches": entry_value == OPCODE_HANDLER_THUMB,
    }


def _state_table_metadata(data: bytes) -> dict[str, object]:
    span = _window(data, STATE_TABLE, STATE_TABLE_ENTRIES * 4)
    values = [read_u32(data, STATE_TABLE + index * 4) for index in range(STATE_TABLE_ENTRIES)]
    selected = values[STATE_HANDLER_STATE_INDEX]
    return {
        "address": _address_field(STATE_TABLE, len(data)),
        "entry_count": STATE_TABLE_ENTRIES,
        "entry_stride": 4,
        "span_length": len(span),
        "span_hash": sha256(span),
        "thumb_pointer_count": sum(value & 1 for value in values),
        "selected_state_index": STATE_HANDLER_STATE_INDEX,
        "selected_entry_address": hex_address(STATE_TABLE + STATE_HANDLER_STATE_INDEX * 4),
        "selected_handler": _address_field(selected, len(data)),
        "selected_handler_matches": selected == STATE_HANDLER_THUMB,
    }


def _stream_groups(data: bytes) -> dict[str, object]:
    positions = _pointer_positions(data, STAGING_WRITER_THUMB)
    groups = _groups_from_positions(
        positions,
        stride=RESOURCE_RECORD_STRIDE,
        record_count=RESOURCE_RECORDS_PER_GROUP,
    )
    group_reports: list[dict[str, object]] = []
    preceding_opcode_count = 0
    source_regions: Counter[str] = Counter()
    source_markers: Counter[str] = Counter()
    argument_values: Counter[str] = Counter()
    source_values: list[int] = []
    for records in groups:
        sources: list[int] = []
        arguments: list[int] = []
        preceding = 0
        next_opcode = 0
        raw_start = records[0] - 4
        raw_end = records[-1] + RESOURCE_RECORD_STRIDE
        for callback in records:
            if read_u32(data, callback - 4) == DESCRIPTOR_OPCODE:
                preceding += 1
            source = read_u32(data, callback + 4)
            argument = read_u32(data, callback + 8)
            sources.append(source)
            arguments.append(argument)
            source_regions[_region(source)] += 1
            argument_values[hex_address(argument)] += 1
            if ROM_BASE <= source < ROM_BASE + len(data):
                source_markers[hex_address(read_u32(data, source) & 0xFF)] += 1
            source_values.append(source)
        for callback in records:
            if read_u32(data, callback + 0x14) == DESCRIPTOR_OPCODE:
                next_opcode += 1
        preceding_opcode_count += preceding
        group_raw = _window(data, raw_start, raw_end - raw_start)
        group_reports.append(
            {
                "start": hex_address(records[0]),
                "command_prefix": hex_address(records[0] - 4),
                "record_count": len(records),
                "record_stride": RESOURCE_RECORD_STRIDE,
                "span_length": len(group_raw),
                "span_hash": sha256(group_raw),
                "preceding_opcode": hex_address(DESCRIPTOR_OPCODE),
                "preceding_opcode_match_count": preceding,
                "next_opcode_match_count": next_opcode,
                "source_region_counts": dict(sorted(Counter(_region(value) for value in sources).items())),
                "source_pointer_count": len(sources),
                "unique_source_pointer_count": len(set(sources)),
                "source_pointer_samples": [
                    _source_sample(data, value) for value in sources[:3]
                ],
                "callback_argument_r2_counts": dict(
                    sorted(Counter(hex_address(value) for value in arguments).items())
                ),
            }
        )
    return {
        "callback_pointer": hex_address(STAGING_WRITER_THUMB),
        "callback_occurrence_count": len(positions),
        "group_count": len(groups),
        "records_per_group": RESOURCE_RECORDS_PER_GROUP,
        "record_stride": RESOURCE_RECORD_STRIDE,
        "preceding_opcode": hex_address(DESCRIPTOR_OPCODE),
        "preceding_opcode_match_count": preceding_opcode_count,
        "source_region_counts": dict(sorted(source_regions.items())),
        "source_header_marker_counts": dict(sorted(source_markers.items())),
        "callback_argument_r2_counts": dict(sorted(argument_values.items())),
        "unique_source_pointer_count": len(set(source_values)),
        "groups": group_reports,
    }


def _reader_contract(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    return {
        "function": _function_metadata(data, OPCODE_HANDLER),
        "direct_bl_callers": callers.get(OPCODE_HANDLER, []),
        "callback_table": _callback_table_metadata(data),
        "trampoline": hex_address(CALLBACK_TRAMPOLINE),
        "entry_argument": "r0=queue_entry",
        "cursor_pointer_field": "callback-table reader global cursor",
        "record_fields": {
            "callback_offset": "+0x00",
            "source_pointer_offset": "+0x04",
            "callback_r2_argument_offset": "+0x08",
        },
        "queue_entry_fields": {
            "source_pointer_offset": hex_address(QUEUE_ENTRY_SOURCE_OFFSET),
            "stream_index_offset": hex_address(QUEUE_ENTRY_INDEX_OFFSET),
        },
        "dispatch": "load callback r3, source r1, bounded argument r2, then BX r3 via 0x0815cccc",
    }


def _state_dispatch_contract(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    return {
        "function": _function_metadata(data, STATE_DISPATCH),
        "direct_bl_callers": callers.get(STATE_DISPATCH, []),
        "state_global": _address_field(STATE_GLOBAL, len(data)),
        "state_table": _state_table_metadata(data),
        "selection": "halfword [0x0203b554] * 4 + 0x0879243c, then BX selected handler",
        "resource_handler": {
            "function": _function_metadata(data, STATE_HANDLER, long_boundary=True),
            "direct_bl_callers": callers.get(STATE_HANDLER, []),
            "thumb_pointer": _address_field(STATE_HANDLER_THUMB, len(data)),
            "producer_callsite": hex_address(STATE_HANDLER_PRODUCER_CALLSITE),
            "producer_target": hex_address(QUEUE_PRODUCER),
            "producer_arguments": {
                "r0": _address_field(DESCRIPTOR_BASE, len(data)),
                "r1": hex_address(0x0000FFFF),
            },
            "descriptor_literal_load": _literal_metadata(data, 0x0813F23E),
            "mode_literal_load": _literal_metadata(data, 0x0813F240),
        },
    }


def _staging_contract(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    return {
        "function": _function_metadata(data, STAGING_WRITER),
        "direct_bl_callers": callers.get(STAGING_WRITER, []),
        "thumb_pointer": _address_field(STAGING_WRITER_THUMB, len(data)),
        "arguments": {
            "r1": "ROM source pointer passed to Huff wrapper",
            "r2": "bounded output-bank/index argument",
        },
        "huff": {
            "wrapper": hex_address(HUFF_WRAPPER),
            "swi": hex_address(0x13),
            "destination": _address_field(STAGING_INTERMEDIATE, len(data)),
        },
        "lz77_wram": {
            "wrapper": hex_address(LZ77_WRAPPER),
            "swi": hex_address(0x11),
            "destination_expression": "0x02001000 + (r2 << 12)",
        },
        "existing_obj_edge": {
            "source": _address_field(STAGING_BASE, len(data)),
            "destination": _address_field(0x06010000, len(data)),
            "status": "confirmed_static_edge_from_m1.12; runtime association_not_established",
        },
    }


def static_report(data: bytes) -> dict[str, object]:
    targets = (
        OPCODE_HANDLER,
        STATE_DISPATCH,
        STATE_HANDLER,
        QUEUE_DRAIN,
        QUEUE_PRODUCER,
        STAGING_WRITER,
    )
    callers = _direct_bl_callers_index(data, targets)
    descriptor_span = _window(data, DESCRIPTOR_BASE, 0x18)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one named state table, descriptor base, opcode-0x0c handler, and exact staging callback runs",
            "descriptor_base": hex_address(DESCRIPTOR_BASE),
            "descriptor_bounded_span_length": len(descriptor_span),
            "descriptor_bounded_span_hash": sha256(descriptor_span),
            "glyph_pattern_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "state_dispatch": _state_dispatch_contract(data, callers),
        "queue": {
            "drain": {
                "function": _function_metadata(data, QUEUE_DRAIN),
                "direct_bl_callers": callers.get(QUEUE_DRAIN, []),
            },
            "producer": {
                "function": _function_metadata(data, QUEUE_PRODUCER),
                "direct_bl_callers": callers.get(QUEUE_PRODUCER, []),
            },
            "descriptor_source": _address_field(DESCRIPTOR_BASE, len(data)),
            "entry_source_offset": hex_address(QUEUE_ENTRY_SOURCE_OFFSET),
            "entry_stream_index_offset": hex_address(QUEUE_ENTRY_INDEX_OFFSET),
            "sentinel": hex_address(0x10241224),
        },
        "opcode_reader": _reader_contract(data, callers),
        "staging_writer": _staging_contract(data, callers),
        "stream": _stream_groups(data),
        "summary": {
            "state_table_selected_handler": STATE_HANDLER_THUMB,
            "descriptor_initial_opcode": DESCRIPTOR_OPCODE,
            "opcode_handler_match": read_u32(data, CALLBACK_TABLE + OPCODE_HANDLER_TABLE_INDEX * 8)
            == OPCODE_HANDLER_THUMB,
            "callback_occurrence_count": len(_pointer_positions(data, STAGING_WRITER_THUMB)),
            "preceding_opcode_match_count": _stream_groups(data)["preceding_opcode_match_count"],
            "source_pointer_provenance": "rom_pointer_plus_bounded_r2_argument",
            "code_unit_or_string_id": "not_established",
            "glyph_identity": "not_established",
            "runtime": "not_run_listener_blocker_in_previous_bounded_probe",
            "translation_ledger": "blocked",
        },
        "conclusions": {
            "confirmed": [
                "state_table_index_5_to_0x0813f22c_thumb_handler",
                "state_handler_queues_descriptor_0x08794e24_with_mode_0x0000ffff",
                "descriptor_opcode_0x0c_selects_callback_table_entry_12",
                "opcode_reader_passes_record_source_plus_r2_to_callback",
                "callback_0x0813ef65_reaches_huff_then_lz77_staging_writer",
            ],
            "provisional": [
                "descriptor_path_is_resource_or_asset_dispatch_not_text_table",
                "r2_is_output_bank_or_index_not_code_unit",
            ],
            "negative": [
                "no_natural_runtime_hit_due_listener_blocker",
                "no_code_unit_or_string_id_recovered",
                "no_unicode_or_glyph_identity_recovered",
            ],
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
