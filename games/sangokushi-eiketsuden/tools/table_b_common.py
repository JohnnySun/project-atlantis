#!/usr/bin/env python3
"""Shared, source-safe static helpers for the B3EJ table-B slice.

This module reports offsets, counts, hashes and control-byte statistics.  The
extractor imports its record decoder from here but writes original text only
to the ignored ``research/sangokushi-eiketsuden-decoded.jsonl`` path.
"""

from __future__ import annotations

import hashlib
import struct
from collections import Counter
from pathlib import Path
from typing import Iterable

try:
    import capstone
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("capstone is required for the B3EJ static consumer scan") from exc


ROM_BASE = 0x08000000
EXPECTED_GAME_CODE = "B3EJ"

TABLE_B_OFFSET = 0x0D1FFC
TABLE_B_NEXT_STRUCT_OFFSET = 0x0D20AC
TABLE_C_OFFSET = 0x0D20D8

CONSUMER_FUNCTION_START = 0x026054
CONSUMER_FUNCTION_END = 0x0264A4
CONSUMER_DISPATCH_LITERAL_SLOT = 0x026084
CONSUMER_DISPATCH_TABLE = 0x026088
CONSUMER_DISPATCH_COUNT = 0x23
CONSUMER_DISPATCH_LIMIT = 0x22
CONSUMER_DISPATCH_CODE_SPAN = (0x026054, 0x026080)
CONSUMER_TABLE_B_CODE_SPAN = (0x02629C, 0x02634C)
CONSUMER_EPILOGUE_SPAN = (0x026494, 0x0264A4)
CONSUMER_TABLE_LITERAL_SLOT = 0x026350

RECORD_POINTER_LOAD_ADDRESS = 0x026306
RECORD_WRAPPER_ADDRESS = 0x000D8F0
FORMAT_READER_ADDRESS = 0x000D3FC
RECORD_WRAPPER_SPAN = (0x000D8F0, 0x000D904)
FORMAT_READER_SPAN = (0x000D3FC, 0x000D6B6)


class StaticContractError(ValueError):
    """Raised when the reviewed B3EJ static contract no longer matches."""


def gba_address(file_offset: int) -> int:
    return ROM_BASE + file_offset


def hex_offset(value: int) -> str:
    return f"0x{value:06X}"


def hex_address(value: int) -> str:
    return f"0x{value:08X}"


