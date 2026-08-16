#!/usr/bin/env python3
"""Bounded A5TJ code-unit to font-bank/renderer provenance.

M1.32 takes five already identity-anchored positions from the M1.30 demon and
M1.31 skill prefixes.  It follows each 16-bit unit through the audited font
bank address expression, hashes only the two 0x20-byte ROM source blocks used
by the builder, applies the statically verified byte swizzle, and checks the
inverse transform.  The report emits addresses, hashes, lengths, counts,
stable/reference IDs, and boolean status only.  It never emits unit values,
characters, source bytes, glyph bytes, or a translation ledger.

This is a static source-to-font addressing edge, not a natural runtime scene
capture.  The builder/renderer call graph is verified separately from the
identity anchors.
"""

from __future__ import annotations

import argparse
import hashlib
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
from m111_obj_consumer import _direct_bl_callers_index  # noqa: E402
from m118_codeunit_font import (  # noqa: E402
    FONT_BANK_POINTER_ENTRY_STRIDE,
    FONT_BANK_POINTER_TABLE,
    FONT_BUILD,
    FONT_DESCRIPTOR,
    FONT_SCRATCH_SMALL,
    CODEUNIT_RENDER_SMALL,
    font_source_address,
)
from m130_demon_crossmap import _DEMON_UNIT_MAP  # noqa: E402
from m131_skill_crossmap import _SKILL_UNIT_MAP  # noqa: E402
from m19_state_mapping import _function_end  # noqa: E402


SCHEMA = "smt2.m1.32.font-edge.v1"

FONT_BUILD_END = 0x080AC0D2
RENDER_SMALL_END = 0x080AC296
RENDER_WRITER_CALLSITE = 0x080AC286
RENDER_WRITER = 0x080AA1F4
FONT_BUILD_LITERAL = 0x080ABF34
FONT_BUILD_SCRATCH_LITERAL = 0x080ABF54
RENDER_MAP_LITERAL = 0x080AC25E
RENDER_DESCRIPTOR_LITERAL = 0x080AC274

FONT_BLOCK_BYTES = 0x20
PAIRED_BLOCK_OFFSET = 0x200
SWIZZLED_BYTES_PER_BLOCK = 0x40

DEMON_TABLE_BASE = 0x0819CB74
DEMON_TABLE_STRIDE = 0x60
DEMON_FIELD_OFFSET = 0x22
SKILL_TABLE_BASE = 0x0819B9F4
SKILL_TABLE_STRIDE = 0x1C
SKILL_FIELD_OFFSET = 0x06

