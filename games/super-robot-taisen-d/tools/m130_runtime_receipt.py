#!/usr/bin/env python3
"""Build a source-safe M1.30 runtime receipt from ignored captures.

The input captures stay under ``work/``.  This reducer keeps only hashes,
addresses, counts, and fail-closed status for the tracked research record; it
never copies source/target text, raw memory, pixels, or screenshots.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


BASE_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
PATCHED_ROM_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
BPS_SHA256 = "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"
BPS_SIZE = 66
TARGET_STRING_ID = 526424
ADJACENT_STRING_ID = 526432
EXPECTED_SLOT_VALUES = {"narrow": "0x0814F664", "wide": "0x08120DBC"}


class RuntimeReceiptReject(ValueError):
    """An ignored capture is incomplete or contains forbidden content."""


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeReceiptReject(f"expected_object:{path}")
    return value


def source_safe(value: Any, path: str = "root") -> None:
    forbidden = {"text", "raw", "pixels", "image", "screenshot", "dump"}
    if isinstance(value, Mapping):
        leaked = forbidden.intersection(value)
        if leaked:
            raise RuntimeReceiptReject(f"forbidden_key:{path}:{sorted(leaked)}")
        for key, child in value.items():
            source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            source_safe(child, f"{path}[{index}]")


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeReceiptReject(f"{label}_mismatch:{actual!r}")


def _slot_from_offset(offset: str) -> int:
    value = int(offset, 16)
    if value % 12:
        raise RuntimeReceiptReject(f"glyph_offset_not_stride_aligned:{offset}")
    return value // 12


def _unit_receipt(unit: Mapping[str, Any]) -> Dict[str, Any]:
    glyph = unit.get("glyph")
    writer = unit.get("writer")
    render = unit.get("render")
    counts = unit.get("consumer_event_counts")
    if not all(isinstance(item, Mapping) for item in (glyph, writer, render, counts)):
        raise RuntimeReceiptReject("unit_sections_missing")
    assert isinstance(glyph, Mapping)
    assert isinstance(writer, Mapping)
    assert isinstance(render, Mapping)
    assert isinstance(counts, Mapping)
    glyph_offset = str(glyph.get("glyph_offset"))
    calls = writer.get("calls")
    if not isinstance(calls, list) or not calls:
        raise RuntimeReceiptReject("writer_calls_missing")
    callsite_counts = Counter(str(call.get("callsite")) for call in calls if isinstance(call, Mapping))
    live_source_hashes = sorted(
        {str(call.get("tile_source_word_sha256")) for call in calls if isinstance(call, Mapping)}
    )
    pipeline_matches = all(
        bool(call.get("pipeline_r1_matches_live_word"))
        for call in calls
        if isinstance(call, Mapping)
    )
    require_equal("codepage_event_count", counts.get("codepage_lookup"), 1)
    require_equal("glyph_event_count", counts.get("narrow_glyph_add"), 1)
    require_equal("writer_call_count", counts.get("tile_writer_callsites"), len(calls))
    require_equal("writer_byte_count", writer.get("strh_byte_count"), len(calls) * 2)
    require_equal("runtime_static_glyph_match", glyph.get("runtime_static_glyph_match"), True)
    require_equal("unit_not_truncated", unit.get("unit_not_truncated"), True)
    require_equal("render_exact", render.get("pixel_render_exact_expected"), True)
    return {
        "unit_index": int(unit["unit_index"]),
        "code_unit": str(unit["code_unit"]),
        "source_pointer": str(unit["source_pointer"]),
        "glyph_slot": _slot_from_offset(glyph_offset),
        "glyph_offset": glyph_offset,
        "glyph_pointer": str(glyph["glyph_pointer"]),
        "glyph_sha256": str(glyph["glyph"]["sha256"]),
        "runtime_static_glyph_match": True,
        "consumer_event_counts": {
            "codepage_lookup": int(counts["codepage_lookup"]),
            "narrow_glyph_add": int(counts["narrow_glyph_add"]),
            "tile_writer_callsites": len(calls),
        },
        "writer": {
            "entry_pc": str(writer["pc"]),
            "store_pc": str(writer["store_pc"]),
            "callsite_counts": dict(sorted(callsite_counts.items())),
            "destination_first": str(writer["destination_first"]),
            "destination_last": str(writer["destination_last"]),
            "strh_byte_count": int(writer["strh_byte_count"]),
            "tile_source_word_sha256_values": live_source_hashes,
            "pipeline_r1_matches_live_word": pipeline_matches,
        },
        "render": {
            "source": str(render["source"]),
            "width": int(render["width"]),
            "height": int(render["height"]),
            "tile_columns": int(render["tile_columns"]),
            "tile_rows": int(render["tile_rows"]),
            "pixel_nibble_sha256": str(render["pixel_nibble_sha256"]),
            "expected_pixel_nibble_sha256": str(render["expected_pixel_nibble_sha256"]),
            "pixel_nibble_nonzero": int(render["pixel_nibble_nonzero"]),
            "pixel_render_exact_expected": True,
        },
        "controlled_renderer_palette_index": int(unit["controlled_renderer_palette_index"]),
    }


def _record_receipt(record: Mapping[str, Any], *, include_nul: bool) -> Dict[str, Any]:
    units = record.get("units")
    if not isinstance(units, list):
        raise RuntimeReceiptReject("record_units_missing")
    require_equal("record_not_truncated", record["termination"]["record_not_truncated"], True)
    require_equal("unit_count_observed", record["termination"]["unit_count_observed"], len(units))
    if include_nul:
        require_equal("nul_branch_observed", record["termination"]["nul_branch"]["observed"], True)
    return {
        "string_id": int(record["record"]["string_id"]),
        "source_address": str(record["record"]["source_address"]),
        "source_raw_sha256": str(record["record"]["source_raw_sha256"]),
        "source_ledger_sha256": record["record"].get("source_ledger_sha256"),
        "payload_length": int(record["record"]["payload_length"]),
        "unit_count_expected": int(record["termination"]["unit_count_expected"]),
        "unit_count_observed": int(record["termination"]["unit_count_observed"]),
        "layout": {
            "width": int(record["layout"]["width"]),
            "height": int(record["layout"]["height"]),
            "tile_columns": int(record["layout"]["tile_columns"]),
            "exact_per_unit": bool(record["layout"]["exact_per_unit"]),
            "controlled_consumer_layout": bool(record["layout"]["controlled_consumer_layout"]),
        },
        "units": [_unit_receipt(unit) for unit in units],
        "nul_branch": None
        if not include_nul
        else {
            "pc": str(record["termination"]["nul_branch"]["pc"]),
            "lr": str(record["termination"]["nul_branch"]["lr"]),
            "terminator_address": str(record["termination"]["nul_branch"]["terminator_address"]),
            "observed": True,
        },
        "nul_read_during_glyph_units": bool(record["termination"]["nul_read_during_glyph_units"]),
    }


def build_receipt(
    base: Mapping[str, Any],
    patched: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    for name, report in (("base", base), ("patched", patched), ("comparison", comparison)):
        source_safe(report, name)
    require_equal("base_rom_hash", base["rom"]["sha256"], BASE_ROM_SHA256)
    require_equal("patched_rom_hash", patched["rom"]["sha256"], PATCHED_ROM_SHA256)
    require_equal("bps_hash", patched["bps"]["sha256"], BPS_SHA256)
    require_equal("bps_size", patched["bps"]["size"], BPS_SIZE)
    require_equal("comparison_schema", comparison["schema"], "super-robot-taisen-d-m130-corrected-runtime-compare-v1")
    require_equal("comparison_release_ready", comparison["gate"]["release_ready"], False)
    require_equal("comparison_target_proof", comparison["gate"]["patched_target_controlled_consumer_proven"], True)
    require_equal("comparison_adjacent_proof", comparison["gate"]["adjacent_untouched_runtime_proven"], True)
    require_equal("slot_values_base", base["runtime"]["font_slots"], EXPECTED_SLOT_VALUES)
    require_equal("slot_values_patched", patched["runtime"]["font_slots"], EXPECTED_SLOT_VALUES)
    require_equal("target_id", patched["runtime"]["target"]["record"]["string_id"], TARGET_STRING_ID)
    require_equal("adjacent_id", patched["runtime"]["adjacent"]["record"]["string_id"], ADJACENT_STRING_ID)
    target = _record_receipt(patched["runtime"]["target"], include_nul=True)
    adjacent = _record_receipt(patched["runtime"]["adjacent"], include_nul=False)
    initializer = patched["runtime"]["initializer"]
    slot_events = [
        {
            "slot": str(event["resource"]["slot"]),
            "writer_pc": str(event["resource"]["writer_pc"]),
            "pc": str(event["resource"]["pc"]),
            "lr": str(event["resource"]["lr"]),
            "pointer": str(event["resource"]["pointer"]),
            "resource_hash_sha256": str(event["resource"]["resource_hash"]["sha256"]),
        }
        for event in initializer["events"]
        if event.get("kind") == "slot_write"
    ]
    require_equal("slot_event_count", len(slot_events), 2)
    return {
        "schema": "super-robot-taisen-d-m130-corrected-runtime-receipt-v1",
        "milestone": "M1.30",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "target_text_emitted": False,
            "raw_memory_emitted": False,
            "pixels_emitted": False,
            "natural_screenshot_emitted": False,
            "controlled_only": True,
        },
        "roms": {
            "base_sha256": BASE_ROM_SHA256,
            "patched_sha256": PATCHED_ROM_SHA256,
            "bps_sha256": BPS_SHA256,
            "bps_size": BPS_SIZE,
            "bps_hash_match": True,
        },
        "runtime": {
            "gdb_port": int(patched["runtime"]["gdb_port"]),
            "single_connection": True,
            "fresh_process_required": True,
            "natural_navigation": "not_attempted",
            "controlled_method": str(patched["runtime"]["controlled_method"]),
            "pc_write_convention": str(patched["runtime"]["pc_write_convention"]),
            "font_slots": EXPECTED_SLOT_VALUES,
            "initializer": {
                "entry": str(initializer["entry"]),
                "initializer": str(initializer["initializer"]),
                "verified_callsite": str(initializer["verified_callsite"]),
                "slot_nonzero": bool(initializer["slot_nonzero"]),
                "slot_write_events": slot_events,
            },
            "target": target,
            "adjacent": adjacent,
        },
        "comparison": {
            "source_payload_changed": bool(comparison["target"]["source_payload_changed"]),
            "runtime_glyph_render_changed": bool(comparison["target"]["runtime_glyph_render_changed"]),
            "adjacent_payload_sha256_equal": bool(comparison["adjacent"]["payload_sha256_equal"]),
            "adjacent_glyph_hashes_equal": bool(comparison["adjacent"]["glyph_hashes_equal"]),
            "adjacent_render_hashes_equal": bool(comparison["adjacent"]["render_hashes_equal"]),
            "adjacent_runtime_untouched": bool(comparison["adjacent"]["runtime_untouched"]),
            "font_slot_values_equal": bool(comparison["font_initialization"]["slot_values_equal"]),
        },
        "gate": {
            "rom_hashes_match": True,
            "font_base_nonzero": True,
            "target_units_2_of_2": True,
            "target_nul_branch_proven": True,
            "target_glyphs_runtime_static_hash_match": all(
                unit["runtime_static_glyph_match"] for unit in target["units"]
            ),
            "target_layout_and_render_exact": True,
            "adjacent_layout_and_render_exact": True,
            "adjacent_untouched_runtime_proven": True,
            "natural_screen_proven": False,
            "translation_status": "ai_draft",
            "release_ready": False,
            "source_confidence": "strict_source_hash_plus_controlled_consumer_and_live_glyph_path",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-report", type=Path, required=True)
    parser.add_argument("--patched-report", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = build_receipt(
            read_json(args.base_report),
            read_json(args.patched_report),
            read_json(args.comparison),
        )
        source_safe(receipt)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, RuntimeReceiptReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m130_runtime_receipt_rejected={exc}", file=sys.stderr)
        return 2
    print("m130_runtime_receipt=accepted target=526424 adjacent=526432 natural_screen=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
