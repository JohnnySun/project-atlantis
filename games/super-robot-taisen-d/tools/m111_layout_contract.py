#!/usr/bin/env python3
"""Bounded static layout contract for the A6SJ text consumer.

This tool disassembles only the already verified consumer range
``0x08008724..0x08008A0C``.  It records the NUL exit, two-byte cursor advance,
8/12-pixel glyph-width accumulator, tile-grid allocation, and the final
mode-dependent branch.  The branch and helper semantics that are not proven
by this function remain opaque; no numeric value is promoted to a control or
speaker token.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    import capstone
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("capstone is required for bounded consumer disassembly") from exc

from m110_boundary_audit import build_report as build_boundary_audit
from m17_layout import ROM_BASE, read_source_records, sha256


CONSUMER_START = 0x08008724
CONSUMER_END = 0x08008A0C
CONSUMER_LENGTH = CONSUMER_END - CONSUMER_START


class LayoutContractError(RuntimeError):
    """A verified consumer instruction changed or a contract is ambiguous."""


def address(value: int) -> str:
    return f"0x{value:08X}"


def disassemble_consumer(rom: bytes) -> List[Any]:
    start = CONSUMER_START - ROM_BASE
    end = CONSUMER_END - ROM_BASE
    if start < 0 or end > len(rom):
        raise LayoutContractError("consumer range outside ROM")
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    instructions = list(md.disasm(rom[start:end], CONSUMER_START))
    if not instructions:
        raise LayoutContractError("consumer disassembly is empty")
    return instructions


def _instruction_map(instructions: Iterable[Any]) -> Dict[int, Any]:
    return {int(instruction.address): instruction for instruction in instructions}


def _require(
    instruction_map: Mapping[int, Any], pc: int, mnemonic: str, operand_fragment: str = ""
) -> Any:
    instruction = instruction_map.get(pc)
    if instruction is None or instruction.mnemonic != mnemonic:
        raise LayoutContractError(f"instruction gate failed at {address(pc)}")
    if operand_fragment and operand_fragment not in instruction.op_str.replace(" ", ""):
        raise LayoutContractError(f"operand gate failed at {address(pc)}")
    return instruction


def _branch_target(instruction: Any) -> str:
    if not instruction.operands or instruction.operands[0].type != capstone.CS_OP_IMM:
        return "opaque"
    return address(int(instruction.operands[0].imm))


def _instruction_metadata(instruction: Any) -> Dict[str, str]:
    return {
        "pc": address(int(instruction.address)),
        "mnemonic": instruction.mnemonic,
        "operands": instruction.op_str,
    }


def width_summary(widths: Sequence[int]) -> Dict[str, Any]:
    if not widths:
        raise LayoutContractError("width set is empty")
    return {
        "record_count": len(widths),
        "minimum_pixels": min(widths),
        "maximum_pixels": max(widths),
        "distinct_count": len(set(widths)),
        "maximum_observed_tile_columns": math.ceil(max(widths) / 8),
        "maximum_observed_tile_bytes": math.ceil(max(widths) / 8) * 64,
        "engine_limit_proven": False,
    }


def verify_consumer_contract(rom: bytes) -> Dict[str, Any]:
    instructions = disassemble_consumer(rom)
    instruction_map = _instruction_map(instructions)
    gates = {
        "terminator_load": _require(instruction_map, 0x0800876C, "ldrb"),
        "terminator_compare": _require(instruction_map, 0x0800876E, "cmp"),
        "terminator_exit": _require(instruction_map, 0x08008770, "beq"),
        "glyph_load": _require(instruction_map, 0x08008774, "ldrh"),
        "width_compare": _require(instruction_map, 0x0800877A, "cmp"),
        "narrow_branch": _require(instruction_map, 0x0800877C, "bls"),
        "wide_width_add": _require(instruction_map, 0x08008780, "add"),
        "narrow_width_add": _require(instruction_map, 0x08008788, "movs"),
        "cursor_advance": _require(instruction_map, 0x0800878C, "adds"),
        "loop_exit": _require(instruction_map, 0x08008796, "bne"),
        "render_loop_terminator_load": _require(instruction_map, 0x08008950, "ldrb"),
        "render_loop_terminator_exit": _require(instruction_map, 0x08008954, "beq"),
        "mode_sign_extend": _require(instruction_map, 0x08008968, "asrs"),
        "mode_compare": _require(instruction_map, 0x0800896C, "cmp"),
        "mode_other_branch": _require(instruction_map, 0x0800896E, "bne"),
    }
    if _branch_target(gates["terminator_exit"]) != address(0x08008798):
        raise LayoutContractError("terminator exit target changed")
    if _branch_target(gates["narrow_branch"]) != address(0x08008788):
        raise LayoutContractError("narrow/wide branch target changed")
    if _branch_target(gates["loop_exit"]) != address(0x08008774):
        raise LayoutContractError("glyph loop target changed")
    if _branch_target(gates["render_loop_terminator_exit"]) != address(0x08008958):
        raise LayoutContractError("render loop exit target changed")
    if _branch_target(gates["mode_other_branch"]) != address(0x080089C6):
        raise LayoutContractError("mode branch target changed")

    direct_calls: Dict[str, int] = {}
    for instruction in instructions:
        if instruction.mnemonic == "bl" and instruction.operands:
            target = _branch_target(instruction)
            direct_calls[target] = direct_calls.get(target, 0) + 1
    code = rom[CONSUMER_START - ROM_BASE : CONSUMER_END - ROM_BASE]
    return {
        "consumer": address(CONSUMER_START),
        "code_end_exclusive": address(CONSUMER_END),
        "code_length": CONSUMER_LENGTH,
        "code_sha256": sha256(code),
        "terminator": {
            "token": "NUL",
            "source_byte_load": _instruction_metadata(gates["terminator_load"]),
            "compare": _instruction_metadata(gates["terminator_compare"]),
            "exit": _instruction_metadata(gates["terminator_exit"]),
            "exit_target": _branch_target(gates["terminator_exit"]),
            "render_loop_load": _instruction_metadata(gates["render_loop_terminator_load"]),
            "render_loop_exit": _instruction_metadata(gates["render_loop_terminator_exit"]),
            "render_loop_exit_target": _branch_target(gates["render_loop_terminator_exit"]),
        },
        "glyph_units": {
            "load": _instruction_metadata(gates["glyph_load"]),
            "verified_unit_bytes": 2,
            "cursor_advance_pixels": "8 for low-byte <= 0x87; 12 otherwise",
            "source_cursor_advance_bytes": 2,
            "narrow_branch": _instruction_metadata(gates["narrow_branch"]),
            "narrow_branch_target": _branch_target(gates["narrow_branch"]),
            "width_compare": _instruction_metadata(gates["width_compare"]),
            "wide_width_add": _instruction_metadata(gates["wide_width_add"]),
            "narrow_width_add": _instruction_metadata(gates["narrow_width_add"]),
            "loop_back": _instruction_metadata(gates["loop_exit"]),
            "loop_back_target": _branch_target(gates["loop_exit"]),
        },
        "line_layout": {
            "accumulator_register": "sl",
            "initial_value": 0,
            "tile_column_formula": "ceil(accumulated_pixel_width / 8)",
            "partial_tile_flag": "accumulated_pixel_width & 7 != 0",
            "allocation_unit": 64,
            "tile_row_bytes": 32,
            "glyph_render_rows": 12,
            "newline_branch": False,
            "speaker_field": "opaque; not named by this function",
            "branch_state": "opaque; mode field is only compared, not semantically named",
        },
        "final_mode_branch": {
            "sign_extend": _instruction_metadata(gates["mode_sign_extend"]),
            "compare": _instruction_metadata(gates["mode_compare"]),
            "equal_value": 1,
            "other_branch": _instruction_metadata(gates["mode_other_branch"]),
            "other_branch_target": _branch_target(gates["mode_other_branch"]),
            "equal_path": "bounded direct destination copy path",
            "other_path": "opaque helper path; no speaker/newline name assigned",
        },
        "direct_call_targets": dict(sorted(direct_calls.items())),
        "unknown_semantics": ["newline", "speaker", "branch mode meaning", "full multi-line policy"],
    }


def build_report(rom: bytes, source_records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    consumer = verify_consumer_contract(rom)
    boundary = build_boundary_audit(rom, source_records)
    # The boundary report intentionally contains no per-record source text;
    # only its safe layout aggregate is reused here.
    return {
        "schema": "super-robot-taisen-d-m111-layout-contract-v1",
        "game_code": "A6SJ",
        "consumer": consumer,
        "corpus": {
            "record_count": boundary["source_range"]["record_count"],
            "source_corpus_digest": boundary["source_range"]["source_corpus_digest"],
            "status_counts": boundary["tokenization"]["status_counts"],
            "contract_eligible_record_count": boundary["layout"]["contract_eligible_record_count"],
            "line_width": {
                "minimum_pixels": boundary["layout"]["line_width_minimum"],
                "maximum_pixels": boundary["layout"]["line_width_maximum"],
                "distinct_count": boundary["layout"]["line_width_distinct_count"],
                "maximum_observed_tile_columns": math.ceil(int(boundary["layout"]["line_width_maximum"]) / 8),
                "maximum_observed_tile_bytes": math.ceil(int(boundary["layout"]["line_width_maximum"]) / 8) * 64,
                "engine_limit_proven": False,
            },
        },
        "contract": {
            "terminator": "NUL",
            "glyph_unit_bytes": 2,
            "glyph_widths": {"narrow": 8, "wide": 12},
            "unknown_token_policy": "opaque and reject for translation",
            "newline_policy": "unconfirmed_opaque",
            "speaker_policy": "unconfirmed_opaque",
            "translation_started": False,
        },
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rom = args.rom.read_bytes()
    source_records = read_source_records(args.source_table)
    report = build_report(rom, source_records)
    write_report(args.output, report)
    print(
        f"m111_layout=accepted consumer={report['consumer']['consumer']} "
        f"records={report['corpus']['record_count']} "
        f"newline_branch={report['consumer']['line_layout']['newline_branch']} "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
