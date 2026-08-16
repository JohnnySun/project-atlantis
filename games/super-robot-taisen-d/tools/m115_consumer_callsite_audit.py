#!/usr/bin/env python3
"""Audit only direct references to the already known text consumer.

This is not a pointer-pool scan.  It disassembles the bounded executable
prefix before the verified static source pool and checks only for an immediate
Thumb BL/BLX target or a PC-relative literal containing the known consumer
address.  Register-indirect dispatch remains explicitly unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

import capstone

from m17_layout import ROM_BASE


CONSUMER = 0x08008724
EXECUTABLE_END_OFFSET = 0x076000
EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"


class CallsiteAuditReject(ValueError):
    """The bounded known-target audit rejected its input."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def address(value: int) -> str:
    return f"0x{value:08X}"


def direct_call_candidates(rom: bytes) -> List[Dict[str, Any]]:
    end = EXECUTABLE_END_OFFSET
    if end > len(rom):
        raise CallsiteAuditReject("bounded_executable_range_outside_rom")
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    candidates: List[Dict[str, Any]] = []
    for instruction in md.disasm(rom[:end], ROM_BASE):
        if instruction.mnemonic not in {"bl", "blx"} or not instruction.operands:
            continue
        operand = instruction.operands[0]
        if operand.type == capstone.CS_OP_IMM and int(operand.imm) in {CONSUMER, CONSUMER | 1}:
            candidates.append(
                {
                    "kind": "direct_branch",
                    "instruction": address(int(instruction.address)),
                    "mnemonic": instruction.mnemonic,
                    "target": address(int(operand.imm)),
                }
            )
    return candidates


def pc_literal_candidates(rom: bytes) -> List[Dict[str, Any]]:
    end = EXECUTABLE_END_OFFSET
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    candidates: List[Dict[str, Any]] = []
    for instruction in md.disasm(rom[:end], ROM_BASE):
        if instruction.mnemonic != "ldr" or len(instruction.operands) < 2:
            continue
        memory = instruction.operands[1]
        if memory.type != capstone.CS_OP_MEM or memory.mem.base != capstone.arm.ARM_REG_PC:
            continue
        literal_address = ((int(instruction.address) + 4) & ~3) + int(memory.mem.disp)
        file_offset = literal_address - ROM_BASE
        if not 0 <= file_offset <= len(rom) - 4:
            continue
        value = int.from_bytes(rom[file_offset : file_offset + 4], "little")
        if value in {CONSUMER, CONSUMER | 1}:
            candidates.append(
                {
                    "kind": "pc_relative_literal",
                    "instruction": address(int(instruction.address)),
                    "literal_address": address(literal_address),
                    "target": address(value),
                }
            )
    return candidates


def build_report(rom: bytes) -> Dict[str, Any]:
    rom_hash = sha256(rom)
    if rom_hash != EXPECTED_ROM_SHA256:
        raise CallsiteAuditReject("rom_hash_mismatch")
    executable = rom[:EXECUTABLE_END_OFFSET]
    direct = direct_call_candidates(rom)
    literals = pc_literal_candidates(rom)
    return {
        "schema": "super-robot-taisen-d-m115-known-consumer-callsite-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "source_safe_hashes_only": True},
        "rom": {"sha256": rom_hash, "expected_sha256": EXPECTED_ROM_SHA256, "hash_match": True},
        "bounded_range": {
            "start": address(ROM_BASE),
            "end_exclusive": address(ROM_BASE + EXECUTABLE_END_OFFSET),
            "length": EXECUTABLE_END_OFFSET,
            "sha256": sha256(executable),
        },
        "target": {"consumer": address(CONSUMER), "target_forms_checked": ["thumb_bl_immediate", "thumb_blx_immediate", "pc_relative_literal"]},
        "direct_call_candidates": direct,
        "pc_relative_literal_candidates": literals,
        "gate": {
            "rom_hash_match": True,
            "direct_call_candidate_count": len(direct),
            "pc_relative_literal_candidate_count": len(literals),
            "known_consumer_direct_reference_found": bool(direct or literals),
            "indirect_register_dispatch": "unresolved",
            "runtime_caller_required": not bool(direct or literals),
            "translation_started": False,
        },
        "next_condition": "runtime entry breakpoint must capture LR/callsite and r0 source pointer before semantic labels",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.rom.read_bytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, CallsiteAuditReject, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"m115_consumer_callsite_rejected={exc}")
        return 2
    print(
        "m115_consumer_callsite=accepted direct={} literals={} runtime_required={}".format(
            report["gate"]["direct_call_candidate_count"],
            report["gate"]["pc_relative_literal_candidate_count"],
            report["gate"]["runtime_caller_required"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
