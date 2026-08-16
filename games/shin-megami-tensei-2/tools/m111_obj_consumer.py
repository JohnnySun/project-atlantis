#!/usr/bin/env python3
"""Bounded A5TJ OAM/OBJ consumer and source-class mapper.

M1.11 follows only the already identified OAM buffer path, the fixed OBJ-DMA
sites, and the twelve literal references to the OBJ-VRAM base.  It records
addresses, function boundaries, hashes, lengths, and counts.  It deliberately
does not scan glyph patterns, emit instruction/data bytes, decode strings, or
create a translation source table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import (  # noqa: E402
    FIXED_DMA_CANDIDATES,
    ROM_BASE,
    ROM_LIMIT,
    address_metadata,
    decode_fixed_dma,
    hex_address,
    read_u16,
    sha256,
    thumb_bl_target,
)
from m19_state_mapping import (  # noqa: E402
    _function_end,
    _function_start,
    _literal_ref_index,
)


SCHEMA = "smt2.m1.11.obj-consumer.v1"

OAM_BUFFER = 0x030033F0
OAM_DESTINATION = 0x07000000
OAM_DMA_REGISTER = 0x040000D4
OAM_DMA_CONTROL = 0x84000100
OAM_DMA_UNITS = OAM_DMA_CONTROL & 0xFFFF
OBJ_VRAM_BASE = 0x06010000
OBJ_DMA_DESTINATION = 0x06013000

OAM_DMA_FUNCTION = 0x080A9AF4
OAM_DMA_SETUP = 0x080A9B06
OAM_DMA_SETUP_END = 0x080A9B26
OAM_DMA_POST_CALL = 0x080A9B26
OAM_DMA_POST_TARGET = 0x080AABC8

OAM_NODES = (
    ("oam_table_fill", 0x080A9DD0, "function"),
    ("oam_base_copy_candidate", 0x080A9E38, "inline_or_fallthrough_candidate"),
    ("oam_record_append", 0x080A9EA8, "function"),
    ("oam_object_builder", 0x080A9F04, "function"),
)

OAM_WORKING_DATA = (
    0x030033F0,
    0x030031E0,
    0x03002130,
    0x030031F0,
    0x03003950,
    0x030031C8,
)

TRACKED_LITERAL_VALUES = (
    OAM_BUFFER,
    OBJ_VRAM_BASE,
    OBJ_DMA_DESTINATION,
    OAM_DMA_REGISTER,
    *OAM_WORKING_DATA[1:],
)

FUNCTION_WINDOW = 0x100
INLINE_WINDOW = 0x30
MAX_CALLERS = 48


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


def _boundary_metadata(data: bytes, entry: int, *, window_length: int = FUNCTION_WINDOW) -> dict[str, object]:
    """Return boundary evidence without exposing instruction bytes."""
    raw = _window(data, entry, window_length)
    end = _function_end(data, entry)
    return {
        "entry": address_metadata(entry, len(data)),
        "length": max(0, end - entry) if end > entry else None,
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "prologue_is_thumb_push_lr": bool(raw and (read_u16(data, entry) & 0xFF00) == 0xB500),
        "return_candidates": [hex_address(int(value, 16)) for value in _return_candidates(data, entry)],
    }


def _return_candidates(data: bytes, entry: int) -> list[str]:
    """Find only the address of bounded Thumb BX epilogues."""
    result: list[str] = []
    end = min(ROM_BASE + len(data), entry + 0x500)
    for address in range(entry + 0x20, end - 1, 2):
        if read_u16(data, address) & 0xFF87 == 0x4700:
            result.append(hex_address(address))
            if len(result) >= 8:
                break
    return result


def _direct_bl_callers_index(data: bytes, targets: Iterable[int], *, limit: int = MAX_CALLERS) -> dict[int, list[str]]:
    wanted = set(targets)
    result = {target: [] for target in wanted}
    for offset in range(0, max(0, len(data) - 3), 2):
        address = ROM_BASE + offset
        try:
            target = thumb_bl_target(data, address)
        except (ValueError, IndexError):
            continue
        if target in wanted and len(result[target]) < limit:
            result[target].append(hex_address(address))
    return result


def _ref_metadata(data: bytes, refs: dict[int, list[dict[str, object]]], value: int, callers: dict[int, list[str]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for ref in refs.get(value, []):
        instruction = int(str(ref["instruction"]), 16)
        function = _function_start(data, instruction)
        result.append(
            {
                "literal_load_address": ref["instruction"],
                "literal_address": ref["literal_address"],
                "loaded_register": ref["register"],
                "value": address_metadata(value, len(data)),
                "function": None if function is None else _boundary_metadata(data, function),
                "function_direct_bl_callers": callers.get(function or -1, []),
            }
        )
    return result


def _fixed_obj_dma_metadata(data: bytes) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    caller_index = _direct_bl_callers_index(
        data, (int(spec["entry"]) for spec in FIXED_DMA_CANDIDATES)
    )
    for spec in FIXED_DMA_CANDIDATES:
        entry = int(spec["entry"])
        decoded = decode_fixed_dma(data, entry)
        item: dict[str, object] = {
            "name": spec["name"],
            "entry": hex_address(entry),
            "window_length": 0x12,
            "window_hash": decoded["instruction_hash"],
            "pattern_valid": bool(decoded["instruction_pattern_valid"]),
            "direct_bl_callers": caller_index.get(entry, []),
        }
        fields = decoded.get("decoded")
        if isinstance(fields, dict):
            item["dma_parameters"] = {
                name: {
                    "literal_address": value.get("literal_address"),
                    "value": value.get("value"),
                }
                for name, value in fields.items()
                if isinstance(value, dict) and name in {"dma_register", "source", "destination", "control"}
            }
            control = fields.get("control")
            if isinstance(control, dict):
                item["transfer_units"] = int(str(control["value"]), 16) & 0xFFFF
        result.append(item)
    return result


def _oam_dma_metadata(data: bytes, callers: dict[int, list[str]]) -> dict[str, object]:
    target = thumb_bl_target(data, OAM_DMA_POST_CALL)
    setup_raw = _window(data, OAM_DMA_SETUP, OAM_DMA_SETUP_END - OAM_DMA_SETUP)
    function_boundary = _boundary_metadata(data, OAM_DMA_FUNCTION)
    return {
        "function": function_boundary,
        "direct_bl_callers": callers.get(OAM_DMA_FUNCTION, []),
        "setup_window": {
            "start": hex_address(OAM_DMA_SETUP),
            "end": hex_address(OAM_DMA_SETUP_END),
            "length": len(setup_raw),
            "hash": sha256(setup_raw) if setup_raw else None,
        },
        "dma_parameters": {
            "register": address_metadata(OAM_DMA_REGISTER, len(data)),
            "source": address_metadata(OAM_BUFFER, len(data)),
            "destination": address_metadata(OAM_DESTINATION, len(data)),
            "control": hex_address(OAM_DMA_CONTROL),
            "transfer_units": OAM_DMA_UNITS,
            "destination_construction": "movs_0xe0_then_lsl_19_to_0x07000000",
        },
        "post_setup_call": {
            "callsite": hex_address(OAM_DMA_POST_CALL),
            "target": None if target is None else hex_address(target),
            "expected_target": hex_address(OAM_DMA_POST_TARGET),
            "target_match": target == OAM_DMA_POST_TARGET,
            "target_direct_bl_callers": callers.get(OAM_DMA_POST_TARGET, []),
        },
        "source_class": "oam_attribute_buffer_to_oam",
        "glyph_provenance": "not_established_by_oam_dma",
    }


def _oam_node_metadata(data: bytes, refs: dict[int, list[dict[str, object]]], callers: dict[int, list[str]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name, entry, boundary_status in OAM_NODES:
        item: dict[str, object] = {
            "name": name,
            "entry": hex_address(entry),
            "boundary_status": boundary_status,
            "direct_bl_callers": callers.get(entry, []),
            "literal_references": [],
        }
        node_end = entry + INLINE_WINDOW
        if boundary_status == "function":
            item["function"] = _boundary_metadata(data, entry)
            bounded_end = _function_end(data, entry)
            if bounded_end > entry:
                node_end = bounded_end
        else:
            item["window"] = _window_metadata(data, entry, INLINE_WINDOW)
        for value in OAM_WORKING_DATA:
            for ref in refs.get(value, []):
                instruction = int(str(ref["instruction"]), 16)
                if entry <= instruction < node_end:
                    item["literal_references"].append(
                        {
                            "literal_load_address": ref["instruction"],
                            "literal_address": ref["literal_address"],
                            "loaded_register": ref["register"],
                            "value": address_metadata(value, len(data)),
                        }
                    )
        result.append(item)
    return result


def static_report(data: bytes) -> dict[str, object]:
    refs = _literal_ref_index(data, TRACKED_LITERAL_VALUES)
    tracked_targets = [OAM_DMA_FUNCTION, OAM_DMA_POST_TARGET]
    tracked_targets.extend(entry for _, entry, _ in OAM_NODES)
    for value_refs in refs.values():
        for ref in value_refs:
            function = _function_start(data, int(str(ref["instruction"]), 16))
            if function is not None:
                tracked_targets.append(function)
    callers = _direct_bl_callers_index(data, tracked_targets)
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "bounded known OAM nodes, fixed OBJ-DMA sites, and OBJ-VRAM-base literal references",
            "glyph_pattern_scan": False,
            "full_rom_source_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "oam_dma": _oam_dma_metadata(data, callers),
        "oam_nodes": _oam_node_metadata(data, refs, callers),
        "literal_consumers": {
            "oam_buffer": _ref_metadata(data, refs, OAM_BUFFER, callers),
            "obj_vram_base": _ref_metadata(data, refs, OBJ_VRAM_BASE, callers),
            "fixed_obj_vram_destination": _ref_metadata(data, refs, OBJ_DMA_DESTINATION, callers),
            "dma3_register": {
                "bounded_reference_count": len(refs.get(OAM_DMA_REGISTER, [])),
                "oam_setup_references": [
                    ref for ref in refs.get(OAM_DMA_REGISTER, [])
                    if OAM_DMA_SETUP <= int(str(ref["instruction"]), 16) < OAM_DMA_SETUP_END
                ],
            },
        },
        "fixed_obj_dma_sites": _fixed_obj_dma_metadata(data),
        "consumer_edges": {
            "oam": [
                {
                    "from": hex_address(OAM_BUFFER),
                    "to": hex_address(OAM_DESTINATION),
                    "via": hex_address(OAM_DMA_FUNCTION),
                    "transfer_units": OAM_DMA_UNITS,
                    "classification": "oam_metadata_consumer",
                }
            ],
            "obj": [
                {
                    "from": "runtime_or_resource_source",
                    "to": hex_address(OBJ_DMA_DESTINATION),
                    "via": hex_address(entry),
                    "classification": "fixed_obj_dma_destination_only",
                }
                for entry in (int(spec["entry"]) for spec in FIXED_DMA_CANDIDATES)
            ],
            "obj_vram_base_literal": {
                "address": hex_address(OBJ_VRAM_BASE),
                "reference_count": len(refs.get(OBJ_VRAM_BASE, [])),
                "classification": "bounded_obj_vram_destination_candidates",
                "source_pointer_or_code_unit": "not_recovered",
            },
        },
        "conclusions": {
            "confirmed": [
                "oam_buffer_0x030033f0_is_copied_to_oam_0x07000000_by_dma3",
                "oam_nodes_write_or_consume_attribute_buffers_before_the_dma",
                "0x06010000_has_twelve_bounded_thumb_literal_references",
                "eight_fixed_0x06013000_sites_remain_fixed_dma_patterns",
            ],
            "provisional": [
                "0x06010000_literal_references_are_obj_vram_destination_candidates",
                "fixed_obj_dma_source_class_is_runtime_or_resource_not_text",
            ],
            "negative": [
                "no_source_pointer_to_code_unit_or_glyph_writer_in_this_bounded_static_slice",
                "no_text_identity_or_codepage_claim_from_oam_or_obj_destination_metadata",
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
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
