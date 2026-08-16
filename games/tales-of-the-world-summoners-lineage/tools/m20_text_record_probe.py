#!/usr/bin/env python3
"""Metadata-only A9PJ text-record and code-unit probe.

This probe records the part of the text path that is already supported by
static control-flow evidence, without exporting source bytes or decoded
Japanese.  It deliberately keeps these questions separate:

* ``glyph_addressing``: a 16-bit renderer input indexes a 24-byte record table;
* ``glyph_identity``: the keyboard table confirms two runtime-backed identities,
  while the renderer transfer gate remains provisional;
* ``codepage``: the renderer's index width is known, but it is not Unicode or
  a general Japanese mapping;
* ``control_code``: the null terminator and ``0xFF70`` parser branch are
  recorded as behavior candidates, not translated text.

The optional pointer scan only emits aggregate stream metadata and stable
candidate IDs.  A private caller may use the same functions to create a
local, ignored source table after a later runtime/context gate.  No function
prints code-unit sequences or source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Iterable


DECODER_VERSION = "m20-text-record-probe-20260816.v1"
ROM_BASE = 0x08000000
EXPECTED_ROM_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"

FONT_RECORD_BUS_BASE = 0x08089E00
FONT_RECORD_FILE_BASE = FONT_RECORD_BUS_BASE - ROM_BASE
FONT_RECORD_STRIDE = 0x18
FONT_RECORD_HALFWORDS = FONT_RECORD_STRIDE // 2
FONT_RECORD_INDEX_MAX = 0xFFFF

NULL_CODE_UNIT = 0x0000
LINE_ADVANCE_CODE_UNIT = 0xFF70

# These are addresses of instructions, not guessed function names.  The
# disassembly and M1.6/M1.7 runtime receipts are the provenance for these
# fields; keeping them here makes the emitted report self-describing.
TEXT_RENDERER_ENTRY = 0x080049A0
TEXT_RENDERER_INDEX_ARITHMETIC = 0x080049C8
TEXT_RENDERER_FONT_LITERAL = 0x08004B00
TEXT_RENDERER_RECORD_READ_SITES = (0x08004A3A, 0x08004B16)
TEXT_STREAM_FUNCTION_ENTRY = 0x0800638C
TEXT_STREAM_LDRH = 0x080063B6
TEXT_STREAM_RENDERER_BL = 0x080063C2
TEXT_STREAM_CONTROL_FUNCTION = 0x080063E0
TEXT_STREAM_TERMINATOR_COMPARE = 0x08006404
TEXT_STREAM_CONTROL_COMPARE = 0x0800640E
TEXT_STREAM_LINE_SKIP = 0x08006410
TEXT_STREAM_LINE_RESET = 0x08006412
TEXT_STREAM_LINE_ADVANCE = 0x08006414
TEXT_STREAM_CONTROL_BRANCH = 0x08006416

# A separate packed-layout caller loads an 8-bit value before calling the same
# renderer.  It is useful negative/contrast evidence: it must not be silently
# merged with the 16-bit text-stream path.
PACKED_CALLER_LDRB = 0x080048DC
PACKED_CALLER = 0x080048E4

DEFAULT_TARGET_START = 0x1F0000
DEFAULT_TARGET_END = 0x2C0000
DEFAULT_SCAN_START = 0
DEFAULT_SCAN_END = 0x800000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex_offset(value: int) -> str:
    return f"0x{value:X}"


def font_record_file_offset(code_unit: int) -> int:
    """Return the clean-ROM file offset for an unsigned 16-bit index."""

    if not 0 <= code_unit <= FONT_RECORD_INDEX_MAX:
        raise ValueError("code unit must fit an unsigned 16-bit value")
    return FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE


def font_record_bus_address(code_unit: int) -> int:
    return ROM_BASE + font_record_file_offset(code_unit)


def font_record_table_end_file_offset() -> int:
    return font_record_file_offset(FONT_RECORD_INDEX_MAX) + FONT_RECORD_STRIDE


def code_unit_class(code_unit: int) -> str:
    if not 0 <= code_unit <= FONT_RECORD_INDEX_MAX:
        raise ValueError("code unit must fit an unsigned 16-bit value")
    if code_unit == NULL_CODE_UNIT:
        return "terminator"
    if code_unit == LINE_ADVANCE_CODE_UNIT:
        return "control-candidate"
    return "font-record-index"


def record_metadata(data: bytes, code_unit: int) -> dict[str, object]:
    """Summarize one 24-byte record without returning its rows or bytes."""

    offset = font_record_file_offset(code_unit)
    record = data[offset:offset + FONT_RECORD_STRIDE]
    if len(record) != FONT_RECORD_STRIDE:
        raise ValueError("font record is outside the supplied ROM")
    rows = [
        int.from_bytes(record[index:index + 2], "little")
        for index in range(0, FONT_RECORD_STRIDE, 2)
    ]
    nonzero_rows = [index for index, row in enumerate(rows) if row]
    # Keep the tool runnable on the system Python versions used by the
    # repository; ``int.bit_count`` is not available on all of them.
    bit_counts = [bin(row).count("1") for row in rows]
    return {
        "code_unit": f"0x{code_unit:04X}",
        "code_unit_class": code_unit_class(code_unit),
        "record_bus_address": f"0x{font_record_bus_address(code_unit):08X}",
        "record_file_offset": hex_offset(offset),
        "record_length": len(record),
        "record_halfword_count": len(rows),
        "record_sha256": sha256(record),
        "nonzero_halfword_count": sum(row != 0 for row in rows),
        "nonzero_row_range": None
        if not nonzero_rows
        else [nonzero_rows[0], nonzero_rows[-1]],
        "row_bit_count_min": min(bit_counts),
        "row_bit_count_max": max(bit_counts),
        "row_bit_count_total": sum(bit_counts),
        "row_width_bits": 16,
    }


def font_table_profile(
    data: bytes,
    *,
    start_code_unit: int = 0,
    end_code_unit: int = FONT_RECORD_INDEX_MAX + 1,
) -> dict[str, object]:
    """Profile table geometry and occupancy, never the record contents."""

    if not 0 <= start_code_unit <= end_code_unit <= FONT_RECORD_INDEX_MAX + 1:
        raise ValueError("invalid font table unit range")
    start = font_record_file_offset(start_code_unit)
    end = font_record_file_offset(end_code_unit - 1) + FONT_RECORD_STRIDE if end_code_unit else start
    if end > len(data):
        raise ValueError("font table range is outside the supplied ROM")

    nonzero_records = 0
    nonzero_halfwords = 0
    row_count = 0
    record_hashes: set[str] = set()
    for code_unit in range(start_code_unit, end_code_unit):
        offset = font_record_file_offset(code_unit)
        record = data[offset:offset + FONT_RECORD_STRIDE]
        record_hashes.add(sha256(record))
        rows = [
            int.from_bytes(record[index:index + 2], "little")
            for index in range(0, FONT_RECORD_STRIDE, 2)
        ]
        count = sum(row != 0 for row in rows)
        if count:
            nonzero_records += 1
            nonzero_halfwords += count
            row_count += len(rows)

    return {
        "file_range": [hex_offset(start), hex_offset(end)],
        "code_unit_range": [f"0x{start_code_unit:04X}", f"0x{end_code_unit - 1:04X}"],
        "record_stride": FONT_RECORD_STRIDE,
        "record_length": FONT_RECORD_STRIDE,
        "record_halfword_count": FONT_RECORD_HALFWORDS,
        "records_profiled": end_code_unit - start_code_unit,
        "nonzero_records": nonzero_records,
        "blank_records": (end_code_unit - start_code_unit) - nonzero_records,
        "nonzero_halfwords": nonzero_halfwords,
        "row_slots_in_nonzero_records": row_count,
        "distinct_record_sha256_count": len(record_hashes),
    }


def read_halfword_stream(
    data: bytes,
    target: int,
    *,
    max_units: int = 0x400,
) -> dict[str, object]:
    """Summarize a candidate 16-bit stream without exposing its units."""

    if not 0 <= target < len(data):
        raise ValueError("stream target is outside the supplied ROM")
    if max_units <= 0:
        raise ValueError("max_units must be positive")

    position = target
    units_read = 0
    terminated = False
    control_count = 0
    index_count = 0
    nonzero_count = 0
    min_unit: int | None = None
    max_unit: int | None = None
    raw_end = target
    classes: Counter[str] = Counter()

    while units_read < max_units and position + 2 <= len(data):
        code_unit = int.from_bytes(data[position:position + 2], "little")
        position += 2
        raw_end = position
        units_read += 1
        kind = code_unit_class(code_unit)
        classes[kind] += 1
        if code_unit == NULL_CODE_UNIT:
            terminated = True
            break
        nonzero_count += 1
        if code_unit == LINE_ADVANCE_CODE_UNIT:
            control_count += 1
        else:
            index_count += 1
            min_unit = code_unit if min_unit is None else min(min_unit, code_unit)
            max_unit = code_unit if max_unit is None else max(max_unit, code_unit)

    raw = data[target:raw_end]
    return {
        "target_file_offset": hex_offset(target),
        "byte_length": len(raw),
        "unit_count_including_terminator": units_read,
        "nonzero_unit_count": nonzero_count,
        "terminated_by_0000": terminated,
        "capped_or_truncated": not terminated,
        "control_candidate_count": control_count,
        "font_record_index_count": index_count,
        "font_record_index_min": None if min_unit is None else f"0x{min_unit:04X}",
        "font_record_index_max": None if max_unit is None else f"0x{max_unit:04X}",
        "class_counts": dict(sorted(classes.items())),
        "stream_sha256": sha256(raw),
    }


def find_pointer_references(
    data: bytes,
    *,
    scan_start: int,
    scan_end: int,
    target_start: int,
    target_end: int,
    alignment: int = 4,
) -> list[tuple[int, int]]:
    if alignment <= 0:
        raise ValueError("alignment must be positive")
    upper = min(scan_end, len(data) - 3)
    references: list[tuple[int, int]] = []
    for offset in range(scan_start, upper, alignment):
        value = struct.unpack_from("<I", data, offset)[0]
        target = value - ROM_BASE
        if target_start <= target < target_end:
            references.append((offset, target))
    return references


def stable_candidate_id(pointer_offset: int, target: int, byte_length: int) -> str:
    identity = f"a9pj:{DECODER_VERSION}:ptr={pointer_offset:x}:target={target:x}:len={byte_length:x}"
    return hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def candidate_metadata(
    data: bytes,
    references: Iterable[tuple[int, int]],
    *,
    max_units: int,
    limit: int,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[int] = set()
    for pointer_offset, target in references:
        if target in seen:
            continue
        seen.add(target)
        stream = read_halfword_stream(data, target, max_units=max_units)
        result.append(
            {
                "string_id": stable_candidate_id(
                    pointer_offset,
                    target,
                    int(stream["byte_length"]),
                ),
                "pointer_file_offset": hex_offset(pointer_offset),
                "stream": stream,
                "role": "unclassified-16-bit-candidate",
                "runtime_context": "none",
                "source_text_emitted": False,
            }
        )
        if len(result) >= limit:
            break
    return result


def parser_evidence() -> dict[str, object]:
    return {
        "renderer": {
            "entry_pc": f"0x{TEXT_RENDERER_ENTRY:08X}",
            "index_arithmetic_pc": f"0x{TEXT_RENDERER_INDEX_ARITHMETIC:08X}",
            "record_formula": "FONT_RECORD_BUS_BASE + (code_unit * 0x18)",
            "input_normalization": "r3 = (r3 << 16) >> 16",
            "record_read_sites": [f"0x{pc:08X}" for pc in TEXT_RENDERER_RECORD_READ_SITES],
            "font_literal_pc": f"0x{TEXT_RENDERER_FONT_LITERAL:08X}",
        },
        "codepage": {
            "status": "index-width-confirmed-mapping-unconfirmed",
            "primary_stream_width_bits": 16,
            "primary_stream_load_pc": f"0x{TEXT_STREAM_LDRH:08X}",
            "primary_stream_function_entry": f"0x{TEXT_STREAM_FUNCTION_ENTRY:08X}",
            "primary_stream_renderer_bl_pc": f"0x{TEXT_STREAM_RENDERER_BL:08X}",
            "name_entry_code_units": ["0x005E", "0x0066"],
            "name_entry_identity_status": "confirmed-for-row0-keyboard-table; transfer-gate-pending",
            "keyboard_table_bus_base": "0x0808884C",
            "keyboard_table_formula": "0x0808884C + 2 * (row * 65 + selection_index)",
            "keyboard_row0_confirmed_code_units": ["0x005E", "0x0062", "0x0066", "0x006B", "0x006F"],
            "keyboard_row0_confirmed_labels": ["あ", "い", "う", "え", "お"],
            "general_stream_mapping_confirmed": False,
            "alternate_packed_caller_load_width_bits": 8,
            "alternate_packed_caller_load_pc": f"0x{PACKED_CALLER_LDRB:08X}",
            "alternate_packed_caller_pc": f"0x{PACKED_CALLER:08X}",
            "note": "The 8-bit packed caller is not merged with the 16-bit text-stream codepage.",
        },
        "control_code": {
            "status": "parser-behavior-candidate",
            "terminator_code_unit": "0x0000",
            "terminator_compare_pc": f"0x{TEXT_STREAM_TERMINATOR_COMPARE:08X}",
            "line_advance_candidate_code_unit": "0xFF70",
            "control_compare_pc": f"0x{TEXT_STREAM_CONTROL_COMPARE:08X}",
            "behavior": {
                "skip_bytes": 2,
                "reset_horizontal_position": True,
                "vertical_advance": "0x0C",
            },
            "behavior_pcs": [
                f"0x{TEXT_STREAM_LINE_SKIP:08X}",
                f"0x{TEXT_STREAM_LINE_RESET:08X}",
                f"0x{TEXT_STREAM_LINE_ADVANCE:08X}",
                f"0x{TEXT_STREAM_CONTROL_BRANCH:08X}",
            ],
            "semantic_name": None,
            "runtime_sequence_confirmed": False,
        },
        "glyph_identity": {
            "confirmed_count": 2,
            "confirmed_code_units": ["0x005E", "0x0066"],
            "keyboard_table_only_code_units": ["0x0062", "0x006B", "0x006F"],
            "provisional_transfer_gate_code_units": ["0x005E", "0x0066"],
            "keyboard_asset_byte_receipt": False,
        },
    }


def probe(args: argparse.Namespace) -> dict[str, object]:
    data = args.rom.read_bytes()
    rom_hash = sha256(data)
    if args.scan_start < 0 or args.scan_end < args.scan_start:
        raise ValueError("invalid scan range")
    references = find_pointer_references(
        data,
        scan_start=args.scan_start,
        scan_end=min(args.scan_end, len(data)),
        target_start=args.target_start,
        target_end=args.target_end,
        alignment=args.alignment,
    )
    unique_targets = {target for _, target in references}
    stream_profiles = [
        read_halfword_stream(data, target, max_units=args.max_units)
        for target in sorted(unique_targets)
    ]
    report: dict[str, object] = {
        "decoder_version": DECODER_VERSION,
        "rom": {
            "path": str(args.rom),
            "sha256": rom_hash,
            "expected_a9pj_sha256_match": rom_hash == EXPECTED_ROM_SHA256,
            "file_size": len(data),
        },
        "scope": {
            "pointer_scan_file_range": [hex_offset(args.scan_start), hex_offset(min(args.scan_end, len(data)))],
            "pointer_alignment": args.alignment,
            "candidate_target_file_range": [hex_offset(args.target_start), hex_offset(args.target_end)],
            "max_units_per_candidate": args.max_units,
        },
        "font_table": {
            "bus_base": f"0x{FONT_RECORD_BUS_BASE:08X}",
            "file_base": hex_offset(FONT_RECORD_FILE_BASE),
            "stride": FONT_RECORD_STRIDE,
            "record_length": FONT_RECORD_STRIDE,
            "full_16bit_table_file_end": hex_offset(font_record_table_end_file_offset()),
            "full_16bit_table_fits_rom": font_record_table_end_file_offset() <= len(data),
            "profile": font_table_profile(data),
            "runtime_samples": [record_metadata(data, unit) for unit in (0x005E, 0x0066)],
        },
        "parser_evidence": parser_evidence(),
        "pointer_references": len(references),
        "distinct_pointer_targets": len(unique_targets),
        "candidate_profile": {
            "profiled_targets": len(stream_profiles),
            "nul_terminated_targets": sum(bool(item["terminated_by_0000"]) for item in stream_profiles),
            "capped_or_truncated_targets": sum(bool(item["capped_or_truncated"]) for item in stream_profiles),
            "targets_with_control_candidate": sum(
                int(item["control_candidate_count"]) > 0 for item in stream_profiles
            ),
            "control_candidate_occurrences": sum(
                int(item["control_candidate_count"]) for item in stream_profiles
            ),
            "targets_with_class": dict(
                sorted(
                    Counter(
                        key
                        for item in stream_profiles
                        for key in item["class_counts"]
                    ).items()
                )
            ),
            "class_occurrences": dict(
                sorted(
                    Counter(
                        key
                        for item in stream_profiles
                        for key, count in item["class_counts"].items()
                        for _ in range(int(count))
                    ).items()
                )
            ),
            "role": "unclassified; pointer geometry alone is not text proof",
        },
        "candidate_metadata_sample": candidate_metadata(
            data,
            references,
            max_units=args.max_units,
            limit=args.candidate_limit,
        ),
        "source_text_emitted": False,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=DEFAULT_SCAN_START)
    parser.add_argument("--scan-end", type=lambda value: int(value, 0), default=DEFAULT_SCAN_END)
    parser.add_argument("--target-start", type=lambda value: int(value, 0), default=DEFAULT_TARGET_START)
    parser.add_argument("--target-end", type=lambda value: int(value, 0), default=DEFAULT_TARGET_END)
    parser.add_argument("--alignment", type=int, default=4)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=0x400)
    parser.add_argument("--candidate-limit", type=lambda value: int(value, 0), default=32)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.candidate_limit < 0:
        parser.error("--candidate-limit must be non-negative")
    report = probe(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
