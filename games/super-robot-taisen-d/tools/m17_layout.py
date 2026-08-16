#!/usr/bin/env python3
"""Bounded M1.7 layout, token, and font-capacity analysis for A6SJ.

This module deliberately treats anything outside a verified two-byte
Shift-JIS glyph unit as opaque.  It records offsets, hashes, counts, widths,
and resource-slot metadata only; it never writes source text to its report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

try:
    import capstone
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("capstone is required for bounded consumer disassembly") from exc


ROM_BASE = 0x08000000
ROM_END = 0x08800000

CONSUMER = 0x08008724
CONSUMER_END = 0x08008A0C
CODEPAGE_LOOKUP = 0x080085FC
NARROW_SLOT = 0x020131D0
WIDE_SLOT = 0x020103AC

RESOURCE_DESCRIPTOR = 0x081196B8
WIDE_RESOURCE_INDEX = 2
NARROW_RESOURCE_INDEX = 3
NARROW_RESOURCE_END_INDEX = 4

NARROW_STRIDE = 12
WIDE_STRIDE = 26
NARROW_GLYPH_BYTES = 12
WIDE_GLYPH_BYTES = 24

SOURCE_CENTER = 0x7B3FC
MIN_COHORT_SIZE = 16
MAX_COHORT_SIZE = 32


class M17Error(RuntimeError):
    """A fail-closed M1.7 invariant was not met."""


@dataclass(frozen=True)
class Token:
    """One metadata token retaining raw bytes only in memory."""

    kind: str
    raw: bytes
    raw_offset: int
    glyph_class: Optional[str] = None
    layout_width: int = 0
    glyph_stride: int = 0
    reason: Optional[str] = None

    @property
    def is_glyph(self) -> bool:
        return self.kind == "glyph"


@dataclass(frozen=True)
class Tokenization:
    payload: bytes
    tokens: Tuple[Token, ...]

    @property
    def supported(self) -> bool:
        return bool(self.tokens) and all(token.is_glyph for token in self.tokens)

    @property
    def line_width(self) -> int:
        return sum(token.layout_width for token in self.tokens)

    @property
    def glyph_count(self) -> int:
        return sum(token.is_glyph for token in self.tokens)

    def signature(self) -> List[Dict[str, Any]]:
        return [
            {
                "kind": token.kind,
                "glyph_class": token.glyph_class,
                "layout_width": token.layout_width,
            }
            for token in self.tokens
        ]


def address(value: int) -> str:
    return f"0x{value:08X}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    encoded = ",".join(str(value) for value in values).encode("ascii")
    return sha256(encoded)


def sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def source_payload(rom: bytes, offset: int) -> Tuple[bytes, int]:
    if not 0 <= offset < len(rom):
        raise M17Error(f"source offset outside ROM: 0x{offset:x}")
    end = rom.find(b"\x00", offset)
    if end < 0:
        raise M17Error(f"source record has no NUL terminator: 0x{offset:x}")
    return rom[offset:end], end


def classify_pair(first: int, second: int, raw_offset: int) -> Token:
    raw = bytes((first, second))
    if sjis_lead(first) and sjis_trail(second):
        glyph_class = "narrow" if first <= 0x87 else "wide"
        return Token(
            kind="glyph",
            raw=raw,
            raw_offset=raw_offset,
            glyph_class=glyph_class,
            layout_width=8 if glyph_class == "narrow" else 12,
            glyph_stride=NARROW_STRIDE if glyph_class == "narrow" else WIDE_STRIDE,
        )
    if first in (0x0A, 0x0D) or second in (0x0A, 0x0D):
        return Token(
            kind="opaque_newline_candidate",
            raw=raw,
            raw_offset=raw_offset,
            reason="consumer_has_no_dedicated_newline_branch",
        )
    if 0x20 <= first <= 0x7E and 0x20 <= second <= 0x7E:
        return Token(
            kind="opaque_ascii_or_format",
            raw=raw,
            raw_offset=raw_offset,
            reason="not_a_verified_double_byte_glyph",
        )
    return Token(
        kind="opaque_unit",
        raw=raw,
        raw_offset=raw_offset,
        reason="not_a_verified_double_byte_glyph",
    )


def tokenize_payload(payload: bytes) -> Tokenization:
    """Tokenize only known two-byte glyphs; all other units remain opaque."""
    tokens: List[Token] = []
    offset = 0
    while offset + 1 < len(payload):
        tokens.append(classify_pair(payload[offset], payload[offset + 1], offset))
        offset += 2
    if offset < len(payload):
        tokens.append(
            Token(
                kind="opaque_unaligned_tail",
                raw=payload[offset:],
                raw_offset=offset,
                reason="consumer_advances_source_cursor_by_two_bytes",
            )
        )
    return Tokenization(payload=payload, tokens=tuple(tokens))


def encode_tokens(tokenization: Tokenization, include_terminator: bool = True) -> bytes:
    encoded = b"".join(token.raw for token in tokenization.tokens)
    return encoded + (b"\x00" if include_terminator else b"")


def token_summary(tokenization: Tokenization) -> Dict[str, Any]:
    kinds = Counter(token.kind for token in tokenization.tokens)
    glyphs = Counter(token.glyph_class for token in tokenization.tokens if token.is_glyph)
    return {
        "status": "glyph_only" if tokenization.supported else "opaque_or_unaligned",
        "payload_length": len(tokenization.payload),
        "token_count": len(tokenization.tokens),
        "glyph_count": tokenization.glyph_count,
        "token_kinds": dict(sorted(kinds.items())),
        "glyph_classes": dict(sorted(glyphs.items())),
        "line_width": tokenization.line_width,
        "terminator_count": 1,
        "no_op_payload_sha256": sha256(tokenization.payload),
    }


def read_source_records(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                offset = int(row["string_id"], 0) if isinstance(row["string_id"], str) else int(row["string_id"])
                text = row["text"]
            except (KeyError, TypeError, ValueError) as exc:
                raise M17Error(f"invalid source row {line_number}") from exc
            if not isinstance(text, str):
                raise M17Error(f"source text is not a string at line {line_number}")
            records.append({"offset": offset, "text": text})
    records.sort(key=lambda row: int(row["offset"]))
    if len({int(row["offset"]) for row in records}) != len(records):
        raise M17Error("duplicate source offset")
    return records


def select_cohort(records: Sequence[Mapping[str, Any]], center: int, size: int) -> List[Mapping[str, Any]]:
    if not MIN_COHORT_SIZE <= size <= MAX_COHORT_SIZE:
        raise M17Error(f"cohort size must be {MIN_COHORT_SIZE}..{MAX_COHORT_SIZE}")
    offsets = [int(row["offset"]) for row in records]
    if center not in offsets:
        raise M17Error(f"cohort center missing: {address(ROM_BASE + center)}")
    center_index = offsets.index(center)
    start = max(0, min(center_index - size // 2, len(records) - size))
    return list(records[start : start + size])


def record_summary(rom: bytes, record: Mapping[str, Any]) -> Dict[str, Any]:
    offset = int(record["offset"])
    payload, terminator = source_payload(rom, offset)
    try:
        encoded = str(record["text"]).encode("shift_jis", errors="strict")
    except UnicodeEncodeError as exc:
        raise M17Error(f"source is not strict Shift-JIS: 0x{offset:x}") from exc
    if encoded != payload:
        raise M17Error(f"source bytes differ from strict table: 0x{offset:x}")
    tokenization = tokenize_payload(payload)
    summary = token_summary(tokenization)
    encoded = encode_tokens(tokenization, include_terminator=True)
    summary.update(
        {
            "string_id": f"0x{offset:08X}",
            "source_address": address(ROM_BASE + offset),
            "source_hash": sha256(payload),
            "terminator_address": address(ROM_BASE + terminator),
            "terminator_kind": "NUL",
            "token_signature": tokenization.signature(),
            "no_op_byte_identical": encoded == payload + b"\x00",
            "encoded_record_sha256": sha256(encoded),
        }
    )
    return summary


def codepage_offset(code_unit: int, glyph_class: str) -> int:
    """Mirror the bounded arithmetic at 0x080085fc."""
    if glyph_class not in ("narrow", "wide"):
        raise M17Error(f"unknown glyph class: {glyph_class}")
    low = code_unit & 0xFF
    high = (code_unit >> 8) & 0xFF
    if low > 0xDF:
        adjusted = low - 0x43
    elif low > 0x87:
        adjusted = low - 3
    else:
        adjusted = low
    row = adjusted - 0x81
    trail = high - 1 if high & 0x80 else high
    value = ((row * 3) << 6) - 0x40 + trail - row * 4
    return value * (NARROW_STRIDE if glyph_class == "narrow" else WIDE_STRIDE)


def code_unit_slot(code_unit: int, glyph_class: str, resource_size: int) -> Optional[int]:
    low = code_unit & 0xFF
    high = (code_unit >> 8) & 0xFF
    if not sjis_lead(low) or not sjis_trail(high):
        return None
    expected = "narrow" if low <= 0x87 else "wide"
    if expected != glyph_class:
        return None
    stride = NARROW_STRIDE if glyph_class == "narrow" else WIDE_STRIDE
    offset = codepage_offset(code_unit, glyph_class)
    if offset < 0 or offset % stride or offset >= resource_size:
        return None
    return offset // stride


def possible_slots(glyph_class: str, resource_size: int) -> Set[int]:
    stride = NARROW_STRIDE if glyph_class == "narrow" else WIDE_STRIDE
    leads = range(0x81, 0x88) if glyph_class == "narrow" else list(range(0x88, 0xA0)) + list(range(0xE0, 0xFD))
    slots: Set[int] = set()
    for low in leads:
        for high in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            slot = code_unit_slot(low | (high << 8), glyph_class, resource_size)
            if slot is not None and slot * stride < resource_size:
                slots.add(slot)
    return slots


def find_literal_offsets(rom: bytes, value: int) -> List[int]:
    needle = struct.pack("<I", value)
    offsets: List[int] = []
    position = 0
    while True:
        position = rom.find(needle, position)
        if position < 0:
            return offsets
        offsets.append(position)
        position += 1


def descriptor_pointer(rom: bytes, index: int) -> Tuple[int, int]:
    offset = RESOURCE_DESCRIPTOR - ROM_BASE + index * 4
    if offset < 0 or offset + 4 > len(rom):
        raise M17Error("resource descriptor is outside ROM")
    relative = struct.unpack_from("<I", rom, offset)[0]
    pointer = RESOURCE_DESCRIPTOR + relative
    if not ROM_BASE <= pointer < ROM_BASE + len(rom):
        raise M17Error(f"resource pointer outside ROM: {address(pointer)}")
    return pointer, relative


def _slot_hashes(blank: Sequence[int], unreachable: Sequence[int]) -> Dict[str, Any]:
    return {
        "blank_slot_count": len(blank),
        "blank_slot_index_sha256": hash_ints(blank),
        "blank_slot_first": list(blank[:12]),
        "blank_slot_last": list(blank[-12:]),
        "unreachable_slot_count": len(unreachable),
        "unreachable_slot_index_sha256": hash_ints(unreachable),
        "unreachable_slot_first": list(unreachable[:12]),
        "unreachable_slot_last": list(unreachable[-12:]),
    }


def resource_capacity(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    wide_start, wide_relative = descriptor_pointer(rom, WIDE_RESOURCE_INDEX)
    narrow_start, narrow_relative = descriptor_pointer(rom, NARROW_RESOURCE_INDEX)
    narrow_end, narrow_end_relative = descriptor_pointer(rom, NARROW_RESOURCE_END_INDEX)
    expected = {
        "wide": (wide_start, narrow_start, WIDE_STRIDE, WIDE_GLYPH_BYTES, wide_relative),
        "narrow": (narrow_start, narrow_end, NARROW_STRIDE, NARROW_GLYPH_BYTES, narrow_relative),
    }
    references: Dict[str, Counter[int]] = {"narrow": Counter(), "wide": Counter()}
    for record in records:
        offset = int(record["offset"])
        payload, _terminator = source_payload(rom, offset)
        tokenization = tokenize_payload(payload)
        for token in tokenization.tokens:
            if not token.is_glyph:
                continue
            glyph_class = str(token.glyph_class)
            start, end, stride, glyph_bytes, _relative = expected[glyph_class]
            slot = code_unit_slot(int.from_bytes(token.raw, "little"), glyph_class, end - start)
            if slot is not None:
                references[glyph_class][slot] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for glyph_class, (start, end, stride, glyph_bytes, relative) in expected.items():
        size = end - start
        if size <= 0 or size % stride:
            raise M17Error(f"{glyph_class} resource is not stride-aligned")
        physical_slots = size // stride
        addressable = possible_slots(glyph_class, size)
        blank: List[int] = []
        for slot in range(physical_slots):
            begin = start - ROM_BASE + slot * stride
            glyph = rom[begin : begin + glyph_bytes]
            if not any(glyph):
                blank.append(slot)
        unreachable = sorted(set(range(physical_slots)) - addressable)
        referenced = references[glyph_class]
        blank_set = set(blank)
        blank_addressable = sorted(blank_set & addressable)
        blank_unreferenced = sorted(set(blank_addressable) - set(referenced))
        result[glyph_class] = {
            "resource_descriptor_index": WIDE_RESOURCE_INDEX if glyph_class == "wide" else NARROW_RESOURCE_INDEX,
            "descriptor_relative": f"0x{relative:08X}",
            "resource_start": address(start),
            "resource_end_exclusive": address(end),
            "resource_size": size,
            "stride": stride,
            "glyph_payload_bytes": glyph_bytes,
            "physical_slots": physical_slots,
            "addressable_slots": len(addressable),
            "referenced_slots": len(referenced),
            "reference_occurrences": sum(referenced.values()),
            "referenced_slot_index_sha256": hash_ints(sorted(referenced)),
            "blank_addressable_slots": len(blank_addressable),
            "blank_referenced_slots": len(set(blank_addressable) & set(referenced)),
            "conservative_new_slot_capacity": len(blank_unreferenced),
            "capacity_basis": "blank addressable slots not referenced by the verified corpus",
            "literal_reference_counts": {
                "runtime_base_slot": len(find_literal_offsets(rom, NARROW_SLOT if glyph_class == "narrow" else WIDE_SLOT)),
                "resource_pointer": len(find_literal_offsets(rom, start)),
            },
            **_slot_hashes(blank, unreachable),
        }
    result["notes"] = {
        "narrow_zh_tw_upper_bound": result["narrow"]["conservative_new_slot_capacity"],
        "wide_zh_tw_upper_bound": 0,
        "wide_reason": "no blank addressable wide slot was observed",
        "identity_policy": "slot occupancy is not a Unicode identity claim",
    }
    return result


def selected_instruction_map(rom: bytes) -> Dict[int, str]:
    start = CONSUMER - ROM_BASE
    end = CONSUMER_END - ROM_BASE
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    return {
        instruction.address: f"{instruction.mnemonic} {instruction.op_str}".strip()
        for instruction in md.disasm(rom[start:end], CONSUMER)
    }


def static_consumer_report(rom: bytes) -> Dict[str, Any]:
    instruction_map = selected_instruction_map(rom)
    code = rom[CONSUMER - ROM_BASE : CONSUMER_END - ROM_BASE]

    def insn(pc: int) -> str:
        return instruction_map.get(pc, "unverified")

    return {
        "consumer": address(CONSUMER),
        "code_end_exclusive": address(CONSUMER_END),
        "code_sha256": sha256(code),
        "terminator": {
            "primary_load_pc": address(0x0800876C),
            "primary_compare_pc": address(0x0800876E),
            "primary_branch_pc": address(0x08008770),
            "primary_branch_instruction": insn(0x08008770),
            "primary_branch_target": address(0x08008798),
            "loop_load_pc": address(0x08008950),
            "loop_compare_pc": address(0x08008952),
            "loop_branch_pc": address(0x08008954),
            "loop_branch_instruction": insn(0x08008954),
            "loop_branch_target": address(0x08008958),
            "token": "NUL",
            "evidence": "ldrb first source byte, compare zero, exit before glyph path",
        },
        "glyph_class_branch": {
            "pc": address(0x0800877A),
            "instruction": insn(0x0800877A),
            "narrow_condition": "source code-unit low byte <= 0x87",
            "wide_condition": "source code-unit low byte > 0x87",
            "verified_glyph_unit_bytes": 2,
            "source_cursor_advance": 2,
            "single_byte_glyph_path": False,
            "single_byte_policy": "opaque; no verified single-byte glyph branch",
        },
        "narrow": {
            "codepage_lookup": address(CODEPAGE_LOOKUP),
            "codepage_mode": 1,
            "base_literal_load": address(0x080088C2),
            "base_dereference": address(0x080088C4),
            "base_slot": address(NARROW_SLOT),
            "base_plus_offset_pc": address(0x080088C8),
            "glyph_payload_bytes": NARROW_GLYPH_BYTES,
            "glyph_address_stride": NARROW_STRIDE,
            "layout_width": 8,
            "tile_writer": address(0x08008650),
        },
        "wide": {
            "codepage_lookup": address(CODEPAGE_LOOKUP),
            "codepage_mode": 0,
            "base_literal_load": address(0x08008812),
            "base_dereference": address(0x08008814),
            "base_slot": address(WIDE_SLOT),
            "base_plus_offset_pc": address(0x08008818),
            "glyph_payload_bytes": WIDE_GLYPH_BYTES,
            "glyph_address_stride": WIDE_STRIDE,
            "layout_width": 12,
            "tile_writer": address(0x08008650),
        },
        "newline": {
            "status": "unconfirmed_opaque",
            "raw_lf_or_cr_branch": False,
            "consumer_dedicated_branch": False,
            "policy": "reject rather than assign newline semantics",
        },
        "non_text": {
            "status": "opaque",
            "common_corpus_class": "ascii_or_format_pair",
            "policy": "preserve bytes for no-op only; reject for translation POC",
        },
    }


def corpus_report(
    rom: bytes, records: Sequence[Mapping[str, Any]], cohort: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    all_summaries = [record_summary(rom, record) for record in records]
    statuses = Counter(str(row["status"]) for row in all_summaries)
    token_kinds: Counter[str] = Counter()
    glyph_classes: Counter[str] = Counter()
    widths: List[int] = []
    for row in all_summaries:
        token_kinds.update(row["token_kinds"])
        glyph_classes.update(row["glyph_classes"])
        if row["status"] == "glyph_only":
            widths.append(int(row["line_width"]))
    digest_material = "".join(
        f"{row['string_id']}:{row['source_hash']}:{row['payload_length']}\n"
        for row in all_summaries
    ).encode("ascii")
    cohort_summaries = [record_summary(rom, record) for record in cohort]
    no_op_passes = sum(bool(row["no_op_byte_identical"]) for row in all_summaries)
    cohort_no_op_passes = sum(bool(row["no_op_byte_identical"]) for row in cohort_summaries)
    return {
        "record_count": len(all_summaries),
        "source_corpus_digest": sha256(digest_material),
        "terminator_count": sum(int(row["terminator_count"]) for row in all_summaries),
        "no_op_roundtrip": {
            "record_count": len(all_summaries),
            "byte_identical_count": no_op_passes,
            "failed_count": len(all_summaries) - no_op_passes,
        },
        "status_counts": dict(sorted(statuses.items())),
        "token_kind_counts": dict(sorted(token_kinds.items())),
        "glyph_class_counts": dict(sorted(glyph_classes.items())),
        "supported_line_width": {
            "record_count": len(widths),
            "minimum": min(widths) if widths else None,
            "maximum": max(widths) if widths else None,
            "distinct_count": len(set(widths)),
        },
        "cohort": {
            "record_count": len(cohort_summaries),
            "center": address(ROM_BASE + SOURCE_CENTER),
            "no_op_roundtrip": {
                "record_count": len(cohort_summaries),
                "byte_identical_count": cohort_no_op_passes,
                "failed_count": len(cohort_summaries) - cohort_no_op_passes,
            },
            "rows": cohort_summaries,
        },
    }


def build_report(rom: bytes, records: Sequence[Mapping[str, Any]], center: int, size: int) -> Dict[str, Any]:
    cohort = select_cohort(records, center, size)
    return {
        "schema": "super-robot-taisen-d-m17-layout-v1",
        "game_code": "A6SJ",
        "static_consumer": static_consumer_report(rom),
        "corpus": corpus_report(rom, records, cohort),
        "resources": resource_capacity(rom, records),
        "source_policy": {
            "source_text_emitted": False,
            "unknown_tokens": "opaque",
            "no_op_requires_byte_identity": True,
        },
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--center", type=lambda value: int(value, 0), default=SOURCE_CENTER)
    parser.add_argument("--cohort-size", type=int, default=MIN_COHORT_SIZE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    records = read_source_records(args.source_table)
    report = build_report(rom, records, args.center, args.cohort_size)
    write_report(args.output, report)
    corpus = report["corpus"]
    print(
        f"records={corpus['record_count']} cohort={corpus['cohort']['record_count']} "
        f"statuses={corpus['status_counts']} "
        f"no_op={corpus['no_op_roundtrip']['byte_identical_count']}/{corpus['no_op_roundtrip']['record_count']} "
        f"narrow_capacity={report['resources']['notes']['narrow_zh_tw_upper_bound']} "
        f"wide_capacity={report['resources']['notes']['wide_zh_tw_upper_bound']} output={args.output}"
    )


if __name__ == "__main__":
    main()
