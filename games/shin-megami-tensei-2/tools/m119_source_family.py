#!/usr/bin/env python3
"""Bounded A5TJ text-reader family and source-provenance probe.

M1.19 follows the two named 16-bit readers from M1.18 to their direct
callers.  It records caller boundaries, bounded argument provenance, and one
inline ROM code-unit source family that is directly referenced by the same
caller function.  It deliberately does not decode text, infer Unicode, scan
the ROM for strings, or create a translation ledger.
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
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)
from m118_codeunit_font import (  # noqa: E402
    CODE_UNIT_LINE_BREAK,
    CODE_UNIT_TERMINATOR,
    CODEUNIT_STRING_LARGE,
    CODEUNIT_STRING_SMALL,
    _function_end,
    _function_start,
)


SCHEMA = "smt2.m1.19.source-family.v1"

# This is the one manually bounded family selected from the direct reader
# caller at 0x080b52c4.  The next pointer-shaped data at 0x08162c34 is used by
# another code path, so the probe does not infer it into this family.
INLINE_FAMILY_CALLER = 0x080B52C4
INLINE_FAMILY_BASE = 0x08162B0C
INLINE_FAMILY_LAST = 0x08162C26
INLINE_FAMILY_MAX_SCAN = 0x100

MAX_DIRECT_CALLERS = 64
MAX_CALLER_LAYERS = 3
MAX_LAYER_RECORDS = 192
ARGUMENT_BACKSCAN_BYTES = 0x80


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


def _source_terminator_metadata(
    data: bytes, pointer: int, upper_bound: int | None
) -> dict[str, object]:
    """Scan one named pointer only until zero/0x0301 or a hard bound."""
    if not ROM_BASE <= pointer < ROM_BASE + len(data):
        return {
            "available": False,
            "source_pointer": address_metadata(pointer, len(data)),
            "termination": "pointer_out_of_bounds",
            "raw_source_emitted": False,
        }
    end = min(ROM_BASE + len(data), pointer + INLINE_FAMILY_MAX_SCAN)
    if upper_bound is not None and pointer < upper_bound:
        end = min(end, upper_bound)
    raw = _window(data, pointer, end - pointer)
    units: list[int] = []
    termination: str | None = None
    terminator_offset: int | None = None
    for offset in range(0, len(raw) - 1, 2):
        unit = read_u16(raw, ROM_BASE + offset)
        units.append(unit)
        if unit == 0:
            termination = "zero_0000"
            terminator_offset = offset
            break
        if unit == CODE_UNIT_TERMINATOR:
            termination = "terminator_0301"
            terminator_offset = offset
            break
    if terminator_offset is None:
        consumed = raw
        termination = "not_found_within_bounded_window"
    else:
        consumed = raw[: terminator_offset + 2]
    classes = Counter(
        "zero_0000" if unit == 0
        else "line_break_0300" if unit == CODE_UNIT_LINE_BREAK
        else "terminator_0301" if unit == CODE_UNIT_TERMINATOR
        else "single_byte_page_unit" if unit < 0x100
        else "multi_byte_code_unit"
        for unit in units
    )
    return {
        "available": bool(raw),
        "source_pointer": address_metadata(pointer, len(data)),
        "window_length": len(raw),
        "length": len(consumed),
        "unit_count": len(units),
        "hash": sha256(consumed) if consumed else None,
        "termination": termination,
        "terminator_offset": terminator_offset,
        "line_break_count": units.count(CODE_UNIT_LINE_BREAK),
        "terminator_count": units.count(CODE_UNIT_TERMINATOR),
        "zero_unit_count": units.count(0),
        "unit_class_counts": dict(sorted(classes.items())),
        "odd_window_length": len(raw) % 2 == 1,
        "raw_source_emitted": False,
        "decoded_text_emitted": False,
    }


def _inline_family_pointers(data: bytes) -> list[dict[str, object]]:
    """Extract only literal pointers in the named caller's bounded span."""
    end = _function_end(data, INLINE_FAMILY_CALLER)
    found: dict[int, list[dict[str, str]]] = {}
    if end <= INLINE_FAMILY_CALLER:
        return []
    for address in range(INLINE_FAMILY_CALLER, end, 2):
        try:
            loaded = thumb_literal_load(data, address)
            value = int(str(loaded["value"]), 16)
        except (ValueError, IndexError):
            continue
        if not INLINE_FAMILY_BASE <= value <= INLINE_FAMILY_LAST:
            continue
        found.setdefault(value, []).append(
            {
                "instruction": hex_address(address),
                "literal_address": str(loaded["literal_address"]),
            }
        )
    pointers = sorted(found)
    result: list[dict[str, object]] = []
    for index, pointer in enumerate(pointers):
        next_pointer = pointers[index + 1] if index + 1 < len(pointers) else None
        result.append(
            {
                "record_id": index + 1,
                "source_pointer": address_metadata(pointer, len(data)),
                "literal_loads": found[pointer],
                "pointer_delta": (
                    None if next_pointer is None else next_pointer - pointer
                ),
                "source": _source_terminator_metadata(data, pointer, next_pointer),
            }
        )
    return result


