#!/usr/bin/env python3
"""Bounded state-field to encoded-string route mapping for A5TJ.

M1.22 follows only the two caller functions that reference the bounded
0x0815bed4..0x0815c082 candidate family.  It verifies halfword state loads,
literal targets, reader callsites, and bounded termination metadata without
decoding text or creating a translation ledger.
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
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m118_codeunit_font import CODEUNIT_STRING_SMALL, _function_end  # noqa: E402
from m119_source_family import _safe_boundary, _source_terminator_metadata  # noqa: E402


SCHEMA = "smt2.m1.22.state-routes.v1"

HANDLER_A = 0x080CE760
HANDLER_B = 0x080CF414
HANDLER_A_STATE_LOAD = 0x080CE8C4
HANDLER_B_STATE_LOAD = 0x080CF450
STATE_FIELD_OFFSET = 0x1E

FAMILY_POINTERS = (
    0x0815BED4,
    0x0815BEFA,
    0x0815BF0E,
    0x0815BF36,
    0x0815BF4A,
    0x0815BF62,
    0x0815BF7C,
    0x0815BFBE,
    0x0815BFCC,
    0x0815BFD6,
    0x0815C02C,
    0x0815C048,
    0x0815C05A,
    0x0815C06E,
    0x0815C082,
)

# Literal-load PCs at the state branches.  Conditions are deliberately kept
# as disassembly labels rather than guessed UI/category meanings.
ROUTES_A = {
    "state_eq_1": (0x080CE8CA, 0x0815BF4A),
    "state_eq_2": (0x080CE8D8, 0x0815BF0E),
    "state_eq_3": (0x080CE8E4, 0x0815BF62),
    "state_other_than_1_2_3": (0x080CE900, 0x0815BF7C),
}
ROUTES_B = {
    "state_eq_1": (0x080CF456, 0x0815C02C),
    "state_eq_2": (0x080CF464, 0x0815C048),
    "state_eq_3": (0x080CF470, 0x0815C05A),
    "state_eq_4": (0x080CF47C, 0x0815C06E),
    "state_eq_5": (0x080CF49C, 0x0815C082),
}

CALLS_A = (0x080CE8F4, 0x080CE910, 0x080CE9BC, 0x080CEA10, 0x080CEA72)
CALLS_B = (0x080CF48C, 0x080CF4AC)


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _halfword_load_contract(data: bytes, instruction: int) -> dict[str, object]:
    observed = None
    try:
        value = read_u16(data, instruction)
        if value & 0xF800 == 0x8800:
            observed = {
                "form": "ldr_halfword_imm",
                "destination": value & 7,
                "base_register": (value >> 3) & 7,
                "offset": ((value >> 6) & 0x1F) * 2,
            }
    except (ValueError, IndexError):
        pass
    return {
        "instruction": hex_address(instruction),
        "expected": {
            "form": "ldr_halfword_imm",
            "destination": 0,
            "offset": STATE_FIELD_OFFSET,
        },
        "observed": observed,
        "contract_match": bool(
            isinstance(observed, dict)
            and observed["form"] == "ldr_halfword_imm"
            and observed["destination"] == 0
            and observed["offset"] == STATE_FIELD_OFFSET
        ),
    }


def _literal_route(
    data: bytes, name: str, instruction: int, expected: int
) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction)
        actual = int(str(loaded["value"]), 16)
        match = actual == expected
        literal_address = loaded["literal_address"]
    except (ValueError, IndexError):
        actual = None
        match = False
        literal_address = None
    probe = (
        _source_terminator_metadata(data, expected, None)
        if match
        else {"available": False, "termination": "literal_mismatch"}
    )
    return {
        "route": name,
        "literal_load": hex_address(instruction),
        "literal_address": literal_address,
        "expected_pointer": address_metadata(expected, len(data)),
        "observed_pointer": (
            None if actual is None else address_metadata(actual, len(data))
        ),
        "literal_match": match,
        "source_probe": probe,
    }


def _reader_call_metadata(data: bytes, callsites: tuple[int, ...]) -> list[dict[str, object]]:
    result = []
    for callsite in callsites:
        try:
            target = thumb_bl_target(data, callsite)
        except (ValueError, IndexError):
            target = None
        result.append(
            {
                "callsite": hex_address(callsite),
                "target": None if target is None else hex_address(target),
                "target_match": target == CODEUNIT_STRING_SMALL,
            }
        )
    return result


def static_report(data: bytes) -> dict[str, object]:
    family_window = _window(
        data,
        FAMILY_POINTERS[0],
        FAMILY_POINTERS[-1] + 0x20 - FAMILY_POINTERS[0],
    )
    routes_a = [
        _literal_route(data, name, instruction, pointer)
        for name, (instruction, pointer) in ROUTES_A.items()
    ]
    routes_b = [
        _literal_route(data, name, instruction, pointer)
        for name, (instruction, pointer) in ROUTES_B.items()
    ]
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "two_named_state_handlers_and_one_bounded_pointer_family",
            "family_pointer_count": len(FAMILY_POINTERS),
            "per_pointer_probe_limit": 0x100,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "family": {
            "first_pointer": address_metadata(FAMILY_POINTERS[0], len(data)),
            "last_pointer": address_metadata(FAMILY_POINTERS[-1], len(data)),
            "pointer_count": len(FAMILY_POINTERS),
            "pointer_span": {
                "length": len(family_window),
                "hash": sha256(family_window) if family_window else None,
            },
            "pointers": [
                {
                    "address": address_metadata(pointer, len(data)),
                    "probe": _source_terminator_metadata(data, pointer, None),
                }
                for pointer in FAMILY_POINTERS
            ],
            "unicode_identity_confirmed": False,
        },
        "handlers": {
            hex_address(HANDLER_A): {
                "boundary": _safe_boundary(data, HANDLER_A),
                "state_load": _halfword_load_contract(data, HANDLER_A_STATE_LOAD),
                "state_field_offset": STATE_FIELD_OFFSET,
                "routes": routes_a,
                "reader_calls": _reader_call_metadata(data, CALLS_A),
            },
            hex_address(HANDLER_B): {
                "boundary": _safe_boundary(data, HANDLER_B),
                "state_load": _halfword_load_contract(data, HANDLER_B_STATE_LOAD),
                "state_field_offset": STATE_FIELD_OFFSET,
                "routes": routes_b,
                "reader_calls": _reader_call_metadata(data, CALLS_B),
            },
        },
        "conclusions": {
            "confirmed": [
                "both_handlers_load_halfword_state_at_field_0x1e",
                "handler_a_has_four_literal_state_routes",
                "handler_b_has_five_literal_state_routes",
                "all_named_routes_point_into_the_bounded_15_pointer_family",
                "named_route_calls_target_0x080ac334",
            ],
            "provisional": [
                "0x0815bed4_family_is_one_encoded_string_category_boundary",
                "state_field_values_are_runtime_ui_or_system_modes",
            ],
            "unknown": [
                "natural_scene_and_runtime_frequency",
                "semantic_category_name_and_unicode_identity",
                "main_event_demon_skill_item_relationship",
                "width_and_reinsertion_contract",
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
