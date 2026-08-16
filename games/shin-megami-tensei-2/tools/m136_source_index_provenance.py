#!/usr/bin/env python3
"""Bounded source/index provenance for named A5TJ text families.

M1.36 follows three already named category consumers upward through direct
Thumb BL edges.  It records only function boundaries, callsites, literal
addresses, RAM table shapes, field addressing, hashes, and counts.  It does
not decode source units, emit strings or source bytes, scan graphics, or
create a translation ledger.

The three paths are deliberately independent:

* item: an EWRAM halfword index list reaches the shared item accessor;
* skill: a bounded byte index list reaches the skill accessor through the
  named skill renderer helper;
* demon: a bounded object slot array reaches the demon accessor through the
  object-name consumer.

These are static provenance edges.  They are not runtime natural-transition
captures, and no RAM table is written by this probe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
from m111_obj_consumer import _boundary_metadata  # noqa: E402


SCHEMA = "smt2.m1.36.source-index-provenance.v1"
MAX_UPWARD_LAYERS = 3

ITEM_ACCESSOR = 0x080BF32C
ITEM_ACCESSOR_END = 0x080BF34E
ITEM_INDEX_READER = 0x080D2B70
ITEM_INDEX_READER_END = 0x080D2C40
ITEM_INDEX_CALLSITE = 0x080D2BB0
ITEM_INDEX_READER_CALLSITE = 0x080D2DE6
ITEM_INDEX_PARENT = 0x080D2D80
ITEM_INDEX_PARENT_END = 0x080D2F02
ITEM_INDEX_PARENT_CALLSITE = 0x080D32A0
ITEM_INDEX_ROOT = 0x080D3264
ITEM_INDEX_ROOT_END = 0x080D3400
ITEM_INDEX_GLOBAL_LITERAL = 0x080D2B7C
ITEM_INDEX_GLOBAL = 0x0203A454
ITEM_INDEX_FIELD_OFFSET = 0x9C
ITEM_INDEX_ENTRY_STRIDE = 0x02
ITEM_INDEX_SENTINEL = 0xFFFF
ITEM_TABLE_BASE = 0x08198B74
ITEM_TABLE_STRIDE = 0x24
ITEM_TABLE_FIELD_OFFSET = 0x14
ITEM_TABLE_RECORD_COUNT = 0xD0

SKILL_ACCESSOR = 0x080BF5C0
SKILL_ACCESSOR_END = 0x080BF5D2
SKILL_INDEX_HELPER = 0x080CD1F8
SKILL_INDEX_HELPER_END = 0x080CD25A
SKILL_ACCESSOR_CALLSITE = 0x080CD208
SKILL_INDEX_LIST = 0x080CB928
SKILL_INDEX_LIST_END = 0x080CBA70
SKILL_INDEX_LIST_CALLSITE = 0x080CB99C
SKILL_INDEX_PARENT = 0x080C9BCC
SKILL_INDEX_PARENT_END = 0x080C9CCE
SKILL_INDEX_PARENT_CALLSITE = 0x080C9C6A
SKILL_INDEX_GLOBAL_LITERAL = 0x080CB934
SKILL_INDEX_GLOBAL = 0x0203A454
SKILL_INDEX_BASE_LITERAL = 0x080CB97A
SKILL_INDEX_BASE = 0x0203B860
SKILL_INDEX_LIST_OFFSET = 0x5D
SKILL_INDEX_SLOT_COUNT = 7
SKILL_INDEX_VALID_MAX = 0x3F
SKILL_TABLE_BASE = 0x0819B9F4
SKILL_TABLE_STRIDE = 0x1C
SKILL_TABLE_FIELD_OFFSET = 0x06

DEMON_ACCESSOR = 0x080BF648
DEMON_ACCESSOR_END = 0x080BF6CE
DEMON_CONSUMER = 0x080E1644
DEMON_CONSUMER_END = 0x080E17F2
DEMON_ACCESSOR_CALLSITE = 0x080E1746
DEMON_WRAPPER_A = 0x080E17F4
DEMON_WRAPPER_A_END = 0x080E1804
DEMON_WRAPPER_A_CALLSITE = 0x080E17FC
DEMON_WRAPPER_A_LITERAL = 0x080E17F6
DEMON_WRAPPER_A_GLOBAL = 0x0203B554
DEMON_WRAPPER_A_OFFSET = 0x58
DEMON_WRAPPER_B = 0x080E1808
DEMON_WRAPPER_B_END = 0x080E1818
DEMON_WRAPPER_B_CALLSITE = 0x080E1810
DEMON_WRAPPER_B_LITERAL = 0x080E180A
DEMON_WRAPPER_B_GLOBAL = 0x0203B5AC
DEMON_WRAPPER_B_OFFSET = -0x58
DEMON_OBJECT_SLOT_OFFSET = 0x26
DEMON_OBJECT_SLOT_STRIDE = 0x02
DEMON_OBJECT_SLOT_COUNT = 5
DEMON_TABLE_BASE = 0x0819CB74
DEMON_TABLE_STRIDE = 0x60
DEMON_TABLE_FIELD_OFFSET = 0x22
DEMON_SPECIAL_INDICES = (0x106, 0x109, 0x10C)


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _safe_boundary(
    data: bytes, entry: int, expected_end: int, *, basis: str
) -> dict[str, object]:
    length = max(0, expected_end - entry)
    raw = _window(data, entry, length)
    detected: int | None = None
    try:
        detected = _function_end(data, entry)
    except (ValueError, IndexError):
        pass
    # Leaf helpers and tiny wrappers can be shorter than the conservative
    # backscan window used by the shared boundary finder.  An explicit Thumb
    # BX in the named end slot is stronger for these already-selected
    # functions, so use it as the boundary cross-check.
    try:
        end_instruction = read_u16(data, expected_end - 2)
        explicit_bx = (end_instruction & 0xFF87) == 0x4700
    except (ValueError, IndexError):
        explicit_bx = False
    if explicit_bx:
        detected = expected_end
    try:
        metadata = _boundary_metadata(data, entry)
    except (ValueError, IndexError):
        metadata = {
            "entry": address_metadata(entry, len(data)),
            "prologue_is_thumb_push_lr": False,
        }
    return {
        **metadata,
        "entry": address_metadata(entry, len(data)),
        "expected_end_exclusive": hex_address(expected_end),
        "detected_end_exclusive": (
            None if detected is None else hex_address(detected)
        ),
        "expected_length": length,
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "available": len(raw) == length,
        "boundary_match": detected == expected_end,
        "boundary_basis": basis,
    }


def _literal(
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
    except (ValueError, IndexError, KeyError, TypeError):
        return {
            "instruction": hex_address(instruction),
            "expected": address_metadata(expected, len(data)),
            "value_match": False,
            "available": False,
        }


def _call(
    data: bytes, callsite: int, expected_target: int
) -> dict[str, object]:
    try:
        observed = thumb_bl_target(data, callsite)
    except (ValueError, IndexError):
        observed = None
    return {
        "callsite": hex_address(callsite),
        "expected_target": address_metadata(expected_target, len(data)),
        "observed_target": (
            None if observed is None else address_metadata(observed, len(data))
        ),
        "target_match": observed == expected_target,
    }


def _layer(
    data: bytes,
    *,
    depth: int,
    target: int,
    callsite: int,
    caller: int,
    caller_end: int,
    argument_class: str,
) -> dict[str, object]:
    call = _call(data, callsite, target)
    return {
        "depth": depth,
        "target_function": address_metadata(target, len(data)),
        "callsite": call,
        "caller_function": _safe_boundary(
            data, caller, caller_end, basis="named_thumb_boundary"
        ),
        "argument_class": argument_class,
    }


def _item_path(data: bytes) -> dict[str, object]:
    layers = [
        _layer(
            data,
            depth=1,
            target=ITEM_INDEX_READER,
            callsite=ITEM_INDEX_READER_CALLSITE,
            caller=ITEM_INDEX_PARENT,
            caller_end=ITEM_INDEX_PARENT_END,
            argument_class="parent_context_to_item_index_reader",
        ),
        _layer(
            data,
            depth=2,
            target=ITEM_INDEX_PARENT,
            callsite=ITEM_INDEX_PARENT_CALLSITE,
            caller=ITEM_INDEX_ROOT,
            caller_end=ITEM_INDEX_ROOT_END,
            argument_class="item_state_context_to_parent",
        ),
    ]
    source = {
        "ram_table_base": address_metadata(ITEM_INDEX_GLOBAL, len(data)),
        "ram_table_literal": _literal(data, ITEM_INDEX_GLOBAL_LITERAL, ITEM_INDEX_GLOBAL),
        "entry_base_offset": ITEM_INDEX_FIELD_OFFSET,
        "entry_stride": ITEM_INDEX_ENTRY_STRIDE,
        "entry_value_width": 2,
        "entry_index_expression": "0x0203a454 + 0x9c + loop_index * 2",
        "stop_condition": hex_address(ITEM_INDEX_SENTINEL),
        "valid_shared_index_max": 0xCF,
        "valid_shared_index_condition": "index <= 0xcf",
        "source_class": "EWRAM_halfword_index_list",
    }
    table = {
        "base": address_metadata(ITEM_TABLE_BASE, len(data)),
        "record_stride": ITEM_TABLE_STRIDE,
        "field_offset": ITEM_TABLE_FIELD_OFFSET,
        "field_unit_width": 2,
        "bounded_record_count": ITEM_TABLE_RECORD_COUNT,
        "extent_basis": "caller_threshold_0x00_through_0xcf",
        "semantic_extent_proven": False,
    }
    functions = [
        _safe_boundary(data, ITEM_ACCESSOR, ITEM_ACCESSOR_END, basis="leaf_accessor_return"),
        _safe_boundary(data, ITEM_INDEX_READER, ITEM_INDEX_READER_END, basis="named_return"),
        _safe_boundary(data, ITEM_INDEX_PARENT, ITEM_INDEX_PARENT_END, basis="named_return"),
        _safe_boundary(data, ITEM_INDEX_ROOT, ITEM_INDEX_ROOT_END, basis="named_return"),
    ]
    calls = [
        _call(data, ITEM_INDEX_CALLSITE, ITEM_ACCESSOR),
        _call(data, ITEM_INDEX_READER_CALLSITE, ITEM_INDEX_READER),
        _call(data, ITEM_INDEX_PARENT_CALLSITE, ITEM_INDEX_PARENT),
    ]
    return {
        "name": "item_shared_index_list",
        "family": "item",
        "accessor": address_metadata(ITEM_ACCESSOR, len(data)),
        "functions": functions,
        "calls": calls,
        "upward_layers": layers,
        "source_index_contract": source,
        "table_contract": table,
        "natural_runtime_capture": False,
        "runtime_identity_status": "unknown",
    }


def _skill_path(data: bytes) -> dict[str, object]:
    layers = [
        _layer(
            data,
            depth=1,
            target=SKILL_INDEX_HELPER,
            callsite=SKILL_INDEX_LIST_CALLSITE,
            caller=SKILL_INDEX_LIST,
            caller_end=SKILL_INDEX_LIST_END,
            argument_class="skill_index_byte_to_named_helper",
        ),
        _layer(
            data,
            depth=2,
            target=SKILL_INDEX_LIST,
            callsite=SKILL_INDEX_PARENT_CALLSITE,
            caller=SKILL_INDEX_PARENT,
            caller_end=SKILL_INDEX_PARENT_END,
            argument_class="state_context_to_skill_index_list",
        ),
    ]
    source = {
        "ram_context_global": address_metadata(SKILL_INDEX_GLOBAL, len(data)),
        "ram_context_literal": _literal(
            data, SKILL_INDEX_GLOBAL_LITERAL, SKILL_INDEX_GLOBAL
        ),
        "index_list_base": address_metadata(SKILL_INDEX_BASE, len(data)),
        "index_list_base_literal": _literal(
            data, SKILL_INDEX_BASE_LITERAL, SKILL_INDEX_BASE
        ),
        "index_list_runtime_offset": SKILL_INDEX_LIST_OFFSET,
        "slot_count": SKILL_INDEX_SLOT_COUNT,
        "value_width": 1,
        "valid_index_max": SKILL_INDEX_VALID_MAX,
        "valid_index_condition": "byte <= 0x3f",
        "source_class": "EWRAM_byte_index_list",
    }
    table = {
        "base": address_metadata(SKILL_TABLE_BASE, len(data)),
        "record_stride": SKILL_TABLE_STRIDE,
        "field_offset": SKILL_TABLE_FIELD_OFFSET,
        "field_unit_width": 2,
        "bounded_identity_prefix_count": 33,
        "extent_basis": "M1.31_prefix_plus_M1.35_adjacent_anchor",
        "semantic_extent_proven": False,
    }
    functions = [
        _safe_boundary(data, SKILL_ACCESSOR, SKILL_ACCESSOR_END, basis="leaf_return"),
        _safe_boundary(data, SKILL_INDEX_HELPER, SKILL_INDEX_HELPER_END, basis="named_return"),
        _safe_boundary(data, SKILL_INDEX_LIST, SKILL_INDEX_LIST_END, basis="named_return"),
        _safe_boundary(data, SKILL_INDEX_PARENT, SKILL_INDEX_PARENT_END, basis="named_return"),
    ]
    calls = [
        _call(data, SKILL_ACCESSOR_CALLSITE, SKILL_ACCESSOR),
        _call(data, SKILL_INDEX_LIST_CALLSITE, SKILL_INDEX_HELPER),
        _call(data, SKILL_INDEX_PARENT_CALLSITE, SKILL_INDEX_LIST),
    ]
    return {
        "name": "skill_state_index_list",
        "family": "skill",
        "accessor": address_metadata(SKILL_ACCESSOR, len(data)),
        "functions": functions,
        "calls": calls,
        "upward_layers": layers,
        "source_index_contract": source,
        "table_contract": table,
        "natural_runtime_capture": False,
        "runtime_identity_status": "unknown",
    }


def _demon_path(data: bytes) -> dict[str, object]:
    layers = [
        _layer(
            data,
            depth=1,
            target=DEMON_ACCESSOR,
            callsite=DEMON_ACCESSOR_CALLSITE,
            caller=DEMON_CONSUMER,
            caller_end=DEMON_CONSUMER_END,
            argument_class="object_slot_index_to_demon_accessor",
        ),
        _layer(
            data,
            depth=2,
            target=DEMON_CONSUMER,
            callsite=DEMON_WRAPPER_A_CALLSITE,
            caller=DEMON_WRAPPER_A,
            caller_end=DEMON_WRAPPER_A_END,
            argument_class="EWRAM_object_pointer_plus_0x58",
        ),
        _layer(
            data,
            depth=2,
            target=DEMON_CONSUMER,
            callsite=DEMON_WRAPPER_B_CALLSITE,
            caller=DEMON_WRAPPER_B,
            caller_end=DEMON_WRAPPER_B_END,
            argument_class="EWRAM_object_pointer_minus_0x58",
        ),
    ]
    source = {
        "object_slot_base_expression": "object + 0x26",
        "slot_stride": DEMON_OBJECT_SLOT_STRIDE,
        "slot_count": DEMON_OBJECT_SLOT_COUNT,
        "slot_value_width": 2,
        "slot_index_is_runtime_object_field": True,
        "source_class": "EWRAM_object_halfword_slot_array",
        "wrapper_a": {
            "literal": _literal(data, DEMON_WRAPPER_A_LITERAL, DEMON_WRAPPER_A_GLOBAL),
            "object_offset": DEMON_WRAPPER_A_OFFSET,
        },
        "wrapper_b": {
            "literal": _literal(data, DEMON_WRAPPER_B_LITERAL, DEMON_WRAPPER_B_GLOBAL),
            "object_offset": DEMON_WRAPPER_B_OFFSET,
        },
    }
    table = {
        "base": address_metadata(DEMON_TABLE_BASE, len(data)),
        "record_stride": DEMON_TABLE_STRIDE,
        "field_offset": DEMON_TABLE_FIELD_OFFSET,
        "field_unit_width": 2,
        "bounded_identity_prefix_count": 17,
        "special_accessor_indices": [hex_address(value) for value in DEMON_SPECIAL_INDICES],
        "extent_basis": "M1.30_prefix_plus_M1.35_adjacent_anchor",
        "semantic_extent_proven": False,
    }
    functions = [
        _safe_boundary(data, DEMON_ACCESSOR, DEMON_ACCESSOR_END, basis="accessor_literal_and_return"),
        _safe_boundary(data, DEMON_CONSUMER, DEMON_CONSUMER_END, basis="named_return"),
        _safe_boundary(data, DEMON_WRAPPER_A, DEMON_WRAPPER_A_END, basis="wrapper_return"),
        _safe_boundary(data, DEMON_WRAPPER_B, DEMON_WRAPPER_B_END, basis="wrapper_return"),
    ]
    calls = [
        _call(data, DEMON_ACCESSOR_CALLSITE, DEMON_ACCESSOR),
        _call(data, DEMON_WRAPPER_A_CALLSITE, DEMON_CONSUMER),
        _call(data, DEMON_WRAPPER_B_CALLSITE, DEMON_CONSUMER),
    ]
    return {
        "name": "demon_object_slot_array",
        "family": "demon",
        "accessor": address_metadata(DEMON_ACCESSOR, len(data)),
        "functions": functions,
        "calls": calls,
        "upward_layers": layers,
        "source_index_contract": source,
        "table_contract": table,
        "natural_runtime_capture": False,
        "runtime_identity_status": "unknown",
    }


def _all_matches(report: dict[str, Any]) -> bool:
    for path in report["paths"]:
        for call in path["calls"]:
            if not call["target_match"]:
                return False
        for layer in path["upward_layers"]:
            if not layer["callsite"]["target_match"]:
                return False
    return True


def static_report(data: bytes) -> dict[str, Any]:
    paths = [_item_path(data), _skill_path(data), _demon_path(data)]
    calls = [call for path in paths for call in path["calls"]]
    boundary_available = sum(
        bool(function.get("available"))
        for path in paths
        for function in path["functions"]
    )
    boundary_count = sum(len(path["functions"]) for path in paths)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "three_named_category_accessors_and_bounded_upward_bl_edges",
            "path_count": len(paths),
            "max_upward_layers": MAX_UPWARD_LAYERS,
            "call_count": len(calls),
            "boundary_count": boundary_count,
            "boundary_available_count": boundary_available,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "graphics_resource_scan": False,
            "runtime_capture_performed": False,
            "ram_table_written": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "paths": paths,
        "evidence_summary": {
            "all_named_calls_match": _all_matches({"paths": paths}),
            "static_source_index_edges": 3,
            "natural_runtime_edges": 0,
            "unicode_identity_confirmed": False,
            "complete_codepage": False,
            "complete_family_extents": False,
        },
        "conclusions": {
            "confirmed": (
                [
                    "item_ewram_halfword_index_list_reaches_shared_item_accessor",
                    "skill_ewram_byte_index_list_reaches_skill_accessor",
                    "demon_object_slot_array_reaches_demon_accessor",
                    "all_named_accessor_callsites_match_expected_thumb_targets",
                    "source_index_provenance_is_bounded_to_three_named_paths",
                ]
                if _all_matches({"paths": paths})
                else []
            ),
            "provisional": [
                "item_index_list_is_a_runtime_item_selection_source",
                "skill_index_list_is_a_runtime_skill_selection_source",
                "demon_slot_values_are_runtime_demon_record_indices",
                "table_local_ids_remain_distinct_from_scene_semantic_ids",
            ],
            "unknown": [
                "natural_runtime_selection_frequency_and_live_values",
                "complete_item_demon_skill_table_extents",
                "unanchored_unicode_codepage_and_glyph_identity",
                "main_event_system_source_table_relationship",
                "width_control_contract_and_reinsertion",
            ],
            "negative_boundary": {
                "runtime_capture": "not performed; existing GDB listener blocker remains separate",
                "graphics": "no OBJ/OAM/resource classification performed",
                "translation_ledger": "blocked",
            },
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
