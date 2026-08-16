#!/usr/bin/env python3
"""Validate the bounded B3EJ title/menu state dispatcher.

The dispatcher at file offset ``0x05D2EC`` reads a state byte, bounds the
state to twelve entries, and jumps through a literal-backed table.  This
analyzer keeps the dispatcher code, literal pool, jump table, and handler
entry probes separate so inline data is never treated as Thumb code.  It
reports only offsets, targets, counts, and instruction summaries; it does
not emit ROM bytes, source text, or rendered output.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
EXPECTED_GAME_CODE = common.EXPECTED_GAME_CODE

STATE_DISPATCH_SPAN = (0x05D2EC, 0x05D310)
STATE_BYTE_LITERAL_OFFSET = 0x05D310
STATE_BYTE_ADDRESS = 0x030042D1
STATE_TABLE_LITERAL_OFFSET = 0x05D314
STATE_TABLE_OFFSET = 0x05D318
STATE_TABLE_ADDRESS = ROM_BASE + STATE_TABLE_OFFSET
STATE_COUNT = 12
STATE_TABLE_END = STATE_TABLE_OFFSET + STATE_COUNT * 4

# The table is data, not Thumb instructions.  The first word is the literal
# loaded by 0x0805D308; the twelve handler pointers begin at 0x05D318.
STATE_DATA_GAP = (STATE_BYTE_LITERAL_OFFSET, STATE_TABLE_END)
EXPECTED_HANDLER_TARGETS = (
    ROM_BASE + 0x05D348,
    ROM_BASE + 0x05D548,
    ROM_BASE + 0x05D744,
    ROM_BASE + 0x05D944,
    ROM_BASE + 0x05DB68,
    ROM_BASE + 0x05DD3C,
    ROM_BASE + 0x05DF14,
    ROM_BASE + 0x05DF38,
    ROM_BASE + 0x05DF14,
    ROM_BASE + 0x05DF38,
    ROM_BASE + 0x05DF50,
    ROM_BASE + 0x05DF74,
)

# These are deliberately short, instruction-aligned probes.  Handler bodies
# contain separate literal/data islands and are not assigned menu semantics
# by this tool.
HANDLER_ENTRY_PROBE_BYTES = 8
HANDLER_CODE_REGION = (0x05D348, 0x05E078)
STATE_CALLER_PROBES = (
    {"file_offset": 0x05E07C, "span": (0x05E078, 0x05E084)},
    {"file_offset": 0x05FB06, "span": (0x05FB00, 0x05FB0A)},
)

TITLE_MENU_OWNER_SPAN = (0x05D10C, 0x05D27C)
TITLE_MENU_OWNER_CALLER = {
    "file_offset": 0x05CA94,
    "span": (0x05CA80, 0x05CA98),
    "target": ROM_BASE + 0x05D10C,
}

# State 12 reaches this short, reviewed handler tail.  It writes zero to the
# same state byte used by the dispatcher; this is lifecycle evidence only.
STATE_RESET_HANDLER_SPAN = (0x05DF74, 0x05DF88)


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise common.StaticContractError(f"word outside ROM at {_offset(offset)}")
    return struct.unpack_from("<I", data, offset)[0]


def _expect_instruction(
    instructions: dict[int, object],
    file_offset: int,
    expected: str,
) -> object:
    instruction = instructions.get(file_offset)
    if instruction is None:
        raise common.StaticContractError(f"missing Thumb instruction at {_offset(file_offset)}")
    actual = common.instruction_summary(instruction)
    if actual != expected:
        raise common.StaticContractError(
            f"instruction changed at {_offset(file_offset)}: {actual!r} != {expected!r}"
        )
    return instruction


def _span_report(data: bytes, span: tuple[int, int]) -> dict[str, object]:
    instructions = common.disassemble_thumb_span(data, *span)
    return {
        "file_start": _offset(span[0]),
        "file_end_exclusive": _offset(span[1]),
        "gba_start": _address(ROM_BASE + span[0]),
        "gba_end_exclusive": _address(ROM_BASE + span[1]),
        "instruction_count": len(instructions),
        "all_thumb_instructions_decoded": True,
        "first_instruction": common.instruction_summary(instructions[0]),
        "last_instruction": common.instruction_summary(instructions[-1]),
    }


def _instruction_map(data: bytes, span: tuple[int, int]) -> dict[int, object]:
    return {
        instruction.address - ROM_BASE: instruction
        for instruction in common.disassemble_thumb_span(data, *span)
    }


def _literal_target(data: bytes, instruction_offset: int) -> tuple[int, int]:
    halfword = struct.unpack_from("<H", data, instruction_offset)[0]
    target = common.thumb_literal_target(instruction_offset, halfword)
    target_offset = target - ROM_BASE
    return target, _read_u32(data, target_offset)


def parse_state_table(data: bytes) -> dict[str, object]:
    """Parse and validate only the literal-backed state pointer table."""

    if STATE_TABLE_END + 4 > len(data):
        raise common.StaticContractError("state table exceeds ROM")
    literal_value = _read_u32(data, STATE_TABLE_LITERAL_OFFSET)
    if literal_value != STATE_TABLE_ADDRESS:
        raise common.StaticContractError("state table literal changed")

    pointers = [_read_u32(data, STATE_TABLE_OFFSET + index * 4) for index in range(STATE_COUNT)]
    targets = []
    for index, pointer in enumerate(pointers, start=1):
        if pointer != EXPECTED_HANDLER_TARGETS[index - 1]:
            raise common.StaticContractError(
                f"state {index} handler changed: {_address(pointer)} != "
                f"{_address(EXPECTED_HANDLER_TARGETS[index - 1])}"
            )
        target_offset = pointer - ROM_BASE
        if target_offset % 2 or not (HANDLER_CODE_REGION[0] <= target_offset < HANDLER_CODE_REGION[1]):
            raise common.StaticContractError(f"state {index} target is outside reviewed Thumb region")
        targets.append({
            "state_value": index,
            "table_index": index - 1,
            "pointer_file_offset": _offset(STATE_TABLE_OFFSET + (index - 1) * 4),
            "handler_gba_address": _address(pointer),
            "handler_file_offset": _offset(target_offset),
        })

    return {
        "literal_file_offset": _offset(STATE_TABLE_LITERAL_OFFSET),
        "literal_value": _address(literal_value),
        "table_file_offset": _offset(STATE_TABLE_OFFSET),
        "table_gba_address": _address(STATE_TABLE_ADDRESS),
        "entry_count": STATE_COUNT,
        "table_end_file_offset_exclusive": _offset(STATE_TABLE_END),
        "targets": targets,
    }


def analyze_title_menu_state(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        raise common.StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != EXPECTED_GAME_CODE:
        raise common.StaticContractError(f"unexpected game code: {game_code!r}")

    dispatcher = _instruction_map(data, STATE_DISPATCH_SPAN)
    _expect_instruction(dispatcher, 0x05D2EC, "push {r4, r5, r6, r7, lr}")
    state_load = _expect_instruction(dispatcher, 0x05D2F6, "ldr r1, [pc, #0x18]")
    _expect_instruction(dispatcher, 0x05D2F8, "ldrb r0, [r1]")
    _expect_instruction(dispatcher, 0x05D2FA, "subs r0, #1")
    _expect_instruction(dispatcher, 0x05D2FE, "cmp r0, #0xb")
    range_branch = _expect_instruction(dispatcher, 0x05D300, "bls #0x805d306")
    fallback_call = _expect_instruction(dispatcher, 0x05D302, "bl #0x805dfa6")
    _expect_instruction(dispatcher, 0x05D306, "lsls r0, r0, #2")
    table_load = _expect_instruction(dispatcher, 0x05D308, "ldr r1, [pc, #8]")
    _expect_instruction(dispatcher, 0x05D30A, "adds r0, r0, r1")
    _expect_instruction(dispatcher, 0x05D30C, "ldr r0, [r0]")
    _expect_instruction(dispatcher, 0x05D30E, "mov pc, r0")

    state_literal_target, state_literal_value = _literal_target(data, 0x05D2F6)
    table_literal_target, table_literal_value = _literal_target(data, 0x05D308)
    if state_literal_target != ROM_BASE + STATE_BYTE_LITERAL_OFFSET:
        raise common.StaticContractError("state-byte literal target changed")
    if state_literal_value != STATE_BYTE_ADDRESS:
        raise common.StaticContractError("state-byte literal value changed")
    if table_literal_target != ROM_BASE + STATE_TABLE_LITERAL_OFFSET:
        raise common.StaticContractError("state-table literal target changed")
    if table_literal_value != STATE_TABLE_ADDRESS:
        raise common.StaticContractError("state-table literal value changed")
    if common.branch_target(range_branch) != ROM_BASE + 0x05D306:
        raise common.StaticContractError("state range branch target changed")
    if common.branch_target(fallback_call) != ROM_BASE + 0x05DFA6:
        raise common.StaticContractError("state fallback target changed")

    state_table = parse_state_table(data)
    handler_probes = []
    for target in EXPECTED_HANDLER_TARGETS:
        target_offset = target - ROM_BASE
        span = (target_offset, target_offset + HANDLER_ENTRY_PROBE_BYTES)
        instructions = common.disassemble_thumb_span(data, *span)
        handler_probes.append({
            "handler_gba_address": _address(target),
            "handler_file_offset": _offset(target_offset),
            "probe_bytes": HANDLER_ENTRY_PROBE_BYTES,
            "instruction_count": len(instructions),
            "first_instruction": common.instruction_summary(instructions[0]),
            "last_instruction": common.instruction_summary(instructions[-1]),
            "entry_probe_status": "valid-thumb-entry-probe",
        })

    caller_reports = []
    caller_map = {}
    for probe in STATE_CALLER_PROBES:
        report = _span_report(data, probe["span"])
        instructions = _instruction_map(data, probe["span"])
        call = instructions.get(probe["file_offset"])
        if call is None or call.mnemonic != "bl" or common.branch_target(call) != ROM_BASE + 0x05D2EC:
            raise common.StaticContractError(
                f"state caller changed at {_offset(probe['file_offset'])}"
            )
        report.update({
            "callsite_file_offset": _offset(probe["file_offset"]),
            "callsite_gba_address": _address(ROM_BASE + probe["file_offset"]),
            "call_target": _address(common.branch_target(call) or 0),
        })
        caller_reports.append(report)

    owner = _instruction_map(data, TITLE_MENU_OWNER_SPAN)
    _expect_instruction(owner, 0x05D10C, "push {r4, lr}")
    _expect_instruction(owner, 0x05D110, "bl #0x805cf58")
    _expect_instruction(owner, 0x05D27A, "bx r0")
    owner_caller = _instruction_map(data, TITLE_MENU_OWNER_CALLER["span"])
    owner_call = owner_caller.get(TITLE_MENU_OWNER_CALLER["file_offset"])
    if owner_call is None or common.branch_target(owner_call) != TITLE_MENU_OWNER_CALLER["target"]:
        raise common.StaticContractError("title menu owner caller changed")

    reset = _instruction_map(data, STATE_RESET_HANDLER_SPAN)
    reset_load = _expect_instruction(reset, 0x05DF80, "ldr r1, [pc, #0xc]")
    _expect_instruction(reset, 0x05DF82, "movs r0, #0")
    _expect_instruction(reset, 0x05DF84, "strb r0, [r1]")
    reset_literal_target, reset_literal_value = _literal_target(data, 0x05DF80)
    if reset_literal_value != STATE_BYTE_ADDRESS:
        raise common.StaticContractError("state reset literal changed")

    return {
        "read_only": True,
        "rom": {"size_bytes": len(data), "game_code": game_code},
        "dispatcher": {
            "function_span": _span_report(data, STATE_DISPATCH_SPAN),
            "state_byte_address": _address(STATE_BYTE_ADDRESS),
            "state_literal_file_offset": _offset(STATE_BYTE_LITERAL_OFFSET),
            "state_literal_target": _address(state_literal_target),
            "state_transition": "state_byte - 1; unsigned <= 0x0B; table_index = (state - 1) * 4",
            "valid_state_values": [1, STATE_COUNT],
            "out_of_range_action": "BL 0x0805DFA6 fallback",
            "indirect_transfer": "LDR r0,[table+index]; MOV pc,r0; Thumb state is preserved",
        },
        "data_boundaries": {
            "excluded_gap_file_start": _offset(STATE_DATA_GAP[0]),
            "excluded_gap_file_end_exclusive": _offset(STATE_DATA_GAP[1]),
            "excluded_gap_meaning": "state-byte literal, state-table literal, and 12 handler pointers; not Thumb code",
            "state_table": state_table,
        },
        "handler_entry_probes": {
            "reviewed_code_region": {
                "file_start": _offset(HANDLER_CODE_REGION[0]),
                "file_end_exclusive": _offset(HANDLER_CODE_REGION[1]),
            },
            "unique_handler_count": len(set(EXPECTED_HANDLER_TARGETS)),
            "probes": handler_probes,
            "semantic_scope": "entry validity only; handler menu/battle labels remain unassigned",
        },
        "caller_chain": {
            "dispatcher_callers": caller_reports,
            "title_menu_owner": {
                "entry": _address(ROM_BASE + TITLE_MENU_OWNER_SPAN[0]),
                "function_span": _span_report(data, TITLE_MENU_OWNER_SPAN),
                "input_poll_call": _address(ROM_BASE + 0x05CF58),
                "caller": {
                    "callsite_file_offset": _offset(TITLE_MENU_OWNER_CALLER["file_offset"]),
                    "callsite_gba_address": _address(ROM_BASE + TITLE_MENU_OWNER_CALLER["file_offset"]),
                    "target": _address(TITLE_MENU_OWNER_CALLER["target"]),
                    "span": _span_report(data, TITLE_MENU_OWNER_CALLER["span"]),
                },
                "semantic_scope": "title/menu display owner and input-poll edge; not a Table-B consumer",
            },
        },
        "state_lifecycle": {
            "state12_handler_entry": _address(EXPECTED_HANDLER_TARGETS[-1]),
            "reset_span": _span_report(data, STATE_RESET_HANDLER_SPAN),
            "reset_literal_target": _address(reset_literal_target),
            "reset_literal_value": _address(reset_literal_value),
            "meaning": "state-12 tail writes zero to the dispatcher state byte before fallback; exact UI meaning unknown",
        },
        "classification": {
            "confirmed": [
                "dispatcher Thumb span and fallback/range branch",
                "state byte literal 0x030042D1",
                "12-entry table boundary and exact handler targets",
                "two direct dispatcher callers at 0x0805E07C and 0x0805FB06",
                "title/menu owner 0x0805D10C called from 0x0805CA94",
                "state-12 reset tail writes zero to the same state byte",
            ],
            "provisional": [
                "the dispatcher is a title/menu-side state machine based on its reviewed callers and runtime OAM receipt",
                "handler entries are state-specific UI/render routines; no individual state label is assigned",
            ],
            "negative": [
                "this chain contains no Table-B index bound and no direct path to 0x08026054",
            ],
            "unknown": [
                "which handler state corresponds to each OAM label",
                "the transition that makes normal event descriptor field r4+0x14 nonzero",
                "natural story/battle event byte provenance and actual Table-B index",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_title_menu_state(args.rom.read_bytes())
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
