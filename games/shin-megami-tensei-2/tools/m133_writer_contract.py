#!/usr/bin/env python3
"""Bounded A5TJ text-cursor and OAM-writer layout contract.

M1.33 stays on the already named 16-bit text path.  It verifies the Thumb
function boundaries, literal pools, callsites, and field operations around
``0x080aa1f4``.  It also verifies the two bounded 16-bit readers' control
branches and their caller-supplied cursor step.  The report contains only
addresses, masks, hashes, lengths, counts, and status metadata; it never
emits ROM instructions, source units, decoded text, OAM bytes, or a ledger.

The synthetic layout fixture is intentionally separate from ROM data.  It
checks the reversible modulo fields that a reinsertion encoder can preserve
from an existing descriptor template, without claiming that the complete
runtime font or screen-width contract is solved.
"""

from __future__ import annotations

import argparse
import hashlib
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
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m111_obj_consumer import _direct_bl_callers_index  # noqa: E402
from m19_state_mapping import _function_end  # noqa: E402


SCHEMA = "smt2.m1.33.writer-layout.v1"

WRITER = 0x080AA1F4
WRITER_END = 0x080AA2D2
OAM_ALLOCATOR = 0x080A9EA8
OAM_ALLOCATOR_END = 0x080A9F04

RENDER_SMALL = 0x080AC218
RENDER_SMALL_END = 0x080AC296
RENDER_LARGE = 0x080AC2A0
RENDER_LARGE_END = 0x080AC32A
STRING_SMALL = 0x080AC334
STRING_SMALL_END = 0x080AC3A8
STRING_LARGE = 0x080AC3AC
STRING_LARGE_END = 0x080AC434

DESCRIPTOR = 0x0815EE18
WRITER_ALLOC_CALLSITE = 0x080AA234
SMALL_WRITER_CALLSITE = 0x080AC286
LARGE_WRITER_CALLSITE = 0x080AC318
SMALL_RENDER_CALLSITE = 0x080AC37E
LARGE_RENDER_CALLSITE = 0x080AC40A

FONT_DESCRIPTOR_SMALL_LOAD = 0x080AC274
FONT_DESCRIPTOR_LARGE_LOAD = 0x080AC306

LINE_BREAK_UNIT = 0x0300
TERMINATOR_UNIT = 0x0301


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + max(0, length))]


def _safe_read_u16(data: bytes, address: int) -> int | None:
    try:
        return read_u16(data, address)
    except (ValueError, IndexError):
        return None


def _hex(value: int) -> str:
    return f"0x{value:08x}"


def _boundary(data: bytes, entry: int, expected_end: int) -> dict[str, object]:
    raw = _window(data, entry, expected_end - entry)
    try:
        detected_end = _function_end(data, entry)
    except (ValueError, IndexError):
        detected_end = None
    prologue = _safe_read_u16(data, entry)
    return {
        "entry": address_metadata(entry, len(data)),
        "expected_end_exclusive": hex_address(expected_end),
        "detected_end_exclusive": (
            None if detected_end is None else hex_address(detected_end)
        ),
        "code_length": len(raw),
        "code_hash": sha256(raw) if raw else None,
        "thumb_push_prologue": (
            prologue is not None and (prologue & 0xFF00) == 0xB500
        ),
        "return_instruction_boundary": (
            (
                lambda value: value is not None and (value & 0xFF87) == 0x4700
            )(_safe_read_u16(data, expected_end - 2))
        ),
        "boundary_match": detected_end == expected_end,
    }


