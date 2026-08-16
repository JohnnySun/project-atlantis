#!/usr/bin/env python3
"""Bounded A5TJ skill-record code-unit cross-map.

M1.31 follows the adjacent Thumb accessor ``0x080bf5c0`` and its bounded
caller ``0x080bf5d8`` to the ROM record family at ``0x0819b9f4``.  Thirty-two
public Japanese skill-name anchors are compared privately against the fixed
``+0x06`` field.  The report emits only addresses, boundaries, hashes,
lengths, counts, reference IDs, and match metadata; it never emits record
bytes, unit values, decoded text, glyphs, or a translation ledger.

The record extent is intentionally not inferred from this prefix.  The
accessor's addressing formula is established, but only the bounded prefix is
semantically cross-checked here.
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
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m111_obj_consumer import _direct_bl_callers_index  # noqa: E402
from m19_state_mapping import _function_end  # noqa: E402


SCHEMA = "smt2.m1.31.skill-crossmap.v1"

ACCESSOR = 0x080BF5C0
ACCESSOR_END = 0x080BF5D2
ACCESSOR_LITERAL_INSTRUCTION = 0x080BF5CC
TABLE_BASE = 0x0819B9F4
TABLE_STRIDE = 0x1C
FIELD_OFFSET = 0x06
FIELD_UNIT_COUNT = 8

CONSUMER = 0x080BF5D8
CONSUMER_END = 0x080BF648
ACCESSOR_CALLSITE = 0x080BF606
RENDER_CALLSITE = 0x080BF620
RENDER_SMALL = 0x080AC218
STACK_POINTER_ARG = 0x00

# These public Japanese names are comparison anchors only.  They remain
# private to the comparison operation and are not emitted by the report.
_ANCHORS = (
    ("skill-sequence-00", "アギ"),
    ("skill-sequence-01", "アギラオ"),
    ("skill-sequence-02", "マハラギ"),
    ("skill-sequence-03", "マハラギオン"),
    ("skill-sequence-04", "ブフ"),
    ("skill-sequence-05", "ブフーラ"),
    ("skill-sequence-06", "マハーブフ"),
    ("skill-sequence-07", "マハブフーラ"),
    ("skill-sequence-08", "ジオ"),
    ("skill-sequence-09", "ジオンガ"),
    ("skill-sequence-10", "マハジオ"),
    ("skill-sequence-11", "マハジオンガ"),
    ("skill-sequence-12", "ザン"),
    ("skill-sequence-13", "ザンマ"),
    ("skill-sequence-14", "マハザン"),
    ("skill-sequence-15", "マハザンマ"),
    ("skill-sequence-16", "テンタラフー"),
    ("skill-sequence-17", "メギド"),
    ("skill-sequence-18", "メギドラオン"),
    ("skill-sequence-19", "ドルミナー"),
    ("skill-sequence-20", "シバブー"),
    ("skill-sequence-21", "プリンパ"),
    ("skill-sequence-22", "ハピルマ"),
    ("skill-sequence-23", "マリンカリン"),
    ("skill-sequence-24", "マカジャマ"),
    ("skill-sequence-25", "ムド"),
    ("skill-sequence-26", "ムドオン"),
    ("skill-sequence-27", "ハンマ"),
    ("skill-sequence-28", "マハンマ"),
    ("skill-sequence-29", "タルンダ"),
    ("skill-sequence-30", "ラクンダ"),
    ("skill-sequence-31", "スクンダ"),
)

# Only the 32-anchor alphabet is retained.  This is not a complete codepage
# and is never serialized into the report.
_SKILL_UNIT_MAP = {
    0x001B: "ー",
    0x017B: "ア",
    0x0183: "オ",
    0x0184: "カ",
    0x0185: "ガ",
    0x0187: "ギ",
    0x0188: "ク",
    0x018F: "ザ",
    0x0190: "シ",
    0x0191: "ジ",
    0x0192: "ス",
    0x0198: "タ",
    0x0199: "ダ",
    0x019F: "テ",
    0x01A2: "ド",
    0x01A3: "ナ",
    0x01A8: "ハ",
    0x01A9: "バ",
    0x01AA: "パ",
    0x01AD: "ピ",
    0x01AE: "フ",
    0x01AF: "ブ",
    0x01B0: "プ",
    0x01B7: "マ",
    0x01B8: "ミ",
    0x01BA: "ム",
    0x01BB: "メ",
    0x01BD: "ャ",
    0x01C3: "ラ",
    0x01C4: "リ",
    0x01C5: "ル",
    0x01CD: "ン",
}

REFERENCE_SOURCES = (
    "https://w.atwiki.jp/shinmegamitensei2/pages/530.html",
    "https://wikiwiki.jp/snes007/%E7%9C%9F%E3%83%BB%E5%A5%B3%E7%A5%9E%E8%BB%A2%E7%94%9F%E2%85%A1%E3%80%80%E5%90%84%E7%A8%AE%E3%83%AA%E3%82%B9%E3%83%88",
    "https://w.atwiki.jp/shinmegamitensei2/pages/391.html",
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
    first = _safe_u16(data, entry)
    explicit_return = _safe_u16(data, expected_end - 2) in (0x4770, 0x4700)
    boundary_match = detected == expected_end or explicit_return
    return {
        "entry": address_metadata(entry, len(data)),
        "expected_end_exclusive": hex_address(expected_end),
        "detected_end_exclusive": (
            hex_address(expected_end)
            if explicit_return
            else None if detected is None else hex_address(detected)
        ),
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "available": len(raw) == expected_end - entry,
        "boundary_match": boundary_match,
        "boundary_basis": (
            "explicit_return_at_expected_end"
            if explicit_return
            else "conservative_first_bx_scan"
        ),
        "prologue_is_thumb_push_lr": first is not None and (first & 0xFF00) == 0xB500,
        "return_bx_lr": _safe_u16(data, expected_end - 2) == 0x4770,
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


def _field_units(data: bytes, ordinal: int) -> tuple[list[int], str, int]:
    address = TABLE_BASE + ordinal * TABLE_STRIDE + FIELD_OFFSET
    field = _window(data, address, FIELD_UNIT_COUNT * 2)
    if len(field) != FIELD_UNIT_COUNT * 2:
        return [], "record_out_of_bounds", len(field)
    units: list[int] = []
    termination = "fixed_width"
    for offset in range(0, len(field), 2):
        unit = read_u16(data, address + offset)
        if unit == 0:
            termination = "zero_0000"
            break
        units.append(unit)
    return units, termination, len(field)


def _anchor(data: bytes, ordinal: int, reference_id: str, expected: str) -> dict[str, object]:
    record_address = TABLE_BASE + ordinal * TABLE_STRIDE
    field_address = record_address + FIELD_OFFSET
    field = _window(data, field_address, FIELD_UNIT_COUNT * 2)
    units, termination, field_length = _field_units(data, ordinal)
    decoded = "".join(_SKILL_UNIT_MAP.get(unit, "") for unit in units)
    mapped = len(decoded) == len(units) and all(unit in _SKILL_UNIT_MAP for unit in units)
    return {
        "ordinal": ordinal,
        "stable_id": f"m31-skill-record-{ordinal:04d}",
        "record_address": address_metadata(record_address, len(data)),
        "field_offset": FIELD_OFFSET,
        "field_length": field_length,
        "field_hash": sha256(field) if field else None,
        "observed_unit_count": len(units),
        "expected_unit_count": len(expected),
        "termination": termination,
        "reference_id": reference_id,
        "all_units_mapped": mapped,
        "identity_match": bool(mapped and decoded == expected),
        "raw_field_emitted": False,
        "raw_units_emitted": False,
        "decoded_text_emitted": False,
    }


def _call_metadata(data: bytes, callsite: int, expected_target: int) -> dict[str, object]:
    observed = _safe_bl(data, callsite)
    return {
        "callsite": hex_address(callsite),
        "expected_target": address_metadata(expected_target, len(data)),
        "observed_target": None if observed is None else address_metadata(observed, len(data)),
        "target_match": observed == expected_target,
    }


def static_report(data: bytes) -> dict[str, object]:
    anchors = [_anchor(data, ordinal, reference_id, expected) for ordinal, (reference_id, expected) in enumerate(_ANCHORS)]
    matched = sum(bool(item["identity_match"]) for item in anchors)
    manifest = json.dumps(
        {"units": sorted((f"{unit:04x}", char) for unit, char in _SKILL_UNIT_MAP.items())},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    accessor_boundary = _boundary(data, ACCESSOR, ACCESSOR_END)
    consumer_boundary = _boundary(data, CONSUMER, CONSUMER_END)
    literal = _literal(data, ACCESSOR_LITERAL_INSTRUCTION, TABLE_BASE)
    callsites = [
        _call_metadata(data, ACCESSOR_CALLSITE, ACCESSOR),
        _call_metadata(data, RENDER_CALLSITE, RENDER_SMALL),
    ]
    direct_callers = _direct_bl_callers_index(data, (ACCESSOR, CONSUMER), limit=16)
    static_confirmed = (
        accessor_boundary["available"]
        and accessor_boundary["boundary_match"]
        and consumer_boundary["available"]
        and consumer_boundary["boundary_match"]
        and literal["value_match"]
        and all(item["target_match"] for item in callsites)
        and matched == len(_ANCHORS)
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "thirty_two_consecutive_skill_name_anchors_at_named_accessor_target",
            "accessor": address_metadata(ACCESSOR, len(data)),
            "table_base": address_metadata(TABLE_BASE, len(data)),
            "table_stride": TABLE_STRIDE,
            "field_offset": FIELD_OFFSET,
            "field_unit_count": FIELD_UNIT_COUNT,
            "anchor_count": len(_ANCHORS),
            "table_extent_proven": False,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "runtime_capture_performed": False,
            "raw_field_emitted": False,
            "raw_units_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "static_provenance": {
            "accessor_boundary": accessor_boundary,
            "caller_boundary": consumer_boundary,
            "table_literal": literal,
            "callsites": callsites,
            "direct_bl_callers": {
                hex_address(target): callers for target, callers in direct_callers.items()
            },
            "accessor_contract": {
                "index_normalization": "low_16_bits",
                "record_addressing": "table_base + index * 0x1c",
                "returned_record_field_offset": FIELD_OFFSET,
            },
            "consumer_contract": {
                "accessor_callsite": hex_address(ACCESSOR_CALLSITE),
                "copied_unit_count_max": FIELD_UNIT_COUNT,
                "field_termination": "zero_0000_or_eight_units",
                "render_target": hex_address(RENDER_SMALL),
                "render_argument_stack_offset": STACK_POINTER_ARG,
            },
        },
        "category_crossmap": {
            "candidate_category": "skill",
            "bounded_prefix_records": len(_ANCHORS),
            "consecutive_identity_matches": matched,
            "prefix_identity_status": "confirmed" if static_confirmed else "unconfirmed",
            "full_table_category_status": "provisional",
            "stable_id_formula": "m31-skill-record-{ordinal:04d}",
            "identity_manifest_hash": hashlib.sha256(manifest).hexdigest(),
            "mapped_unit_count": len(_SKILL_UNIT_MAP),
            "complete_codepage": False,
            "external_reference_urls": list(REFERENCE_SOURCES),
        },
        "anchors": anchors,
        "conclusions": {
            "confirmed": (
                [
                    "accessor_literal_and_thumb_boundaries_match_named_skill_record_path",
                    "thirty_two_consecutive_0x0819b9f4_fields_match_external_skill_sequence",
                    "bounded_skill_code_unit_identity_is_separate_from_item_and_demon_namespaces",
                ]
                if static_confirmed
                else []
            ),
            "provisional": [
                "0x0819b9f4_table_is_a_skill_record_family_for_bounded_prefix_only",
                "full_skill_table_extent_and_category_spans_are_not_proven",
                "external_names_are_identity_anchors_not_translation_ledger_entries",
            ],
            "unknown": [
                "natural_runtime_skill_selection_and_live_render_argument",
                "unanchored_code_units_and_complete_codepage",
                "glyph_identity_width_control_contract_and_reinsertion",
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