def _r0_argument_evidence(data: bytes, callsite: int) -> dict[str, object]:
    """Classify the nearest simple r0 setup without claiming full CFG proof."""
    lower = max(ROM_BASE, callsite - ARGUMENT_BACKSCAN_BYTES)
    candidates: list[dict[str, object]] = []
    for address in range(lower & ~1, callsite, 2):
        try:
            loaded = thumb_literal_load(data, address)
        except (ValueError, IndexError):
            continue
        if int(loaded["register"]) != 0:
            continue
        value = int(str(loaded["value"]), 16)
        candidates.append(
            {
                "kind": "rom_literal_r0_candidate",
                "confidence": "linear_bounded",
                "instruction": hex_address(address),
                "literal_address": str(loaded["literal_address"]),
                "value": address_metadata(value, len(data)),
            }
        )
    # Thumb ADD r0,SP,#imm is 0xa800 | imm/4.  It is the stack-buffer form
    # used by the large reader callers; keep only its shape and offset.
    for address in range(lower & ~1, callsite, 2):
        try:
            instruction = read_u16(data, address)
        except (ValueError, IndexError):
            continue
        if instruction & 0xFF00 == 0xA800:
            candidates.append(
                {
                    "kind": "stack_buffer_r0_candidate",
                    "confidence": "linear_bounded",
                    "instruction": hex_address(address),
                    "stack_offset": (instruction & 0xFF) * 4,
                }
            )
    return {
        "callsite": hex_address(callsite),
        "candidate_count": len(candidates),
        "candidates": candidates[-8:],
        "source_identity_confirmed": False,
    }


def _direct_callers(data: bytes, target: int) -> list[dict[str, object]]:
    index = _direct_bl_callers_index(data, (target,), limit=MAX_DIRECT_CALLERS)
    result: list[dict[str, object]] = []
    for text_address in index.get(target, []):
        callsite = int(text_address, 16)
        function = _function_start(data, callsite)
        result.append(
            {
                "callsite": text_address,
                "caller_function": (
                    None if function is None else _safe_boundary(data, function)
                ),
                "argument_evidence": _r0_argument_evidence(data, callsite),
            }
        )
    return result


