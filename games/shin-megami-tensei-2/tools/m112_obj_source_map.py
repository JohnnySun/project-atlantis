#!/usr/bin/env python3
"""Bounded static source-class mapping for A5TJ OBJ-VRAM consumers.

This is the non-runtime companion to M1.12.  It follows only the twelve
literal-load PCs established by M1.11 and recognizes the small Thumb DMA3
setup shape immediately surrounding a destination load.  It reports source
and destination addresses, control/length, caller addresses, and hashes only;
it does not scan glyphs, decode strings, or emit payload bytes.
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
    sha256,
    thumb_literal_load,
)
from m111_obj_consumer import OBJ_VRAM_BASE, _direct_bl_callers_index  # noqa: E402


SCHEMA = "smt2.m1.12.obj-source-map.v1"
DMA3 = 0x040000D4
OBJ_TARGETS = (
    0x080ABD80,
    0x080AC1B0,
    0x080BD136,
    0x080C1350,
    0x080D1DFC,
    0x080D5514,
    0x080D5E6E,
    0x080D5F8E,
    0x080D61F2,
    0x080D9A3E,
    0x080DC6AA,
    0x0813EFCE,
)
WINDOW_BEFORE = 0x20
WINDOW_AFTER = 0x30
SOURCE_SAMPLE_LENGTH = 0x40


def _region(address: int) -> str:
    if ROM_BASE <= address < ROM_LIMIT:
        return "rom"
    if 0x02000000 <= address < 0x02040000:
        return "ewram"
    if 0x03000000 <= address < 0x03008000:
        return "iwram"
    if 0x06000000 <= address < 0x06018000:
        return "vram"
    if 0x07000000 <= address < 0x07000400:
        return "oam"
    if 0x04000000 <= address < 0x04000400:
        return "io"
    return "other"


def _literal(data: bytes, address: int) -> dict[str, object] | None:
    try:
        return thumb_literal_load(data, address)
    except (ValueError, IndexError):
        return None


def _store_fields(data: bytes, address: int) -> dict[str, int] | None:
    instruction = read_u16(data, address)
    if instruction & 0xF800 != 0x6000:
        return None
    return {
        "register": instruction & 7,
        "base_register": (instruction >> 3) & 7,
        "offset": ((instruction >> 6) & 0x1F) * 4,
    }


def _ldr_word_fields(data: bytes, address: int) -> dict[str, int] | None:
    instruction = read_u16(data, address)
    if instruction & 0xF800 != 0x6800:
        return None
    return {
        "register": instruction & 7,
        "base_register": (instruction >> 3) & 7,
        "offset": ((instruction >> 6) & 0x1F) * 4,
    }


def _is_bx(data: bytes, address: int) -> bool:
    return read_u16(data, address) & 0xFF87 == 0x4700


def _address_field(value: int, rom_size: int) -> dict[str, object]:
    return {**address_metadata(value, rom_size), "source_region": _region(value)}


def _source_sample(data: bytes, address: int) -> dict[str, object]:
    if ROM_BASE <= address < ROM_BASE + len(data):
        raw = data[address - ROM_BASE : min(len(data), address - ROM_BASE + SOURCE_SAMPLE_LENGTH)]
        return {"length": len(raw), "hash": sha256(raw)}
    return {"length": 0, "hash": None}


def _source_class(address: int) -> str:
    if address in {0x02001000, 0x0200F874, 0x02006000}:
        return "ewram_runtime_or_staging_candidate"
    if ROM_BASE <= address < ROM_LIMIT:
        return "rom_data_pointer_candidate"
    if 0x02000000 <= address < 0x02040000:
        return "ewram_runtime_buffer_candidate"
    if 0x03000000 <= address < 0x03008000:
        return "iwram_runtime_buffer_candidate"
    return "computed_or_unknown_source"


def _decode_standard_dma(data: bytes, destination_load: int) -> dict[str, object] | None:
    """Recognize the bounded Thumb DMA3 field sequence.

    Some consumers reuse a DMA register loaded earlier in the same function,
    and some continue into a second DMA setup instead of returning immediately.
    Therefore the decoder requires the source/destination/control stores and a
    preceding DMA3 literal, but does not require an adjacent prologue or BX.
    """
    dma_ref = None
    dma_load_address = None
    for address in range(destination_load - 0x40, destination_load - 4, 2):
        candidate = _literal(data, address)
        if candidate is not None and int(str(candidate["value"]), 16) == DMA3:
            dma_ref = candidate
            dma_load_address = address
    if dma_ref is None or dma_load_address is None:
        return None
    entry = dma_load_address
    source_ref = _literal(data, destination_load - 4)
    destination_ref = _literal(data, destination_load)
    control_ref = _literal(data, destination_load + 4)
    if not all((dma_ref, source_ref, destination_ref, control_ref)):
        return None
    store_sad = _store_fields(data, destination_load - 2)
    store_dad = _store_fields(data, destination_load + 2)
    store_cnt = _store_fields(data, destination_load + 6)
    read_cnt = _ldr_word_fields(data, destination_load + 8)
    if not all((store_sad, store_dad, store_cnt, read_cnt)):
        return None
    dma_value = int(str(dma_ref["value"]), 16)
    source_value = int(str(source_ref["value"]), 16)
    destination_value = int(str(destination_ref["value"]), 16)
    control_value = int(str(control_ref["value"]), 16)
    shape_valid = (
        dma_value == DMA3
        and destination_value == OBJ_VRAM_BASE
        and store_sad["base_register"] == dma_ref["register"]
        and store_sad["register"] == source_ref["register"]
        and store_sad["offset"] == 0
        and store_dad["base_register"] == dma_ref["register"]
        and store_dad["register"] == destination_ref["register"]
        and store_dad["offset"] == 4
        and store_cnt["base_register"] == dma_ref["register"]
        and store_cnt["register"] == control_ref["register"]
        and store_cnt["offset"] == 8
        and read_cnt["base_register"] == dma_ref["register"]
        and read_cnt["offset"] == 8
    )
    if not shape_valid:
        return None
    raw = data[entry - ROM_BASE : destination_load + 12 - ROM_BASE]
    return {
        "entry": hex_address(entry),
        "window_length": len(raw),
        "window_hash": sha256(raw),
        "dma_register": _address_field(dma_value, len(data)),
        "source": _address_field(source_value, len(data)),
        "destination": _address_field(destination_value, len(data)),
        "control": hex_address(control_value),
        "transfer_units": control_value & 0xFFFF,
        "source_class": _source_class(source_value),
        "source_sample": _source_sample(data, source_value),
        "pattern": "literal_source_dest_control_dma3",
    }


def _target_item(data: bytes, target: int, callers: dict[int, list[str]]) -> dict[str, object]:
    raw = data[target - ROM_BASE - WINDOW_BEFORE : target - ROM_BASE + WINDOW_AFTER]
    standard = _decode_standard_dma(data, target)
    item: dict[str, object] = {
        "destination_literal_load": hex_address(target),
        "destination_literal": _address_field(OBJ_VRAM_BASE, len(data)),
        "bounded_window": {
            "start": hex_address(target - WINDOW_BEFORE),
            "length": len(raw),
            "hash": sha256(raw) if raw else None,
        },
        "direct_bl_callers_at_pattern_entry": [] if standard is None else callers.get(int(str(standard["entry"]), 16), []),
        "standard_dma_match": standard,
    }
    if standard is None:
        item["source_provenance"] = "not_decoded_in_bounded_destination_window"
        item["destination_role"] = "literal_destination_candidate_or_arithmetic_operand"
    else:
        item["source_provenance"] = "literal_source_field_in_bounded_dma_setup"
        item["destination_role"] = "dma3_destination_field"
    return item


def static_report(data: bytes) -> dict[str, object]:
    callers = _direct_bl_callers_index(data, [target - 6 for target in OBJ_TARGETS])
    targets = [_target_item(data, target, callers) for target in OBJ_TARGETS]
    standard = [item["standard_dma_match"] for item in targets if item["standard_dma_match"]]
    source_classes = Counter(str(item["source_class"]) for item in standard)
    source_addresses = Counter(str(item["source"]["address"]) for item in standard)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "twelve M1.11 OBJ-VRAM literal PCs with bounded Thumb DMA-shape decode",
            "target_count": len(OBJ_TARGETS),
            "glyph_pattern_scan": False,
            "full_rom_source_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "targets": targets,
        "summary": {
            "standard_dma_match_count": len(standard),
            "nonstandard_or_unresolved_count": len(targets) - len(standard),
            "source_class_counts": dict(sorted(source_classes.items())),
            "source_address_counts": dict(sorted(source_addresses.items())),
            "destination": hex_address(OBJ_VRAM_BASE),
            "source_to_code_unit_or_glyph": "not_established",
        },
        "conclusions": {
            "confirmed": [
                "bounded_literal_source_dest_control_dma3_shapes_are_reproducible",
                "0x02001000_to_0x06010000_occurs_in_the_bounded_static_cohort",
            ],
            "provisional": [
                "ewram_sources_are_runtime_or_staging_candidates_not_text_source_tables",
                "rom_sources_are_data_pointer_candidates_without_identity",
            ],
            "negative": [
                "runtime_natural_hit_not_available_in_static_report",
                "source_pointer_to_code_unit_or_glyph_writer_not_recovered",
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
