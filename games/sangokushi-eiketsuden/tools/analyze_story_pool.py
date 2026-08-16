#!/usr/bin/env python3
"""Analyze the pointer-referenced B3EJ story/event text pool.

The pool at file offset 0x0CDB64 is kept separate from the four earlier
candidate pools until its static consumer is documented.  This tool verifies
its 33-entry boundary, reports source-safe record metadata, and checks the
Thumb literal/call chain through the existing text writer.  It deliberately
does not print or save original text, payload bytes or glyph data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

try:
    import capstone
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("capstone is required for the B3J story pool analyzer") from exc


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
STORY_TABLE_OFFSET = 0x0CDB64
STORY_ENTRY_COUNT = 33
STORY_TABLE_END = STORY_TABLE_OFFSET + STORY_ENTRY_COUNT * 4
STORY_TABLE_LITERAL_OFFSET = 0x011990
STORY_CALLER_SPAN = (0x01192C, 0x011BE8)
WRITER_HELPER_SPAN = (0x0118C8, 0x0118F0)
RECORD_PAIR_HELPER_SPAN = (0x011904, 0x01192C)
WRITER_ADDRESS = 0x0800CAD8
RECORD_PAIR_HELPER_ADDRESS = 0x08011904
WRITER_HELPER_ADDRESS = 0x080118C8
STORY_LITERAL_SLOTS = (
    0x011990, 0x011994, 0x011998, 0x01199C, 0x0119A0, 0x0119B0, 0x0119B4,
    0x011A08, 0x011A0C, 0x011A10, 0x011A14, 0x011A18, 0x011A28, 0x011A2C,
    0x011A3C, 0x011A40, 0x011AA0, 0x011AA8, 0x011AAC, 0x011B08, 0x011B10,
    0x011B18, 0x011B28, 0x011B2C, 0x011B94, 0x011B9C, 0x011BA0,
)


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise common.StaticContractError(f"word outside ROM at 0x{offset:06X}")
    return struct.unpack_from("<I", data, offset)[0]


def _thumb_calls(data: bytes, span: tuple[int, int]) -> list[dict[str, object]]:
    start, end = span
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    calls = []
    for instruction in md.disasm(data[start:end], ROM_BASE + start):
        if instruction.mnemonic != "bl":
            continue
        try:
            target = int(instruction.op_str.lstrip("#"), 0)
        except ValueError:
            continue
        calls.append({
            "callsite_gba_address": f"0x{instruction.address:08X}",
            "target_gba_address": f"0x{target:08X}",
        })
    return calls


def _record_metadata(data: bytes, target: int) -> dict[str, object]:
    payload, terminator = common.read_c_string(data, target)
    structure = common.record_structure(payload)
    return {
        "record_file_offset": common.hex_offset(target),
        "record_gba_address": common.hex_address(ROM_BASE + target),
        "terminator_file_offset": common.hex_offset(terminator),
        "payload_length": len(payload),
        "source_hash": hashlib.sha256(payload).hexdigest(),
        "shift_jis_decodable": bool(structure["shift_jis_decodable"]),
        "line_feed_count": int(structure["line_feed_count"]),
        "format_counts": dict(structure["format_counts"]),
        "unknown_format_counts": dict(structure["unknown_format_counts"]),
        "opaque_control_byte_counts": dict(structure["opaque_control_byte_counts"]),
    }


def story_pool_boundary(data: bytes) -> dict[str, object]:
    if STORY_TABLE_END + 8 > len(data):
        raise common.StaticContractError("story table exceeds ROM")
    previous_word = _u32(data, STORY_TABLE_OFFSET - 4)
    pointers = [_u32(data, STORY_TABLE_OFFSET + index * 4) for index in range(STORY_ENTRY_COUNT)]
    if any(not common.is_rom_pointer(pointer, len(data)) for pointer in pointers):
        raise common.StaticContractError("story table contains a non-ROM pointer")
    targets = [pointer - ROM_BASE for pointer in pointers]
    records = [_record_metadata(data, target) for target in targets]
    next_word = _u32(data, STORY_TABLE_END)
    following_word = _u32(data, STORY_TABLE_END + 4)
    if common.is_rom_pointer(previous_word, len(data)):
        raise common.StaticContractError("story table has a preceding ROM pointer")
    if common.is_rom_pointer(next_word, len(data)):
        raise common.StaticContractError("story table did not stop before the next structure")
    return {
        "table_file_offset": common.hex_offset(STORY_TABLE_OFFSET),
        "table_gba_address": common.hex_address(ROM_BASE + STORY_TABLE_OFFSET),
        "entry_count": STORY_ENTRY_COUNT,
        "table_end_file_offset_exclusive": common.hex_offset(STORY_TABLE_END),
        "previous_word": f"0x{previous_word:08X}",
        "next_word": f"0x{next_word:08X}",
        "following_word": f"0x{following_word:08X}",
        "unique_target_count": len(set(targets)),
        "target_file_offset_min": common.hex_offset(min(targets)),
        "target_file_offset_max": common.hex_offset(max(targets)),
        "record_metadata": [
            {"entry": entry, **record} for entry, record in enumerate(records)
        ],
        "payload_length_counts": dict(sorted(Counter(record["payload_length"] for record in records).items())),
        "records_with_line_feed": sum(record["line_feed_count"] > 0 for record in records),
        "shift_jis_valid_count": sum(record["shift_jis_decodable"] for record in records),
        "opaque_control_byte_counts": dict(sorted(
            Counter(
                control
                for record in records
                for control, count in record["opaque_control_byte_counts"].items()
                for _ in range(int(count))
            ).items()
        )),
    }


def static_chain(data: bytes) -> dict[str, object]:
    literal = _u32(data, STORY_TABLE_LITERAL_OFFSET)
    if literal != ROM_BASE + STORY_TABLE_OFFSET:
        raise common.StaticContractError("story table literal does not match table base")
    literal_rows = []
    table_start = ROM_BASE + STORY_TABLE_OFFSET
    table_end = ROM_BASE + STORY_TABLE_END
    for slot in STORY_LITERAL_SLOTS:
        value = _u32(data, slot)
        if not table_start <= value < table_end or (value - table_start) % 4:
            raise common.StaticContractError(f"literal slot 0x{slot:06X} is not a story pointer")
        literal_rows.append({
            "literal_file_offset": common.hex_offset(slot),
            "literal_gba_address": common.hex_address(ROM_BASE + slot),
            "value": common.hex_address(value),
            "entry": (value - table_start) // 4,
        })
    helper_calls = _thumb_calls(data, WRITER_HELPER_SPAN)
    pair_calls = _thumb_calls(data, RECORD_PAIR_HELPER_SPAN)
    caller_calls = _thumb_calls(data, STORY_CALLER_SPAN)
    if not any(int(row["target_gba_address"], 16) == WRITER_ADDRESS for row in helper_calls):
        raise common.StaticContractError("writer helper does not call 0x0800CAD8")
    if not any(int(row["target_gba_address"], 16) == WRITER_HELPER_ADDRESS for row in pair_calls):
        raise common.StaticContractError("record-pair helper does not call writer helper")
    return {
        "table_literal": {
            "literal_file_offset": common.hex_offset(STORY_TABLE_LITERAL_OFFSET),
            "literal_gba_address": common.hex_address(ROM_BASE + STORY_TABLE_LITERAL_OFFSET),
            "value": common.hex_address(literal),
        },
        "literal_slots": literal_rows,
        "caller_span": [common.hex_offset(value) for value in STORY_CALLER_SPAN],
        "record_pair_helper_span": [common.hex_offset(value) for value in RECORD_PAIR_HELPER_SPAN],
        "writer_helper_span": [common.hex_offset(value) for value in WRITER_HELPER_SPAN],
        "caller_calls": caller_calls,
        "record_pair_helper_calls": pair_calls,
        "writer_helper_calls": helper_calls,
        "chain": [
            common.hex_address(literal),
            common.hex_address(RECORD_PAIR_HELPER_ADDRESS),
            common.hex_address(WRITER_HELPER_ADDRESS),
            common.hex_address(WRITER_ADDRESS),
        ],
        "reachability": "static-consumer-confirmed; natural-runtime-pending",
    }


def analyze(data: bytes) -> dict[str, object]:
    boundary = story_pool_boundary(data)
    chain = static_chain(data)
    return {
        "read_only": True,
        "pool": "story-event",
        "decoder_version": "b3ej-story-pool-v1",
        "boundary": boundary,
        "static_chain": chain,
        "note": "Metadata only; original text and raw glyph bytes are intentionally omitted.",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = analyze(args.rom.read_bytes())
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "read_only": report["read_only"],
        "pool": report["pool"],
        "entry_count": report["boundary"]["entry_count"],
        "unique_target_count": report["boundary"]["unique_target_count"],
        "chain": report["static_chain"]["chain"],
        "reachability": report["static_chain"]["reachability"],
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