def _instruction_checks(
    data: bytes, checks: Iterable[tuple[int, str, int]]
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for address, role, expected in checks:
        observed = _safe_read_u16(data, address)
        result.append(
            {
                "pc": hex_address(address),
                "role": role,
                "verified": observed == expected,
            }
        )
    return result


def _literal(data: bytes, instruction: int, expected: int) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction)
        observed = int(str(loaded["value"]), 16)
        return {
            "pc": hex_address(instruction),
            "literal_address": loaded["literal_address"],
            "loaded_register": loaded["register"],
            "expected_value": _hex(expected),
            "observed_value": _hex(observed),
            "value_match": observed == expected,
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return {
            "pc": hex_address(instruction),
            "expected_value": _hex(expected),
            "value_match": False,
        }


def _call(data: bytes, callsite: int, expected: int) -> dict[str, object]:
    try:
        observed = thumb_bl_target(data, callsite)
    except (TypeError, ValueError, IndexError):
        observed = None
    return {
        "callsite": hex_address(callsite),
        "expected_target": address_metadata(expected, len(data)),
        "observed_target": (
            None if observed is None else address_metadata(observed, len(data))
        ),
        "target_match": observed == expected,
    }


def _writer_instruction_contract(data: bytes) -> dict[str, object]:
    checks = _instruction_checks(
        data,
        (
            (0x080AA200, "descriptor_to_slot_argument", 0x1C08),
            (0x080AA202, "record_flags_argument_capture", 0x1C1D),
            (0x080AA204, "stack_argument_0_load", 0x9908),
            (0x080AA206, "stack_argument_1_load", 0x9B09),
            (0x080AA208, "stack_argument_2_load", 0x9E0A),
            (0x080AA20A, "register_2_low16", 0x0412),
            (0x080AA20E, "register_3_low16", 0x4692),
            (0x080AA214, "stack_argument_0_low16", 0x0409),
            (0x080AA218, "stack_argument_1_low16", 0x041B),
            (0x080AA21C, "stack_argument_2_low16", 0x0436),
            (0x080AA230, "slot_low8", 0x0600),
            (0x080AA23C, "copy_descriptor_attr0", 0x8808),
            (0x080AA240, "copy_descriptor_attr1", 0x8848),
            (0x080AA244, "copy_descriptor_attr2", 0x8888),
            (0x080AA25E, "attr0_low_byte_load", 0x7818),
            (0x080AA260, "attr0_add_y_delta", 0x1980),
            (0x080AA262, "attr0_low_byte_store", 0x7018),
            (0x080AA266, "flags_low2_extract", 0x4005),
            (0x080AA268, "flags_to_attr2_bits_10_11", 0x00AD),
            (0x080AA29E, "attr2_low10_load", 0x889A),
            (0x080AA2A4, "attr2_add_tile_delta", 0x1879),
            (0x080AA2B4, "attr2_high_byte_load", 0x795A),
            (0x080AA2B6, "palette_nibble_extract", 0x0911),
            (0x080AA2B8, "palette_delta_add", 0x4451),
            (0x080AA2C2, "attr2_high_byte_store", 0x7158),
        ),
    )
    return {
        "checks": checks,
        "all_verified": bool(checks) and all(item["verified"] for item in checks),
        "checked_instruction_count": len(checks),
    }


def _reader_instruction_contract(data: bytes) -> dict[str, object]:
    checks = _instruction_checks(
        data,
        (
            (0x080AC342, "small_step_stack_load", 0x9809),
            (0x080AC344, "small_step_argument_load", 0x9C0A),
            (0x080AC362, "small_line_break_constant_low", 0x20C0),
            (0x080AC364, "small_line_break_constant_shift", 0x0080),
            (0x080AC382, "small_cursor_step_add", 0x1928),
            (0x080AC388, "small_unit_advance_two_bytes", 0x3602),
            (0x080AC38E, "small_zero_terminator_compare", 0x2800),
            (0x080AC3BA, "large_step_stack_load", 0x980B),
            (0x080AC3BC, "large_step_argument_load", 0x9C0C),
            (0x080AC3E4, "large_line_break_constant_low", 0x20C0),
            (0x080AC3E6, "large_line_break_constant_shift", 0x0080),
            (0x080AC40E, "large_cursor_step_add", 0x1930),
            (0x080AC414, "large_unit_advance_two_bytes", 0x3702),
            (0x080AC41A, "large_zero_terminator_compare", 0x2800),
        ),
    )
    return {
        "checks": checks,
        "all_verified": bool(checks) and all(item["verified"] for item in checks),
        "checked_instruction_count": len(checks),
    }


def _apply_layout(
    descriptor: tuple[int, int, int],
    *,
    palette_delta: int,
    flags: int,
    tile_delta: int,
    x_mode: int,
    y_delta: int,
) -> tuple[int, int, int]:
    """Apply only the writer's audited modulo fields to a descriptor fixture."""
    attr0, attr1, attr2 = descriptor
    attr0 = (attr0 & 0xFF00) | ((attr0 + y_delta) & 0xFF)

    attr1 = (attr1 & ~0x01FF) | (
        ((attr1 & 0x01FF) + (x_mode & 0x01FF)) & 0x01FF
    )
    if (x_mode & 0xF000) == 0x8000:
        attr1 |= 0x10 << 8
    else:
        attr1 &= ~(0x11 << 8)

    attr2 = (attr2 & ~0x03FF) | (((attr2 & 0x03FF) + tile_delta) & 0x03FF)
    attr2 = (attr2 & ~(0x03 << 10)) | ((flags & 0x03) << 10)
    palette = (((attr2 >> 12) & 0x0F) + palette_delta) & 0x0F
    attr2 = (attr2 & 0x0FFF) | (palette << 12)
    return attr0 & 0xFFFF, attr1 & 0xFFFF, attr2 & 0xFFFF


def _decode_modulo_fields(
    descriptor: tuple[int, int, int], output: tuple[int, int, int]
) -> dict[str, object]:
    attr0, attr1, attr2 = descriptor
    out0, out1, out2 = output
    return {
        "y_delta": ((out0 & 0xFF) - (attr0 & 0xFF)) & 0xFF,
        "x_delta": ((out1 & 0x01FF) - (attr1 & 0x01FF)) & 0x01FF,
        "tile_delta": ((out2 & 0x03FF) - (attr2 & 0x03FF)) & 0x03FF,
        "flags": (out2 >> 10) & 0x03,
        "palette_delta": (((out2 >> 12) & 0x0F) - ((attr2 >> 12) & 0x0F)) & 0x0F,
        "mode_is_8000": bool(out1 & (0x10 << 8)),
    }


def _synthetic_roundtrip() -> dict[str, object]:
    descriptor = (0x4217, 0xA2C0, 0xB843)
    arguments = {
        "palette_delta": 0x1234,
        "flags": 0x02,
        "tile_delta": 0x1456,
        "x_mode": 0x8123,
        "y_delta": 0x0178,
    }
    output = _apply_layout(descriptor, **arguments)
    decoded = _decode_modulo_fields(descriptor, output)
    canonical = {
        "y_delta": arguments["y_delta"] & 0xFF,
        "x_delta": arguments["x_mode"] & 0x1FF,
        "tile_delta": arguments["tile_delta"] & 0x3FF,
        "flags": arguments["flags"] & 0x03,
        "palette_delta": arguments["palette_delta"] & 0x0F,
        "mode_is_8000": True,
    }
    manifest = hashlib.sha256(
        json.dumps(decoded, sort_keys=True).encode("ascii")
    ).hexdigest()
    return {
        "modulo_fields_roundtrip": decoded == canonical,
        "canonical_field_count": len(canonical),
        "fixture_manifest_hash": manifest,
        "raw_fixture_emitted": False,
    }


def _layout_contract() -> dict[str, object]:
    return {
        "oam_record_bytes": 6,
        "descriptor_template": {
            "source": "r0 pointer to three halfwords",
            "attr0_offset": 0,
            "attr1_offset": 2,
            "attr2_offset": 4,
        },
        "arguments": {
            "r0": "descriptor_pointer",
            "r1": "oam_slot_low8",
            "r2": "attr2_palette_nibble_delta_mod_16",
            "r3": "attr2_flags_low2_and_mode_high_nibble",
            "stack_0": "attr2_tile_delta_mod_0x400",
            "stack_4": "attr1_x_delta_mod_0x200_and_mode",
            "stack_8": "attr0_y_delta_mod_0x100",
        },
        "fields": {
            "attr0": {
                "offset": 0,
                "operation": "descriptor_attr0_low_byte_plus_stack_8_low16_then_truncate",
                "preserved_mask": _hex(0xFF00),
                "delta_mask": _hex(0xFF),
            },
            "attr1": {
                "offset": 2,
                "operation": "descriptor_attr1_low9_plus_stack_4_low9_modulo",
                "preserved_mask": _hex(0xFE00),
                "delta_mask": _hex(0x1FF),
                "mode_selector": _hex(0x8000),
                "mode_output_bit": _hex(0x1000),
                "non_mode_clear_mask": _hex(0x1100),
            },
            "attr2": {
                "offset": 4,
                "operation": "tile_low10_plus_stack_0_then_flags_and_palette_nibble",
                "tile_delta_mask": _hex(0x3FF),
                "flags_mask": _hex(0x0C00),
                "palette_delta_mask": _hex(0xF000),
            },
        },
        "modulo_layout_roundtrip": _synthetic_roundtrip(),
    }


def static_report(data: bytes) -> dict[str, object]:
    boundaries = {
        "writer": _boundary(data, WRITER, WRITER_END),
        "oam_allocator": _boundary(data, OAM_ALLOCATOR, OAM_ALLOCATOR_END),
        "render_small": _boundary(data, RENDER_SMALL, RENDER_SMALL_END),
        "render_large": _boundary(data, RENDER_LARGE, RENDER_LARGE_END),
        "string_small": _boundary(data, STRING_SMALL, STRING_SMALL_END),
        "string_large": _boundary(data, STRING_LARGE, STRING_LARGE_END),
    }
    calls = [
        _call(data, WRITER_ALLOC_CALLSITE, OAM_ALLOCATOR),
        _call(data, SMALL_WRITER_CALLSITE, WRITER),
        _call(data, LARGE_WRITER_CALLSITE, WRITER),
        _call(data, SMALL_RENDER_CALLSITE, RENDER_SMALL),
        _call(data, LARGE_RENDER_CALLSITE, RENDER_LARGE),
    ]
    literals = [
        _literal(data, 0x080AA22C, 0x00007FFF),
        _literal(data, 0x080AA24E, 0x000001FF),
        _literal(data, 0x080AA256, 0xFFFFFE00),
        _literal(data, 0x080AA2A6, 0x000003FF),
        _literal(data, 0x080AA2AC, 0xFFFFFC00),
        _literal(data, FONT_DESCRIPTOR_SMALL_LOAD, DESCRIPTOR),
        _literal(data, FONT_DESCRIPTOR_LARGE_LOAD, DESCRIPTOR),
        _literal(data, 0x080AC392, TERMINATOR_UNIT),
        _literal(data, 0x080AC41E, TERMINATOR_UNIT),
    ]
    writer_checks = _writer_instruction_contract(data)
    reader_checks = _reader_instruction_contract(data)
    all_boundaries = all(
        item["boundary_match"] and item["thumb_push_prologue"]
        and item["return_instruction_boundary"]
        for item in boundaries.values()
    )
    all_literals = all(item["value_match"] for item in literals)
    all_calls = all(item["target_match"] for item in calls)
    static_confirmed = (
        all_boundaries
        and all_literals
        and all_calls
        and bool(writer_checks["all_verified"])
        and bool(reader_checks["all_verified"])
    )
    writer_callers = _direct_bl_callers_index(data, (WRITER,), limit=64)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "named_writer_reader_layout_contract",
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "runtime_capture_performed": False,
            "raw_instructions_emitted": False,
            "raw_oam_emitted": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "boundaries": boundaries,
        "call_edges": calls,
        "literal_edges": literals,
        "writer_instruction_contract": writer_checks,
        "reader_instruction_contract": reader_checks,
        "writer_callers": {
            hex_address(target): callers
            for target, callers in writer_callers.items()
        },
        "layout_contract": _layout_contract(),
        "control_contract": {
            "line_break_unit": hex_address(LINE_BREAK_UNIT),
            "terminator_units": ["0x0000", hex_address(TERMINATOR_UNIT)],
            "non_control_units": "nonzero_units_other_than_0x0300_and_0x0301_call_renderer",
            "reader_unit_width": 2,
            "reader_step_bytes": 2,
            "step_source": {
                "small": "caller_stack_argument_at_entry_plus_0x28_normalized_to_low16",
                "large": "caller_stack_argument_at_entry_plus_0x30_normalized_to_low16",
            },
            "step_application": {
                "small": "normal_unit_cursor_plus_step; line_break_base_plus_step_and_cursor_reset",
                "large": "normal_unit_cursor_plus_step; line_break_base_plus_step_and_cursor_reset",
            },
            "glyph_dependent_width_lookup_in_named_readers": False,
            "translated_pixel_width_confirmed": False,
        },
        "identity": {
            "named_writer_layout_confirmed": static_confirmed,
            "control_and_cursor_step_contract_confirmed": static_confirmed,
            "complete_codepage": False,
            "complete_width_contract": False,
            "runtime_pixel_layout_confirmed": False,
        },
        "conclusions": {
            "confirmed": (
                [
                    "writer_boundary_and_embedded_literal_pools_match",
                    "descriptor_three_halfword_template_reaches_oam_allocator",
                    "oam_attr0_attr1_attr2_modulo_field_mapping_is_reextractable",
                    "named_readers_have_0x0300_line_break_and_0x0000_or_0x0301_termination",
                    "named_readers_use_caller_supplied_fixed_cursor_step",
                    "bounded_modulo_layout_fixture_roundtrips",
                ]
                if static_confirmed
                else []
            ),
            "provisional": [
                "cursor_step_is_a_layout_advance_not_an_independent_unicode_width_table",
                "oam_field_axis_and_screen_pixel_budget_need_runtime_or_scene_context",
            ],
            "unknown": [
                "complete_codepage_and_unanchored_unicode_identity",
                "translated_font_replacement_and_screen_fit_budget",
                "natural_runtime_writer_arguments_and_live_oam_record_values",
                "source_table_extent_for_main_script_and_event_text",
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