# These five positions are selected from already cross-checked bounded names:
# three repeated-character positions in the demon prefix and two positions in
# the first skill prefix.  Expected characters stay private to comparison.
_ANCHORS = (
    {
        "reference_id": "demon-sequence-00-position-00",
        "family": "demon",
        "ordinal": 0,
        "position": 0,
        "expected": "サ",
    },
    {
        "reference_id": "demon-sequence-00-position-01",
        "family": "demon",
        "ordinal": 0,
        "position": 1,
        "expected": "タ",
    },
    {
        "reference_id": "demon-sequence-00-position-02",
        "family": "demon",
        "ordinal": 0,
        "position": 2,
        "expected": "ン",
    },
    {
        "reference_id": "skill-sequence-00-position-00",
        "family": "skill",
        "ordinal": 0,
        "position": 0,
        "expected": "ア",
    },
    {
        "reference_id": "skill-sequence-00-position-01",
        "family": "skill",
        "ordinal": 0,
        "position": 1,
        "expected": "ギ",
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


def _safe_u32(data: bytes, address: int) -> int | None:
    try:
        return read_u32(data, address)
    except (ValueError, IndexError):
        return None


def _safe_bl(data: bytes, address: int) -> int | None:
    try:
        return thumb_bl_target(data, address)
    except (ValueError, IndexError):
        return None


def _boundary(data: bytes, entry: int, expected_end: int) -> dict[str, object]:
    raw = _window(data, entry, expected_end - entry)
    try:
        detected = _function_end(data, entry)
    except (ValueError, IndexError):
        detected = None
    return {
        "entry": address_metadata(entry, len(data)),
        "expected_end_exclusive": hex_address(expected_end),
        "detected_end_exclusive": None if detected is None else hex_address(detected),
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "available": len(raw) == expected_end - entry,
        "boundary_match": detected == expected_end,
    }


def _literal(data: bytes, instruction: int, expected: int) -> dict[str, object]:
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


def _swizzle_byte(value: int) -> tuple[int, int]:
    """Mirror the two output stores in FONT_BUILD for one source byte."""
    first = ((value & 0xC0) >> 6) | (value & 0x30)
    second = ((value & 0x0C) >> 2) | ((value & 0x03) << 4)
    return first, second


def swizzle_block(source: bytes) -> bytes:
    """Apply the audited 0x20-byte to 0x40-byte font builder transform."""
    if len(source) != FONT_BLOCK_BYTES:
        raise ValueError("font source block must be exactly 0x20 bytes")
    output = bytearray()
    for offset in range(0, FONT_BLOCK_BYTES, 4):
        for value in source[offset : offset + 4]:
            output.extend(_swizzle_byte(value))
    return bytes(output)


def inverse_swizzle_block(transformed: bytes) -> bytes:
    """Invert the audited byte-pair transform without retaining raw output."""
    if len(transformed) != SWIZZLED_BYTES_PER_BLOCK:
        raise ValueError("swizzled block must be exactly 0x40 bytes")
    output = bytearray()
    for offset in range(0, len(transformed), 2):
        first, second = transformed[offset : offset + 2]
        value = ((first & 0x03) << 6) | (first & 0x30)
        value |= (second & 0x03) << 2
        value |= (second & 0x30) >> 4
        output.append(value)
    return bytes(output)


def _anchor_contract(data: bytes, anchor: dict[str, object]) -> dict[str, object]:
    family = str(anchor["family"])
    ordinal = int(anchor["ordinal"])
    position = int(anchor["position"])
    if family == "demon":
        table_base, stride, field_offset, unit_map = (
            DEMON_TABLE_BASE,
            DEMON_TABLE_STRIDE,
            DEMON_FIELD_OFFSET,
            _DEMON_UNIT_MAP,
        )
    else:
        table_base, stride, field_offset, unit_map = (
            SKILL_TABLE_BASE,
            SKILL_TABLE_STRIDE,
            SKILL_FIELD_OFFSET,
            _SKILL_UNIT_MAP,
        )
    record_address = table_base + ordinal * stride
    field_address = record_address + field_offset
    field = _window(data, field_address, 0x10)
    unit = _safe_u16(data, field_address + position * 2)
    unit_identity_match = unit is not None and unit_map.get(unit) == anchor["expected"]
    bank_index = None if unit is None else unit >> 8
    bank_pointer = (
        None
        if bank_index is None
        else _safe_u32(data, FONT_BANK_POINTER_TABLE + bank_index * FONT_BANK_POINTER_ENTRY_STRIDE)
    )
    source_address = (
        None
        if unit is None or bank_pointer is None
        else font_source_address(unit, bank_pointer)
    )
    first_block = b"" if source_address is None else _window(data, source_address, FONT_BLOCK_BYTES)
    paired_block = (
        b"" if source_address is None else _window(data, source_address + PAIRED_BLOCK_OFFSET, FONT_BLOCK_BYTES)
    )
    first_transformed = swizzle_block(first_block) if len(first_block) == FONT_BLOCK_BYTES else b""
    paired_transformed = swizzle_block(paired_block) if len(paired_block) == FONT_BLOCK_BYTES else b""
    inverse_ok = bool(
        first_transformed
        and paired_transformed
        and inverse_swizzle_block(first_transformed) == first_block
        and inverse_swizzle_block(paired_transformed) == paired_block
    )
    return {
        "reference_id": anchor["reference_id"],
        "family": family,
        "record_ordinal": ordinal,
        "position": position,
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": field_offset,
        "field_length": len(field),
        "field_hash": sha256(field) if field else None,
        "font_bank_index": bank_index,
        "font_bank_pointer": None if bank_pointer is None else address_metadata(bank_pointer, len(data)),
        "font_source_address": None if source_address is None else address_metadata(source_address, len(data)),
        "font_source_block_length": len(first_block),
        "font_source_block_hash": sha256(first_block) if first_block else None,
        "paired_source_address": (
            None
            if source_address is None
            else address_metadata(source_address + PAIRED_BLOCK_OFFSET, len(data))
        ),
        "paired_source_block_length": len(paired_block),
        "paired_source_block_hash": sha256(paired_block) if paired_block else None,
        "swizzled_block_length": len(first_transformed),
        "paired_swizzled_block_length": len(paired_transformed),
        "swizzle_hash": sha256(first_transformed + paired_transformed)
        if first_transformed and paired_transformed
        else None,
        "unit_identity_match": unit_identity_match,
        "inverse_transform_match": inverse_ok,
        "glyph_addressing_status": (
            "confirmed"
            if unit_identity_match and inverse_ok and source_address is not None
            else "unconfirmed"
        ),
        "raw_field_emitted": False,
        "raw_unit_emitted": False,
        "raw_font_bytes_emitted": False,
        "decoded_text_emitted": False,
    }


def static_report(data: bytes) -> dict[str, object]:
    anchors = [_anchor_contract(data, anchor) for anchor in _ANCHORS]
    builder = _boundary(data, FONT_BUILD, FONT_BUILD_END)
    renderer = _boundary(data, CODEUNIT_RENDER_SMALL, RENDER_SMALL_END)
    literals = [
        _literal(data, FONT_BUILD_LITERAL, FONT_BANK_POINTER_TABLE),
        _literal(data, FONT_BUILD_SCRATCH_LITERAL, FONT_SCRATCH_SMALL),
        _literal(data, RENDER_MAP_LITERAL, 0x020360DC),
        _literal(data, RENDER_DESCRIPTOR_LITERAL, FONT_DESCRIPTOR),
    ]
    calls = [
        {"callsite": hex_address(RENDER_WRITER_CALLSITE), "target": _safe_bl(data, RENDER_WRITER_CALLSITE)},
    ]
    all_anchors_confirmed = all(
        item["glyph_addressing_status"] == "confirmed" for item in anchors
    )
    static_confirmed = (
        builder["available"]
        and builder["boundary_match"]
        and renderer["available"]
        and renderer["boundary_match"]
        and all(item["value_match"] for item in literals)
        and calls[0]["target"] == RENDER_WRITER
        and all_anchors_confirmed
    )
    direct_callers = _direct_bl_callers_index(data, (FONT_BUILD, CODEUNIT_RENDER_SMALL), limit=16)
    manifest = json.dumps(
        {"anchors": [item["reference_id"] for item in anchors]},
        sort_keys=True,
    ).encode("utf-8")
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "five_identity_anchored_code_units_to_font_blocks_and_static_swizzle",
            "anchor_count": len(_ANCHORS),
            "font_block_bytes": FONT_BLOCK_BYTES,
            "paired_block_offset": PAIRED_BLOCK_OFFSET,
            "swizzled_bytes_per_block": SWIZZLED_BYTES_PER_BLOCK,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "runtime_capture_performed": False,
            "raw_field_emitted": False,
            "raw_unit_emitted": False,
            "raw_font_bytes_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "static_provenance": {
            "font_builder_boundary": builder,
            "renderer_boundary": renderer,
            "literal_edges": literals,
            "renderer_writer_call": {
                "callsite": hex_address(RENDER_WRITER_CALLSITE),
                "expected_target": address_metadata(RENDER_WRITER, len(data)),
                "observed_target": (
                    None
                    if calls[0]["target"] is None
                    else address_metadata(int(calls[0]["target"]), len(data))
                ),
                "target_match": calls[0]["target"] == RENDER_WRITER,
            },
            "direct_bl_callers": {
                hex_address(target): callers for target, callers in direct_callers.items()
            },
            "font_builder_contract": {
                "bank_table": address_metadata(FONT_BANK_POINTER_TABLE, len(data)),
                "bank_entry_stride": FONT_BANK_POINTER_ENTRY_STRIDE,
                "source_block_bytes": FONT_BLOCK_BYTES,
                "paired_source_offset": PAIRED_BLOCK_OFFSET,
                "swizzle_output_bytes_per_source_block": SWIZZLED_BYTES_PER_BLOCK,
                "paired_destination_offset": 0x400,
                "transform_inverse_tested": True,
            },
            "renderer_contract": {
                "font_cache_or_map_global": address_metadata(0x020360DC, len(data)),
                "descriptor": address_metadata(FONT_DESCRIPTOR, len(data)),
                "small_renderer_target": address_metadata(CODEUNIT_RENDER_SMALL, len(data)),
                "writer_target": address_metadata(RENDER_WRITER, len(data)),
            },
        },
        "glyph_edges": anchors,
        "identity": {
            "anchored_glyph_edge_count": sum(
                item["glyph_addressing_status"] == "confirmed" for item in anchors
            ),
            "anchor_count": len(anchors),
            "all_anchored_edges_confirmed": all_anchors_confirmed,
            "anchor_manifest_hash": hashlib.sha256(manifest).hexdigest(),
            "unicode_identity_for_selected_anchors": all(
                item["unit_identity_match"] for item in anchors
            ),
            "complete_codepage": False,
            "complete_width_contract": False,
        },
        "conclusions": {
            "confirmed": (
                [
                    "font_builder_bank_literal_and_renderer_boundaries_match",
                    "five_identity_anchored_units_have_reextractable_font_block_addresses",
                    "audited_byte_swizzle_has_reversible_inverse_for_all_selected_blocks",
                    "selected_units_reach_named_small_renderer_and_oam_writer_static_edge",
                ]
                if static_confirmed
                else []
            ),
            "provisional": [
                "selected_code_unit_to_font_block_identity_is_static_and_bounded",
                "font_block_hashes_are_source_provenance_not_rendered_runtime_capture",
            ],
            "unknown": [
                "natural_runtime_scene_and_live_font_cache_contents",
                "unanchored_unicode_codepage_and_complete_glyph_set",
                "control_code_width_rule_font_replacement_and_reinsertion",
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
