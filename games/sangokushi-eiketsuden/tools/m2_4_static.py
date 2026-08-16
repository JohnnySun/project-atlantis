#!/usr/bin/env python3
"""Source-safe M2.4 caller/state-gate analysis for B3EJ.

This bounded report follows the reviewed Table-B descriptor from its
initializer into the normal event loop.  The game calls the consumer through
the descriptor's function pointer rather than with a direct BL, so the report
keeps the indirect dispatch explicit.  It records decoded instruction spans,
call targets, state gates and selector bounds only; it never emits event
arrays, source records, ROM bytes or rendered output.
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
TABLE_B_COUNT = 44
CONSUMER_ENTRY = 0x026054

# These are deliberately small, reviewed Thumb spans.  The gaps in the
# dispatcher are literal/jump-table data and are never fed to Capstone.
INITIALIZER_SPANS = (
    (0x0264A4, 0x026546),
    (0x026554, 0x0265A0),
    (0x0265B4, 0x026626),
    (0x026630, 0x026646),
)
INITIALIZER_DATA_GAPS = (
    (0x026546, 0x026554),
    (0x0265A0, 0x0265B4),
    (0x026626, 0x026630),
)

DESCRIPTOR_WRAPPER_SPAN = (0x01A4B8, 0x01A4CC)
STATE_LOOP_SPAN = (0x01A738, 0x01A768)
EVENT_POLL_SPAN = (0x01A12C, 0x01A1FC)
STATE_OWNER_SPAN = (0x021A44, 0x021A5C)
DISPATCH_WRAPPER_SPAN = (0x01A720, 0x01A738)
DISPATCHER_CODE_SPANS = (
    (0x01A504, 0x01A51C),
    (0x01A588, 0x01A718),
)
DISPATCHER_DATA_GAP = (0x01A51C, 0x01A588)

DESCRIPTOR_CONSUMER_FIELD = 0x10
DESCRIPTOR_STATE_FIELD = 0x14
DESCRIPTOR_COUNT_FIELD = 0x02
DESCRIPTOR_EVENT_BUFFER_FIELD = 0x1C
STATE_LOOP_ENTRY = 0x01A738
EVENT_POLL_ENTRY = 0x01A12C
STATE_OWNER_ENTRY = 0x021A44
STATE_OWNER_TABLE = 0x0203544C
DISPATCH_VENEER = ROM_BASE + 0x06ED80
STATE_CHECK_VENEER = ROM_BASE + 0x06ED7C
EVENT_SELECTOR_VALUES = (0, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def _instruction_map(data: bytes, spans: tuple[tuple[int, int], ...]) -> dict[int, object]:
    instructions: dict[int, object] = {}
    for start, end in spans:
        for instruction in common.disassemble_thumb_span(data, start, end):
            instructions[instruction.address - ROM_BASE] = instruction
    return instructions


def _instruction_report(data: bytes, start: int, end: int) -> dict[str, object]:
    instructions = common.disassemble_thumb_span(data, start, end)
    calls = []
    branches = []
    for instruction in instructions:
        target = common.branch_target(instruction)
        if target is None:
            continue
        row = {
            "file_offset": _offset(instruction.address - ROM_BASE),
            "instruction": common.instruction_summary(instruction),
            "target": _hex(target),
        }
        if instruction.mnemonic in {"bl", "blx"}:
            calls.append(row)
        else:
            branches.append(row)
    return {
        "file_start": _offset(start),
        "file_end_exclusive": _offset(end),
        "gba_start": _hex(ROM_BASE + start),
        "gba_end_exclusive": _hex(ROM_BASE + end),
        "instruction_count": len(instructions),
        "all_thumb_instructions_decoded": True,
        "first_instruction": common.instruction_summary(instructions[0]),
        "last_instruction": common.instruction_summary(instructions[-1]),
        "call_sites": calls,
        "branch_targets": branches,
    }


def _require_instruction(
    instructions: dict[int, object],
    file_offset: int,
    mnemonic: str,
    contains: str = "",
) -> object:
    instruction = instructions.get(file_offset)
    if instruction is None:
        raise common.StaticContractError(f"missing instruction at {_offset(file_offset)}")
    operands = instruction.op_str.replace(" ", "").lower()
    if instruction.mnemonic != mnemonic or contains.lower() not in operands:
        raise common.StaticContractError(
            f"unexpected instruction at {_offset(file_offset)}: "
            f"{common.instruction_summary(instruction)}"
        )
    return instruction


def _require_branch(instruction: object, target: int, label: str) -> None:
    actual = common.branch_target(instruction)
    if actual != target:
        raise common.StaticContractError(
            f"{label} target changed: {_hex(actual or 0)} != {_hex(target)}"
        )


def _literal_value(data: bytes, file_offset: int) -> tuple[int, int]:
    halfword = struct.unpack_from("<H", data, file_offset)[0]
    literal_address = common.thumb_literal_target(file_offset, halfword)
    literal_offset = literal_address - ROM_BASE
    if literal_offset < 0 or literal_offset + 4 > len(data):
        raise common.StaticContractError(f"literal outside ROM at {_offset(file_offset)}")
    return literal_address, common.read_u32(data, literal_offset)


def _calls_to(instructions: dict[int, object], target: int) -> list[dict[str, str]]:
    rows = []
    for offset, instruction in sorted(instructions.items()):
        if instruction.mnemonic not in {"bl", "blx"}:
            continue
        if common.branch_target(instruction) != target:
            continue
        rows.append({
            "file_offset": _offset(offset),
            "gba_address": _hex(ROM_BASE + offset),
            "instruction": common.instruction_summary(instruction),
            "target": _hex(target),
        })
    return rows


def analyze_m2_4(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        raise common.StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != common.EXPECTED_GAME_CODE:
        raise common.StaticContractError(f"unexpected game code: {game_code!r}")

    boundary = common.parse_table_b_boundary(data)
    if boundary["entry_count"] != TABLE_B_COUNT:
        raise common.StaticContractError("Table-B entry count changed")

    initializer = _instruction_map(data, INITIALIZER_SPANS)
    wrapper = _instruction_map(data, (DESCRIPTOR_WRAPPER_SPAN,))
    state_loop = _instruction_map(data, (STATE_LOOP_SPAN,))
    event_poll = _instruction_map(data, (EVENT_POLL_SPAN,))
    state_owner = _instruction_map(data, (STATE_OWNER_SPAN,))
    dispatch_wrapper = _instruction_map(data, (DISPATCH_WRAPPER_SPAN,))
    dispatcher = _instruction_map(data, DISPATCHER_CODE_SPANS)

    builder_call = _require_instruction(initializer, 0x026510, "bl")
    _require_instruction(initializer, 0x026584, "mov", "r1,sb")
    _require_instruction(initializer, 0x02658A, "str", "[r6,#0x10]")
    _require_instruction(initializer, 0x02658E, "strh", "[r6,#2]")
    _require_instruction(initializer, 0x026598, "str", "[r6,#0x1c]")
    input_selector_call = _require_instruction(initializer, 0x02651C, "bl")
    _require_branch(input_selector_call, ROM_BASE + 0x0241D0, "input selector field call")
    _require_instruction(initializer, 0x026522, "lsrs", "r0,#0x18")
    _require_instruction(initializer, 0x026524, "movs", "r1,#0")
    state_owner_call = _require_instruction(initializer, 0x026526, "bl")
    _require_branch(state_owner_call, ROM_BASE + STATE_OWNER_ENTRY, "state-owner call")
    loop_call = _require_instruction(initializer, 0x0265D2, "bl")
    _require_branch(loop_call, ROM_BASE + STATE_LOOP_ENTRY, "initializer state-loop call")

    _require_instruction(wrapper, 0x01A4B8, "push", "{lr}")
    consumer_load = _require_instruction(wrapper, 0x01A4BE, "ldr", "[r0,#0x10]")
    wrapper_call = _require_instruction(wrapper, 0x01A4C0, "bl")
    _require_branch(wrapper_call, DISPATCH_VENEER, "descriptor wrapper veneer")

    _require_instruction(state_loop, 0x01A73A, "adds", "r4,r0")
    state_load = _require_instruction(state_loop, 0x01A73C, "ldr", "[r4,#0x14]")
    state_check = _require_instruction(state_loop, 0x01A742, "adds", "r0,r4")
    state_check_call = _require_instruction(state_loop, 0x01A744, "bl")
    _require_branch(state_check_call, STATE_CHECK_VENEER, "descriptor state check veneer")
    poll_call = _require_instruction(state_loop, 0x01A748, "bl")
    _require_branch(poll_call, ROM_BASE + EVENT_POLL_ENTRY, "event poll call")
    consumer_load_loop = _require_instruction(state_loop, 0x01A754, "ldr", "[r4,#0x10]")
    dispatch_call = _require_instruction(state_loop, 0x01A758, "bl")
    _require_branch(dispatch_call, DISPATCH_VENEER, "normal consumer veneer")

    poll_input_call = _require_instruction(event_poll, 0x01A130, "bl")
    _require_branch(poll_input_call, ROM_BASE + 0x00C61C, "event input reader")
    poll_normalize_call = _require_instruction(event_poll, 0x01A138, "bl")
    _require_branch(poll_normalize_call, ROM_BASE + 0x01A0D0, "event input normalizer")

    dispatch_call_wrapper = _require_instruction(dispatch_wrapper, 0x01A726, "bl")
    _require_branch(dispatch_call_wrapper, ROM_BASE + 0x01A504, "selector dispatcher")
    _require_instruction(dispatcher, 0x01A50C, "cmp", "#0x19")
    _require_instruction(dispatcher, 0x01A518, "ldr", "[r0]")
    _require_instruction(dispatcher, 0x01A51A, "mov", "pc,r0")

    _require_instruction(state_owner, 0x021A44, "lsls", "r0,r0,#0x10")
    _require_instruction(state_owner, 0x021A48, "lsrs", "r1,#0x10")
    state_literal_address, state_table_value = _literal_value(data, 0x021A4A)
    if state_literal_address != ROM_BASE + 0x021A5C or state_table_value != STATE_OWNER_TABLE:
        raise common.StaticContractError("state-owner table literal changed")
    _require_instruction(state_owner, 0x021A4C, "lsrs", "r0,#0xd")
    _require_instruction(state_owner, 0x021A50, "adds", "r1,r1,r2")
    _require_instruction(state_owner, 0x021A52, "ldrb", "[r1]")
    _require_instruction(state_owner, 0x021A58, "lsrs", "r0,#0x1f")
    _require_instruction(state_owner, 0x021A5A, "bx", "lr")

    return {
        "read_only": True,
        "rom": {"size_bytes": len(data), "game_code": game_code},
        "table_boundary": {
            key: value
            for key, value in boundary.items()
            if key not in {"entries", "following_words"}
        },
        "function_boundaries": {
            "initializer": {
                "spans": [_instruction_report(data, *span) for span in INITIALIZER_SPANS],
                "excluded_data_gaps": [
                    {"file_start": _offset(start), "file_end_exclusive": _offset(end)}
                    for start, end in INITIALIZER_DATA_GAPS
                ],
            },
            "descriptor_wrapper": _instruction_report(data, *DESCRIPTOR_WRAPPER_SPAN),
            "state_loop": _instruction_report(data, *STATE_LOOP_SPAN),
            "event_poll": _instruction_report(data, *EVENT_POLL_SPAN),
            "state_owner": _instruction_report(data, *STATE_OWNER_SPAN),
            "selector_dispatch_wrapper": _instruction_report(data, *DISPATCH_WRAPPER_SPAN),
            "selector_dispatcher": {
                "spans": [_instruction_report(data, *span) for span in DISPATCHER_CODE_SPANS],
                "excluded_data_gap": {
                    "file_start": _offset(DISPATCHER_DATA_GAP[0]),
                    "file_end_exclusive": _offset(DISPATCHER_DATA_GAP[1]),
                    "meaning": "selector jump-table data; not disassembled as Thumb",
                },
            },
        },
        "direct_call_search": {
            "target": _hex(ROM_BASE + CONSUMER_ENTRY),
            "direct_bl_sites_in_reviewed_spans": _calls_to(initializer, ROM_BASE + CONSUMER_ENTRY),
            "status": "no-direct-BL; consumer-reached-through-descriptor-function-pointer",
        },
        "descriptor_provenance": {
            "initializer_call_site": _offset(0x0265D2),
            "initializer_call_target": _hex(ROM_BASE + STATE_LOOP_ENTRY),
            "descriptor_register": "r6",
            "consumer_function_pointer_store": {
                "instruction_file_offset": _offset(0x02658A),
                "field": "r6+0x10",
                "value": _hex(ROM_BASE + CONSUMER_ENTRY),
                "thumb_target": _hex(ROM_BASE + CONSUMER_ENTRY + 1),
            },
            "builder_count_store": {
                "instruction_file_offset": _offset(0x02658E),
                "field": "r6+0x02",
                "meaning": "u16(event-builder return)",
            },
            "event_buffer_store": {
                "instruction_file_offset": _offset(0x026598),
                "field": "r6+0x1C",
                "meaning": "caller stack output buffer",
            },
            "state_gate_store": {
                "instruction_file_offset": _offset(0x026584),
                "field": "r6+0x14",
                "meaning": "value derived from initializer state call; checked before normal dispatch",
            },
            "state_owner": {
                "call_site": _offset(0x026526),
                "target": _hex(ROM_BASE + STATE_OWNER_ENTRY),
                "input_selector_source": "u8(input_structure+0x02) via 0x080241D0",
                "second_argument": "0",
                "state_table": _hex(STATE_OWNER_TABLE),
                "literal_slot": _hex(state_literal_address),
                "formula": "nonzero([0x0203544C + u16(r1) + (u16(r0) << 3)])",
                "stored_as": "r6+0x14 after signed 16-bit normalization",
            },
        },
        "normal_path_chain": {
            "steps": [
                {
                    "stage": "initializer",
                    "address": _hex(ROM_BASE + 0x0264A4),
                    "evidence": "descriptor r6 receives consumer pointer, builder count and event buffer",
                },
                {
                    "stage": "state-loop",
                    "address": _hex(ROM_BASE + STATE_LOOP_ENTRY),
                    "evidence": "r4=r0 descriptor; requires nonzero u32(r4+0x14) before polling",
                },
                {
                    "stage": "event-poll",
                    "address": _hex(ROM_BASE + EVENT_POLL_ENTRY),
                    "evidence": "reads input state through 0x0800C61C and normalizes it; zero result loops",
                },
                {
                    "stage": "indirect-consumer-dispatch",
                    "address": _hex(DISPATCH_VENEER),
                    "evidence": "r2=[r4+0x10], r0=r4, r1=poll result; bx r2 veneer",
                },
                {
                    "stage": "table-b-consumer",
                    "address": _hex(ROM_BASE + CONSUMER_ENTRY),
                    "evidence": "reviewed M2.1 index/load → B pointer → formatter chain",
                },
            ],
            "state_gate": {
                "field": "u32(r4+0x14)",
                "checked_at": _hex(ROM_BASE + 0x01A73C),
                "nonzero_call_target": _hex(STATE_CHECK_VENEER),
                "source": "0x08021A44 nonzero predicate over EWRAM state table 0x0203544C",
                "status": "confirmed-static-gate; exact game-mode semantic remains unresolved",
            },
            "poll_gate": {
                "entry": _hex(ROM_BASE + EVENT_POLL_ENTRY),
                "zero_result": "state loop repeats",
                "nonzero_result": "passed as r1 to indirect consumer",
                "selector_return_values": list(EVENT_SELECTOR_VALUES),
                "selector_bound_status": "confirmed-static-for-poll-return-values; not the Table-B event-byte bound",
            },
            "function_pointer_dispatch": {
                "load_sites": [
                    _offset(0x01A4BE),
                    _offset(0x01A754),
                ],
                "veneer": _hex(DISPATCH_VENEER),
                "consumer_pointer_source": "descriptor r6+0x10 initialized to 0x08026055",
                "status": "confirmed-static-indirect-link",
            },
        },
        "index_bound": {
            "table_b_count": TABLE_B_COUNT,
            "consumer_mask": "event byte & 0x7F",
            "local_consumer_bound": "u16(r6+0x02)",
            "normal_runtime_count_source": "builder table at [0x02014E78], terminated by 0xFF",
            "natural_event_index_lt_44": "not-proven; requires natural runtime cohort",
            "status": "state-gate-confirmed; Table-B global index gate remains open",
        },
        "classification": {
            "confirmed": [
                "valid Thumb spans and excluded jump-table/data gaps",
                "initializer field stores",
                "state field gate and event-poll loop",
                "indirect descriptor pointer to 0x08026054",
            ],
            "provisional": [
                "r4+0x14 is a game-mode/event readiness field; exact semantic label not assigned",
                "poll return values are selector-like inputs, not independently proven Table-B indices",
            ],
            "negative": [
                "no direct BL to 0x08026054 in the reviewed initializer spans",
                "no static relation from normal runtime table count to 44",
            ],
            "unknown": [
                "natural menu/battle state transition that makes r4+0x14 nonzero",
                "natural event-byte provenance and first actual index",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_m2_4(args.rom.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
