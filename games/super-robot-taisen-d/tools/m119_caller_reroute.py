#!/usr/bin/env python3
"""Join one natural consumer hit with its bounded static Thumb callsite.

M1.15's original stream scan stopped at the first undecodable ROM gap.  The
known-target audit now resumes with Capstone skipdata, while this tool stays
bounded to the callsite observed by the fresh mGBA/GDB probe.  It records only
instruction metadata, hashes, registers, and address classifications; it does
not emit the RAM buffer or source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import capstone

from m115_consumer_callsite_audit import (
    CONSUMER,
    EXPECTED_ROM_SHA256,
    direct_call_candidates,
)


PATCHED_ROM_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
ROM_BASE = 0x08000000
EXPECTED_TARGET_POINTER = 0x08080858


class CallerRerouteReject(ValueError):
    """A caller/callsite join invariant failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def address(value: int) -> str:
    return f"0x{value:08X}"


def integer(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


CALLSITE_SPECS: Dict[int, Dict[str, Any]] = {
    0x08066050: {
        "window_start": 0x08066040,
        "window_end_exclusive": 0x08066054,
        "argument_origin": {
            "r0": "r7",
            "r1": "r5_plus_0x400",
            "r2": "constant_0x0D",
            "r3": "constant_0x05",
            "stack_arg_0": "constant_0x01",
        },
        "expected": {
            0x08066040: ("movs", "r1, #0x80"),
            0x08066042: ("lsls", "r1, r1, #3"),
            0x08066044: ("adds", "r1, r5, r1"),
            0x08066046: ("movs", "r4, #1"),
            0x08066048: ("str", "r4, [sp]"),
            0x0806604A: ("adds", "r0, r7, #0"),
            0x0806604C: ("movs", "r2, #0xd"),
            0x0806604E: ("movs", "r3, #5"),
            0x08066050: ("bl", "#0x8008724"),
        },
    },
    0x08066062: {
        "window_start": 0x08066054,
        "window_end_exclusive": 0x08066066,
        "argument_origin": {
            "r0": "r8",
            "r1": "r5_plus_0xC00",
            "r2": "constant_0x0D",
            "r3": "constant_0x06",
            "stack_arg_0": "constant_0x01",
        },
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
}


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise CallerRerouteReject("probe_report_not_object")
    return value


def _disassemble_window(rom: bytes, start: int, end: int) -> list[Any]:
    start_offset = start - ROM_BASE
    end_offset = end - ROM_BASE
    if start_offset < 0 or end_offset > len(rom) or start_offset >= end_offset:
        raise CallerRerouteReject("callsite_window_outside_rom")
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    instructions = list(md.disasm(rom[start_offset:end_offset], start))
    if not instructions:
        raise CallerRerouteReject("callsite_window_disassembly_empty")
    return instructions


def verify_static_callsite(rom: bytes, callsite: int) -> Dict[str, Any]:
    candidates = direct_call_candidates(rom)
    candidate = next(
        (
            item
            for item in candidates
            if integer(item["instruction"]) == callsite and integer(item["target"]) == CONSUMER
        ),
        None,
    )
    spec = CALLSITE_SPECS.get(callsite)
    if candidate is None:
        return {
            "status": "not_a_bounded_direct_candidate",
            "candidate_count": len(candidates),
            "candidate_instruction_hash": sha256(
                ",".join(item["instruction"] for item in candidates).encode("ascii")
            ),
        }
    result: Dict[str, Any] = {
        "status": "direct_consumer_candidate",
        "candidate_count": len(candidates),
        "candidate_instruction_hash": sha256(
            ",".join(item["instruction"] for item in candidates).encode("ascii")
        ),
        "instruction": candidate["instruction"],
        "target": candidate["target"],
    }
    if spec is None:
        result["argument_setup_status"] = "not_decoded_for_this_callsite"
        return result
    instructions = _disassemble_window(rom, spec["window_start"], spec["window_end_exclusive"])
    actual = {int(instruction.address): (instruction.mnemonic, instruction.op_str) for instruction in instructions}
    mismatches = []
    for pc, expected in spec["expected"].items():
        if actual.get(pc) != expected:
            mismatches.append(
                {
                    "pc": address(pc),
                    "expected_mnemonic": expected[0],
                    "expected_operands": expected[1],
                    "actual": actual.get(pc),
                }
            )
    window_start = spec["window_start"]
    window_end = spec["window_end_exclusive"]
    result.update(
        {
            "argument_setup_status": "verified" if not mismatches else "mismatch",
            "argument_origin": spec["argument_origin"],
            "instruction_window": {
                "start": address(window_start),
                "end_exclusive": address(window_end),
                "length": window_end - window_start,
                "sha256": sha256(rom[window_start - ROM_BASE : window_end - ROM_BASE]),
                "instruction_count": len(instructions),
                "instruction_pcs_sha256": sha256(
                    ",".join(address(int(instruction.address)) for instruction in instructions).encode("ascii")
                ),
            },
            "mismatches": mismatches,
        }
    )
    return result


def build_report(rom: bytes, probe: Mapping[str, Any]) -> Dict[str, Any]:
    rom_hash = sha256(rom)
    if rom_hash != PATCHED_ROM_SHA256:
        raise CallerRerouteReject("patched_rom_hash_mismatch")
    caller = probe.get("caller")
    initializer = probe.get("initializer")
    gdb = probe.get("gdb")
    if not isinstance(caller, Mapping) or not isinstance(initializer, Mapping) or not isinstance(gdb, Mapping):
        raise CallerRerouteReject("caller_probe_shape_invalid")
    callsite = integer(caller.get("caller_callsite", 0))
    static = verify_static_callsite(rom, callsite)
    source_pointer = integer(caller.get("source_pointer", 0))
    target_pointer = integer(caller.get("target_pointer", EXPECTED_TARGET_POINTER))
    target_match = caller.get("target_pointer_match") is True
    runtime_entry = caller.get("status") == "consumer_entry_observed"
    base_guard = initializer.get("nonzero_base_guard") is True
    static_match = static.get("status") == "direct_consumer_candidate"
    setup_verified = static.get("argument_setup_status") == "verified"
    return {
        "schema": "super-robot-taisen-d-m119-caller-reroute-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "raw_memory_emitted": False},
        "rom": {"sha256": rom_hash, "expected_sha256": PATCHED_ROM_SHA256, "hash_match": True},
        "gdb": {
            "port": gdb.get("port"),
            "single_connection": gdb.get("single_connection") is True,
            "fresh_process_required": gdb.get("fresh_process_required") is True,
            "window_seconds": gdb.get("window_seconds"),
        },
        "initializer": {
            "nonzero_base_guard": base_guard,
            "slot_values": initializer.get("slot_values"),
        },
        "runtime_caller": {
            "consumer": caller.get("consumer_pc"),
            "status": caller.get("status"),
            "caller_callsite": address(callsite),
            "lr": caller.get("lr"),
            "registers": caller.get("registers"),
            "source_pointer": address(source_pointer),
            "source_pointer_region": caller.get("source_pointer_region"),
            "target_pointer": address(target_pointer),
            "target_pointer_match": target_match,
        },
        "static_callsite": static,
        "gate": {
            "rom_hash_match": True,
            "font_base_nonzero": base_guard,
            "natural_consumer_entry_observed": runtime_entry,
            "known_direct_callsite_static_match": static_match,
            "argument_setup_verified": setup_verified,
            "ram_buffer_consumer_observed": runtime_entry and caller.get("source_pointer_region") == "ram_or_io",
            "target_pointer_match": target_match,
            "target_render_proven": False,
            "natural_screen_proven": False,
            "translation_status": "ai_draft",
        },
        "next_condition": (
            "capture target caller/index or the producer of the RAM buffer before any target render proof"
            if not target_match
            else "capture codepage, glyph, tile-writer, and screen evidence for the matched target pointer"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--caller-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.rom.read_bytes(), read_json(args.caller_report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, CallerRerouteReject, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m119_caller_reroute_rejected={exc}")
        return 2
    print(
        "m119_caller_reroute=accepted callsite={} static_match={} target_match={}".format(
            report["runtime_caller"]["caller_callsite"],
            report["gate"]["known_direct_callsite_static_match"],
            report["gate"]["target_pointer_match"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
