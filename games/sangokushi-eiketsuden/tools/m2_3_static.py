#!/usr/bin/env python3
"""Source-safe M2.3 analysis of B3EJ's event-array builder.

This slice follows the reviewed Table-B consumer's upstream structure
initializer and its event-array builder.  It reports decoded instruction
spans, literal values, call targets, bounds and hashes only; it never emits
the event array, the source records, or any other ROM byte range.
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
UPSTREAM_START = 0x0264A4
UPSTREAM_END = 0x026646
UPSTREAM_CODE_SPANS = (
    (0x0264A4, 0x026546),
    (0x026554, 0x0265A0),
    (0x0265B4, 0x026626),
    (0x026630, 0x026646),
)
UPSTREAM_DATA_GAPS = (
    (0x026546, 0x026554),
    (0x0265A0, 0x0265B4),
    (0x026626, 0x026630),
)
EVENT_BUILDER_START = 0x01929C
EVENT_BUILDER_END = 0x019382
EVENT_BUILDER_CODE_SPANS = (
    (0x01929C, 0x0192FC),
    (0x019308, 0x019382),
)
EVENT_BUILDER_DATA_GAP = (0x0192FC, 0x019308)
EVENT_BUILDER_RUNTIME_TABLE_LITERAL = 0x0192FC
EVENT_BUILDER_RUNTIME_TABLE = 0x02014E78
EVENT_BUILDER_EMPTY_BOUND = 0x2B
EVENT_BUILDER_EMPTY_BOUND_INCLUSIVE_COUNT = 44
EVENT_BUILDER_RETURN_VALUE = 0x019374
EVENT_BUILDER_EXIT_OBSERVATION = 0x019376


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


def _literal_value(data: bytes, file_offset: int) -> tuple[int, int]:
    halfword = struct.unpack_from("<H", data, file_offset)[0]
    literal_address = common.thumb_literal_target(file_offset, halfword)
    literal_offset = literal_address - ROM_BASE
    if literal_offset < 0 or literal_offset + 4 > len(data):
        raise common.StaticContractError(f"literal outside ROM at {_offset(file_offset)}")
    return literal_address, common.read_u32(data, literal_offset)


def _require_branch(instruction: object, target: int, label: str) -> None:
    actual = common.branch_target(instruction)
    if actual != target:
        raise common.StaticContractError(
            f"{label} target changed: {_hex(actual or 0)} != {_hex(target)}"
        )


def index_bound_evidence(table_entry_count: int = TABLE_B_COUNT) -> dict[str, object]:
    """Describe what the static builder proof does and does not establish."""

    return {
        "table_b_entry_count": table_entry_count,
        "r6_plus_0x02": "u16(builder_return_value)",
        "r6_plus_0x1c": "builder_output_buffer_argument_r1 (caller stack buffer)",
        "empty_path_count": EVENT_BUILDER_EMPTY_BOUND_INCLUSIVE_COUNT,
        "normal_path_count_source": "runtime table at [0x02014E78], terminated by 0xFF",
        "static_status": "builder_relation_confirmed; universal_index_lt_44_not-proven",
        "runtime_requirement": "bounded consumer_index_setup cohort with actual masked index and caller LR",
    }


def analyze_m2_3(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        raise common.StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != common.EXPECTED_GAME_CODE:
        raise common.StaticContractError(f"unexpected game code: {game_code!r}")

    boundary = common.parse_table_b_boundary(data)
    if boundary["entry_count"] != TABLE_B_COUNT:
        raise common.StaticContractError("Table-B entry count changed")

    upstream_instructions = _instruction_map(data, UPSTREAM_CODE_SPANS)
    builder_instructions = _instruction_map(data, EVENT_BUILDER_CODE_SPANS)

    builder_call = _require_instruction(upstream_instructions, 0x026510, "bl")
    _require_branch(builder_call, ROM_BASE + EVENT_BUILDER_START, "upstream builder call")
    _require_instruction(upstream_instructions, 0x026518, "mov", "sl,r0")
    _require_instruction(upstream_instructions, 0x026588, "ldr", "[pc")
    literal_address, consumer_pointer = _literal_value(data, 0x026588)
    if literal_address != ROM_BASE + 0x0265AC or consumer_pointer != (ROM_BASE + CONSUMER_ENTRY) | 1:
        raise common.StaticContractError("upstream consumer literal changed")
    _require_instruction(upstream_instructions, 0x02658A, "str", "[r6,#0x10]")
    _require_instruction(upstream_instructions, 0x02658C, "mov", "r2,sl")
    _require_instruction(upstream_instructions, 0x02658E, "strh", "[r6,#2]")
    _require_instruction(upstream_instructions, 0x026596, "mov", "r0,sp")
    _require_instruction(upstream_instructions, 0x026598, "str", "[r6,#0x1c]")

    runtime_table_literal_address, runtime_table_value = _literal_value(data, 0x0192BA)
    if runtime_table_value != EVENT_BUILDER_RUNTIME_TABLE:
        raise common.StaticContractError("event-builder runtime table literal changed")
    _require_instruction(builder_instructions, 0x0192F6, "cmp", "r5,#0x2b")
    empty_loop = _require_instruction(builder_instructions, 0x0192F8, "bls")
    _require_branch(empty_loop, ROM_BASE + 0x0192EC, "empty-path loop")
    _require_instruction(builder_instructions, 0x01936C, "cmp", "r0,#0xff")
    _require_instruction(builder_instructions, EVENT_BUILDER_RETURN_VALUE, "adds", "r0,r5")
    _require_instruction(builder_instructions, EVENT_BUILDER_EXIT_OBSERVATION, "pop", "{r3,r4}")
    _require_instruction(builder_instructions, 0x019380, "bx", "r1")

    consumer = common.analyze_consumer_chain(data)
    return {
        "read_only": True,
        "rom": {"size_bytes": len(data), "game_code": game_code},
        "table_boundary": {
            key: value
            for key, value in boundary.items()
            if key not in {"entries", "following_words"}
        },
        "upstream_initializer": {
            "function_file_span": [_offset(UPSTREAM_START), _offset(UPSTREAM_END)],
            "function_gba_span": [_hex(ROM_BASE + UPSTREAM_START), _hex(ROM_BASE + UPSTREAM_END)],
            "code_spans": [_instruction_report(data, *span) for span in UPSTREAM_CODE_SPANS],
            "excluded_data_gaps": [
                {"file_start": _offset(start), "file_end_exclusive": _offset(end)}
                for start, end in UPSTREAM_DATA_GAPS
            ],
            "builder_call": {
                "call_site": _offset(0x026510),
                "target": _hex(ROM_BASE + EVENT_BUILDER_START),
                "arguments": "r0=input structure, r1=sp output buffer, r2=1",
            },
            "r6_fields": {
                "plus_0x02": "u16 return value from builder, normalized to u16 in r0",
                "plus_0x10": _hex(consumer_pointer),
                "plus_0x1c": "sp output buffer passed as builder r1",
                "plus_0x24": "later event selector; not used as the Table-B bound",
            },
            "consumer_pointer_literal": {
                "slot": _hex(literal_address),
                "value": _hex(consumer_pointer),
                "stored_at": _offset(0x02658A),
            },
        },
        "event_builder": {
            "function_file_span": [_offset(EVENT_BUILDER_START), _offset(EVENT_BUILDER_END)],
            "function_gba_span": [
                _hex(ROM_BASE + EVENT_BUILDER_START),
                _hex(ROM_BASE + EVENT_BUILDER_END),
            ],
            "code_spans": [_instruction_report(data, *span) for span in EVENT_BUILDER_CODE_SPANS],
            "excluded_data_gap": {
                "file_start": _offset(EVENT_BUILDER_DATA_GAP[0]),
                "file_end_exclusive": _offset(EVENT_BUILDER_DATA_GAP[1]),
            },
            "runtime_table_pointer": {
                "literal_slot": _hex(runtime_table_literal_address),
                "value": _hex(runtime_table_value),
                "meaning": "runtime-initialized event source table; contents not statically assumed",
            },
            "empty_path": {
                "loop_compare": _offset(0x0192F6),
                "loop_branch": _offset(0x0192F8),
                "last_index": EVENT_BUILDER_EMPTY_BOUND,
                "returned_count": EVENT_BUILDER_EMPTY_BOUND_INCLUSIVE_COUNT,
            },
            "normal_path": {
                "terminator_compare": _offset(0x01936C),
                "terminator": "0xFF",
                "count_increment": [_offset(0x019360), _offset(0x019364)],
                "returned_count_instruction": _offset(EVENT_BUILDER_RETURN_VALUE),
                "post_return_observation_pc": _hex(ROM_BASE + EVENT_BUILDER_EXIT_OBSERVATION),
            },
        },
        "consumer_chain_selected": {
            "source": "common.analyze_consumer_chain",
            "record_byte_to_table_index": consumer["consumer_chain"]["record_byte_to_index"],
            "status": "consumer_masks_event_byte_to_0x7F; no static compare against 44",
        },
        "index_bound": index_bound_evidence(int(boundary["entry_count"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_m2_3(args.rom.read_bytes())
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
