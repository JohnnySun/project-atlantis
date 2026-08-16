#!/usr/bin/env python3
"""Bounded metadata probe for the first confirmed A5TJ text consumer edge.

M1.17 follows one named byte-table reader and its descriptor dispatch.  It
does not scan for strings, decode the bytes, emit source text, or create a
translation ledger.  Reports contain addresses, function hashes, bounded
record hashes, lengths, classes, and counts only.
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
    thumb_bl_target,
    thumb_literal_load,
)
from m19_state_mapping import (  # noqa: E402
    _function_end,
    _function_start,
    _literal_ref_index,
)
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)


SCHEMA = "smt2.m1.17.text-consumer.v1"

TEXT_TABLE_BASE = 0x08163444
TEXT_TABLE_STRIDE = 0x0A
# This is an audited, bounded ASCII/padded prefix.  Bytes after this prefix
# are deliberately not classified as records by this probe.
TEXT_TABLE_ASCII_RECORDS = 37
TEXT_TABLE_SENTINEL = 0x20

TEXT_READER = 0x080B6460
TEXT_READER_TABLE_LOAD = 0x080B6476
TEXT_READER_LOOP_BYTE_LOAD = 0x080B6496
TEXT_READER_LOOP_CMP = 0x080B649C
TEXT_READER_DISPATCH = 0x080B64E4
TEXT_READER_END = 0x080B6526

DESCRIPTOR_BASE = 0x08163638
GLYPH_DISPATCHER = 0x080AA1F4
GLYPH_DISPATCHER_RETURN = 0x080AA2D0
GLYPH_DISPATCHER_END = 0x080AA2D2

RELATED_TABLE_LOADS = (0x080B6378, 0x080B6476, 0x080B6576)
DESCRIPTOR_LITERAL_LOADS = (0x080B64DC,)
MAX_CALLERS_PER_TARGET = 48
MAX_CALLER_LAYERS = 3


def _window(data: bytes, address: int, length: int) -> bytes:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        return b""
    offset = address - ROM_BASE
    return data[offset : min(len(data), offset + length)]


def _window_metadata(data: bytes, address: int, length: int) -> dict[str, object]:
    raw = _window(data, address, length)
    return {
        "address": address_metadata(address, len(data)),
        "length": len(raw),
        "hash": sha256(raw) if raw else None,
    }


def _record_is_bounded_ascii(record: bytes) -> bool:
    """Validate classes only; never return or decode record contents."""
    return bool(record) and all(
        byte == 0 or 0x20 <= byte <= 0x7E for byte in record
    )


def _record_metadata(data: bytes, index: int) -> dict[str, object]:
    address = TEXT_TABLE_BASE + index * TEXT_TABLE_STRIDE
    record = _window(data, address, TEXT_TABLE_STRIDE)
    first_sentinel = record.find(bytes((TEXT_TABLE_SENTINEL,)))
    return {
        "record_index": index,
        "address": address_metadata(address, len(data)),
        "length": len(record),
        "hash": sha256(record) if record else None,
        "bounded_ascii_padding_class": _record_is_bounded_ascii(record),
        "first_space_offset": first_sentinel if first_sentinel >= 0 else None,
        "space_count": record.count(TEXT_TABLE_SENTINEL),
        "zero_count": record.count(0),
        "non_ascii_count": sum(
            byte not in (0,) and not 0x20 <= byte <= 0x7E for byte in record
        ),
    }


def bounded_table_metadata(data: bytes) -> dict[str, object]:
    """Describe only the manually bounded 37-record table prefix."""
    records = [
        _record_metadata(data, index)
        for index in range(TEXT_TABLE_ASCII_RECORDS)
    ]
    available = sum(int(item["length"]) == TEXT_TABLE_STRIDE for item in records)
    span_length = TEXT_TABLE_ASCII_RECORDS * TEXT_TABLE_STRIDE
    span = _window(data, TEXT_TABLE_BASE, span_length)
    return {
        "base": address_metadata(TEXT_TABLE_BASE, len(data)),
        "stride": TEXT_TABLE_STRIDE,
        "bounded_record_count": TEXT_TABLE_ASCII_RECORDS,
        "available_record_count": available,
        "validated_ascii_padding_record_count": sum(
            bool(item["bounded_ascii_padding_class"]) for item in records
        ),
        "span": {
            "start": address_metadata(TEXT_TABLE_BASE, len(data)),
            "end_exclusive": address_metadata(
                TEXT_TABLE_BASE + span_length, len(data)
            ),
            "length": len(span),
            "hash": sha256(span) if span else None,
        },
        "record_length_counts": dict(
            sorted(Counter(int(item["length"]) for item in records).items())
        ),
        "first_space_offset_counts": dict(
            sorted(
                Counter(
                    item["first_space_offset"]
                    for item in records
                    if item["first_space_offset"] is not None
                ).items()
            )
        ),
        "space_count_total": sum(int(item["space_count"]) for item in records),
        "zero_count_total": sum(int(item["zero_count"]) for item in records),
        "non_ascii_count_total": sum(
            int(item["non_ascii_count"]) for item in records
        ),
        "records": records,
        "raw_bytes_emitted": False,
        "decoded_text_emitted": False,
    }


def _literal_evidence(
    data: bytes, instruction_address: int, expected_value: int
) -> dict[str, object]:
    try:
        loaded = thumb_literal_load(data, instruction_address)
        actual_value = int(str(loaded["value"]), 16)
        return {
            "instruction": hex_address(instruction_address),
            "literal_address": loaded["literal_address"],
            "loaded_register": loaded["register"],
            "value": address_metadata(actual_value, len(data)),
            "expected_value": address_metadata(expected_value, len(data)),
            "value_match": actual_value == expected_value,
        }
    except (ValueError, IndexError) as error:
        return {
            "instruction": hex_address(instruction_address),
            "error_class": type(error).__name__,
            "value_match": False,
        }


def _instruction_contract(data: bytes) -> dict[str, object]:
    # The expected forms are checked internally and represented by role and
    # match status, not by raw instruction words in the report.
    expected = {
        0x080B646E: ("index_field_halfword_load", 0x8C81),
        0x080B6470: ("index_times_four", 0x0088),
        0x080B6472: ("index_addition", 0x1840),
        0x080B6474: ("index_times_ten", 0x0040),
        0x080B6496: ("byte_unit_load", 0x7820),
        0x080B649C: ("space_sentinel_compare", 0x2820),
    }
    result = []
    for address, (role, halfword) in expected.items():
        try:
            observed = read_u16(data, address)
            result.append(
                {
                    "pc": hex_address(address),
                    "role": role,
                    "verified": observed == halfword,
                }
            )
        except (ValueError, IndexError):
            result.append(
                {"pc": hex_address(address), "role": role, "verified": False}
            )
    return {
        "index_addressing": "field_plus_0x24_then_index_times_4_plus_index_then_times_2",
        "unit": "byte",
        "terminator": "space_0x20",
        "checks": result,
        "all_verified": all(bool(item["verified"]) for item in result),
    }


def _caller_layers(
    data: bytes, seeds: Iterable[int]
) -> dict[str, list[dict[str, object]]]:
    """Follow direct Thumb BL callers through at most three function layers."""
    current = list(dict.fromkeys(seeds))
    seen = set(current)
    result: dict[str, list[dict[str, object]]] = {
        hex_address(seed): [] for seed in seeds
    }
    for depth in range(1, MAX_CALLER_LAYERS + 1):
        if not current:
            break
        index = _direct_bl_callers_index(
            data, current, limit=MAX_CALLERS_PER_TARGET
        )
        next_functions: list[int] = []
        for target in current:
            target_key = hex_address(target)
            for callsite_text in index.get(target, []):
                callsite = int(callsite_text, 16)
                function = _function_start(data, callsite)
                item = {
                    "depth": depth,
                    "target": target_key,
                    "callsite": callsite_text,
                    "caller_function": (
                        None if function is None else hex_address(function)
                    ),
                }
                result.setdefault(target_key, []).append(item)
                if function is not None and function not in seen:
                    seen.add(function)
                    next_functions.append(function)
        current = next_functions
    return result


def _function_boundary_metadata(
    data: bytes, entry: int, expected_return: int, expected_end: int
) -> dict[str, object]:
    item = _boundary_metadata(data, entry)
    detected_end = _function_end(data, entry)
    item.update(
        {
            "expected_return": hex_address(expected_return),
            "expected_end_exclusive": hex_address(expected_end),
            "boundary_match": detected_end == expected_end,
        }
    )
    return item


def static_report(data: bytes) -> dict[str, object]:
    table = bounded_table_metadata(data)
    table_refs = _literal_ref_index(data, (TEXT_TABLE_BASE, DESCRIPTOR_BASE))
    literal_loads = [
        _literal_evidence(data, address, TEXT_TABLE_BASE)
        for address in RELATED_TABLE_LOADS
    ]
    descriptor_loads = [
        _literal_evidence(data, address, DESCRIPTOR_BASE)
        for address in DESCRIPTOR_LITERAL_LOADS
    ]
    try:
        dispatch_target = thumb_bl_target(data, TEXT_READER_DISPATCH)
    except (ValueError, IndexError):
        dispatch_target = None
    callers = _direct_bl_callers_index(
        data,
        (TEXT_READER, GLYPH_DISPATCHER),
        limit=MAX_CALLERS_PER_TARGET,
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "one named ROM byte-table reader, bounded ASCII/padding prefix, and its dispatch edge",
            "bounded_table_start": hex_address(TEXT_TABLE_BASE),
            "bounded_table_record_count": TEXT_TABLE_ASCII_RECORDS,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "source_table_created": False,
            "translation_ledger_created": False,
        },
        "table": table,
        "reader": {
            "entry": _function_boundary_metadata(
                data, TEXT_READER, 0x080B6524, TEXT_READER_END
            ),
            "table_literal_load": _literal_evidence(
                data, TEXT_READER_TABLE_LOAD, TEXT_TABLE_BASE
            ),
            "related_table_literal_loads": literal_loads,
            "literal_reference_count": len(table_refs.get(TEXT_TABLE_BASE, [])),
            "instruction_contract": _instruction_contract(data),
            "loop_byte_load": hex_address(TEXT_READER_LOOP_BYTE_LOAD),
            "loop_sentinel_compare": hex_address(TEXT_READER_LOOP_CMP),
            "dispatch_callsite": hex_address(TEXT_READER_DISPATCH),
            "dispatch_target": (
                None if dispatch_target is None else hex_address(dispatch_target)
            ),
            "dispatch_target_match": dispatch_target == GLYPH_DISPATCHER,
            "direct_bl_callers": callers.get(TEXT_READER, []),
        },
        "descriptor_dispatch": {
            "descriptor_literal_loads": descriptor_loads,
            "descriptor_base": address_metadata(DESCRIPTOR_BASE, len(data)),
            "descriptor_window": _window_metadata(data, DESCRIPTOR_BASE, 0x100),
            "target": _function_boundary_metadata(
                data,
                GLYPH_DISPATCHER,
                GLYPH_DISPATCHER_RETURN,
                GLYPH_DISPATCHER_END,
            ),
            "direct_bl_callers": callers.get(GLYPH_DISPATCHER, []),
            "caller_layers": _caller_layers(data, (TEXT_READER, GLYPH_DISPATCHER)),
            "classification": "descriptor_to_oam_record_writer_candidate",
            "incoming_text_byte_consumed": True,
            "glyph_identity_confirmed": False,
        },
        "provenance": {
            "edge": [
                hex_address(TEXT_TABLE_BASE),
                hex_address(TEXT_READER),
                hex_address(TEXT_READER_DISPATCH),
                hex_address(DESCRIPTOR_BASE),
                hex_address(GLYPH_DISPATCHER),
            ],
            "source_parameter": "record_index_from_object_field_plus_0x24",
            "code_unit_parameter": "one ROM table byte loaded by ldrb",
            "descriptor_parameter": "fixed descriptor pointer loaded at dispatch callsite",
            "staging_or_obj_vram_edge": "not established by this text-only slice",
        },
        "conclusions": {
            "confirmed": [
                "0x08163444_is_a_bounded_fixed_stride_0x0a_byte_table_reader_base",
                "0x080b6460_derives_index_times_10_from_object_field_plus_0x24",
                "0x080b6460_consumes_byte_units_until_space_0x20",
                "0x080b64e4_dispatches_to_0x080aa1f4_with_descriptor_pointer_0x08163638",
                "thumb_function_boundaries_and_literal_loads_match_the_named_edge",
            ],
            "provisional": [
                "the_bounded_prefix_is_an_ascii_padded_ui_or_map_label_class",
                "0x080aa1f4_is_a_descriptor_to_oam_record_writer_candidate",
            ],
            "unknown": [
                "japanese_main_script_source_table",
                "codepage_mapping_and_control_codes",
                "unicode_or_glyph_identity",
                "runtime_natural_selector_to_this_table_record",
                "staging_to_obj_vram_provenance_for_this_text_edge",
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