def is_rom_pointer(value: int, rom_size: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + rom_size


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise StaticContractError(f"word read outside ROM: {hex_offset(offset)}")
    return struct.unpack_from("<I", data, offset)[0]


def read_c_string(data: bytes, file_offset: int) -> tuple[bytes, int]:
    if file_offset < 0 or file_offset >= len(data):
        raise StaticContractError(f"record outside ROM: {hex_offset(file_offset)}")
    terminator = data.find(b"\0", file_offset)
    if terminator < 0:
        raise StaticContractError(f"record has no NUL terminator: {hex_offset(file_offset)}")
    return data[file_offset:terminator], terminator


def _sjis_text(payload: bytes) -> str:
    try:
        return payload.decode("shift_jis")
    except UnicodeDecodeError as exc:
        raise StaticContractError(f"record is not valid Shift-JIS: {exc}") from exc


def format_sequences(payload: bytes) -> tuple[Counter[str], Counter[str]]:
    """Count reviewed format sequences and leave all other percent bytes opaque."""

    known = Counter()
    unknown = Counter()
    for index, value in enumerate(payload):
        if value != 0x25:  # '%'
            continue
        if index + 1 < len(payload):
            marker = chr(payload[index + 1])
            sequence = f"%{marker}"
            if marker in "sdu%":
                known[sequence] += 1
            else:
                unknown[sequence] += 1
        else:
            unknown["%<eof>"] += 1
    return known, unknown


def record_structure(payload: bytes) -> dict[str, object]:
    """Decode one record and report structural facts without hiding controls."""

    text = _sjis_text(payload)
    known_formats, unknown_formats = format_sequences(payload)
    opaque_controls = Counter(
        value for value in payload
        if value < 0x20 and value not in (0x09, 0x0A)
    )
    return {
        "text": text,
        "payload_length": len(payload),
        "source_hash": hashlib.sha256(payload).hexdigest(),
        "shift_jis_decodable": True,
        "line_feed_count": payload.count(b"\x0A"),
        "format_counts": dict(sorted(known_formats.items())),
        "unknown_format_counts": dict(sorted(unknown_formats.items())),
        "opaque_control_byte_counts": {
            f"0x{value:02X}": count for value, count in sorted(opaque_controls.items())
        },
    }


def parse_table_b_boundary(data: bytes) -> dict[str, object]:
    """Read the contiguous ROM-pointer run and its adjacent structure evidence."""

    entries: list[dict[str, object]] = []
    offset = TABLE_B_OFFSET
    while offset + 4 <= len(data):
        pointer = read_u32(data, offset)
        if not is_rom_pointer(pointer, len(data)):
            break
        target = pointer - ROM_BASE
        payload, terminator = read_c_string(data, target)
        entries.append({
            "entry": len(entries),
            "pointer_file_offset": hex_offset(offset),
            "pointer_gba_address": hex_address(gba_address(offset)),
            "pointer_value": hex_address(pointer),
            "record_file_offset": hex_offset(target),
            "record_gba_address": hex_address(pointer),
            "record_terminator_file_offset": hex_offset(terminator),
            "record_payload_length": len(payload),
            "record_payload_sha256": hashlib.sha256(payload).hexdigest(),
        })
        offset += 4

    count = len(entries)
    if count == 0:
        raise StaticContractError("table B has no ROM-pointer entries")
    next_word = read_u32(data, offset)
    following_words = []
    cursor = offset
    while cursor < TABLE_C_OFFSET and cursor + 4 <= len(data):
        following_words.append({
            "file_offset": hex_offset(cursor),
            "value": f"0x{read_u32(data, cursor):08X}",
            "is_rom_pointer": is_rom_pointer(read_u32(data, cursor), len(data)),
        })
        cursor += 4

    all_following_non_pointers = all(not bool(row["is_rom_pointer"]) for row in following_words)
    boundary_confirmed = (
        count == 44
        and offset == TABLE_B_NEXT_STRUCT_OFFSET
        and next_word == 0
        and cursor == TABLE_C_OFFSET
        and all_following_non_pointers
    )
    return {
        "table_file_offset": hex_offset(TABLE_B_OFFSET),
        "table_gba_address": hex_address(gba_address(TABLE_B_OFFSET)),
        "entry_count": count,
        "pointer_run_end_exclusive": hex_offset(offset),
        "first_non_pointer_file_offset": hex_offset(offset),
        "first_non_pointer_word": f"0x{next_word:08X}",
        "following_structure_end": hex_offset(cursor),
        "next_pointer_table_c_file_offset": hex_offset(TABLE_C_OFFSET),
        "following_words": following_words,
        "boundary_status": "confirmed-static" if boundary_confirmed else "mismatch",
        "entries": entries,
    }


def table_b_records(data: bytes, boundary: dict[str, object] | None = None) -> list[dict[str, object]]:
    if boundary is None:
        boundary = parse_table_b_boundary(data)
    result = []
    for entry in boundary["entries"]:
        target = int(str(entry["record_file_offset"]), 16)
        payload, _ = read_c_string(data, target)
        result.append({**entry, "payload": payload})
    return result


def direct_word_hits(data: bytes, value: int) -> list[int]:
    return [
        offset
        for offset in range(0, len(data) - 3, 4)
        if read_u32(data, offset) == value
    ]


def table_range_word_hits(data: bytes, start_address: int, end_address: int) -> list[dict[str, object]]:
    hits = []
    for offset in range(0, len(data) - 3, 4):
        value = read_u32(data, offset)
        if start_address <= value < end_address:
            hits.append({"file_offset": hex_offset(offset), "value": hex_address(value)})
    return hits


def _thumb_disassembler() -> "capstone.Cs":
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    return md


def disassemble_thumb_span(data: bytes, start: int, end: int) -> list[object]:
    if start < 0 or end > len(data) or start >= end or start % 2:
        raise StaticContractError(f"invalid Thumb span {hex_offset(start)}..{hex_offset(end)}")
    md = _thumb_disassembler()
    instructions = []
    cursor = start
    while cursor < end:
        decoded = list(md.disasm(data[cursor:end], gba_address(cursor), count=1))
        if not decoded or cursor + decoded[0].size > end:
            raise StaticContractError(f"invalid Thumb instruction at {hex_offset(cursor)}")
        instructions.append(decoded[0])
        cursor += decoded[0].size
    return instructions


def instruction_at(instructions: Iterable[object], address: int) -> object:
    for instruction in instructions:
        if instruction.address == gba_address(address):
            return instruction
    raise StaticContractError(f"instruction not found at {hex_address(gba_address(address))}")


def instruction_summary(instruction: object) -> str:
    text = f"{instruction.mnemonic} {instruction.op_str}".strip()
    return text


def thumb_literal_target(file_offset: int, halfword: int) -> int:
    if halfword & 0xF800 != 0x4800:
        raise StaticContractError(f"not a Thumb PC literal load at {hex_offset(file_offset)}")
    return ((gba_address(file_offset) + 4) & ~3) + ((halfword & 0xFF) * 4)


def thumb_literal_refs_to(data: bytes, literal_address: int, spans: Iterable[tuple[int, int]]) -> list[int]:
    refs = []
    for start, end in spans:
        for instruction in disassemble_thumb_span(data, start, end):
            if instruction.mnemonic != "ldr" or "pc" not in instruction.op_str:
                continue
            halfword = struct.unpack_from("<H", data, instruction.address - ROM_BASE)[0]
            if thumb_literal_target(instruction.address - ROM_BASE, halfword) == literal_address:
                refs.append(instruction.address - ROM_BASE)
    return refs


def arm_literal_refs_to(data: bytes, literal_address: int) -> list[int]:
    """Find ARM PC-relative LDR candidates; caller validation remains separate."""

    refs = []
    for offset in range(0, len(data) - 3, 4):
        word = read_u32(data, offset)
        # ARM LDR immediate, P=1, W=0, L=1, Rn=PC, no register offset.
        if (word & 0x0E5F0000) != 0x051F0000:
            continue
        immediate = word & 0xFFF
        target = gba_address(offset) + 8
        target += immediate if word & (1 << 23) else -immediate
        if target == literal_address:
            refs.append(offset)
    return refs


def branch_target(instruction: object) -> int | None:
    if instruction.mnemonic not in {"bl", "blx", "b", "beq", "bne", "bhi", "bls", "bge", "bgt", "ble", "blt", "bcc", "bcs"}:
        return None
    if not instruction.operands or instruction.operands[0].type != capstone.arm.ARM_OP_IMM:
        return None
    return int(instruction.operands[0].imm)


def _span_report(data: bytes, start: int, end: int) -> dict[str, object]:
    instructions = disassemble_thumb_span(data, start, end)
    return {
        "file_start": hex_offset(start),
        "file_end_exclusive": hex_offset(end),
        "gba_start": hex_address(gba_address(start)),
        "instruction_count": len(instructions),
        "all_thumb_instructions_decoded": True,
        "first_instruction": instruction_summary(instructions[0]),
        "last_instruction": instruction_summary(instructions[-1]),
    }


def analyze_consumer_chain(data: bytes) -> dict[str, object]:
    dispatch = disassemble_thumb_span(data, *CONSUMER_DISPATCH_CODE_SPAN)
    table_b_code = disassemble_thumb_span(data, *CONSUMER_TABLE_B_CODE_SPAN)
    epilogue = disassemble_thumb_span(data, *CONSUMER_EPILOGUE_SPAN)
    wrapper = disassemble_thumb_span(data, *RECORD_WRAPPER_SPAN)
    formatter = disassemble_thumb_span(data, *FORMAT_READER_SPAN)

    dispatch_limit = instruction_at(dispatch, 0x02606E)
    dispatch_table_load = instruction_at(dispatch, 0x026076)
    dispatch_table_pointer = read_u32(data, CONSUMER_DISPATCH_LITERAL_SLOT)
    dispatch_targets = [
        read_u32(data, CONSUMER_DISPATCH_TABLE + index * 4)
        for index in range(CONSUMER_DISPATCH_COUNT)
    ]
    dispatch_targets_in_function = all(
        CONSUMER_FUNCTION_START <= target - ROM_BASE < CONSUMER_FUNCTION_END
        and target % 2 == 0
        for target in dispatch_targets
    )

    literal_load = instruction_at(table_b_code, 0x0262F8)
    literal_halfword = struct.unpack_from("<H", data, 0x0262F8)[0]
    literal_target = thumb_literal_target(0x0262F8, literal_halfword)
    table_base_value = read_u32(data, CONSUMER_TABLE_LITERAL_SLOT)

    chain_addresses = [
        0x0262FA, 0x0262FE, 0x026300, 0x026302, 0x026304, RECORD_POINTER_LOAD_ADDRESS,
    ]
    chain_instructions = [instruction_at(table_b_code, address) for address in chain_addresses]
    lookup_call = instruction_at(table_b_code, 0x026308)
    wrapper_call = instruction_at(wrapper, 0x000D8FA)
    formatter_source_read = instruction_at(formatter, 0x000D410)
    formatter_nul_branch = instruction_at(formatter, 0x000D41A)
    formatter_percent_branch = instruction_at(formatter, 0x000D422)
    formatter_return = instruction_at(formatter, 0x000D6B4)

    if instruction_summary(dispatch_limit) != "cmp r4, #0x22":
        raise StaticContractError("dispatch bound instruction changed")
    if dispatch_table_pointer != gba_address(CONSUMER_DISPATCH_TABLE):
        raise StaticContractError("dispatch table literal changed")
    if literal_target != gba_address(CONSUMER_TABLE_LITERAL_SLOT):
        raise StaticContractError("table-B literal load target changed")
    if table_base_value != gba_address(TABLE_B_OFFSET):
        raise StaticContractError("table-B literal value changed")
    if branch_target(lookup_call) != gba_address(RECORD_WRAPPER_ADDRESS):
        raise StaticContractError("record wrapper branch target changed")
    if branch_target(wrapper_call) != gba_address(FORMAT_READER_ADDRESS):
        raise StaticContractError("formatter branch target changed")
    if not dispatch_targets_in_function:
        raise StaticContractError("dispatch target escaped the reviewed function span")

    return {
        "function_boundary": {
            "function_start": hex_address(gba_address(CONSUMER_FUNCTION_START)),
            "function_end_exclusive": hex_address(gba_address(CONSUMER_FUNCTION_END)),
            "next_function_prologue": hex_address(gba_address(CONSUMER_FUNCTION_END)),
            "spans": [
                _span_report(data, *CONSUMER_DISPATCH_CODE_SPAN),
                _span_report(data, *CONSUMER_TABLE_B_CODE_SPAN),
                _span_report(data, *CONSUMER_EPILOGUE_SPAN),
            ],
            "dispatch_limit": CONSUMER_DISPATCH_LIMIT,
            "dispatch_entry_count": CONSUMER_DISPATCH_COUNT,
            "dispatch_table_file_offset": hex_offset(CONSUMER_DISPATCH_TABLE),
            "dispatch_targets_in_function": dispatch_targets_in_function,
        },
        "literal_references": {
            "table_base_literal_slot": hex_address(gba_address(CONSUMER_TABLE_LITERAL_SLOT)),
            "table_base_literal_value": hex_address(table_base_value),
            "thumb_load_file_offset": hex_offset(0x0262F8),
            "thumb_load": instruction_summary(literal_load),
            "thumb_literal_target": hex_address(literal_target),
            "thumb_refs_in_valid_spans": [
                hex_offset(offset)
                for offset in thumb_literal_refs_to(
                    data, gba_address(CONSUMER_TABLE_LITERAL_SLOT), [CONSUMER_TABLE_B_CODE_SPAN]
                )
            ],
            "arm_refs_to_same_literal": [
                hex_offset(offset) for offset in arm_literal_refs_to(data, gba_address(CONSUMER_TABLE_LITERAL_SLOT))
            ],
        },
        "consumer_chain": {
            "source_record_pointer": {
                "setup_span": [hex_offset(0x0262EC), hex_offset(0x0262F0)],
                "instructions": [instruction_summary(instruction_at(table_b_code, address)) for address in chain_addresses],
            },
            "record_byte_to_index": {
                "read_instruction": instruction_summary(chain_instructions[0]),
                "mask_instructions": [instruction_summary(chain_instructions[1]), instruction_summary(chain_instructions[2])],
                "effective_index_mask": "0x7F",
                "scale_instruction": instruction_summary(chain_instructions[3]),
                "base_add_instruction": instruction_summary(chain_instructions[4]),
            },
            "record_pointer_load": {
                "file_offset": hex_offset(RECORD_POINTER_LOAD_ADDRESS),
                "instruction": instruction_summary(chain_instructions[-1]),
                "result_register": "r0",
            },
            "byte_reader_wrapper": {
                "address": hex_address(gba_address(RECORD_WRAPPER_ADDRESS)),
                "call_instruction": instruction_summary(lookup_call),
                "call_target": hex_address(branch_target(lookup_call) or 0),
                "function_span": _span_report(data, *RECORD_WRAPPER_SPAN),
                "next_call": instruction_summary(wrapper_call),
                "next_call_target": hex_address(branch_target(wrapper_call) or 0),
            },
            "format_reader": {
                "address": hex_address(gba_address(FORMAT_READER_ADDRESS)),
                "function_span": _span_report(data, *FORMAT_READER_SPAN),
                "source_byte_read": instruction_summary(formatter_source_read),
                "nul_test": instruction_summary(formatter_nul_branch),
                "percent_test": instruction_summary(formatter_percent_branch),
                "return": instruction_summary(formatter_return),
                "scope": "byte_reader_and_format_parser_only; glyph_writer_not-proven",
            },
        },
        "caller_index_bound": {
            "effective_mask_max": 0x7F,
            "table_entry_count": 44,
            "status": "not-proven",
            "reason": "The selected consumer masks the event byte to 7 bits but has no local compare against 44 before the table load; the 44-entry ROM boundary is confirmed separately.",
        },
    }


def analyze_rom(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        raise StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != EXPECTED_GAME_CODE:
        raise StaticContractError(f"unexpected game code: {game_code!r}")
    boundary = parse_table_b_boundary(data)
    records = table_b_records(data, boundary)
    structure_counts = Counter()
    format_counts = Counter()
    unknown_format_counts = Counter()
    opaque_counts = Counter()
    shift_jis_valid = 0
    line_feed_records = 0
    for record in records:
        structure = record_structure(record["payload"])
        if structure["shift_jis_decodable"]:
            shift_jis_valid += 1
        if structure["line_feed_count"]:
            line_feed_records += 1
        structure_counts[str(record["record_payload_length"])] += 1
        format_counts.update(structure["format_counts"])
        unknown_format_counts.update(structure["unknown_format_counts"])
        opaque_counts.update(structure["opaque_control_byte_counts"])

    table_start = gba_address(TABLE_B_OFFSET)
    table_end = gba_address(TABLE_B_NEXT_STRUCT_OFFSET)
    return {
        "read_only": True,
        "rom": {
            "size_bytes": len(data),
            "game_code": game_code,
        },
        "table_boundary": {
            key: value for key, value in boundary.items() if key != "entries" and key != "following_words"
        },
        "table_records": {
            "entry_count": len(records),
            "unique_target_count": len({record["record_file_offset"] for record in records}),
            "target_file_offset_min": min(record["record_file_offset"] for record in records),
            "target_file_offset_max": max(record["record_file_offset"] for record in records),
            "pointer_table_gba_range": [hex_address(table_start), hex_address(table_end)],
            "record_target_gba_range": [
                hex_address(gba_address(int(min(record["record_file_offset"] for record in records), 16))),
                hex_address(gba_address(int(max(record["record_file_offset"] for record in records), 16))),
            ],
            "payload_length_counts": dict(sorted(structure_counts.items(), key=lambda pair: int(pair[0]))),
            "shift_jis_valid_count": shift_jis_valid,
            "nul_terminated_count": len(records),
            "records_with_line_feed": line_feed_records,
            "format_counts": dict(sorted(format_counts.items())),
            "unknown_format_counts": dict(sorted(unknown_format_counts.items())),
            "opaque_control_byte_counts": dict(sorted(opaque_counts.items())),
        },
        "reference_search": {
            "table_base_value_hits": [hex_offset(offset) for offset in direct_word_hits(data, table_start)],
            "table_entry_range_word_hits": table_range_word_hits(data, table_start, table_end),
            "entry_zero_target_word_hits": [hex_offset(offset) for offset in direct_word_hits(data, gba_address(0x078528))],
        },
        "consumer_chain": analyze_consumer_chain(data),
    }


def extract_records(data: bytes) -> list[dict[str, object]]:
    boundary = parse_table_b_boundary(data)
    extracted = []
    for record in table_b_records(data, boundary):
        structure = record_structure(record["payload"])
        extracted.append({
            "string_id": f"b3ej:table-b:{record['entry']:03d}",
            "locale": "ja-JP",
            "text": structure.pop("text"),
            "provenance": {
                "status": "confirmed-static",
                "method": "bounded-absolute-pointer-table",
                "table": "menu_battle_candidate_a",
                "table_file_offset": record["pointer_file_offset"],
                "entry": record["entry"],
                "record_file_offset": record["record_file_offset"],
                "record_gba_address": record["record_gba_address"],
                "terminator": "0x00",
                **structure,
            },
        })
    return extracted
