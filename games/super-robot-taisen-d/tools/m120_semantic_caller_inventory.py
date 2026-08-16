#!/usr/bin/env python3
"""Inventory the verified consumer callsites without inventing scene labels.

The input is the corrected bounded known-consumer audit plus the existing
source-safe coverage/layout reports.  This slice disassembles only five
already verified direct callsites and records structural trigger conditions:
wrapper fallback, queue-entry drain, dual-buffer UI, and indexed object
buffer.  ``story``, ``branch``, ``battle``, ``unit``, ``speaker`` and
``newline`` remain explicitly unconfirmed until a source-buffer producer or
screen/queue context identifies them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import capstone

from m115_consumer_callsite_audit import CONSUMER, direct_call_candidates


EXPECTED_RECORD_COUNT = 2325
EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
ROM_BASE = 0x08000000


class SemanticInventoryReject(ValueError):
    """A bounded semantic inventory invariant failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def address(value: int) -> str:
    return f"0x{value:08X}"


def integer(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SemanticInventoryReject(f"expected_object:{path}")
    return value


CALLSITE_SPECS: Dict[int, Dict[str, Any]] = {
    0x0800869E: {
        "structural_class": "wrapper_fallback_zero_stack_arg",
        "trigger_condition": "wrapper_zero_test_falls_through_to_consumer;stack_arg_0=0",
        "start": 0x08008696,
        "end_exclusive": 0x080086A2,
        "expected": {
            0x08008696: ("cmp", "r0, #0"),
            0x08008698: ("bne", "#0x80086a4"),
            0x0800869A: ("str", "r0, [sp]"),
            0x0800869C: ("adds", "r0, r6, #0"),
            0x0800869E: ("bl", "#0x8008724"),
        },
    },
    0x08008E1C: {
        "structural_class": "queue_entry_drain_loop",
        "trigger_condition": "entry_pointer_[r7]_nonzero;index_0..0x3b;clear_after_consumer",
        "start": 0x08008E04,
        "end_exclusive": 0x08008E20,
        "expected": {
            0x08008E04: ("ldr", "r5, [r7]"),
            0x08008E06: ("cmp", "r5, #0"),
            0x08008E08: ("beq", "#0x8008e2a"),
            0x08008E0A: ("adds", "r0, r5, #0"),
            0x08008E0E: ("ldr", "r1, [r5, #4]"),
            0x08008E14: ("ldrb", "r2, [r2]"),
            0x08008E18: ("movs", "r4, #1"),
            0x08008E1A: ("str", "r4, [sp]"),
            0x08008E1C: ("bl", "#0x8008724"),
        },
    },
    0x08066050: {
        "structural_class": "dual_buffer_ui",
        "trigger_condition": "dual_buffer_setup;r0_from_r7;stack_arg_0=1",
        "start": 0x08066040,
        "end_exclusive": 0x08066054,
        "expected": {
            0x08066040: ("movs", "r1, #0x80"),
            0x08066042: ("lsls", "r1, r1, #3"),
            0x08066044: ("adds", "r1, r5, r1"),
            0x08066048: ("str", "r4, [sp]"),
            0x0806604A: ("adds", "r0, r7, #0"),
            0x0806604C: ("movs", "r2, #0xd"),
            0x0806604E: ("movs", "r3, #5"),
            0x08066050: ("bl", "#0x8008724"),
        },
    },
    0x08066062: {
        "structural_class": "dual_buffer_ui",
        "trigger_condition": "dual_buffer_setup;r0_from_r8;stack_arg_0=1",
        "start": 0x08066054,
        "end_exclusive": 0x08066066,
        "expected": {
            0x08066054: ("movs", "r1, #0xc0"),
            0x08066056: ("lsls", "r1, r1, #4"),
            0x08066058: ("adds", "r1, r5, r1"),
            0x0806605A: ("str", "r4, [sp]"),
            0x0806605C: ("mov", "r0, r8"),
            0x0806605E: ("movs", "r2, #0xd"),
            0x08066060: ("movs", "r3, #6"),
            0x08066062: ("bl", "#0x8008724"),
        },
    },
    0x0806E01C: {
        "structural_class": "indexed_object_buffer",
        "trigger_condition": "indexed_object_buffer_[r6]_nonzero;stack_arg_0=1",
        "start": 0x0806E010,
        "end_exclusive": 0x0806E020,
        "expected": {
            0x0806E010: ("movs", "r0, #1"),
            0x0806E012: ("str", "r0, [sp]"),
            0x0806E014: ("adds", "r0, r1, #0"),
            0x0806E016: ("adds", "r1, r4, #0"),
            0x0806E018: ("movs", "r2, #0xd"),
            0x0806E01A: ("movs", "r3, #0"),
            0x0806E01C: ("bl", "#0x8008724"),
        },
    },
}


def verify_callsite(rom: bytes, callsite: int) -> Dict[str, Any]:
    spec = CALLSITE_SPECS.get(callsite)
    if spec is None:
        return {"status": "candidate_without_structural_spec"}
    start = int(spec["start"])
    end = int(spec["end_exclusive"])
    start_offset = start - ROM_BASE
    end_offset = end - ROM_BASE
    if start_offset < 0 or end_offset > len(rom):
        raise SemanticInventoryReject("callsite_window_outside_rom")
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    instructions = list(md.disasm(rom[start_offset:end_offset], start))
    actual = {int(ins.address): (ins.mnemonic, ins.op_str) for ins in instructions}
    mismatches = []
    for pc, expected in spec["expected"].items():
        if actual.get(pc) != expected:
            mismatches.append(
                {
                    "pc": address(pc),
                    "expected": expected,
                    "actual": actual.get(pc),
                }
            )
    return {
        "status": "verified" if not mismatches else "mismatch",
        "structural_class": spec["structural_class"],
        "trigger_condition": spec["trigger_condition"],
        "instruction_window": {
            "start": address(start),
            "end_exclusive": address(end),
            "length": end - start,
            "sha256": sha256(rom[start_offset:end_offset]),
            "instruction_count": len(instructions),
            "instruction_pcs_sha256": sha256(
                ",".join(address(int(ins.address)) for ins in instructions).encode("ascii")
            ),
        },
        "mismatches": mismatches,
    }


def build_report(
    rom: bytes,
    callsite_report: Mapping[str, Any],
    coverage_report: Mapping[str, Any],
    layout_report: Mapping[str, Any],
    runtime_report: Mapping[str, Any],
) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise SemanticInventoryReject("rom_hash_mismatch")
    candidates = direct_call_candidates(rom)
    if len(candidates) != 5:
        raise SemanticInventoryReject(f"direct_candidate_count:{len(candidates)}")
    callsite_rows = []
    for candidate in candidates:
        callsite = integer(candidate["instruction"])
        static = verify_callsite(rom, callsite)
        callsite_rows.append(
            {
                "callsite": address(callsite),
                "consumer": candidate["target"],
                "kind": candidate["kind"],
                "static": static,
            }
        )
    runtime_caller = runtime_report.get("runtime_caller", {})
    runtime_callsite = runtime_caller.get("caller_callsite")
    runtime_match = runtime_callsite in {row["callsite"] for row in callsite_rows}
    consumer = layout_report.get("consumer", {})
    layout_source = layout_report.get("source_corpus", {})
    line_layout = consumer.get("line_layout", {})
    semantic = {
        "story": "unconfirmed",
        "branch": "unconfirmed",
        "battle_dialogue": "unconfirmed",
        "unit_pilot_weapon_spirit": "unconfirmed",
        "ui": "unconfirmed",
        "speaker": "unconfirmed",
        "newline": "unconfirmed",
        "engine_width_limit": "unconfirmed",
        "reason": "structural caller class and RAM buffer identity do not prove scene semantics",
    }
    return {
        "schema": "super-robot-taisen-d-m120-semantic-caller-inventory-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "pointer_report_reused_without_rescan": True,
            "semantic_labels_inferred": False,
        },
        "rom": {"sha256": sha256(rom), "expected_sha256": EXPECTED_ROM_SHA256, "hash_match": True},
        "consumer_callsites": {
            "consumer": address(CONSUMER),
            "candidate_count": len(candidates),
            "candidate_instruction_index_sha256": sha256(
                ",".join(row["instruction"] for row in candidates).encode("ascii")
            ),
            "entries": callsite_rows,
        },
        "runtime_observation": {
            "caller_callsite": runtime_callsite,
            "caller_callsite_matches_static_candidate": runtime_match,
            "consumer_entry_status": runtime_caller.get("status"),
            "source_pointer": runtime_caller.get("source_pointer"),
            "source_pointer_region": runtime_caller.get("source_pointer_region"),
            "target_pointer_match": runtime_caller.get("target_pointer_match"),
            "target_render_proven": False,
            "natural_screen_proven": False,
        },
        "corpus_coverage": {
            "record_count": coverage_report.get("source_corpus", {}).get("record_count"),
            "partition_counts": coverage_report.get("source_corpus", {}).get("partition_counts"),
            "exact_source_candidate_count": coverage_report.get("pointer_join", {}).get("exact_source_candidate_count"),
            "exact_source_record_count": coverage_report.get("pointer_join", {}).get("exact_source_record_count"),
            "caller_cohort_count": coverage_report.get("pointer_join", {}).get("caller_cohort_count"),
            "natural_caller_status": coverage_report.get("runtime_coverage", {}).get("natural_caller_status"),
            "semantic_partition": semantic,
        },
        "layout_boundary": {
            "terminator": consumer.get("terminator"),
            "glyph_units": consumer.get("glyph_units"),
            "newline_branch_in_bounded_consumer": line_layout.get("newline_branch"),
            "newline_engine_semantics": "unconfirmed",
            "speaker_semantics": "unconfirmed",
            "branch_semantics": "unconfirmed",
            "observed_width_minimum": layout_source.get("observed_width_minimum"),
            "observed_width_maximum": layout_source.get("observed_width_maximum"),
            "engine_width_limit_proven": False,
        },
        "gate": {
            "rom_hash_match": True,
            "direct_consumer_candidates_5": len(candidates) == 5,
            "all_callsite_windows_verified": all(row["static"].get("status") == "verified" for row in callsite_rows),
            "runtime_callsite_matches_static_candidate": runtime_match,
            "source_records_2325": coverage_report.get("source_corpus", {}).get("record_count") == EXPECTED_RECORD_COUNT,
            "pointer_report_reused_without_rescan": True,
            "semantic_labels_inferred": False,
            "newline_engine_proven": False,
            "speaker_semantics_proven": False,
            "branch_semantics_proven": False,
            "engine_width_limit_proven": False,
            "translation_status": "ai_draft",
        },
        "next_condition": "identify a source-buffer producer or target caller/index before assigning story/branch/battle/unit/UI labels",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--callsite-report", type=Path, required=True)
    parser.add_argument("--coverage-report", type=Path, required=True)
    parser.add_argument("--layout-report", type=Path, required=True)
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_json(args.callsite_report),
            read_json(args.coverage_report),
            read_json(args.layout_report),
            read_json(args.runtime_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, SemanticInventoryReject, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m120_semantic_caller_inventory_rejected={exc}")
        return 2
    print(
        "m120_semantic_caller_inventory=accepted callsites={} runtime_match={} semantic_labels_inferred={}".format(
            report["consumer_callsites"]["candidate_count"],
            report["gate"]["runtime_callsite_matches_static_candidate"],
            report["gate"]["semantic_labels_inferred"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
