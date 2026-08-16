#!/usr/bin/env python3
"""Bounded A5TJ staging-writer and indirect resource-record mapper.

M1.13 follows the two static ``0x02001000`` staging paths and the exact Thumb
callback pointer used by their resource records.  It reports record shape,
source-pointer classes, function/callsite addresses, hashes, lengths, and
counts only.  It never emits record bytes, decompressed payloads, strings,
glyphs, or a translation source table.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


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
from m111_obj_consumer import (  # noqa: E402
    _boundary_metadata,
    _direct_bl_callers_index,
)


SCHEMA = "smt2.m1.13.staging-resource-map.v1"
STAGING_WRITER = 0x0813EF64
STAGING_WRITER_THUMB = STAGING_WRITER | 1
STAGING_INTERMEDIATE = 0x0200AFC8
STAGING_BASE = 0x02001000
RESOURCE_CALLBACK_TYPE = 1
RESOURCE_RECORD_STRIDE = 0x18
RESOURCE_RECORDS_PER_GROUP = 8
RESOURCE_GROUP_COUNT_EXPECTED = 16

HUFF_WRAPPER = 0x0815CAFC
LZ77_WRAPPER = 0x0815CB00
RESOURCE_INIT = 0x080BD0E0
RESOURCE_INIT_CALLBACK = 0x080BD131
RESOURCE_INIT_REGISTRATION = 0x080BD182
CALLBACK_INIT = 0x0813EFB4
CALLBACK_REGISTRATIONS = (
    (0x0813EFBA, 0x0813EF91),
    (0x0813EFF2, 0x0813EFC9),
)


def _region(address: int) -> str:
    if ROM_BASE <= address < ROM_LIMIT:
        return "rom"
    if 0x02000000 <= address < 0x02040000:
        return "ewram"
    if 0x03000000 <= address < 0x03008000:
        return "iwram"
    if 0x06000000 <= address < 0x06018000:
        return "vram"
    return "other"


def _address_field(value: int, rom_size: int) -> dict[str, object]:
    return {**address_metadata(value, rom_size), "region_class": _region(value)}


def _pointer_positions(data: bytes, value: int) -> list[int]:
    needle = value.to_bytes(4, "little")
    result: list[int] = []
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            break
        result.append(ROM_BASE + found)
        start = found + 1
    return result


def _groups_from_positions(positions: list[int], *, stride: int, record_count: int) -> list[list[int]]:
    position_set = set(positions)
    groups: list[list[int]] = []
    for start in positions:
        if start - stride in position_set:
            continue
        group = [start + stride * index for index in range(record_count)]
        if all(address in position_set for address in group):
            groups.append(group)
    return groups


def _swi_number(data: bytes, address: int) -> int | None:
    for offset in range(0, 8, 2):
        instruction = read_u16(data, address + offset)
        if instruction & 0xFF00 == 0xDF00:
            return instruction & 0xFF
    return None


def _literal_at(data: bytes, address: int) -> dict[str, object] | None:
    try:
        return thumb_literal_load(data, address)
    except (ValueError, IndexError):
        return None


def _resource_group(data: bytes, records: list[int]) -> dict[str, object]:
    source_addresses: list[int] = []
    callback_count = 0
    scalar_stats: dict[str, dict[str, int]] = {}
    for record in records:
        callback = read_u32(data, record)
        if callback == STAGING_WRITER_THUMB:
            callback_count += 1
        source = read_u32(data, record + 4)
        source_addresses.append(source)
        for field_offset in (8, 12, 16):
            key = hex_address(field_offset)
            value = read_u32(data, record + field_offset)
            stats = scalar_stats.setdefault(key, {"count": 0, "nonzero_count": 0, "small_value_count": 0})
            stats["count"] += 1
            stats["nonzero_count"] += value != 0
            stats["small_value_count"] += value <= 0xFF
    raw_start = records[0]
    raw_end = records[-1] + RESOURCE_RECORD_STRIDE
    raw = data[raw_start - ROM_BASE : raw_end - ROM_BASE]
    source_regions = Counter(_region(value) for value in source_addresses)
    source_header_markers = Counter()
    for value in source_addresses:
        if ROM_BASE <= value < ROM_BASE + len(data) and value + 4 <= ROM_BASE + len(data):
            source_header_markers[read_u32(data, value) & 0xFF] += 1
    source_samples = [_address_field(value, len(data)) for value in source_addresses[:3]]
    return {
        "start": hex_address(raw_start),
        "record_count": len(records),
        "record_stride": RESOURCE_RECORD_STRIDE,
        "span_length": len(raw),
        "span_hash": sha256(raw),
        "callback_field_offset": hex_address(0),
        "source_pointer_field_offset": hex_address(4),
        "callback_count": callback_count,
        "source_pointer_count": len(source_addresses),
        "unique_source_pointer_count": len(set(source_addresses)),
        "source_region_counts": dict(sorted(source_regions.items())),
        "source_header_marker_counts": {
            hex_address(marker): count for marker, count in sorted(source_header_markers.items())
        },
        "source_pointer_samples": source_samples,
        "scalar_field_stats": scalar_stats,
        "shape": "callback_plus_source_pointer_plus_three_bounded_scalar_fields",
    }


def _staging_writer(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    window = _boundary_metadata(data, STAGING_WRITER)
    return {
        "function": window,
        "direct_bl_callers": callers.get(STAGING_WRITER, []),
        "thumb_pointer": _address_field(STAGING_WRITER_THUMB, len(data)),
        "intermediate": _address_field(STAGING_INTERMEDIATE, len(data)),
        "destination_base": _address_field(STAGING_BASE, len(data)),
        "argument_provenance": {
            "incoming_r1": "HuffUnComp source pointer candidate",
            "incoming_r2": "12-bit output-bank/index candidate",
            "destination_expression": "0x02001000 + (incoming_r2 << 12)",
        },
        "transform_chain": [
            {
                "stage": "huff",
                "wrapper": hex_address(HUFF_WRAPPER),
                "swi_number": _swi_number(data, HUFF_WRAPPER),
                "source": "incoming r1",
                "destination": hex_address(STAGING_INTERMEDIATE),
            },
            {
                "stage": "lz77_wram",
                "wrapper": hex_address(LZ77_WRAPPER),
                "swi_number": _swi_number(data, LZ77_WRAPPER),
                "source": hex_address(STAGING_INTERMEDIATE),
                "destination": "0x02001000 + (incoming r2 << 12)",
            },
        ],
        "source_identity": "not_established",
    }


def _resource_initializer(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    function = _boundary_metadata(data, RESOURCE_INIT)
    literals = []
    for address in (0x080BD0E4, 0x080BD0E6, 0x080BD0EE, 0x080BD0F6, 0x080BD0F8, 0x080BD108):
        item = _literal_at(data, address)
        if item is not None:
            literals.append(
                {
                    "load_address": hex_address(address),
                    "literal_address": item["literal_address"],
                    "value": item["value"],
                }
            )
    bl_targets = []
    for address in (0x080BD0EA, 0x080BD0F2, 0x080BD104, 0x080BD10C):
        target = thumb_bl_target(data, address)
        bl_targets.append({"callsite": hex_address(address), "target": None if target is None else hex_address(target)})
    return {
        "function": function,
        "direct_bl_callers": callers.get(RESOURCE_INIT, []),
        "literal_loads": literals,
        "calls": bl_targets,
        "decompression_chain": [
            {
                "stage": "huff",
                "source": _address_field(0x08194C78, len(data)),
                "destination": _address_field(STAGING_INTERMEDIATE, len(data)),
                "wrapper": hex_address(HUFF_WRAPPER),
                "swi_number": _swi_number(data, HUFF_WRAPPER),
            },
            {
                "stage": "lz77_wram",
                "source": _address_field(STAGING_INTERMEDIATE, len(data)),
                "destination": _address_field(0x02000000, len(data)),
                "wrapper": hex_address(LZ77_WRAPPER),
                "swi_number": _swi_number(data, LZ77_WRAPPER),
            },
        ],
        "callback_registration": {
            "callsite": hex_address(0x080BD10C),
            "callback": _address_field(0x080BD01D, len(data)),
            "type_argument": RESOURCE_CALLBACK_TYPE,
        },
    }


def _callback_initializer(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    registrations = []
    for callsite, callback in CALLBACK_REGISTRATIONS:
        target = thumb_bl_target(data, callsite)
        registrations.append(
            {
                "callsite": hex_address(callsite),
                "callback": _address_field(callback, len(data)),
                "registration_target": None if target is None else hex_address(target),
                "type_argument": RESOURCE_CALLBACK_TYPE,
            }
        )
    return {
        "function": _boundary_metadata(data, CALLBACK_INIT),
        "direct_bl_callers": callers.get(CALLBACK_INIT, []),
        "registrations": registrations,
        "staging_dma_callback_registration": {
            "callsite": hex_address(RESOURCE_INIT_REGISTRATION),
            "callback": _address_field(RESOURCE_INIT_CALLBACK, len(data)),
            "registration_target": hex_address(0x080A9C40),
            "type_argument": RESOURCE_CALLBACK_TYPE,
        },
    }


def static_report(data: bytes) -> dict[str, object]:
    target_functions = (STAGING_WRITER, RESOURCE_INIT, CALLBACK_INIT, 0x080A9C40)
    callers = _direct_bl_callers_index(data, target_functions)
    positions = _pointer_positions(data, STAGING_WRITER_THUMB)
    groups = _groups_from_positions(
        positions,
        stride=RESOURCE_RECORD_STRIDE,
        record_count=RESOURCE_RECORDS_PER_GROUP,
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "exact Thumb callback pointer runs plus bounded staging/decompressor functions",
            "callback_pointer": hex_address(STAGING_WRITER_THUMB),
            "pointer_occurrence_count": len(positions),
            "group_stride": RESOURCE_RECORD_STRIDE,
            "records_per_group": RESOURCE_RECORDS_PER_GROUP,
            "glyph_pattern_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "staging_writer": _staging_writer(data, callers),
        "resource_initializer": _resource_initializer(data, callers),
        "callback_initializer": _callback_initializer(data, callers),
        "resource_record_groups": [_resource_group(data, group) for group in groups],
        "summary": {
            "group_count": len(groups),
            "record_count": sum(len(group) for group in groups),
            "expected_group_count": RESOURCE_GROUP_COUNT_EXPECTED,
            "expected_shape_match": len(groups) == RESOURCE_GROUP_COUNT_EXPECTED
            and all(len(group) == RESOURCE_RECORDS_PER_GROUP for group in groups),
            "source_identity": "not_established",
            "codepage": "not_established",
            "translation_ledger": "blocked",
        },
        "conclusions": {
            "confirmed": [
                "0x0813ef64_huff_then_lz77_staging_transform",
                "callback_pointer_occurs_in_bounded_16_by_8_stride_0x18_record_candidates",
                "record_source_field_is_rom_pointer_shaped_in_each_group",
            ],
            "provisional": [
                "record_groups_are_resource_or_asset_dispatch_not_yet_text_table",
                "incoming_r1_is_rom_source_candidate_and_incoming_r2_is_output_bank_candidate",
            ],
            "negative": [
                "no_code_unit_or_string_id_recovered",
                "no_natural_runtime_hit_due_listener_blocker",
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
