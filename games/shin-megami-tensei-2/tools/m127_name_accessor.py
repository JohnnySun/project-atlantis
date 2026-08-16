#!/usr/bin/env python3
"""Bounded A5TJ accessor-to-16-bit-reader provenance for one text consumer.

M1.27 follows the already named large text-reader family through one bounded
caller, ``0x080e1030``.  The caller selects one of three ROM-record accessor
paths, copies a fixed eight-halfword field into a stack buffer, appends a zero
unit, and calls the small or large 16-bit reader.  This probe records only
addresses, boundaries, hashes, lengths, counts, and field contracts.  It does
not emit record bytes, unit values, decoded text, glyphs, or a translation
ledger.
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
    address_metadata,
    hex_address,
    read_u16,
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m19_state_mapping import _function_end  # noqa: E402
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)


SCHEMA = "smt2.m1.27.name-accessor.v1"

CONSUMER = 0x080E1030
CONSUMER_END = 0x080E11EE
CONSUMER_DIRECT_CALLER_LIMIT = 32

READER_SMALL = 0x080AC334
READER_LARGE = 0x080AC3AC
ACCESSOR_NORMALIZE_MASK = 0x8000
ACCESSOR_LOW_BYTE_MASK = 0x00FF
FIELD_UNIT_COUNT = 8
FIELD_BYTES = FIELD_UNIT_COUNT * 2

# The caller's two thresholds and source-field offsets are part of this
# bounded contract.  Accessor A and B intentionally share one table base.
ACCESSORS = (
    {
        "name": "shared_table_selector_le_7f",
        "entry": 0x080BF32C,
        "end": 0x080BF34E,
        "literal_instruction": 0x080BF346,
        "table_base": 0x08198B74,
        "record_stride": 0x24,
        "source_field_offset": 0x14,
        "consumer_callsite": 0x080E10DC,
        "consumer_domain": "selector_r1_0x00_through_0x7f",
    },
    {
        "name": "shared_table_selector_80_through_cf",
        "entry": 0x080BF354,
        "end": 0x080BF376,
        "literal_instruction": 0x080BF36E,
        "table_base": 0x08198B74,
        "record_stride": 0x24,
        "source_field_offset": 0x14,
        "consumer_callsite": 0x080E10EE,
        "consumer_domain": "selector_r1_0x80_through_0xcf",
    },
    {
        "name": "secondary_table_selector_above_cf",
        "entry": 0x080BF418,
        "end": 0x080BF436,
        "literal_instruction": 0x080BF42E,
        "table_base": 0x08198EB4,
        "record_stride": 0x20,
        "source_field_offset": 0x0C,
        "consumer_callsite": 0x080E10FA,
        "consumer_domain": "object_field_plus_0x42_runtime_value",
    },
)

SHARED_TABLE_BASE = 0x08198B74
SHARED_TABLE_STRIDE = 0x24
SHARED_TABLE_RECORD_COUNT = 0xD0
SHARED_TABLE_FIELD_OFFSET = 0x14

# The secondary path has no proven record bound.  This is only a fixed-size
# metadata window, not a claim that all 0x100 records belong to one table.
SECONDARY_TABLE_BASE = 0x08198EB4
SECONDARY_TABLE_STRIDE = 0x20
SECONDARY_TABLE_PROBE_COUNT = 0x100
SECONDARY_TABLE_FIELD_OFFSET = 0x0C

CONSUMER_LITERAL_CALLSITE = 0x080E1046
CONSUMER_LITERAL_TARGET = 0x0815E7A0
CONSUMER_SOURCE_FIELD_LOADS = (0x080E10C0, 0x080E10C6)
CONSUMER_SOURCE_FIELD_OFFSETS = (0x40, 0x42)
CONSUMER_COPY_FIRST_LOAD = 0x080E1116
CONSUMER_COPY_FIRST_STORE = 0x080E1118
CONSUMER_COPY_LOOP_COMPARE = 0x080E1122
CONSUMER_APPEND_ZERO = 0x080E1130
CONSUMER_LARGE_CALLSITE = 0x080E115A
CONSUMER_SMALL_CALLSITE = 0x080E1178
CONSUMER_READER_CALLS = (
    (CONSUMER_LARGE_CALLSITE, READER_LARGE),
    (CONSUMER_SMALL_CALLSITE, READER_SMALL),
)

WRAPPERS = (
    {
        "name": "positive_context",
        "callsite": 0x080E11F8,
        "literal_instruction": 0x080E11F2,
        "literal_value": 0x0203B554,
        "consumer_argument_offset": 0x58,
    },
    {
        "name": "negative_context",
        "callsite": 0x080E120C,
        "literal_instruction": 0x080E1206,
        "literal_value": 0x0203B5AC,
        "consumer_argument_offset": -0x58,
    },
)


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


def _safe_bl(data: bytes, callsite: int) -> int | None:
    try:
        return thumb_bl_target(data, callsite)
    except (ValueError, IndexError):
        return None


def _boundary(data: bytes, entry: int, expected_end: int) -> dict[str, object]:
    raw = _window(data, entry, expected_end - entry)
    if len(raw) != expected_end - entry:
        return {
            "entry": address_metadata(entry, len(data)),
            "available": False,
            "expected_end_exclusive": hex_address(expected_end),
            "boundary_match": False,
        }
    try:
        detected = _function_end(data, entry)
    except (ValueError, IndexError):
        detected = None
    metadata = _boundary_metadata(data, entry)
    metadata.update(
        {
            "available": True,
            "expected_end_exclusive": hex_address(expected_end),
            "detected_end_exclusive": (
                None if detected is None else hex_address(detected)
            ),
            "boundary_match": detected == expected_end,
            "instruction_window_hash": sha256(raw),
        }
    )
    return metadata


def _explicit_accessor_boundary(
    data: bytes, entry: int, expected_end: int
) -> dict[str, object]:
    raw = _window(data, entry, expected_end - entry)
    return {
        "entry": address_metadata(entry, len(data)),
        "available": len(raw) == expected_end - entry,
        "expected_end_exclusive": hex_address(expected_end),
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "prologue_is_push_lr": _safe_u16(data, entry) == 0xB500,
        "return_pop_r1": _safe_u16(data, expected_end - 4) == 0xBC02,
        "return_bx_r1": _safe_u16(data, expected_end - 2) == 0x4708,
        "boundary_basis": "pop_r1_then_bx_r1_before_literal_pool",
    }


def _literal_evidence(
    data: bytes, instruction: int, expected: int
) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction)
        observed = int(str(loaded["value"]), 16)
        return {
            "instruction": hex_address(instruction),
            "literal_address": loaded["literal_address"],
            "loaded_register": loaded["register"],
            "expected": address_metadata(expected, len(data)),
            "observed": address_metadata(observed, len(data)),
            "value_match": observed == expected,
        }
    except (ValueError, IndexError, KeyError, TypeError) as error:
        return {
            "instruction": hex_address(instruction),
            "value_match": False,
            "error_class": type(error).__name__,
        }


def _field_window_metadata(
    data: bytes,
    *,
    table_base: int,
    record_stride: int,
    record_count: int,
    field_offset: int,
    scope_basis: str,
    stable_id_prefix: str,
) -> dict[str, object]:
    table_window = _window(data, table_base, record_stride * record_count)
    field_bytes = bytearray()
    termination = Counter()
    line_break_records = 0
    records_available = 0
    for ordinal in range(record_count):
        record_address = table_base + ordinal * record_stride
        field = _window(data, record_address + field_offset, FIELD_BYTES)
        if len(field) != FIELD_BYTES:
            continue
        records_available += 1
        field_bytes.extend(field)
        units = [
            int.from_bytes(field[offset : offset + 2], "little")
            for offset in range(0, FIELD_BYTES, 2)
        ]
        if 0 in units:
            termination["zero_within_fixed_field"] += 1
        else:
            termination["fixed_width_field"] += 1
        if 0x0301 in units:
            termination["0301_within_fixed_field"] += 1
        if 0x0300 in units:
            line_break_records += 1
    return {
        "table_base": address_metadata(table_base, len(data)),
        "record_stride": record_stride,
        "record_count": record_count,
        "scope_basis": scope_basis,
        "stable_id_formula": f"{stable_id_prefix}-{{ordinal:04d}}",
        "field_offset": field_offset,
        "field_unit_count": FIELD_UNIT_COUNT,
        "field_byte_length": FIELD_BYTES,
        "table_window_length": len(table_window),
        "table_window_hash": sha256(table_window) if table_window else None,
        "field_window_hash": sha256(bytes(field_bytes)) if field_bytes else None,
        "records_available": records_available,
        "termination_counts": dict(sorted(termination.items())),
        "records_with_line_break_unit": line_break_records,
        "raw_record_bytes_emitted": False,
        "raw_field_units_emitted": False,
    }


def _accessor_metadata(
    data: bytes,
    accessor: dict[str, int | str],
    direct_callers: dict[int, list[str]],
) -> dict[str, object]:
    entry = int(accessor["entry"])
    end = int(accessor["end"])
    base = int(accessor["table_base"])
    return {
        "name": accessor["name"],
        "entry": hex_address(entry),
        "boundary": _explicit_accessor_boundary(data, entry, end),
        "direct_bl_callers": direct_callers.get(entry, []),
        "direct_bl_caller_count_capped": len(direct_callers.get(entry, [])),
        "literal": _literal_evidence(data, int(accessor["literal_instruction"]), base),
        "record_stride": int(accessor["record_stride"]),
        "source_field_offset": int(accessor["source_field_offset"]),
        "normalization": {
            "high_bit_test": hex_address(ACCESSOR_NORMALIZE_MASK),
            "masked_index": hex_address(ACCESSOR_LOW_BYTE_MASK),
            "meaning": "if input bit 15 is set, use low byte; otherwise retain 16-bit index",
        },
        "consumer_callsite": hex_address(int(accessor["consumer_callsite"])),
        "consumer_call_target": (
            None
            if _safe_bl(data, int(accessor["consumer_callsite"])) is None
            else hex_address(_safe_bl(data, int(accessor["consumer_callsite"])) or 0)
        ),
        "consumer_domain": accessor["consumer_domain"],
    }


def _consumer_metadata(data: bytes, direct_callers: dict[int, list[str]]) -> dict[str, object]:
    call_targets = {
        hex_address(callsite): (
            None if (target := _safe_bl(data, callsite)) is None else hex_address(target)
        )
        for callsite, _expected in CONSUMER_READER_CALLS
    }
    accessor_call_targets = {
        hex_address(int(accessor["consumer_callsite"])): (
            None
            if (target := _safe_bl(data, int(accessor["consumer_callsite"]))) is None
            else hex_address(target)
        )
        for accessor in ACCESSORS
    }
    literal_target = _safe_bl(data, CONSUMER_LITERAL_CALLSITE)
    instruction_contract = {
        "primary_field_add": _safe_u16(data, 0x080E10C0) == 0x3140,
        "primary_field_load": _safe_u16(data, 0x080E10C2) == 0x8809,
        "secondary_field_add": _safe_u16(data, 0x080E10C6) == 0x3042,
        "secondary_field_load": _safe_u16(data, 0x080E10C8) == 0x8800,
        "first_field_load": _safe_u16(data, CONSUMER_COPY_FIRST_LOAD) == 0x8818,
        "first_field_store": _safe_u16(data, CONSUMER_COPY_FIRST_STORE) == 0x8008,
        "fixed_copy_compare_seven": _safe_u16(data, CONSUMER_COPY_LOOP_COMPARE) == 0x2A07,
        "append_zero_movs": _safe_u16(data, 0x080E112E) == 0x2000,
        "append_zero_store": _safe_u16(data, CONSUMER_APPEND_ZERO) == 0x8008,
        "threshold_7f_compare": _safe_u16(data, 0x080E10D6) == 0x297F,
        "threshold_cf_compare": _safe_u16(data, 0x080E10E8) == 0x29CF,
    }
    return {
        "boundary": _boundary(data, CONSUMER, CONSUMER_END),
        "direct_bl_callers": direct_callers.get(CONSUMER, []),
        "direct_bl_caller_count_capped": len(direct_callers.get(CONSUMER, [])),
        "stack_buffer": {
            "offset": 0x0C,
            "fixed_unit_count": FIELD_UNIT_COUNT,
            "fixed_byte_length": FIELD_BYTES,
            "append_zero_offset": 0x1C,
            "raw_stack_bytes_emitted": False,
        },
        "instruction_contract": instruction_contract,
        "object_fields": {
            "primary_selector_offset": CONSUMER_SOURCE_FIELD_OFFSETS[0],
            "secondary_selector_offset": CONSUMER_SOURCE_FIELD_OFFSETS[1],
            "load_callsite_contract": {
                hex_address(CONSUMER_SOURCE_FIELD_LOADS[0]): "ldrh_object_plus_0x40",
                hex_address(CONSUMER_SOURCE_FIELD_LOADS[1]): "ldrh_object_plus_0x42",
            },
        },
        "memset_call": {
            "callsite": hex_address(CONSUMER_LITERAL_CALLSITE),
            "expected_target": hex_address(CONSUMER_LITERAL_TARGET),
            "observed_target": (
                None if literal_target is None else hex_address(literal_target)
            ),
            "target_match": literal_target == CONSUMER_LITERAL_TARGET,
            "arguments": {"destination": "sp+0x0c", "fill": 0, "units": 0x12},
        },
        "selector_dispatch": {
            "thresholds": [0x7F, 0xCF],
            "accessor_call_targets": accessor_call_targets,
            "branch_contract": "r1<=0x7f uses shared table; r1<=0xcf uses same table; otherwise r2 uses secondary path",
        },
        "copy_loop": {
            "first_load": hex_address(CONSUMER_COPY_FIRST_LOAD),
            "first_store": hex_address(CONSUMER_COPY_FIRST_STORE),
            "compare_site": hex_address(CONSUMER_COPY_LOOP_COMPARE),
            "copied_units": FIELD_UNIT_COUNT,
            "append_zero": hex_address(CONSUMER_APPEND_ZERO),
            "source_field_provenance": "selected_record_plus_accessor_specific_field_offset",
        },
        "reader_calls": {
            "call_targets": call_targets,
            "expected_targets": {
                hex_address(site): hex_address(expected)
                for site, expected in CONSUMER_READER_CALLS
            },
            "small_large_selected_by_object_flag": True,
        },
        "runtime_capture_performed": False,
    }


def _wrapper_metadata(data: bytes) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for wrapper in WRAPPERS:
        callsite = int(wrapper["callsite"])
        literal_value = int(wrapper["literal_value"])
        target = _safe_bl(data, callsite)
        items.append(
            {
                "name": wrapper["name"],
                "callsite": hex_address(callsite),
                "consumer_target": None if target is None else hex_address(target),
                "consumer_target_match": target == CONSUMER,
                "literal": _literal_evidence(
                    data, int(wrapper["literal_instruction"]), literal_value
                ),
                "consumer_argument_offset": int(wrapper["consumer_argument_offset"]),
            }
        )
    return items


def static_report(data: bytes) -> dict[str, object]:
    target_entries = [CONSUMER] + [int(item["entry"]) for item in ACCESSORS]
    direct_callers = _direct_bl_callers_index(
        data, target_entries, limit=CONSUMER_DIRECT_CALLER_LIMIT
    )
    accessors = [
        _accessor_metadata(data, item, direct_callers) for item in ACCESSORS
    ]
    consumer = _consumer_metadata(data, direct_callers)
    shared_table = _field_window_metadata(
        data,
        table_base=SHARED_TABLE_BASE,
        record_stride=SHARED_TABLE_STRIDE,
        record_count=SHARED_TABLE_RECORD_COUNT,
        field_offset=SHARED_TABLE_FIELD_OFFSET,
        scope_basis="caller_thresholds_0x00_through_0xcf",
        stable_id_prefix="m27-shared-record",
    )
    secondary_table = _field_window_metadata(
        data,
        table_base=SECONDARY_TABLE_BASE,
        record_stride=SECONDARY_TABLE_STRIDE,
        record_count=SECONDARY_TABLE_PROBE_COUNT,
        field_offset=SECONDARY_TABLE_FIELD_OFFSET,
        scope_basis="fixed_metadata_probe_only_no_table_extent_claim",
        stable_id_prefix="m27-secondary-probe",
    )

    accessor_confirmed = all(
        bool(
            item["boundary"]["available"]
            and item["boundary"]["prologue_is_push_lr"]
            and item["boundary"]["return_pop_r1"]
            and item["boundary"]["return_bx_r1"]
            and item["literal"]["value_match"]
            and item["consumer_call_target"] == item["entry"]
        )
        for item in accessors
    )
    reader_confirmed = all(
        consumer["reader_calls"]["call_targets"].get(hex_address(site))
        == hex_address(expected)
        for site, expected in CONSUMER_READER_CALLS
    )
    consumer_confirmed = bool(
        consumer["boundary"]["available"]
        and consumer["boundary"]["boundary_match"]
        and all(consumer["instruction_contract"].values())
        and consumer["memset_call"]["target_match"]
        and reader_confirmed
        and accessor_confirmed
        and shared_table["records_available"] == SHARED_TABLE_RECORD_COUNT
        and all(wrapper["consumer_target_match"] for wrapper in _wrapper_metadata(data))
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_named_reader_caller_three_accessors_two_table_windows",
            "consumer": address_metadata(CONSUMER, len(data)),
            "shared_table_window_records": SHARED_TABLE_RECORD_COUNT,
            "secondary_table_probe_records": SECONDARY_TABLE_PROBE_COUNT,
            "field_unit_count": FIELD_UNIT_COUNT,
            "direct_caller_cap": CONSUMER_DIRECT_CALLER_LIMIT,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "graphics_resource_scan": False,
            "runtime_capture_performed": False,
            "raw_record_bytes_emitted": False,
            "raw_field_units_emitted": False,
            "decoded_text_emitted": False,
            "glyph_bytes_emitted": False,
            "translation_ledger_created": False,
        },
        "consumer": consumer,
        "accessors": accessors,
        "wrappers": _wrapper_metadata(data),
        "tables": {
            "shared_0x24": shared_table,
            "secondary_0x20_probe": secondary_table,
        },
        "source_edge": {
            "object_fields": [0x40, 0x42],
            "record_source_field_offsets": [0x0C, 0x14],
            "copied_unit_count": FIELD_UNIT_COUNT,
            "stack_buffer_offset": 0x0C,
            "appended_terminator": "0x0000",
            "reader_targets": [hex_address(READER_SMALL), hex_address(READER_LARGE)],
            "stable_id_status": "bounded_local_formula_only",
        },
        "conclusions": {
            "confirmed": (
                [
                    "0x080e1030_selector_fields_reach_three_verified_accessors",
                    "0x08198b74_shared_table_has_caller_bounded_0x24_records_0_to_cf",
                    "selected_record_fixed_field_copies_eight_16bit_units_to_stack",
                    "stack_field_appends_zero_before_named_16bit_reader",
                    "small_and_large_reader_call_targets_are_verified",
                ]
                if consumer_confirmed
                else []
            ),
            "provisional": [
                "shared_table_records_are_text-like_fixed_fields_but_semantic_category_is_unconfirmed",
                "secondary_0x20_window_may_be_a_related_record_family_but_extent_and_index_domain_are_unknown",
                "m27-shared-record-ordinal_ids_are_addressing_ids_not_translation_ids",
            ],
            "unknown": [
                "natural_runtime_object_values_and_scene_frequency",
                "main_event_demon_skill_item_or_system_category",
                "Unicode_identity_codepage_mapping_and_glyph_identity",
                "width_rule_control_code_contract_beyond_fixed_copy_and_zero_append",
                "full_secondary_table_extent_and_reinsertion_contract",
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