def _caller_layers(data: bytes, seeds: Iterable[int]) -> list[dict[str, object]]:
    current = list(dict.fromkeys(seeds))
    seen = set(current)
    result: list[dict[str, object]] = []
    for depth in range(1, MAX_CALLER_LAYERS + 1):
        if not current or len(result) >= MAX_LAYER_RECORDS:
            break
        index = _direct_bl_callers_index(
            data, current, limit=MAX_DIRECT_CALLERS
        )
        next_functions: list[int] = []
        for target in current:
            for text_address in index.get(target, []):
                callsite = int(text_address, 16)
                function = _function_start(data, callsite)
                result.append(
                    {
                        "depth": depth,
                        "target": hex_address(target),
                        "callsite": text_address,
                        "caller_function": (
                            None
                            if function is None
                            else _safe_boundary(data, function)
                        ),
                    }
                )
                if function is not None and function not in seen:
                    seen.add(function)
                    next_functions.append(function)
                if len(result) >= MAX_LAYER_RECORDS:
                    break
            if len(result) >= MAX_LAYER_RECORDS:
                break
        current = next_functions
    return result


def static_report(data: bytes) -> dict[str, object]:
    small_callers = _direct_callers(data, CODEUNIT_STRING_SMALL)
    large_callers = _direct_callers(data, CODEUNIT_STRING_LARGE)
    family_records = _inline_family_pointers(data)
    family_span = _window(
        data,
        INLINE_FAMILY_BASE,
        INLINE_FAMILY_LAST + 0x20 - INLINE_FAMILY_BASE,
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "named_reader_family_direct_callers_and_one_bounded_inline_source_family",
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "reader_family": {
            "small": {
                "entry": _safe_boundary(data, CODEUNIT_STRING_SMALL),
                "direct_callsite_count": len(small_callers),
                "direct_callers": small_callers,
            },
            "large": {
                "entry": _safe_boundary(data, CODEUNIT_STRING_LARGE),
                "direct_callsite_count": len(large_callers),
                "direct_callers": large_callers,
            },
            "caller_layers": _caller_layers(
                data, (CODEUNIT_STRING_SMALL, CODEUNIT_STRING_LARGE)
            ),
        },
        "inline_source_family": {
            "caller_function": _safe_boundary(data, INLINE_FAMILY_CALLER),
            "base": address_metadata(INLINE_FAMILY_BASE, len(data)),
            "last_pointer": address_metadata(INLINE_FAMILY_LAST, len(data)),
            "bounded_pointer_count": len(family_records),
            "record_ids_contiguous": [
                int(item["record_id"]) for item in family_records
            ] == list(range(1, len(family_records) + 1)),
            "pointer_ref_function": hex_address(INLINE_FAMILY_CALLER),
            "pointer_span": {
                "length": len(family_span),
                "hash": sha256(family_span) if family_span else None,
            },
            "termination_counts": dict(
                sorted(
                    Counter(
                        str(item["source"].get("termination"))
                        for item in family_records
                        if isinstance(item.get("source"), dict)
                    ).items()
                )
            ),
            "terminated_record_count": sum(
                int(
                    isinstance(item.get("source"), dict)
                    and item["source"].get("termination")
                    in {"zero_0000", "terminator_0301"}
                )
                for item in family_records
            ),
            "records": family_records,
            "category": "bounded_inline_16bit_zero_terminated_candidate",
            "stable_unicode_identity": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
        },
        "conclusions": {
            "confirmed": [
                "0x080ac334_and_0x080ac3ac_have_bounded_direct_caller_sets",
                "0x080b52c4_directly_references_a_bounded_inline_16bit_pointer_family",
                "inline_family_records_are_zero_terminated_with_metadata_only_hashes",
                "large_reader_has_one_rom_pointer_path_and_four_stack_buffer_paths",
                "caller_boundaries_are_recorded_through_three_bounded_bl_layers",
            ],
            "provisional": [
                "inline_family_is_a_ui_or_system_codeunit_category",
                "direct_caller_argument_evidence_is_linear_bounded_not_full_cfg_proof",
            ],
            "unknown": [
                "category_semantics_and_scene_selection",
                "unicode_identity_and_codepage_mapping",
                "main_event_demon_skill_item_source_families",
                "control_codes_beyond_zero_and_0x0301",
                "translated_width_and_reinsertion_contract",
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
