#!/usr/bin/env python3
"""Cross-reference FE6 loader candidates with bounded static caller gates.

M1.11 is intentionally static.  It joins the proven 163 loader callsites
with the two non-selector candidate functions identified in M1.8/M1.9 and
records only function spans, BL targets, memory-operation classes, and
register-source clues.  It never assigns a scene/category from address
proximity and never emits ROM bytes or text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from trace_m18_callers import (  # noqa: E402
    LOADER_ENTRY,
    ROM_BASE,
    ROM_SIZE,
    _capstone_instructions,
    _classify_index_source,
    _function_for_call,
    identity,
    is_rom_pointer,
    prologue_addresses,
    return_addresses,
    scan_direct_calls,
    hex32,
)


PRIMARY_CALLER = 0x080985D8
PRIMARY_LOADER_CALL = 0x080985EC
ALTERNATE_CALLER = 0x08098624
ALTERNATE_LOADER_CALLS = (0x0809867A, 0x08098694)
SELECTOR_CALLER = 0x08098AFC
SELECTOR_LOADER_CALL = 0x08098B10

# These are callback addresses observed in the ROM's dispatch-like data near
# file offsets 0x691200..0x691368.  The Thumb bit is part of the stored
# function pointer; the report records the surrounding word classes but never
# treats the table as a scene/category map without a runtime receipt.
DISPATCH_POINTER_TARGETS = {
    0x08098340: "alternate_caller",
    0x080984A8: "primary_caller_high_group",
}


def _instruction_text(row: dict[str, object]) -> str:
    return f"{hex32(int(row['address']))}: {row['mnemonic']} {row['op_str']}".rstrip()


def _bl_target(op_str: str) -> str | None:
    if "#" not in op_str:
        return None
    candidate = op_str.rsplit("#", 1)[1].strip()
    try:
        return hex32(int(candidate, 0))
    except ValueError:
        return None


def _function_gate_row(
    rom: bytes,
    callsite: int,
    prologues: list[int],
    returns: list[int],
    *,
    target: int,
) -> dict[str, object]:
    bounds = _function_for_call(callsite, prologues, returns)
    start_value = bounds.get("function_start")
    return_value = bounds.get("function_return")
    instructions: list[dict[str, object]] = []
    if isinstance(start_value, str) and isinstance(return_value, str):
        start = int(start_value, 16)
        end = int(return_value, 16) + 2
        instructions = _capstone_instructions(rom, start, end)
    selected = [
        _instruction_text(row)
        for row in instructions
        if str(row["mnemonic"]) in {
            "bl", "ldr", "ldrh", "ldrb", "ldrsb", "str", "strh",
            "cmp", "tst", "bne", "beq", "ble", "blt", "bgt",
        }
    ]
    bl_targets = sorted(
        target_value
        for target_value in (
            _bl_target(str(row["op_str"]))
            for row in instructions
            if row["mnemonic"] == "bl"
        )
        if target_value is not None
    )
    return {
        "callsite": hex32(callsite),
        "target_function": hex32(target),
        "function_start": start_value,
        "function_return": return_value,
        "function_boundary_confidence": bounds["function_boundary_confidence"],
        "index_source_class": _classify_index_source(selected),
        "direct_bl_targets": bl_targets,
        "bounded_memory_and_branch_ops": selected[:96],
    }


def _target_rows(rom: bytes, target: int) -> list[dict[str, object]]:
    prologues = prologue_addresses(rom)
    returns = return_addresses(rom, ROM_BASE, ROM_BASE + len(rom))
    return [
        _function_gate_row(rom, callsite, prologues, returns, target=target)
        for callsite in scan_direct_calls(rom, target)
    ]


def _word_class(value: int) -> str:
    if is_rom_pointer(value):
        return "rom_pointer"
    if value == 0:
        return "zero"
    return "scalar"


def _dispatch_pointer_hits(rom: bytes) -> list[dict[str, object]]:
    """Find aligned Thumb callback pointers and bounded scalar neighbors.

    This is deliberately a structural census, not a parser for the unknown
    table.  A small word window is enough to make the candidate dispatch
    provenance reproducible while avoiding emission of arbitrary ROM text.
    """

    hits: list[dict[str, object]] = []
    wanted = {target | 1: (target, role) for target, role in DISPATCH_POINTER_TARGETS.items()}
    for offset in range(0, len(rom) - 3, 4):
        value = int.from_bytes(rom[offset:offset + 4], "little")
        match = wanted.get(value)
        if match is None:
            continue
        target, role = match
        window_start = max(0, offset - 16)
        window_end = min(len(rom), offset + 20)
        neighbors = []
        for neighbor_offset in range(window_start, window_end, 4):
            neighbor = int.from_bytes(rom[neighbor_offset:neighbor_offset + 4], "little")
            neighbors.append({
                "file_offset": f"0x{neighbor_offset:06x}",
                "value": hex32(neighbor),
                "class": _word_class(neighbor),
            })
        hits.append({
            "file_offset": f"0x{offset:06x}",
            "gba_address": hex32(ROM_BASE + offset),
            "stored_thumb_pointer": hex32(value),
            "target_function": hex32(target),
            "role": role,
            "neighbor_words": neighbors,
        })
    return hits


def _candidate_loader_calls(
    rom: bytes,
    function_start: str,
) -> list[str]:
    prologues = prologue_addresses(rom)
    returns = return_addresses(rom, ROM_BASE, ROM_BASE + len(rom))
    result: list[str] = []
    for callsite in scan_direct_calls(rom, LOADER_ENTRY):
        bounds = _function_for_call(callsite, prologues, returns)
        if bounds.get("function_start") == function_start:
            result.append(hex32(callsite))
    return result


def build_report(rom_path: Path) -> dict[str, object]:
    rom = rom_path.read_bytes()
    rom_identity = identity(rom_path)
    primary_key = hex32(PRIMARY_CALLER)
    alternate_key = hex32(ALTERNATE_CALLER)
    selector_key = hex32(SELECTOR_CALLER)
    return {
        "schema": "afej-m111-static-gate-report-v1",
        "rom": rom_identity,
        "loader": {
            "entry": hex32(LOADER_ENTRY),
            "direct_callsite_count": len(scan_direct_calls(rom, LOADER_ENTRY)),
        },
        "candidate_functions": {
            primary_key: {
                "role": "non_selector_loader_caller_candidate",
                "loader_callsites": _candidate_loader_calls(rom, primary_key),
                "direct_callers": _target_rows(rom, PRIMARY_CALLER),
            },
            alternate_key: {
                "role": "alternate_non_selector_loader_caller_candidate",
                "loader_callsites": _candidate_loader_calls(rom, alternate_key),
                "direct_callers": _target_rows(rom, ALTERNATE_CALLER),
            },
            selector_key: {
                "role": "known_selector_reference",
                "loader_callsites": _candidate_loader_calls(rom, selector_key),
                "direct_callers": _target_rows(rom, SELECTOR_CALLER),
            },
        },
        "dispatch_pointer_candidates": _dispatch_pointer_hits(rom),
        "semantic_boundary": {
            "scene_or_content_category": "not_inferred_from_static_gate",
            "natural_reachability": "requires_runtime_receipt",
            "unicode_or_codepage": "not_inferred",
            "source_bytes_emitted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(args.rom)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"output={args.output}")
    print(f"loader_direct_calls={report['loader']['direct_callsite_count']}")
    for key, value in report["candidate_functions"].items():
        print(f"{key}_direct_callers={len(value['direct_callers'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
