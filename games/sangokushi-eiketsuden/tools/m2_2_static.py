#!/usr/bin/env python3
"""Source-safe static analysis for the B3EJ M2.2 text-to-glyph pipeline.

The report contains only function boundaries, call targets, RAM/ROM
addresses, counts, hashes and Unicode codepoint identities for three small
sentinels.  It never writes or prints the complete table-B source strings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Iterable


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE

FORMATTER_START = 0x000D3FC
FORMATTER_END = 0x000D6B6
FORMATTER_VENEER = 0x006ED80
FORMATTER_WRITER_LITERAL_SLOT = 0x000D904
OUTPUT_WRITER_START = 0x000CAD8
OUTPUT_WRITER_END = 0x000CE06
OUTPUT_WRITER_NEXT_FUNCTION = 0x000CE1C

SJIS_RENDERER_START = 0x0008D18
SJIS_RENDERER_END = 0x0008D6C
CODEPAGE_LOOKUP_START = 0x00650A4
CODEPAGE_LOOKUP_END = 0x00650DC
GLYPH_EXPAND_START = 0x00650DC
GLYPH_EXPAND_END = 0x0065254
VRAM_SETUP_START = 0x0065058
VRAM_SETUP_END = 0x0065096
VRAM_COPY_START = 0x00656D4
VRAM_COPY_END = 0x00656EA
TILEMAP_WRITER_START = 0x0008914
TILEMAP_WRITER_END = 0x000896C
COPY_HELPER_START = 0x0000214
COPY_HELPER_END = 0x000022A

CODEPAGE_TABLE_FILE_OFFSET = 0x024110C
CODEPAGE_TABLE_GBA = ROM_BASE + CODEPAGE_TABLE_FILE_OFFSET
CODEPAGE_LAST_INDEX = 0x729
GLYPH_SOURCE_BASES = (0x08232BCC, 0x0822468C)
GLYPH_STRIDE = 0x20
GLYPH_CACHE_BASE = 0x02000000
GLYPH_CACHE_BYTES = 0x80
VRAM_BASE = 0x06000000
TILEMAP_BASE = 0x02013050

CONSUMER_ENTRY = 0x026054
CONSUMER_INDEX_SETUP = 0x0262D8
CONSUMER_RECORD_BYTE = 0x0262FA
CONSUMER_RECORD_LOAD = 0x026306
CONSUMER_WRAPPER_CALL = 0x026308
CONSUMER_CASE_END = 0x02634C

SENTINELS = (
    (0, "U+90E8", 0x9594),  # 部
    (0, "U+306B", 0x82C9),  # に
    (0, "U+529B", 0x97CD),  # 力
)


def _address(file_offset: int) -> int:
    return ROM_BASE + file_offset


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def _read_u16(data: bytes, file_offset: int) -> int:
    return struct.unpack_from("<H", data, file_offset)[0]


def _read_u32(data: bytes, file_offset: int) -> int:
    return struct.unpack_from("<I", data, file_offset)[0]


def _instruction_map(data: bytes, start: int, end: int) -> dict[int, object]:
    md = common._thumb_disassembler()
    return {
        instruction.address: instruction
        for instruction in md.disasm(data[start:end], _address(start))
    }


def _is_terminal(instruction: object) -> bool:
    mnemonic = instruction.mnemonic
    operands = instruction.op_str.replace(" ", "")
    if mnemonic == "bx":
        return True
    if mnemonic == "pop" and "pc" in operands:
        return True
    if mnemonic == "mov" and operands.startswith("pc,"):
        return True
    return False


def reachable_thumb_function(
    data: bytes,
    start: int,
    scan_end: int,
    expected_end: int,
) -> dict[str, object]:
    """Follow direct Thumb control flow and exclude inline literal/data pools."""

    instructions = _instruction_map(data, start, scan_end)
    work = [_address(start)]
    reachable: set[int] = set()
    calls: list[dict[str, object]] = []
    branch_targets: list[dict[str, object]] = []

    while work:
        address = work.pop()
        if address in reachable or address not in instructions:
            continue
        reachable.add(address)
        instruction = instructions[address]
        target = common.branch_target(instruction)
        next_address = address + instruction.size

        if instruction.mnemonic in {"bl", "blx"}:
            if target is not None:
                calls.append({
                    "file_offset": _offset(address - ROM_BASE),
                    "instruction": common.instruction_summary(instruction),
                    "target": _hex(target),
                })
            if next_address in instructions:
                work.append(next_address)
            continue

        if target is not None:
            branch_targets.append({
                "file_offset": _offset(address - ROM_BASE),
                "instruction": common.instruction_summary(instruction),
                "target": _hex(target),
            })
            if target in instructions:
                work.append(target)
            if instruction.mnemonic != "b" and next_address in instructions:
                work.append(next_address)
            continue

        if _is_terminal(instruction):
            continue
        if next_address in instructions:
            work.append(next_address)

    if not reachable:
        raise common.StaticContractError(f"empty Thumb function at {_offset(start)}")
    actual_end = max(reachable) - ROM_BASE + 2
    if actual_end != expected_end:
        raise common.StaticContractError(
            f"function {_offset(start)} ended at {_offset(actual_end)}, "
            f"expected {_offset(expected_end)}"
        )

    return {
        "file_start": _offset(start),
        "file_end_exclusive": _offset(expected_end),
        "gba_start": _hex(_address(start)),
        "gba_end_exclusive": _hex(_address(expected_end)),
        "instruction_count": len(reachable),
        "all_reachable_instructions_decoded": True,
        "call_sites": sorted(calls, key=lambda row: row["file_offset"]),
        "branch_targets": sorted(branch_targets, key=lambda row: row["file_offset"]),
        "return_sites": [
            {
                "file_offset": _offset(address - ROM_BASE),
                "instruction": common.instruction_summary(instructions[address]),
            }
            for address in sorted(reachable)
            if _is_terminal(instructions[address])
        ],
        "excluded_non_code_count": len(set(instructions) - reachable),
    }


def _exact_span(data: bytes, start: int, end: int) -> dict[str, object]:
    instructions = common.disassemble_thumb_span(data, start, end)
    call_sites = []
    for instruction in instructions:
        target = common.branch_target(instruction)
        if target is not None and instruction.mnemonic in {"bl", "blx"}:
            call_sites.append({
                "file_offset": _offset(instruction.address - ROM_BASE),
                "instruction": common.instruction_summary(instruction),
                "target": _hex(target),
            })
    return {
        "file_start": _offset(start),
        "file_end_exclusive": _offset(end),
        "gba_start": _hex(_address(start)),
        "gba_end_exclusive": _hex(_address(end)),
        "instruction_count": len(instructions),
        "all_instructions_decoded": True,
        "first_instruction": common.instruction_summary(instructions[0]),
        "last_instruction": common.instruction_summary(instructions[-1]),
        "call_sites": call_sites,
    }


def _reachable_instruction(data: bytes, report: dict[str, object], file_offset: int) -> object:
    start = int(str(report["file_start"]), 16)
    end = int(str(report["file_end_exclusive"]), 16)
    instructions = _instruction_map(data, start, end)
    instruction = instructions.get(_address(file_offset))
    if instruction is None:
        raise common.StaticContractError(f"instruction not reachable at {_offset(file_offset)}")
    return instruction


def _literal_refs(data: bytes, report: dict[str, object]) -> list[dict[str, object]]:
    start = int(str(report["file_start"]), 16)
    end = int(str(report["file_end_exclusive"]), 16)
    instructions = _instruction_map(data, start, end)
    refs = []
    for instruction in instructions.values():
        if instruction.mnemonic != "ldr" or "[pc" not in instruction.op_str:
            continue
        file_offset = instruction.address - ROM_BASE
        halfword = _read_u16(data, file_offset)
        literal_address = common.thumb_literal_target(file_offset, halfword)
        literal_offset = literal_address - ROM_BASE
        value = _read_u32(data, literal_offset) if 0 <= literal_offset <= len(data) - 4 else None
        refs.append({
            "instruction_file_offset": _offset(file_offset),
            "instruction": common.instruction_summary(instruction),
            "literal_slot": _hex(literal_address),
            "literal_value": None if value is None else _hex(value),
        })
    return sorted(refs, key=lambda row: row["instruction_file_offset"])


def _calls(report: dict[str, object]) -> set[int]:
    return {
        int(str(call["target"]), 16)
        for call in report["call_sites"]
    }


def _require_call(report: dict[str, object], file_offset: int, target: int) -> None:
    for call in report["call_sites"]:
        if int(str(call["file_offset"]), 16) == file_offset:
            if int(str(call["target"]), 16) != target:
                raise common.StaticContractError(
                    f"call at {_offset(file_offset)} changed: {call}"
                )
            return
    raise common.StaticContractError(f"missing call at {_offset(file_offset)}")


def _require_instruction(
    data: bytes,
    report: dict[str, object],
    file_offset: int,
    mnemonic: str,
    contains: str = "",
) -> object:
    instruction = _reachable_instruction(data, report, file_offset)
    if instruction.mnemonic != mnemonic or contains not in instruction.op_str:
        raise common.StaticContractError(
            f"unexpected instruction at {_offset(file_offset)}: "
            f"{common.instruction_summary(instruction)}"
        )
    return instruction


def _find_codepage_index(data: bytes, code: int) -> int:
    for index in range(CODEPAGE_LAST_INDEX + 1):
        if _read_u16(data, CODEPAGE_TABLE_FILE_OFFSET + index * 2) == code:
            return index
    raise common.StaticContractError(f"SJIS code not in reviewed codepage table: 0x{code:04X}")


def _sentinel_report(data: bytes, records: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for entry, codepoint, code in SENTINELS:
        payload = records[entry]["payload"]
        encoded = chr(int(codepoint[2:], 16)).encode("shift_jis")
        positions = [
            offset for offset in range(0, len(payload) - len(encoded) + 1)
            if payload[offset:offset + len(encoded)] == encoded
        ]
        if len(positions) != 1:
            raise common.StaticContractError(
                f"sentinel {codepoint} occurrence count is {len(positions)} in B[{entry}]"
            )
        codepage_index = _find_codepage_index(data, code)
        source_offsets = []
        for base in GLYPH_SOURCE_BASES:
            # The lookup returns the codepage-table index in r1.  The glyph
            # expander saves that index and uses it as the 0x20-byte stride;
            # it does not index the source font by the raw Shift-JIS value.
            source_offset = base - ROM_BASE + codepage_index * GLYPH_STRIDE
            glyph = data[source_offset:source_offset + GLYPH_STRIDE]
            if len(glyph) != GLYPH_STRIDE or not any(glyph):
                raise common.StaticContractError(
                    f"glyph source missing or blank for {codepoint}: {_offset(source_offset)}"
                )
            source_offsets.append({
                "file_offset": _offset(source_offset),
                "gba_address": _hex(_address(source_offset)),
                "byte_length": len(glyph),
                "nonzero_byte_count": sum(value != 0 for value in glyph),
                "sha256": hashlib.sha256(glyph).hexdigest(),
            })
        result.append({
            "record_entry": entry,
            "record_byte_offset": positions[0],
            "unicode_codepoint": codepoint,
            "sjis_code": f"0x{code:04X}",
            "codepage_table_file_offset": _offset(
                CODEPAGE_TABLE_FILE_OFFSET + codepage_index * 2
            ),
            "codepage_table_index": codepage_index,
            "glyph_source_stride": GLYPH_STRIDE,
            "glyph_sources": source_offsets,
            "formatter_to_renderer_status": "confirmed-static",
            "runtime_glyph_hit": "pending",
        })
    return result


def analyze_m2_2(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        raise common.StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != "B3EJ":
        raise common.StaticContractError(f"unexpected game code: {game_code!r}")

    boundary = common.parse_table_b_boundary(data)
    records = common.table_b_records(data, boundary)

    formatter = _exact_span(data, FORMATTER_START, FORMATTER_END)
    wrapper = _exact_span(data, common.RECORD_WRAPPER_ADDRESS, 0x000D904)
    veneer = _exact_span(data, FORMATTER_VENEER, FORMATTER_VENEER + 2)
    output_writer = reachable_thumb_function(
        data, OUTPUT_WRITER_START, 0x000CE1C, OUTPUT_WRITER_END
    )
    sjis_renderer = _exact_span(data, SJIS_RENDERER_START, SJIS_RENDERER_END)
    codepage_lookup = reachable_thumb_function(
        data, CODEPAGE_LOOKUP_START, CODEPAGE_LOOKUP_END, CODEPAGE_LOOKUP_END
    )
    glyph_expand = reachable_thumb_function(
        data, GLYPH_EXPAND_START, GLYPH_EXPAND_END, GLYPH_EXPAND_END
    )
    vram_setup = reachable_thumb_function(
        data, VRAM_SETUP_START, VRAM_SETUP_END, VRAM_SETUP_END
    )
    vram_copy = _exact_span(data, VRAM_COPY_START, VRAM_COPY_END)
    tilemap_writer = _exact_span(data, TILEMAP_WRITER_START, TILEMAP_WRITER_END)
    copy_helper = _exact_span(data, COPY_HELPER_START, COPY_HELPER_END)

    _require_call(formatter, 0x000D6A2, _address(FORMATTER_VENEER))
    _require_call(wrapper, 0x000D8FA, _address(FORMATTER_START))
    _require_call(output_writer, 0x000CB62, _address(SJIS_RENDERER_START))
    _require_call(output_writer, 0x000CBAA, _address(0x0018164))
    _require_call(output_writer, 0x000CC1A, _address(0x0008E50))
    _require_call(sjis_renderer, 0x0008D48, _address(0x00650A4))
    _require_call(sjis_renderer, 0x0008D4C, _address(VRAM_COPY_START))
    _require_call(sjis_renderer, 0x0008D58, _address(TILEMAP_WRITER_START))
    _require_call(codepage_lookup, 0x00650D2, _address(GLYPH_EXPAND_START))
    _require_call(vram_copy, 0x00656E2, _address(COPY_HELPER_START))
    _require_instruction(data, glyph_expand, 0x00650EC, "str", "[sp]")
    _require_instruction(data, glyph_expand, 0x0065108, "lsls", "r6, #5")

    wrapper_literal = _read_u32(data, FORMATTER_WRITER_LITERAL_SLOT)
    if wrapper_literal != _address(OUTPUT_WRITER_START) | 1:
        raise common.StaticContractError(
            f"formatter writer pointer changed: {_hex(wrapper_literal)}"
        )
    if common.instruction_summary(_reachable_instruction(data, veneer, FORMATTER_VENEER)) != "bx r2":
        raise common.StaticContractError("formatter veneer is no longer bx r2")

    lookup_literals = _literal_refs(data, codepage_lookup)
    glyph_literals = _literal_refs(data, glyph_expand)
    setup_literals = _literal_refs(data, vram_setup)
    tilemap_literals = [
        row for row in _literal_refs(data, {
            "file_start": _offset(TILEMAP_WRITER_START),
            "file_end_exclusive": _offset(TILEMAP_WRITER_END),
        })
    ]
    lookup_literal_values = {row["literal_value"] for row in lookup_literals}
    if _hex(CODEPAGE_TABLE_GBA) not in lookup_literal_values:
        raise common.StaticContractError("codepage table literal is not referenced")
    if _hex(CODEPAGE_LAST_INDEX) not in lookup_literal_values:
        raise common.StaticContractError("codepage count literal is not referenced")
    glyph_literal_values = {row["literal_value"] for row in glyph_literals}
    for base in GLYPH_SOURCE_BASES:
        if _hex(base) not in glyph_literal_values:
            raise common.StaticContractError(f"glyph source literal missing: {_hex(base)}")

    consumer = common.analyze_consumer_chain(data)
    consumer_index = {
        "entry_file_offset": _offset(CONSUMER_ENTRY),
        "entry_argument": "r0 -> r6 at 0x0802605E",
        "index_formula": "u16(r6+0x06) * u16(r6+0x08) + u16(r6+0x00) + u16(r6+0x04)",
        "local_bound_field": "u16(r6+0x02)",
        "local_bound_branch": "bge 0x08026340 before [r6+0x1C] + index",
        "record_byte_base_field": "u32(r6+0x1C)",
        "effective_table_index": "u8(record_byte) & 0x7F",
        "table_entry_count": boundary["entry_count"],
        "status": "not-proven",
        "reason": "The reviewed structure only proves index < u16(r6+0x02); no static relation from that field or the r6 upstream caller to 44 was found.",
        "runtime_metadata_required": [
            "actual_index",
            "event_array_index",
            "masked_table_index",
            "r6_base",
            "u16_fields_at_r6_plus_0x00_0x02_0x04_0x06_0x08",
            "record_byte_base",
            "caller_lr",
        ],
    }

    sentinel_report = _sentinel_report(data, records)
    pipeline = {
        "formatter": {
            **formatter,
            "input": "r0 source record pointer",
            "local_output_buffer": "formatter stack +0x18",
            "local_frame_bytes": 0xC8,
            "terminator": "0x00",
            "output_call": _hex(_address(FORMATTER_VENEER)),
        },
        "formatter_veneer": {
            **veneer,
            "instruction": "bx r2",
            "wrapper_literal_slot": _hex(_address(FORMATTER_WRITER_LITERAL_SLOT)),
            "wrapper_literal_value": _hex(wrapper_literal),
            "resolved_writer": _hex(_address(OUTPUT_WRITER_START)),
        },
        "output_writer": {
            **output_writer,
            "next_function_prologue": _hex(_address(OUTPUT_WRITER_NEXT_FUNCTION)),
            "literal_pool_after_function": [_offset(x) for x in range(0x000CE06, 0x000CE1C, 4)],
            "sjis_lead_path": {
                "lead_checks": [_offset(0x000CB0C), _offset(0x000CB18)],
                "code_unit_build": [_offset(0x000CB24), _offset(0x000CB28)],
                "renderer_call": _hex(_address(SJIS_RENDERER_START)),
            },
            "calls": {
                "sjis_renderer": _hex(_address(SJIS_RENDERER_START)),
                "ascii_renderer": _hex(_address(0x0018164)),
                "mapped_single_byte_renderer": _hex(_address(0x0008E50)),
            },
        },
        "sjis_renderer": {
            **sjis_renderer,
            "codepage_lookup": _hex(_address(CODEPAGE_LOOKUP_START)),
            "glyph_cache_copy": _hex(_address(VRAM_COPY_START)),
            "tilemap_writer": _hex(_address(TILEMAP_WRITER_START)),
        },
        "codepage_lookup": {
            **codepage_lookup,
            "literal_refs": lookup_literals,
            "table_file_offset": _offset(CODEPAGE_TABLE_FILE_OFFSET),
            "table_gba_address": _hex(CODEPAGE_TABLE_GBA),
            "last_index_literal": _hex(CODEPAGE_LAST_INDEX),
            "entry_count_inclusive": CODEPAGE_LAST_INDEX + 1,
            "operation": "linear membership lookup of 16-bit SJIS code unit",
        },
        "glyph_expand": {
            **glyph_expand,
            "literal_refs": glyph_literals,
            "source_bases": [_hex(base) for base in GLYPH_SOURCE_BASES],
            "source_formula": "glyph_source = base + codepage_table_index * 0x20",
            "codepage_index_evidence": {
                "lookup_match_returns_index": _offset(0x00650D0),
                "index_saved_to_stack": _offset(0x00650EC),
                "index_stride_multiply": _offset(0x0065108),
            },
            "cache_base": _hex(GLYPH_CACHE_BASE),
            "expanded_bytes": GLYPH_CACHE_BYTES,
        },
        "vram_path": {
            "setup": {**vram_setup, "literal_refs": setup_literals},
            "copy": {**vram_copy, "helper": {**copy_helper}},
            "destination_formula": "0x06000000 + (r1 << 5) + (3 << 14) from 0x08065058",
            "copy_source": _hex(GLYPH_CACHE_BASE),
            "copy_length_formula": "r2 bytes at copy helper; setup stores renderer tile units (4) << 5 = 0x80",
            "tilemap_writer": {**tilemap_writer, "literal_refs": tilemap_literals, "base": _hex(TILEMAP_BASE)},
        },
        "sentinels": sentinel_report,
    }

    return {
        "read_only": True,
        "rom": {"size_bytes": len(data), "game_code": game_code},
        "function_boundaries": {
            "formatter": formatter,
            "wrapper": wrapper,
            "formatter_veneer": veneer,
            "output_writer": output_writer,
            "sjis_renderer": sjis_renderer,
            "codepage_lookup": codepage_lookup,
            "glyph_expand": glyph_expand,
            "vram_setup": vram_setup,
            "vram_copy": vram_copy,
            "tilemap_writer": tilemap_writer,
            "copy_helper": copy_helper,
        },
        "consumer_index": consumer_index,
        "consumer_static_baseline": consumer,
        "pipeline": pipeline,
        "glyph_addressing": {
            "status": "confirmed-static-addressing; runtime-write-observation-pending",
            "source_bases": [_hex(base) for base in GLYPH_SOURCE_BASES],
            "stride": GLYPH_STRIDE,
            "cache": _hex(GLYPH_CACHE_BASE),
            "vram": _hex(VRAM_BASE),
            "tilemap": _hex(TILEMAP_BASE),
        },
        "unicode_identity": {
            "status": "confirmed-static-for-three-sjis-sentinels; runtime-glyph-identity-pending",
            "sentinel_count": len(sentinel_report),
            "codepoints": [row["unicode_codepoint"] for row in sentinel_report],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_m2_2(args.rom.read_bytes())
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
