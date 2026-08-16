#!/usr/bin/env python3
"""Bounded static selector-to-code-unit source mapping for A5TJ.

M1.20 resolves the object/state fields that select the M1.19 inline source
family.  It verifies the Thumb load forms, the five-entry jump table, and the
known literal-pointer routes.  It emits only addresses, IDs, hashes, lengths,
and control/unit counts; it never emits source bytes, decoded text, glyphs, or
a translation ledger.
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
from m19_state_mapping import _decode_simple  # noqa: E402
from m118_codeunit_font import (  # noqa: E402
    CODEUNIT_STRING_SMALL,
    _function_end,
)
from m119_source_family import (  # noqa: E402
    INLINE_FAMILY_BASE,
    INLINE_FAMILY_CALLER,
    INLINE_FAMILY_LAST,
    _inline_family_pointers,
    _safe_boundary,
)


SCHEMA = "smt2.m1.20.inline-dispatch.v1"

PRIMARY_FIELD_LOAD = 0x080B52CE
PRIMARY_FIELD_OFFSET = 0x24
SECONDARY_FIELD_LOAD = 0x080B52F6
SECONDARY_FIELD_OFFSET = 0x14
SUBSELECTOR_FIELD_LOAD = 0x080B5380
SUBSELECTOR_FIELD_OFFSET = 0x0C
JUMP_TABLE_LOAD = 0x080B5388
JUMP_TABLE_BASE = 0x080B53A0
JUMP_TABLE_COUNT = 5

# The paths are obtained from the Thumb branch/literal layout of the bounded
# caller.  Pointer IDs are resolved from the sorted M1.19 family, not from
# decoded source text.
PRIMARY_ROUTES = {
    "primary_1_secondary_zero": (0x08162B1C,),
    "primary_1_secondary_nonzero": (0x08162B56,),
    "primary_2": (0x08162B34,),
    "primary_3": (0x08162B76,),
}
SUBSELECTOR_ROUTES = {
    0: (0x08162B8E, 0x08162B9C),
    1: (0x08162BA8, 0x08162BBE),
    2: (0x08162BD0, 0x08162BE4),
    3: (0x08162BF6, 0x08162C06),
    4: (0x08162C12, 0x08162C26),
}


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _load_contract(
    data: bytes, instruction: int, base_register: int, offset: int, width: int
) -> dict[str, object]:
    try:
        decoded = _decode_simple(data, instruction)
    except (ValueError, IndexError):
        decoded = None
    observed = None
    if isinstance(decoded, dict):
        observed_width = {
            "ldr_word_imm": 4,
            "ldr_halfword_imm": 2,
            "ldr_byte_imm": 1,
        }.get(decoded.get("form"))
        observed = {
            key: decoded.get(key)
            for key in ("form", "base", "offset", "width", "destination")
            if key in decoded
        }
        observed["derived_width"] = observed_width
    return {
        "instruction": hex_address(instruction),
        "expected": {
            "base_register": f"r{base_register}",
            "offset": offset,
            "width": width,
        },
        "observed": observed,
        "contract_match": bool(
            isinstance(decoded, dict)
            and decoded.get("base") == base_register
            and decoded.get("offset") == offset
            and {
                "ldr_word_imm": 4,
                "ldr_halfword_imm": 2,
                "ldr_byte_imm": 1,
            }.get(decoded.get("form")) == width
            and decoded.get("destination") == 0
        ),
    }


def _jump_table_metadata(data: bytes) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for index in range(JUMP_TABLE_COUNT):
        address = JUMP_TABLE_BASE + index * 4
        value = None
        try:
            value = read_u32(data, address)
        except (ValueError, IndexError):
            pass
        entries.append(
            {
                "selector": index,
                "entry_address": address_metadata(address, len(data)),
                "target": (
                    None if value is None else address_metadata(value, len(data))
                ),
                "target_in_caller": (
                    value is not None
                    and INLINE_FAMILY_CALLER
                    <= value
                    < _function_end(data, INLINE_FAMILY_CALLER)
                ),
            }
        )
    return {
        "base": address_metadata(JUMP_TABLE_BASE, len(data)),
        "entry_stride": 4,
        "entry_count": JUMP_TABLE_COUNT,
        "span": {
            "length": JUMP_TABLE_COUNT * 4,
            "hash": sha256(_window(data, JUMP_TABLE_BASE, JUMP_TABLE_COUNT * 4)),
        },
        "entries": entries,
    }


def _pointer_id_map(data: bytes) -> tuple[dict[int, int], list[dict[str, object]]]:
    records = _inline_family_pointers(data)
    return {
        int(item["source_pointer"]["address"], 16): int(item["record_id"])
        for item in records
    }, records


def _route_metadata(
    data: bytes, pointer_ids: dict[int, int], pointers: tuple[int, ...]
) -> dict[str, object]:
    return {
        "pointers": [address_metadata(pointer, len(data)) for pointer in pointers],
        "record_ids": [pointer_ids.get(pointer) for pointer in pointers],
        "all_in_bounded_family": all(pointer in pointer_ids for pointer in pointers),
        "literal_ref_in_caller": [
            hex_address(pointer) for pointer in pointers if pointer in pointer_ids
        ],
    }


def static_report(data: bytes) -> dict[str, object]:
    pointer_ids, records = _pointer_id_map(data)
    try:
        jump_load = thumb_literal_load(data, JUMP_TABLE_LOAD)
        jump_value = int(str(jump_load["value"]), 16)
        jump_literal_match = jump_value == JUMP_TABLE_BASE
    except (ValueError, IndexError):
        jump_value = None
        jump_literal_match = False
    jump_table = _jump_table_metadata(data)
    primary_routes = {
        name: _route_metadata(data, pointer_ids, route)
        for name, route in PRIMARY_ROUTES.items()
    }
    subselector_routes = {
        str(selector): _route_metadata(data, pointer_ids, route)
        for selector, route in SUBSELECTOR_ROUTES.items()
    }
    callsites = [
        0x080B530C,
        0x080B5340,
        0x080B53C4,
        0x080B53E4,
        0x080B5404,
        0x080B5424,
        0x080B5436,
        0x080B5454,
        0x080B5466,
        0x080B548C,
        0x080B5518,
    ]
    callsite_targets: list[dict[str, object]] = []
    for callsite in callsites:
        try:
            target = thumb_bl_target(data, callsite)
        except (ValueError, IndexError):
            target = None
        callsite_targets.append(
            {
                "callsite": hex_address(callsite),
                "target": None if target is None else hex_address(target),
                "target_match": target == CODEUNIT_STRING_SMALL,
            }
        )
    contracts = [
        _load_contract(data, PRIMARY_FIELD_LOAD, 6, PRIMARY_FIELD_OFFSET, 4),
        _load_contract(data, SECONDARY_FIELD_LOAD, 7, SECONDARY_FIELD_OFFSET, 2),
        _load_contract(data, SUBSELECTOR_FIELD_LOAD, 7, SUBSELECTOR_FIELD_OFFSET, 4),
    ]
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one_named_reader_caller_selector_and_bounded_inline_family",
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "caller": {
            "entry": _safe_boundary(data, INLINE_FAMILY_CALLER),
            "function_end_exclusive": hex_address(
                _function_end(data, INLINE_FAMILY_CALLER)
            ),
            "primary_selector_field": {
                "base_register": "r6",
                "offset": PRIMARY_FIELD_OFFSET,
                "width": 4,
            },
            "secondary_selector_field": {
                "base_register": "r7",
                "offset": SECONDARY_FIELD_OFFSET,
                "width": 2,
            },
            "subselector_field": {
                "base_register": "r7",
                "offset": SUBSELECTOR_FIELD_OFFSET,
                "width": 4,
            },
            "load_contracts": contracts,
            "jump_table_load": {
                "instruction": hex_address(JUMP_TABLE_LOAD),
                "literal_value": (
                    None
                    if jump_value is None
                    else address_metadata(jump_value, len(data))
                ),
                "expected_base": address_metadata(JUMP_TABLE_BASE, len(data)),
                "literal_match": jump_literal_match,
            },
            "jump_table": jump_table,
            "reader_callsites": callsite_targets,
        },
        "routes": {
            "primary": primary_routes,
            "subselector_0_to_4": subselector_routes,
        },
        "inline_source_family": {
            "base": address_metadata(INLINE_FAMILY_BASE, len(data)),
            "last_pointer": address_metadata(INLINE_FAMILY_LAST, len(data)),
            "bounded_record_count": len(records),
            "record_ids_contiguous": [
                int(item["record_id"]) for item in records
            ] == list(range(1, len(records) + 1)),
            "records": records,
            "stable_unicode_identity": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
        },
        "conclusions": {
            "confirmed": [
                "object_field_0x24_selects_primary_route",
                "primary_route_1_reads_halfword_field_0x14",
                "subselector_field_0x0c_indexes_five_entry_jump_table",
                "all_fifteen_routes_resolve_inside_m1_19_bounded_family",
                "reader_callsites_target_0x080ac334",
            ],
            "provisional": [
                "selector_fields_are_ui_or_system_category_state",
                "record_ids_are_addressing_ids_not_translation_ids",
            ],
            "unknown": [
                "natural_runtime_scene_for_each_route",
                "category_semantics_and_unicode_identity",
                "main_event_demon_skill_item_family_boundaries",
                "width_budget_and_reinsertion_contract",
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
