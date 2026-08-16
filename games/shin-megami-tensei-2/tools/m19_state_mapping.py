#!/usr/bin/env python3
"""Bounded A5TJ selector initializer/source-state mapping.

This is a static follow-up to M1.8.  It follows only the four selector-table
writer candidates already identified there, their Thumb BL callers, and up to
three caller layers.  The report contains addresses, instruction forms,
register provenance classes, function hashes, lengths, and counts.  It never
emits instruction bytes, ROM/RAM payloads, complete strings, glyph patterns,
or a translation source table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


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
    read_u32,
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)
from m18_initializer_probe import (  # noqa: E402
    _decode_thumb_store,
    _rom_offset,
)


SCHEMA = "smt2.m1.9.static-state-mapping.v1"

SELECTOR_TABLE_GLOBAL = 0x03006950
SELECTOR_SAVED_GLOBAL = 0x030068C0
SELECTOR_COPY_SOURCE = 0x030066B0
SELECTOR_COPY_DESTINATION = 0x03005CA8
SELECTOR_COUNTER_GLOBAL = 0x0203DB40
ROM_SELECTOR_LITERAL = 0x08036666
RESOURCE_TABLE_LITERAL = 0x08791BDC

# These are the four priority functions from M1.8.  The first three are the
# selector-table writer candidates named in the roadmap; the fourth is the
# helper which restores the saved RAM table pointer.
SEED_FUNCTIONS = (
    0x0812F2B4,
    0x0813E184,
    0x0813E428,
    0x0813E574,
)

TRACKED_LITERALS = (
    SELECTOR_TABLE_GLOBAL,
    SELECTOR_SAVED_GLOBAL,
    SELECTOR_COPY_SOURCE,
    SELECTOR_COPY_DESTINATION,
    SELECTOR_COUNTER_GLOBAL,
    ROM_SELECTOR_LITERAL,
    RESOURCE_TABLE_LITERAL,
)

MAX_FUNCTION_BACKSCAN = 0x400
FUNCTION_HASH_LENGTH = 0x100
MAX_CALLERS_PER_TARGET = 48
MAX_CALLER_LAYERS = 3
ARGUMENT_CONTEXT_INSTRUCTIONS = 12


def _address_class(value: int) -> str:
    if ROM_BASE <= value < ROM_LIMIT:
        return "rom_pointer"
    if 0x02000000 <= value < 0x02040000:
        return "ewram_address"
    if 0x03000000 <= value < 0x03008000:
        return "iwram_address"
    if 0x04000000 <= value < 0x04000400:
        return "io_address"
    if 0x05000000 <= value < 0x05000400:
        return "palette_address"
    if 0x06000000 <= value < 0x06018000:
        return "vram_address"
    if 0x07000000 <= value < 0x07000400:
        return "oam_address"
    return "constant"


def _value_metadata(value: int, rom_size: int) -> dict[str, object]:
    return {
        **address_metadata(value, rom_size),
        "class": _address_class(value),
    }


def _function_start(data: bytes, address: int) -> int | None:
    """Find a bounded Thumb push-with-LR prologue before an address."""
    if _rom_offset(address) is None:
        return None
    lower = max(ROM_BASE, address - MAX_FUNCTION_BACKSCAN)
    for candidate in range(address & ~1, lower - 2, -2):
        halfword = read_u16(data, candidate)
        if halfword & 0xFF00 == 0xB500:
            return candidate
    return None


def _return_candidates(data: bytes, start: int | None) -> list[str]:
    if start is None or _rom_offset(start) is None:
        return []
    end = min(ROM_BASE + len(data), start + 0x300)
    result: list[str] = []
    for address in range(start, end - 1, 2):
        # BX any register is used by the game's epilogues after POPs.  The
        # mask keeps this a Thumb high-register BX check, not a raw byte scan.
        if read_u16(data, address) & 0xFF87 == 0x4700:
            result.append(hex_address(address))
            if len(result) >= 8:
                break
    return result


def _function_end(data: bytes, start: int | None) -> int:
    """Return a conservative first Thumb BX epilogue boundary."""
    if start is None or _rom_offset(start) is None:
        return ROM_BASE
    end = min(ROM_BASE + len(data), start + 0x500)
    for address in range(start + 0x20, end - 1, 2):
        if read_u16(data, address) & 0xFF87 == 0x4700:
            return address + 2
    return min(end, start + 0x300)


def _function_metadata(data: bytes, start: int | None) -> dict[str, object] | None:
    if start is None or _rom_offset(start) is None:
        return None
    window = data[start - ROM_BASE : min(len(data), start - ROM_BASE + FUNCTION_HASH_LENGTH)]
    return {
        "entry": address_metadata(start, len(data)),
        "thumb": True,
        "prologue_halfword": hex_address(read_u16(data, start)),
        "window_length": len(window),
        "window_hash": sha256(window),
        "return_candidates": _return_candidates(data, start),
    }


def _literal_ref_index(data: bytes, values: Iterable[int]) -> dict[int, list[dict[str, object]]]:
    wanted = set(values)
    result: dict[int, list[dict[str, object]]] = {value: [] for value in wanted}
    for offset in range(0, max(0, len(data) - 1), 2):
        instruction_address = ROM_BASE + offset
        try:
            item = thumb_literal_load(data, instruction_address)
        except (ValueError, IndexError):
            continue
        value = int(str(item["value"]), 16)
        if value not in wanted:
            continue
        result[value].append(
            {
                "instruction": hex_address(instruction_address),
                "literal_address": item["literal_address"],
                "register": item["register"],
                "value": _value_metadata(value, len(data)),
            }
        )
    return result


def _decode_simple(data: bytes, address: int) -> dict[str, object] | None:
    """Decode only Thumb-1 forms needed for bounded argument provenance."""
    instruction = read_u16(data, address)
    if instruction & 0xF800 == 0x2000:
        return {"form": "movs_imm", "destination": (instruction >> 8) & 7, "immediate": instruction & 0xFF}
    if instruction & 0xF800 in (0x3000, 0x3800):
        return {
            "form": "adds_imm" if instruction & 0x0800 == 0 else "subs_imm",
            "destination": (instruction >> 8) & 7,
            "source": (instruction >> 8) & 7,
            "immediate": instruction & 0xFF,
        }
    if instruction & 0xF800 == 0x1800 and instruction & 0x0600 == 0x0400:
        return {
            "form": "adds_imm3" if instruction & 0x0200 == 0 else "subs_imm3",
            "destination": instruction & 7,
            "source": (instruction >> 3) & 7,
            "immediate": (instruction >> 6) & 7,
        }
    if instruction & 0xF800 == 0x1800:
        return {
            "form": "addsub_reg",
            "destination": instruction & 7,
            "source": (instruction >> 3) & 7,
            "offset_register": (instruction >> 6) & 7,
        }
    if instruction & 0xF800 in (0x0000, 0x0800, 0x1000):
        return {
            "form": {0x0000: "lsls_imm", 0x0800: "lsrs_imm", 0x1000: "asrs_imm"}[instruction & 0xF800],
            "destination": instruction & 7,
            "source": (instruction >> 3) & 7,
            "immediate": (instruction >> 6) & 0x1F,
        }
    if instruction & 0xF800 == 0x6800:
        return {
            "form": "ldr_word_imm",
            "destination": instruction & 7,
            "base": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 4,
        }
    if instruction & 0xF800 == 0x7800:
        return {
            "form": "ldr_byte_imm",
            "destination": instruction & 7,
            "base": (instruction >> 3) & 7,
            "offset": (instruction >> 6) & 0x1F,
        }
    if instruction & 0xF800 == 0x8800:
        return {
            "form": "ldr_halfword_imm",
            "destination": instruction & 7,
            "base": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 2,
        }
    if instruction & 0xFF00 == 0x4600:
        # Thumb high-register MOV: Rm is bits 6:3 and Rd is bits 7:4 plus
        # the low register bits.  This is needed for r8/r9 saved pointers.
        return {
            "form": "mov_reg",
            "destination": ((instruction >> 4) & 8) | (instruction & 7),
            "source": (instruction >> 3) & 0xF,
        }
    if instruction & 0xFF00 == 0x4400:
        operation = (instruction >> 8) & 3
        if operation == 0:
            return {
                "form": "add_reg_high",
                "destination": ((instruction >> 4) & 8) | (instruction & 7),
                "source": (instruction >> 3) & 0xF,
            }
        if operation == 2:
            return {
                "form": "mov_reg_high",
                "destination": ((instruction >> 4) & 8) | (instruction & 7),
                "source": (instruction >> 3) & 0xF,
            }
    if instruction & 0xF800 == 0xF000:
        target = thumb_bl_target(data, address)
        if target is not None:
            return {"form": "bl", "target": hex_address(target)}
    store = _decode_thumb_store(data, address)
    if store is not None:
        return {
            "form": str(store["form"]),
            "source": int(store["source_register"]),
            "base": int(store["base_register"]),
            "offset": int(store.get("offset", 0)),
            "width": int(store["width"]),
        }
    return None


def _unknown(reason: str = "unknown") -> dict[str, object]:
    return {"kind": "unknown", "reason": reason}


def _initial_registers() -> dict[int, dict[str, object]]:
    # Keep high registers because these routines park the selector pointer in
    # r8/r9 and use them again immediately before the store.
    return {index: {"kind": "incoming_register", "register": f"r{index}"} for index in range(16)}


def _copy_provenance(item: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(item))


def _apply_instruction(
    data: bytes,
    address: int,
    registers: dict[int, dict[str, object]],
) -> dict[str, object] | None:
    literal = None
    try:
        literal = thumb_literal_load(data, address)
    except (ValueError, IndexError):
        pass
    if literal is not None:
        destination = int(literal["register"])
        value = int(str(literal["value"]), 16)
        registers[destination] = {
            "kind": "literal_address",
            "value": _value_metadata(value, len(data)),
        }
        return {
            "form": "ldr_literal",
            "destination": destination,
            "literal": _value_metadata(value, len(data)),
        }
    decoded = _decode_simple(data, address)
    if decoded is None:
        return None
    form = decoded["form"]
    destination = decoded.get("destination")
    source = decoded.get("source")
    if form == "movs_imm":
        registers[int(destination)] = {"kind": "constant", "value": int(decoded["immediate"])}
    elif form in {"mov_reg", "mov_reg_high", "add_reg_high"} and source is not None and destination is not None:
        registers[int(destination)] = _copy_provenance(registers[int(source)])
    elif form in {"adds_imm", "subs_imm", "adds_imm3", "subs_imm3"} and destination is not None:
        prior = _copy_provenance(registers[int(destination)])
        if form in {"adds_imm3", "subs_imm3"} and source is not None:
            prior = _copy_provenance(registers[int(source)])
        immediate = int(decoded["immediate"])
        if form in {"adds_imm3", "subs_imm3"} and immediate == 0 and source is not None:
            registers[int(destination)] = prior
            return decoded
        registers[int(destination)] = {
            "kind": "derived",
            "operation": "add" if form in {"adds_imm", "adds_imm3"} else "sub",
            "input": prior,
            "immediate": immediate,
        }
    elif form == "addsub_reg" and destination is not None and source is not None:
        registers[int(destination)] = {
            "kind": "derived",
            "operation": "addsub_reg",
            "left": _copy_provenance(registers[int(source)]),
            "right": _copy_provenance(registers[int(decoded["offset_register"])]),
        }
    elif form in {"lsls_imm", "lsrs_imm", "asrs_imm"} and destination is not None and source is not None:
        registers[int(destination)] = {
            "kind": "derived",
            "operation": str(form),
            "input": _copy_provenance(registers[int(source)]),
            "immediate": int(decoded["immediate"]),
        }
    elif form in {"ldr_word_imm", "ldr_halfword_imm", "ldr_byte_imm"} and destination is not None:
        base = int(decoded["base"])
        registers[int(destination)] = {
            "kind": "runtime_load",
            "base_register": f"r{base}",
            "base": _copy_provenance(registers[base]),
            "offset": int(decoded["offset"]),
            "width": {"ldr_word_imm": 4, "ldr_halfword_imm": 2, "ldr_byte_imm": 1}[str(form)],
        }
    elif form == "bl":
        registers[0] = _unknown("subroutine_return")
    return decoded


def _provenance_before(data: bytes, start: int | None, stop_address: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    registers = _initial_registers()
    context: list[dict[str, object]] = []
    if start is None or _rom_offset(start) is None or stop_address <= start:
        return registers, context
    lower = max(start, stop_address - 0x300)
    for address in range(lower & ~1, stop_address, 2):
        try:
            decoded = _apply_instruction(data, address, registers)
        except (ValueError, IndexError):
            continue
        if decoded is not None:
            decoded = {"address": hex_address(address), **decoded}
            context.append(decoded)
    return registers, context[-ARGUMENT_CONTEXT_INSTRUCTIONS:]


def _store_edges_for_function(
    data: bytes,
    start: int,
    literal_refs: dict[int, list[dict[str, object]]],
) -> list[dict[str, object]]:
    edges: list[dict[str, object]] = []
    end = _function_end(data, start)
    tracked_by_instruction: dict[int, tuple[int, int]] = {}
    for value, refs in literal_refs.items():
        for ref in refs:
            instruction = int(str(ref["instruction"]), 16)
            if start <= instruction < end:
                tracked_by_instruction[instruction] = (int(ref["register"]), value)
    for load_address, (base_register, target_global) in sorted(tracked_by_instruction.items()):
        for offset in range(2, 0x22, 2):
            store_address = load_address + offset
            if store_address >= end:
                break
            store = _decode_thumb_store(data, store_address)
            if store is None or int(store["base_register"]) != base_register:
                continue
            registers, context = _provenance_before(data, start, store_address)
            source_register = int(store["source_register"])
            edges.append(
                {
                    "target_global": _value_metadata(target_global, len(data)),
                    "literal_load": hex_address(load_address),
                    "store_pc": hex_address(store_address),
                    "watch_stop_pc": hex_address(store_address + 2),
                    "width": int(store["width"]),
                    "form": store["form"],
                    "base_register": f"r{base_register}",
                    "source_register": f"r{source_register}",
                    "source_provenance": registers[source_register],
                    "context_count": len(context),
                    "context_forms": [
                        {key: value for key, value in item.items() if key in {"address", "form", "destination", "source", "base", "target"}}
                        for item in context
                    ],
                }
            )
            break
    return edges


def _global_store_edges(
    data: bytes,
    start: int,
    literal_refs: dict[int, list[dict[str, object]]],
) -> list[dict[str, object]]:
    return _store_edges_for_function(data, start, literal_refs)


def _bounded_copy_contract(data: bytes, start: int) -> dict[str, object] | None:
    """Describe the one verified byte-copy loop without exposing its bytes."""
    if start != 0x0813E574:
        return None
    loop_start = 0x0813E59A
    loop_end = 0x0813E5AA
    if _rom_offset(loop_end) is None:
        return None
    loop = data[loop_start - ROM_BASE : loop_end - ROM_BASE]
    return {
        "source": _value_metadata(SELECTOR_COPY_SOURCE, len(data)),
        "destination": _value_metadata(SELECTOR_COPY_DESTINATION, len(data)),
        "length": 0x167,
        "unit_width": 1,
        "loop_pc": hex_address(loop_start),
        "loop_length": len(loop),
        "loop_hash": sha256(loop),
        "transform": "byte_copy_indexed_loop",
    }


def _argument_mapping(data: bytes, callsite: int, function_start: int | None) -> dict[str, object]:
    registers, context = _provenance_before(data, function_start, callsite)
    return {
        "callsite": hex_address(callsite),
        "caller_function": _function_metadata(data, function_start),
        "linear_provisional": True,
        "registers_at_call": {f"r{index}": registers[index] for index in range(4)},
        "context_count": len(context),
        "context_forms": [
            {key: value for key, value in item.items() if key in {"address", "form", "destination", "source", "base", "target", "literal"}}
            for item in context
        ],
    }


def _bl_index(data: bytes) -> dict[int, list[int]]:
    index: dict[int, list[int]] = {}
    for offset in range(0, max(0, len(data) - 3), 2):
        address = ROM_BASE + offset
        try:
            target = thumb_bl_target(data, address)
        except (ValueError, IndexError):
            continue
        if target is None:
            continue
        callers = index.setdefault(target, [])
        if len(callers) < MAX_CALLERS_PER_TARGET:
            callers.append(address)
    return index


def _caller_layers(data: bytes, seed: int, bl_index: dict[int, list[int]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    frontier = [seed]
    seen_functions = {seed}
    for depth in range(1, MAX_CALLER_LAYERS + 1):
        next_frontier: list[int] = []
        for target in frontier:
            for callsite in bl_index.get(target, []):
                caller = _function_start(data, callsite)
                item: dict[str, object] = {
                    "depth": depth,
                    "target_function": address_metadata(target, len(data)),
                    "callsite": hex_address(callsite),
                    "thumb_boundary_valid": caller is not None,
                    "caller_function": _function_metadata(data, caller),
                    "argument_mapping": _argument_mapping(data, callsite, caller),
                }
                result.append(item)
                if caller is not None and caller not in seen_functions:
                    seen_functions.add(caller)
                    next_frontier.append(caller)
        frontier = next_frontier
        if not frontier:
            break
    return result


def _seed_summary(
    data: bytes,
    seed: int,
    bl_index: dict[int, list[int]],
    literal_refs: dict[int, list[dict[str, object]]],
) -> dict[str, object]:
    function = _function_metadata(data, seed)
    local_refs = []
    for value, refs in literal_refs.items():
        for ref in refs:
            instruction = int(str(ref["instruction"]), 16)
            if seed <= instruction < seed + 0x300:
                local_refs.append(ref)
    return {
        "function": function,
        "literal_pool_refs": local_refs,
        "selector_global_store_edges": _global_store_edges(data, seed, literal_refs),
        "bounded_copy_contract": _bounded_copy_contract(data, seed),
        "direct_caller_count": len(bl_index.get(seed, [])),
        "direct_callers": _caller_layers(data, seed, bl_index),
    }


def static_report(data: bytes) -> dict[str, object]:
    literal_refs = _literal_ref_index(data, TRACKED_LITERALS)
    bl_index = _bl_index(data)
    seeds = [_seed_summary(data, seed, bl_index, literal_refs) for seed in SEED_FUNCTIONS]
    ref_function_counts: dict[str, int] = {}
    for value, refs in literal_refs.items():
        ref_function_counts[hex_address(value)] = len({_function_start(data, int(str(ref["instruction"]), 16)) for ref in refs})
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "tracked selector globals, bounded Thumb literal/store decoding, and BL caller graph",
            "glyph_pattern_scan": False,
            "source_table_created": False,
            "max_caller_layers": MAX_CALLER_LAYERS,
            "function_window_length": FUNCTION_HASH_LENGTH,
        },
        "tracked_literals": {
            hex_address(value): {
                "class": _address_class(value),
                "literal_ref_count": len(literal_refs[value]),
                "function_count": ref_function_counts[hex_address(value)],
            }
            for value in TRACKED_LITERALS
        },
        "seed_functions": seeds,
        "conclusions": {
            "selector_swap_writer": {
                "function": hex_address(0x0813E428),
                "store_pc": hex_address(0x0813E458),
                "target_global": hex_address(SELECTOR_TABLE_GLOBAL),
                "source": "incoming r0 at function entry; caller mapping remains runtime-memory or wrapper-derived",
                "status": "provisional",
            },
            "selector_restore_writer": {
                "function": hex_address(0x0813E574),
                "store_pc": hex_address(0x0813E5B2),
                "target_global": hex_address(SELECTOR_TABLE_GLOBAL),
                "source": "runtime load through RAM 0x030068c0",
                "status": "confirmed_static_edge_provisional_semantics",
            },
            "fixed_rom_selector_branch": {
                "function": hex_address(0x0812F2B4),
                "store_pc": hex_address(0x0812F386),
                "target_global": hex_address(SELECTOR_TABLE_GLOBAL),
                "source": hex_address(ROM_SELECTOR_LITERAL),
                "status": "confirmed_static_edge_not_natural_runtime_initializer",
            },
        },
        "negative_boundary": {
            "natural_runtime_selector_hit": "not attempted in M1.9; M1.8 cohorts had zero selector-table writes/reads",
            "glyph_source": "not established",
            "codepage": "not established",
            "translation_ledger": "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = args.rom.read_bytes()
    report = static_report(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
