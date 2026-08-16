#!/usr/bin/env python3
"""Make the A6SJ control/layout evidence explicitly fail closed.

M1.28 does not decode a new token and does not add a translation.  It joins
the source-safe M1.23 consumer disassembly with M1.26 corpus/encoder counts
and emits a machine-checkable distinction between proven byte boundaries and
unproven newline, speaker, branch, and engine-width semantics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
EXPECTED_NARROW_SHAPE_COUNT = 939
EXPECTED_MIXED_COUNT = 833
EXPECTED_WIDE_COUNT = 417
EXPECTED_OPAQUE_COUNT = 136
EXPECTED_OPAQUE_UNIT_COUNT = 1120
EXPECTED_OBSERVED_WIDTH_MAX = 240
STATIC_WIDTH_CAP = 64


class ControlLayoutReject(ValueError):
    """A reused semantic or corpus invariant failed closed."""


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ControlLayoutReject(f"expected_object:{path}")
    return value


def _source_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        # ``source`` is allowed as an address/provenance metadata field; raw
        # source text is represented by the exact ``text`` key and target
        # records by ``targets``.
        if "text" in value or "targets" in value:
            raise ControlLayoutReject(f"source_or_target_text_key:{path}")
        for key, child in value.items():
            _source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _source_safe(child, f"{path}[{index}]")


def _equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ControlLayoutReject(f"{label}_mismatch")


def build_report(m123: Mapping[str, Any], m126: Mapping[str, Any]) -> Dict[str, Any]:
    _source_safe(m123, "m123")
    _source_safe(m126, "m126")
    _equal("m123_rom_hash", m123.get("rom", {}).get("sha256"), EXPECTED_ROM_SHA256)
    _equal("m126_rom_hash", m126.get("inputs", {}).get("rom_sha256"), EXPECTED_ROM_SHA256)

    source = m123.get("source_corpus")
    if not isinstance(source, Mapping):
        raise ControlLayoutReject("m123_source_corpus_missing")
    for key in ("record_count", "nul_terminated_count", "token_encode_no_op_count"):
        _equal(f"m123_{key}", int(source.get(key, -1)), EXPECTED_RECORD_COUNT)
    _equal("opaque_unit_count", int(source.get("opaque_unit_count", -1)), EXPECTED_OPAQUE_UNIT_COUNT)
    _equal("opaque_newline_candidate_count", int(source.get("opaque_newline_candidate_count", -1)), 0)
    _equal("observed_width_maximum", int(source.get("observed_width_maximum", -1)), EXPECTED_OBSERVED_WIDTH_MAX)
    _equal("observed_width_is_engine_limit", bool(source.get("observed_width_is_engine_limit")), False)

    window = m123.get("consumer_window")
    if not isinstance(window, Mapping):
        raise ControlLayoutReject("m123_consumer_window_missing")
    newline_compares = window.get("direct_newline_byte_compares")
    if not isinstance(newline_compares, list):
        raise ControlLayoutReject("newline_compare_metadata_missing")
    _equal("dedicated_newline_compare_count", len(newline_compares), 0)

    proven = m123.get("proven_control_flow")
    if not isinstance(proven, Mapping):
        raise ControlLayoutReject("proven_control_flow_missing")
    source_nul = proven.get("source_terminator", {})
    glyph_loop = proven.get("glyph_loop", {})
    render_nul = proven.get("render_loop_terminator", {})
    mode = proven.get("mode_routing_field", {})
    _equal("source_nul_token", source_nul.get("token_name"), "NUL")
    _equal("source_nul_exit", source_nul.get("exit_target"), "0x08008798")
    _equal("glyph_unit_bytes", int(glyph_loop.get("unit_bytes", -1)), 2)
    _equal("glyph_cursor_advance", int(glyph_loop.get("cursor_advance_bytes", -1)), 2)
    _equal("render_nul_token", render_nul.get("token_name"), "NUL")
    _equal("mode_semantic_name", mode.get("semantic_name"), "opaque_mode_field")

    m126_source = m126.get("source_corpus")
    m126_boundary = m126.get("fail_closed_boundary")
    if not isinstance(m126_source, Mapping) or not isinstance(m126_boundary, Mapping):
        raise ControlLayoutReject("m126_corpus_boundary_missing")
    partition_counts = m126_source.get("partition_counts")
    if not isinstance(partition_counts, Mapping):
        raise ControlLayoutReject("partition_counts_missing")
    expected_partitions = {
        "glyph_only_narrow": EXPECTED_NARROW_SHAPE_COUNT,
        "glyph_only_mixed": EXPECTED_MIXED_COUNT,
        "glyph_only_wide": EXPECTED_WIDE_COUNT,
        "opaque_or_unaligned": EXPECTED_OPAQUE_COUNT,
    }
    for key, expected in expected_partitions.items():
        _equal(f"partition_{key}", int(partition_counts.get(key, -1)), expected)
    _equal("translated_narrow_only", int(m126_boundary.get("translated_narrow_only_count", -1)), 12)
    _equal("untranslated_narrow_only", int(m126_boundary.get("untranslated_narrow_only_count", -1)), 927)
    _equal("rejected_total", int(m126_boundary.get("rejected_total_count", -1)), 2313)

    return {
        "schema": "super-robot-taisen-d-m128-control-layout-contract-v1",
        "milestone": "M1.28",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "target_text_emitted": False,
            "raw_memory_emitted": False,
            "semantic_labels_inferred": False,
            "pointer_report_rescanned": False,
            "translation_started": False,
        },
        "proven_boundaries": {
            "source_terminator": {
                "token": "NUL",
                "consumer_compare": "0x0800876E cmp r0,#0",
                "exit": "0x08008770 -> 0x08008798",
                "record_count": EXPECTED_RECORD_COUNT,
            },
            "render_terminator": {
                "token": "NUL",
                "exit": "0x08008954 -> 0x08008958",
            },
            "glyph_unit": {
                "load": "0x08008774 ldrh",
                "code_unit_bytes": 2,
                "cursor_advance": "0x0800878C adds r5,#2",
                "loop": "0x08008796 -> 0x08008774",
            },
            "opaque_mode_field": {
                "load": "0x08008966 ldr r1,[sp,#0x5C]",
                "route": "asrs high-halfword by 0x10; cmp #1; equal/other paths",
                "semantic_name": "opaque_mode_field",
            },
        },
        "semantic_status": {
            "newline": {
                "dedicated_consumer_byte_compare_count": 0,
                "opaque_source_candidate_count": 0,
                "status": "unconfirmed; do not infer absence globally",
            },
            "speaker": {
                "mode_field_origin": "proven",
                "meaning": "unconfirmed",
                "status": "opaque; do not name",
            },
            "branch": {
                "mode_field_origin": "proven",
                "meaning": "unconfirmed",
                "status": "opaque; do not name",
            },
            "engine_width": {
                "observed_minimum": int(source.get("observed_width_minimum", 0)),
                "observed_maximum": EXPECTED_OBSERVED_WIDTH_MAX,
                "engine_limit_proven": False,
                "status": "unconfirmed",
            },
        },
        "corpus_boundary": {
            "record_count": EXPECTED_RECORD_COUNT,
            "partition_counts": dict(sorted((str(k), int(v)) for k, v in partition_counts.items())),
            "source_no_op_count": EXPECTED_RECORD_COUNT,
            "structural_single_line_narrow_shape_count": EXPECTED_NARROW_SHAPE_COUNT,
            "target_encoder_admissible_count": 12,
            "opaque_unit_count": EXPECTED_OPAQUE_UNIT_COUNT,
            "wide_new_slot_capacity": 0,
        },
        "fail_closed_contract": {
            "accepted_source_shape": {
                "partition": "glyph_only_narrow",
                "terminator": "NUL",
                "opaque_or_unaligned": False,
                "token_level_line_count": 1,
                "maximum_width_pixels": STATIC_WIDTH_CAP,
                "engine_width_limit_proven": False,
                "same_length": True,
                "wide_glyph": False,
            },
            "required_target_gates": [
                "source_hash_match",
                "font_and_rom_hash_match",
                "verified_narrow_code_unit_and_slot",
                "target_glyph_present",
                "same_length",
                "width_at_or_below_static_cap",
                "NUL_preserved",
                "no_opaque_control_or_unconfirmed_semantic_field",
            ],
            "reject_reasons": [
                "opaque_or_unaligned_token",
                "opaque_newline_or_control_candidate",
                "speaker_semantics_unconfirmed",
                "branch_semantics_unconfirmed",
                "engine_line_count_unconfirmed",
                "width_over_static_cap",
                "wide_identity_or_new_slot_unproven",
                "missing_glyph",
                "variable_length",
            ],
            "no_batch_translation": True,
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": True,
            "source_nul_2325": True,
            "source_token_encode_no_op_2325": True,
            "consumer_disassembly_verified": True,
            "two_byte_glyph_loop_verified": True,
            "nul_terminator_verified": True,
            "unknown_tokens_fail_closed": True,
            "newline_semantics_proven": False,
            "speaker_semantics_proven": False,
            "branch_semantics_proven": False,
            "engine_width_limit_proven": False,
            "translation_started": False,
            "runtime_screen_proven": False,
            "release_ready": False,
        },
        "next_condition": "producer/queue context plus runtime stop-protocol evidence must bind the opaque mode field and screen layout before newline/speaker/branch or engine-width semantics can be named",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m123-report", type=Path, required=True)
    parser.add_argument("--m126-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(read_json(args.m123_report), read_json(args.m126_report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ControlLayoutReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m128_control_layout_contract_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m128_control_layout_contract=accepted records={} narrow_shape={} target_admissible={} newline_compare=0".format(
            report["corpus_boundary"]["record_count"],
            report["corpus_boundary"]["structural_single_line_narrow_shape_count"],
            report["corpus_boundary"]["target_encoder_admissible_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
