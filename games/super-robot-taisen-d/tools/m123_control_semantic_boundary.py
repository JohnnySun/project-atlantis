#!/usr/bin/env python3
"""Bound the A6SJ consumer's control and layout semantics without naming them.

M1.23 disassembles only the already verified consumer window and joins its
source-safe aggregate reports.  It proves the two NUL exits, the two-byte
glyph loop, the absence of a dedicated 0x0A/0x0D compare in that window, and
the final stack-field routing branch.  It does not promote that stack field to
speaker/newline/branch semantics, and it keeps every opaque source unit
reject-closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m111_layout_contract import (  # noqa: E402
    CONSUMER_END,
    CONSUMER_START,
    LayoutContractError,
    _branch_target,
    disassemble_consumer,
    verify_consumer_contract,
)
from m17_layout import ROM_BASE, sha256  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
EXPECTED_CONSUMER_SHA256 = "b318d2b6e3dda2242397c61e2f9519114d7d898fe33c5475c93c99fa31abb613"
MODE_LOAD_PC = 0x08008966
MODE_SIGN_EXTEND_PC = 0x08008968
MODE_COMPARE_PC = 0x0800896C
MODE_OTHER_BRANCH_PC = 0x0800896E
MODE_OTHER_TARGET = 0x080089C6


class SemanticBoundaryReject(ValueError):
    """A bounded static semantic/layout invariant failed closed."""


def address(value: int) -> str:
    return f"0x{value:08X}"


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SemanticBoundaryReject(f"expected_object:{path}")
    return value


def _assert_source_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        if "text" in value:
            raise SemanticBoundaryReject(f"source_text_key:{path}")
        for key, child in value.items():
            _assert_source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_source_safe(child, f"{path}[{index}]")


def _instruction_map(instructions: Iterable[Any]) -> Dict[int, Any]:
    return {int(instruction.address): instruction for instruction in instructions}


def _instruction_metadata(instruction: Any) -> Dict[str, str]:
    return {
        "pc": address(int(instruction.address)),
        "mnemonic": str(instruction.mnemonic),
        "operands": str(instruction.op_str),
    }


def _normalize_operands(instruction: Any) -> str:
    return str(instruction.op_str).replace(" ", "").lower()


def _instruction_index_sha256(instructions: Sequence[Any]) -> str:
    value = "".join(
        f"{int(instruction.address):08x}:{instruction.mnemonic}:{instruction.op_str}\n"
        for instruction in instructions
    )
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _window_metadata(
    instructions: Sequence[Any],
    rom: bytes,
    start: int,
    end: int,
) -> Dict[str, Any]:
    selected = [instruction for instruction in instructions if start <= int(instruction.address) < end]
    if not selected:
        raise SemanticBoundaryReject(f"empty_instruction_window:{address(start)}")
    raw_start = start - ROM_BASE
    raw_end = end - ROM_BASE
    if raw_start < 0 or raw_end > len(rom):
        raise SemanticBoundaryReject("instruction_window_outside_rom")
    return {
        "start": address(start),
        "end_exclusive": address(end),
        "instruction_count": len(selected),
        "instruction_pcs_sha256": _instruction_index_sha256(selected),
        "bytes_sha256": sha256(rom[raw_start:raw_end]),
        "key_instructions": [_instruction_metadata(instruction) for instruction in selected],
    }


def _direct_bl_targets(instructions: Sequence[Any]) -> List[str]:
    targets: List[str] = []
    for instruction in instructions:
        if instruction.mnemonic != "bl":
            continue
        try:
            targets.append(_branch_target(instruction))
        except (AttributeError, IndexError, TypeError):
            targets.append("opaque")
    return sorted(set(targets))


def _require_instruction(
    instruction_map: Mapping[int, Any], pc: int, mnemonic: str, operands: Optional[str] = None
) -> Any:
    instruction = instruction_map.get(pc)
    if instruction is None or instruction.mnemonic != mnemonic:
        raise SemanticBoundaryReject(f"instruction_gate:{address(pc)}")
    if operands is not None and _normalize_operands(instruction) != operands:
        raise SemanticBoundaryReject(f"operand_gate:{address(pc)}")
    return instruction


def _control_source_summary(
    layout_report: Mapping[str, Any], inventory_report: Mapping[str, Any]
) -> Dict[str, Any]:
    source_corpus = layout_report.get("source_corpus")
    if not isinstance(source_corpus, Mapping):
        raise SemanticBoundaryReject("layout_source_corpus_missing")
    if int(source_corpus.get("record_count", -1)) != EXPECTED_RECORD_COUNT:
        raise SemanticBoundaryReject("source_record_count_mismatch")
    if int(source_corpus.get("nul_terminated_count", -1)) != EXPECTED_RECORD_COUNT:
        raise SemanticBoundaryReject("source_nul_count_mismatch")
    if int(source_corpus.get("token_encode_no_op_count", -1)) != EXPECTED_RECORD_COUNT:
        raise SemanticBoundaryReject("source_no_op_count_mismatch")
    token_counts = inventory_report.get("token_kind_counts")
    if not isinstance(token_counts, Mapping):
        raise SemanticBoundaryReject("inventory_token_counts_missing")
    normalized_counts = {str(key): int(value) for key, value in token_counts.items()}
    return {
        "record_count": EXPECTED_RECORD_COUNT,
        "nul_terminated_count": int(source_corpus["nul_terminated_count"]),
        "token_encode_no_op_count": int(source_corpus["token_encode_no_op_count"]),
        "token_kind_counts": dict(sorted(normalized_counts.items())),
        "opaque_newline_candidate_count": normalized_counts.get("opaque_newline_candidate", 0),
        "opaque_unit_count": sum(
            value for key, value in normalized_counts.items() if key.startswith("opaque_")
        ),
        "observed_width_minimum": int(source_corpus.get("observed_width_minimum", 0)),
        "observed_width_maximum": int(source_corpus.get("observed_width_maximum", 0)),
        "observed_width_is_engine_limit": False,
    }


def _caller_summary(caller_report: Mapping[str, Any]) -> Dict[str, Any]:
    source_policy = caller_report.get("source_policy")
    if not isinstance(source_policy, Mapping) or source_policy.get("semantic_labels_inferred") is not False:
        raise SemanticBoundaryReject("caller_semantic_label_gate_failed")
    calls = caller_report.get("consumer_callsites")
    if not isinstance(calls, Mapping):
        raise SemanticBoundaryReject("caller_report_missing")
    entries = calls.get("entries")
    if not isinstance(entries, list):
        raise SemanticBoundaryReject("caller_entries_missing")
    classes = Counter()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise SemanticBoundaryReject("caller_entry_invalid")
        static = entry.get("static")
        if not isinstance(static, Mapping) or static.get("status") != "verified":
            raise SemanticBoundaryReject("caller_window_not_verified")
        classes[str(static.get("structural_class", "opaque"))] += 1
    runtime = caller_report.get("runtime_observation")
    if not isinstance(runtime, Mapping):
        raise SemanticBoundaryReject("caller_runtime_observation_missing")
    return {
        "consumer": calls.get("consumer"),
        "candidate_count": int(calls.get("candidate_count", -1)),
        "candidate_instruction_index_sha256": calls.get("candidate_instruction_index_sha256"),
        "verified_structural_class_counts": dict(sorted(classes.items())),
        "runtime_callsite": runtime.get("caller_callsite"),
        "runtime_target_pointer_match": runtime.get("target_pointer_match"),
        "semantic_labels_inferred": False,
        "pointer_report_rescanned": False,
    }


def build_report(
    rom: bytes,
    layout_report: Mapping[str, Any],
    inventory_report: Mapping[str, Any],
    caller_report: Mapping[str, Any],
) -> Dict[str, Any]:
    _assert_source_safe(layout_report, "layout_report")
    _assert_source_safe(inventory_report, "inventory_report")
    _assert_source_safe(caller_report, "caller_report")
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise SemanticBoundaryReject("rom_hash_mismatch")
    consumer = verify_consumer_contract(rom)
    if consumer.get("code_sha256") != EXPECTED_CONSUMER_SHA256:
        raise SemanticBoundaryReject("consumer_code_hash_mismatch")
    instructions = disassemble_consumer(rom)
    instruction_map = _instruction_map(instructions)

    _require_instruction(instruction_map, 0x0800876C, "ldrb")
    _require_instruction(instruction_map, 0x0800876E, "cmp", "r0,#0")
    terminator_exit = _require_instruction(instruction_map, 0x08008770, "beq")
    if _branch_target(terminator_exit) != address(0x08008798):
        raise SemanticBoundaryReject("source_nul_exit_target_changed")
    _require_instruction(instruction_map, 0x08008774, "ldrh")
    _require_instruction(instruction_map, 0x0800878C, "adds", "r5,#2")
    loop_exit = _require_instruction(instruction_map, 0x08008796, "bne")
    if _branch_target(loop_exit) != address(0x08008774):
        raise SemanticBoundaryReject("glyph_loop_target_changed")
    render_exit = _require_instruction(instruction_map, 0x08008954, "beq")
    if _branch_target(render_exit) != address(0x08008958):
        raise SemanticBoundaryReject("render_nul_exit_target_changed")
    _require_instruction(instruction_map, MODE_LOAD_PC, "ldr", "r1,[sp,#0x5c]")
    _require_instruction(instruction_map, MODE_SIGN_EXTEND_PC, "asrs", "r0,r1,#0x10")
    _require_instruction(instruction_map, MODE_COMPARE_PC, "cmp", "r0,#1")
    mode_branch = _require_instruction(instruction_map, MODE_OTHER_BRANCH_PC, "bne")
    if _branch_target(mode_branch) != address(MODE_OTHER_TARGET):
        raise SemanticBoundaryReject("mode_other_branch_target_changed")

    newline_compares = [
        instruction
        for instruction in instructions
        if instruction.mnemonic == "cmp" and any(
            marker in _normalize_operands(instruction) for marker in ("#0xa", "#0xd")
        )
    ]
    source = _control_source_summary(layout_report, inventory_report)
    caller = _caller_summary(caller_report)
    equal_path = [instruction for instruction in instructions if 0x08008970 <= int(instruction.address) < MODE_OTHER_TARGET]
    other_path = [instruction for instruction in instructions if MODE_OTHER_TARGET <= int(instruction.address) < 0x080089DE]
    layout_safe = layout_report.get("layout_safe_subset", {})
    if not isinstance(layout_safe, Mapping):
        raise SemanticBoundaryReject("layout_safe_subset_missing")

    return {
        "schema": "super-robot-taisen-d-m123-control-semantic-boundary-v1",
        "milestone": "M1.23",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "semantic_labels_inferred": False,
            "pointer_report_rescanned": False,
        },
        "rom": {
            "sha256": sha256(rom),
            "expected_sha256": EXPECTED_ROM_SHA256,
            "hash_match": True,
        },
        "consumer_window": {
            "start": address(CONSUMER_START),
            "end_exclusive": address(CONSUMER_END),
            "code_sha256": consumer["code_sha256"],
            "instruction_count": len(instructions),
            "terminator_window": _window_metadata(instructions, rom, 0x0800876C, 0x08008798),
            "render_terminator_window": _window_metadata(instructions, rom, 0x08008950, 0x08008958),
            "glyph_loop_window": _window_metadata(instructions, rom, 0x08008774, 0x08008798),
            "mode_window": _window_metadata(instructions, rom, 0x08008966, 0x080089DE),
            "direct_newline_byte_compares": [_instruction_metadata(item) for item in newline_compares],
        },
        "proven_control_flow": {
            "source_terminator": {
                "load_pc": "0x0800876C",
                "compare_pc": "0x0800876E",
                "compare_value": 0,
                "exit_pc": "0x08008770",
                "exit_target": "0x08008798",
                "token_name": "NUL",
            },
            "glyph_loop": {
                "load_pc": "0x08008774",
                "unit_bytes": 2,
                "cursor_advance_pc": "0x0800878C",
                "cursor_advance_bytes": 2,
                "loop_test_pc": "0x08008794",
                "loop_pc": "0x08008796",
                "loop_target": "0x08008774",
            },
            "render_loop_terminator": {
                "load_pc": "0x08008950",
                "exit_pc": "0x08008954",
                "exit_target": "0x08008958",
                "token_name": "NUL",
            },
            "mode_routing_field": {
                "load_pc": address(MODE_LOAD_PC),
                "source": "stack+0x5C",
                "sign_extend_pc": address(MODE_SIGN_EXTEND_PC),
                "sign_extend": "high halfword by arithmetic shift right 0x10",
                "compare_pc": address(MODE_COMPARE_PC),
                "compare_value": 1,
                "other_branch_pc": address(MODE_OTHER_BRANCH_PC),
                "other_branch_target": address(MODE_OTHER_TARGET),
                "semantic_name": "opaque_mode_field",
            },
        },
        "mode_paths": {
            "equal_value_1": {
                "window": _window_metadata(instructions, rom, 0x08008970, MODE_OTHER_TARGET),
                "direct_bl_targets": _direct_bl_targets(equal_path),
                "operation": "bounded halfword destination-copy path",
                "speaker_newline_branch_proven": False,
            },
            "other_value": {
                "window": _window_metadata(instructions, rom, MODE_OTHER_TARGET, 0x080089DE),
                "direct_bl_targets": _direct_bl_targets(other_path),
                "operation": "opaque helper path",
                "speaker_newline_branch_proven": False,
            },
        },
        "source_corpus": source,
        "caller_boundary": caller,
        "fail_closed_contract": {
            "accepted_static_shape": {
                "token_class": "glyph_only_narrow",
                "opaque_token_count": 0,
                "line_count": 1,
                "max_width_pixels": int(layout_safe.get("width_cap_pixels", 64)),
                "engine_width_limit_proven": False,
                "same_length": True,
                "wide_glyph": False,
            },
            "reject_reasons": [
                "opaque_or_unaligned_token",
                "opaque_newline_candidate",
                "speaker_semantics_unconfirmed",
                "branch_semantics_unconfirmed",
                "line_count_not_proven_single",
                "width_over_observed_static_cap",
                "wide_glyph_without_accepted_existing_identity",
                "variable_length",
            ],
            "newline_policy": "unconfirmed_opaque; no dedicated consumer compare; do not translate",
            "speaker_policy": "unconfirmed_opaque_mode_or_caller_field; do not name",
            "branch_policy": "unconfirmed_opaque_mode_or_caller_field; do not name",
            "maximum_width_policy": "64px static POC cap only; observed 240px is not an engine limit",
        },
        "gate": {
            "rom_hash_match": True,
            "consumer_disassembly_verified": True,
            "consumer_code_hash_match": True,
            "source_records_2325": source["record_count"] == EXPECTED_RECORD_COUNT,
            "source_nul_2325": source["nul_terminated_count"] == EXPECTED_RECORD_COUNT,
            "source_token_encode_no_op_2325": source["token_encode_no_op_count"] == EXPECTED_RECORD_COUNT,
            "two_byte_glyph_loop_verified": True,
            "nul_terminator_verified": True,
            "dedicated_newline_byte_compare": len(newline_compares) == 0,
            "newline_semantics_proven": False,
            "speaker_semantics_proven": False,
            "branch_semantics_proven": False,
            "mode_field_origin_proven": True,
            "mode_field_semantics_named": False,
            "engine_width_limit_proven": False,
            "fail_closed_unknown_tokens": True,
            "translation_started": False,
            "source_text_emitted": False,
        },
        "next_condition": (
            "capture a producer/queue record with source pointer plus mode-field value, or a natural "
            "screen/VRAM layout, before assigning newline, speaker, branch, line-count, or engine-width semantics"
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--layout-report", type=Path, required=True)
    parser.add_argument("--inventory-report", type=Path, required=True)
    parser.add_argument("--caller-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_json(args.layout_report),
            read_json(args.inventory_report),
            read_json(args.caller_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, LayoutContractError, SemanticBoundaryReject, TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"m123_control_semantic_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m123_control_semantic=accepted records={} newline_compare={} mode_semantics_named={} width_max={}".format(
            report["source_corpus"]["record_count"],
            report["gate"]["dedicated_newline_byte_compare"],
            report["gate"]["mode_field_semantics_named"],
            report["source_corpus"]["observed_width_maximum"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
