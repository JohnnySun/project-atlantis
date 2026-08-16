#!/usr/bin/env python3
"""Fail-closed narrow-glyph allocator and static M1.8 POC builder.

The A6SJ narrow resource is a 544-slot, 8x12, one-bit-per-pixel bitmap
resource.  This tool allocates only blank, addressable, unreferenced slots
from the verified source corpus.  It never allocates a wide slot, overwrites
one of the three blank-but-referenced slots, or emits original source text in
its metadata reports.

The optional ``seed-ledger`` and ``set-target`` commands operate on local
ledger/work files.  ``build`` requires the restored work record and its
source-safe ledger record, then writes only ignored ROM/report/render output.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

try:
    from m17_layout import (
        M17Error,
        NARROW_GLYPH_BYTES,
        NARROW_STRIDE,
        ROM_BASE,
        code_unit_slot,
        hash_ints,
        possible_slots,
        read_source_records,
        resource_capacity,
        sha256,
        source_payload,
        tokenize_payload,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - direct script execution
    if exc.name != "m17_layout":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from m17_layout import (
        M17Error,
        NARROW_GLYPH_BYTES,
        NARROW_STRIDE,
        ROM_BASE,
        code_unit_slot,
        hash_ints,
        possible_slots,
        read_source_records,
        resource_capacity,
        sha256,
        source_payload,
        tokenize_payload,
    )


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FONT = REPO_ROOT / "vendor/fonts/unifont/unifont_t-17.0.05.hex.gz"
DEFAULT_LICENSE = REPO_ROOT / "vendor/fonts/unifont/OFL-1.1.txt"

ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
FONT_SHA256 = "c1768bd7fea203db1f419045d5a9e4d420772445e29b96c8873471d3f46c5b53"
LICENSE_SHA256 = "869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded"
FONT_SOURCE_URL = (
    "https://unifoundry.com/pub/unifont/unifont-17.0.05/font-builds/"
    "unifont_t-17.0.05.hex.gz"
)
FONT_LICENSE = "SIL OFL 1.1 or GPL-2.0-or-later with the GNU font exception"

NARROW_RESOURCE_START = 0x0814F664
NARROW_RESOURCE_END = 0x08150FE4
TARGET_OFFSET = 0x080858
ADJACENT_OFFSET = 0x080860
TARGET_RECORD_ID = TARGET_OFFSET - ROM_BASE
DECODER_VERSION = "A6SJ strict Shift-JIS NUL scan v1"


class AllocatorReject(ValueError):
    """A fail-closed M1.8 gate rejected an input or allocation."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass(frozen=True)
class Allocation:
    character: str
    codepoint: int
    slot: int
    code_unit: int
    raw_code_unit: bytes
    font_source_sha256: str
    glyph_bytes: bytes


def address(value: int) -> str:
    return f"0x{value:08X}"


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def read_one_jsonl(path: Path) -> Dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 1:
        raise AllocatorReject("record_count", f"expected exactly one record in {path}")
    return rows[0]


def write_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def load_font_metadata(font_path: Path, license_path: Path) -> Dict[str, Any]:
    actual_font_hash = file_sha256(font_path)
    if actual_font_hash != FONT_SHA256:
        raise AllocatorReject("font_hash_mismatch", relative_path(font_path))
    actual_license_hash = file_sha256(license_path)
    if actual_license_hash != LICENSE_SHA256:
        raise AllocatorReject("font_license_hash_mismatch", relative_path(license_path))
    return {
        "source_path": relative_path(font_path),
        "source_url": FONT_SOURCE_URL,
        "source_sha256": actual_font_hash,
        "license_path": relative_path(license_path),
        "license_sha256": actual_license_hash,
        "license": FONT_LICENSE,
        "redistributable": True,
        "transform": "Unifont T-source 16x16 box-any downsample to 8x12; x=2-column blocks, y=floor intervals",
    }


def load_unifont_rows(font_path: Path, codepoints: Iterable[int]) -> Dict[int, Tuple[int, ...]]:
    wanted = set(codepoints)
    found: Dict[int, Tuple[int, ...]] = {}
    with gzip.open(font_path, "rt", encoding="ascii") as handle:
        for line in handle:
            line = line.strip()
            if not line or ":" not in line:
                continue
            codepoint_text, bitmap_text = line.split(":", 1)
            codepoint = int(codepoint_text, 16)
            if codepoint not in wanted:
                continue
            if len(bitmap_text) != 64:
                raise AllocatorReject("font_format_mismatch", f"U+{codepoint:04X} is not 16x16")
            found[codepoint] = tuple(
                int(bitmap_text[row * 4 : row * 4 + 4], 16) for row in range(16)
            )
    missing = sorted(wanted - set(found))
    if missing:
        raise AllocatorReject("missing_glyph", ", ".join(f"U+{cp:04X}" for cp in missing))
    return found


def source_bitmap_sha256(rows: Sequence[int]) -> str:
    return sha256(b"".join(row.to_bytes(2, "big") for row in rows))


def downsample_16x16_to_8x12(rows: Sequence[int]) -> bytes:
    if len(rows) != 16 or any(row < 0 or row > 0xFFFF for row in rows):
        raise AllocatorReject("font_format_mismatch", "expected sixteen 16-bit rows")
    result = bytearray()
    for output_y in range(12):
        source_y0 = (output_y * 16) // 12
        source_y1 = ((output_y + 1) * 16) // 12
        packed = 0
        for output_x in range(8):
            source_x0 = output_x * 2
            ink = any(
                rows[source_y] & (0x8000 >> source_x)
                for source_y in range(source_y0, source_y1)
                for source_x in range(source_x0, source_x0 + 2)
            )
            if ink:
                packed |= 0x80 >> output_x
        result.append(packed)
    return bytes(result)


def render_narrow_4bpp(glyph_bytes: bytes, palette_index: int = 1) -> bytes:
    """Mirror 0x080085B0: eight row bits become four packed 4bpp bytes."""
    if len(glyph_bytes) != NARROW_GLYPH_BYTES:
        raise AllocatorReject("glyph_format_mismatch", "narrow glyph must be 12 bytes")
    if not 0 <= palette_index <= 0x0F:
        raise AllocatorReject("glyph_format_mismatch", "palette index outside 4bpp range")
    output = bytearray(12 * 4)
    for row_index, row in enumerate(glyph_bytes):
        for bit_index in range(8):
            if row & (0x80 >> bit_index):
                output[row_index * 4 + bit_index // 2] |= (
                    palette_index if bit_index % 2 == 0 else palette_index << 4
                )
    return bytes(output)


def render_narrow_1bpp(glyph_bytes: bytes) -> bytes:
    if len(glyph_bytes) != NARROW_GLYPH_BYTES:
        raise AllocatorReject("glyph_format_mismatch", "narrow glyph must be 12 bytes")
    return glyph_bytes


def render_string_1bpp(glyphs: Sequence[bytes]) -> bytes:
    if not glyphs:
        raise AllocatorReject("missing_glyph", "cannot render an empty string")
    for glyph in glyphs:
        if len(glyph) != NARROW_GLYPH_BYTES:
            raise AllocatorReject("glyph_format_mismatch", "string contains non-narrow glyph")
    return b"".join(glyph[row : row + 1] for row in range(12) for glyph in glyphs)


def render_string_4bpp(glyphs: Sequence[bytes]) -> bytes:
    return b"".join(render_narrow_4bpp(glyph) for glyph in glyphs)


def write_pgm(path: Path, glyphs: Sequence[bytes]) -> None:
    if not glyphs:
        raise AllocatorReject("missing_glyph", "cannot write an empty render")
    width = 8 * len(glyphs)
    rows = bytearray()
    for y in range(12):
        for glyph in glyphs:
            row = glyph[y]
            rows.extend(255 if row & (0x80 >> x) else 0 for x in range(8))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"P5\n{width} 12\n255\n".encode("ascii") + bytes(rows))


def enumerate_narrow_code_units(resource_size: int) -> Dict[int, Tuple[int, ...]]:
    """Return slot -> valid two-byte source code units for narrow mode."""
    result: Dict[int, List[int]] = {}
    trails = list(range(0x40, 0x7F)) + list(range(0x80, 0xFD))
    for lead in range(0x81, 0x88):
        for trail in trails:
            code_unit = lead | (trail << 8)
            slot = code_unit_slot(code_unit, "narrow", resource_size)
            if slot is not None:
                result.setdefault(slot, []).append(code_unit)
    return {slot: tuple(sorted(units)) for slot, units in sorted(result.items())}


def code_unit_bytes(code_unit: int) -> bytes:
    return bytes((code_unit & 0xFF, (code_unit >> 8) & 0xFF))


def narrow_occupancy(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    resources = resource_capacity(rom, records)["narrow"]
    start = int(resources["resource_start"], 0)
    size = int(resources["resource_size"])
    physical_slots = int(resources["physical_slots"])
    slot_to_units = enumerate_narrow_code_units(size)
    addressable = set(slot_to_units)
    references: Counter[int] = Counter()
    for record in records:
        payload, _terminator = source_payload(rom, int(record["offset"]))
        for token in tokenize_payload(payload).tokens:
            if not token.is_glyph or token.glyph_class != "narrow":
                continue
            slot = code_unit_slot(int.from_bytes(token.raw, "little"), "narrow", size)
            if slot is not None:
                references[slot] += 1
    blank = []
    for slot in range(physical_slots):
        begin = start - ROM_BASE + slot * NARROW_STRIDE
        if not any(rom[begin : begin + NARROW_GLYPH_BYTES]):
            blank.append(slot)
    blank_set = set(blank)
    protected = sorted(blank_set & set(references))
    free = sorted(blank_set & addressable - set(references))
    collisions = sorted(slot for slot, units in slot_to_units.items() if len(units) != 1)
    if collisions:
        raise AllocatorReject("code_unit_slot_collision", str(collisions[:8]))
    if protected != [0, 57, 58]:
        raise AllocatorReject("resource_occupancy_mismatch", f"protected blank slots changed: {protected}")
    return {
        "resource_start": start,
        "resource_end_exclusive": start + size,
        "resource_size": size,
        "stride": NARROW_STRIDE,
        "glyph_payload_bytes": NARROW_GLYPH_BYTES,
        "physical_slots": physical_slots,
        "addressable_slots": len(addressable),
        "addressable_slot_first": min(addressable),
        "addressable_slot_last": max(addressable),
        "slot_to_units": slot_to_units,
        "referenced_slots": sorted(references),
        "reference_occurrences": sum(references.values()),
        "blank_slots": blank,
        "protected_blank_referenced_slots": protected,
        "free_blank_slots": free,
        "free_slot_index_sha256": hash_ints(free),
        "addressable_code_unit_first": code_unit_bytes(slot_to_units[min(addressable)][0]).hex(),
        "addressable_code_unit_last": code_unit_bytes(slot_to_units[max(addressable)][0]).hex(),
    }


def validate_source_shape(payload: bytes) -> Tuple[int, Any]:
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        raise AllocatorReject("opaque_or_control", "source contains an opaque token or unaligned tail")
    if any(token.glyph_class != "narrow" for token in tokenization.tokens):
        raise AllocatorReject("wide_glyph", "source record is not narrow-only")
    return len(tokenization.tokens), tokenization


def allocate_target(
    target_text: str,
    source_unit_count: int,
    occupancy: Mapping[str, Any],
    font_rows: Mapping[int, Sequence[int]],
) -> Tuple[Allocation, ...]:
    if any(ord(char) < 0x20 or char in "\x7f\n\r\t" for char in target_text):
        raise AllocatorReject("opaque_or_control", "target contains a control character")
    if len(target_text) != source_unit_count:
        raise AllocatorReject("variable_length", f"target units={len(target_text)} source units={source_unit_count}")
    # Prefer the high end of the addressable range.  These slots are blank,
    # unreferenced by the verified corpus, and the selected code units are
    # outside the conventional low punctuation block; the corpus bound still
    # remains explicit in the report.
    free_slots = sorted(occupancy["free_blank_slots"], reverse=True)
    slot_to_units = occupancy["slot_to_units"]
    allocations: List[Allocation] = []
    by_codepoint: Dict[int, Allocation] = {}
    next_slot = 0
    for char in target_text:
        codepoint = ord(char)
        if codepoint in by_codepoint:
            allocations.append(by_codepoint[codepoint])
            continue
        if codepoint not in font_rows:
            raise AllocatorReject("missing_glyph", f"U+{codepoint:04X}")
        if next_slot >= len(free_slots):
            raise AllocatorReject("capacity_exceeded", "no unreferenced blank narrow slot remains")
        slot = free_slots[next_slot]
        next_slot += 1
        units = tuple(slot_to_units.get(slot, ()))
        if len(units) != 1:
            raise AllocatorReject("code_unit_slot_collision", f"slot={slot} units={units}")
        code_unit = units[0]
        if code_unit_bytes(code_unit)[0] > 0x87:
            raise AllocatorReject("wide_glyph", f"code unit {code_unit_bytes(code_unit).hex()}")
        glyph_bytes = downsample_16x16_to_8x12(font_rows[codepoint])
        if not any(glyph_bytes):
            raise AllocatorReject("missing_glyph", f"font glyph U+{codepoint:04X} is blank")
        allocation = Allocation(
            character=char,
            codepoint=codepoint,
            slot=slot,
            code_unit=code_unit,
            raw_code_unit=code_unit_bytes(code_unit),
            font_source_sha256=source_bitmap_sha256(font_rows[codepoint]),
            glyph_bytes=glyph_bytes,
        )
        by_codepoint[codepoint] = allocation
        allocations.append(allocation)
    if len({allocation.slot for allocation in allocations}) != len(set(by_codepoint)):
        raise AllocatorReject("code_unit_slot_collision", "target codepoints share a slot")
    return tuple(allocations)


def _record_by_offset(records: Sequence[Mapping[str, Any]], offset: int) -> Mapping[str, Any]:
    for record in records:
        if int(record["offset"]) == offset:
            return record
    raise AllocatorReject("source_record_missing", address(offset))


def _glyph_bytes_at(rom: bytes, code_unit: int, occupancy: Mapping[str, Any]) -> bytes:
    slot = code_unit_slot(code_unit, "narrow", int(occupancy["resource_size"]))
    if slot is None:
        raise AllocatorReject("code_unit_out_of_range", code_unit_bytes(code_unit).hex())
    begin = int(occupancy["resource_start"]) - ROM_BASE + slot * NARROW_STRIDE
    return rom[begin : begin + NARROW_GLYPH_BYTES]


def render_record_summary(rom: bytes, offset: int, occupancy: Mapping[str, Any]) -> Dict[str, Any]:
    payload, _terminator = source_payload(rom, offset)
    unit_count, tokenization = validate_source_shape(payload)
    glyphs = [
        _glyph_bytes_at(rom, int.from_bytes(token.raw, "little"), occupancy)
        for token in tokenization.tokens
    ]
    for glyph in glyphs:
        if len(glyph) != NARROW_GLYPH_BYTES:
            raise AllocatorReject("glyph_format_mismatch", address(offset))
    rendered_1bpp = render_string_1bpp(glyphs)
    rendered_4bpp = render_string_4bpp(glyphs)
    slots = [
        code_unit_slot(int.from_bytes(token.raw, "little"), "narrow", int(occupancy["resource_size"]))
        for token in tokenization.tokens
    ]
    return {
        "source_address": address(ROM_BASE + offset),
        "payload_length": len(payload),
        "payload_sha256": sha256(payload),
        "unit_count": unit_count,
        "slot_index_sha256": hash_ints(int(slot) for slot in slots if slot is not None),
        "glyph_bytes_sha256": sha256(b"".join(glyphs)),
        "render_1bpp": {"width": 8 * unit_count, "height": 12, "sha256": sha256(rendered_1bpp)},
        "render_4bpp": {"bytes": len(rendered_4bpp), "sha256": sha256(rendered_4bpp)},
    }


def _allocation_report(allocation: Allocation) -> Dict[str, Any]:
    rendered_1bpp = render_narrow_1bpp(allocation.glyph_bytes)
    rendered_4bpp = render_narrow_4bpp(allocation.glyph_bytes)
    return {
        "character": allocation.character,
        "codepoint": f"U+{allocation.codepoint:04X}",
        "slot": allocation.slot,
        "code_unit_little_endian": f"0x{allocation.code_unit:04X}",
        "raw_code_unit_bytes": allocation.raw_code_unit.hex(),
        "font_glyph_source_sha256": allocation.font_source_sha256,
        "glyph_bytes_sha256": sha256(allocation.glyph_bytes),
        "glyph_nonzero_bytes": sum(byte != 0 for byte in allocation.glyph_bytes),
        "render_1bpp": {"width": 8, "height": 12, "sha256": sha256(rendered_1bpp)},
        "render_4bpp": {"bytes": len(rendered_4bpp), "sha256": sha256(rendered_4bpp)},
    }


def build_plan(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    source_offset: int,
    target_text: str,
    font_path: Path,
    license_path: Path,
    *,
    ledger_source_hash: Optional[str] = None,
) -> Dict[str, Any]:
    actual_rom_hash = sha256(rom)
    if actual_rom_hash != ROM_SHA256:
        raise AllocatorReject("rom_hash_mismatch", actual_rom_hash)
    font = load_font_metadata(font_path, license_path)
    source_record = _record_by_offset(records, source_offset)
    source_text = str(source_record["text"])
    try:
        source_encoded = source_text.encode("shift_jis", errors="strict")
    except UnicodeEncodeError as exc:
        raise AllocatorReject("source_hash_mismatch", address(source_offset)) from exc
    rom_payload, terminator = source_payload(rom, source_offset)
    if rom_payload != source_encoded:
        raise AllocatorReject("source_hash_mismatch", address(source_offset))
    source_ledger_hash = sha256(source_text.encode("utf-8"))
    if ledger_source_hash is not None and ledger_source_hash != source_ledger_hash:
        raise AllocatorReject("source_hash_mismatch", "ledger source hash differs")
    source_unit_count, tokenization = validate_source_shape(source_encoded)
    if len(source_encoded) != source_unit_count * 2:
        raise AllocatorReject("source_format_mismatch", "source is not all two-byte units")
    if len(target_text.encode("utf-8")) == 0:
        raise AllocatorReject("variable_length", "target is empty")
    occupancy = narrow_occupancy(rom, records)
    font_rows = load_unifont_rows(font_path, {ord(char) for char in target_text})
    allocations = allocate_target(target_text, source_unit_count, occupancy, font_rows)
    target_payload = b"".join(allocation.raw_code_unit for allocation in allocations)
    if len(target_payload) != len(source_encoded):
        raise AllocatorReject("variable_length", "target payload length differs")
    return {
        "source_offset": source_offset,
        "source_address": address(ROM_BASE + source_offset),
        "source_payload": source_encoded,
        "source_raw_sha256": sha256(source_encoded),
        "source_ledger_sha256": source_ledger_hash or sha256(source_text.encode("utf-8")),
        "source_terminator_address": address(ROM_BASE + terminator),
        "source_unit_count": source_unit_count,
        "source_line_width": tokenization.line_width,
        "target_text": target_text,
        "target_payload": target_payload,
        "target_payload_sha256": sha256(target_payload),
        "allocations": allocations,
        "font": font,
        "occupancy": occupancy,
    }


def patch_rom(rom: bytes, plan: Mapping[str, Any]) -> bytes:
    patched = bytearray(rom)
    source_offset = int(plan["source_offset"])
    source_payload_bytes = bytes(plan["source_payload"])
    target_payload = bytes(plan["target_payload"])
    if len(source_payload_bytes) != len(target_payload):
        raise AllocatorReject("variable_length", "patch payload length differs")
    patched[source_offset : source_offset + len(target_payload)] = target_payload
    occupancy = plan["occupancy"]
    for allocation in plan["allocations"]:
        begin = int(occupancy["resource_start"]) - ROM_BASE + allocation.slot * NARROW_STRIDE
        before = bytes(patched[begin : begin + NARROW_GLYPH_BYTES])
        if any(before):
            raise AllocatorReject("slot_collision", f"slot {allocation.slot} is not blank")
        patched[begin : begin + NARROW_GLYPH_BYTES] = allocation.glyph_bytes
    return bytes(patched)


def build_report(
    rom: bytes,
    patched_rom: bytes,
    plan: Mapping[str, Any],
    adjacent_offset: int,
    render_dir: Optional[Path],
) -> Dict[str, Any]:
    occupancy = plan["occupancy"]
    target_before = render_record_summary(rom, int(plan["source_offset"]), occupancy)
    target_after = render_record_summary(patched_rom, int(plan["source_offset"]), occupancy)
    adjacent_before = render_record_summary(rom, adjacent_offset, occupancy)
    adjacent_after = render_record_summary(patched_rom, adjacent_offset, occupancy)
    if adjacent_before != adjacent_after:
        raise AllocatorReject("adjacent_record_changed", address(adjacent_offset))
    if target_before["payload_sha256"] == target_after["payload_sha256"]:
        raise AllocatorReject("patch_not_changed", address(int(plan["source_offset"])))
    if render_dir is not None:
        write_pgm(render_dir / "target-after.pgm", [
            _glyph_bytes_at(patched_rom, allocation.code_unit, occupancy)
            for allocation in plan["allocations"]
        ])
        adjacent_payload, _ = source_payload(patched_rom, adjacent_offset)
        adjacent_tokens = tokenize_payload(adjacent_payload)
        write_pgm(render_dir / "adjacent-untouched.pgm", [
            _glyph_bytes_at(patched_rom, int.from_bytes(token.raw, "little"), occupancy)
            for token in adjacent_tokens.tokens
        ])
    changed_ranges = [
        {
            "address": address(ROM_BASE + int(plan["source_offset"])),
            "length": len(plan["target_payload"]),
            "kind": "source_record_same_length",
        }
    ]
    for allocation in plan["allocations"]:
        changed_ranges.append(
            {
                "address": address(int(occupancy["resource_start"]) + allocation.slot * NARROW_STRIDE),
                "length": NARROW_GLYPH_BYTES,
                "kind": "blank_narrow_glyph_slot",
                "slot": allocation.slot,
            }
        )
    return {
        "schema": "super-robot-taisen-d-m18-narrow-poc-v1",
        "game_code": "A6SJ",
        "source": {
            "string_id": int(plan["source_offset"]),
            "source_address": plan["source_address"],
            "raw_sha256": plan["source_raw_sha256"],
            "ledger_sha256": plan["source_ledger_sha256"],
            "payload_length": len(plan["source_payload"]),
            "unit_count": plan["source_unit_count"],
            "line_width": plan["source_line_width"],
            "terminator": "NUL",
            "glyph_class": "narrow_only",
        },
        "target": {
            "locale": "zh-TW",
            "text": plan["target_text"],
            "payload_sha256": plan["target_payload_sha256"],
            "payload_length": len(plan["target_payload"]),
            "equal_source_length": len(plan["target_payload"]) == len(plan["source_payload"]),
            "line_width": plan["source_line_width"],
        },
        "font": plan["font"],
        "allocator": {
            "mode": "narrow_only",
            "resource_start": address(int(occupancy["resource_start"])),
            "resource_end_exclusive": address(int(occupancy["resource_end_exclusive"])),
            "stride": NARROW_STRIDE,
            "glyph_payload_bytes": NARROW_GLYPH_BYTES,
            "physical_slots": occupancy["physical_slots"],
            "addressable_slots": occupancy["addressable_slots"],
            "addressable_code_unit_first": occupancy["addressable_code_unit_first"],
            "addressable_code_unit_last": occupancy["addressable_code_unit_last"],
            "referenced_slot_count": len(occupancy["referenced_slots"]),
            "reference_occurrences": occupancy["reference_occurrences"],
            "protected_blank_referenced_slots": occupancy["protected_blank_referenced_slots"],
            "free_blank_slot_count": len(occupancy["free_blank_slots"]),
            "free_slot_index_sha256": occupancy["free_slot_index_sha256"],
            "allocated_slot_count": len(set(allocation.slot for allocation in plan["allocations"])),
            "rejection_contract": [
                "rom_hash_mismatch",
                "font_hash_mismatch",
                "font_license_hash_mismatch",
                "source_hash_mismatch",
                "code_unit_slot_collision",
                "code_unit_out_of_range",
                "wide_glyph",
                "opaque_or_control",
                "missing_glyph",
                "capacity_exceeded",
                "variable_length",
            ],
        },
        "allocations": [_allocation_report(allocation) for allocation in plan["allocations"]],
        "rom": {
            "source_sha256": sha256(rom),
            "patched_sha256": sha256(patched_rom),
            "modified": rom != patched_rom,
            "changed_ranges": changed_ranges,
        },
        "static_render": {
            "target_before": target_before,
            "target_after": target_after,
            "adjacent_offset": address(ROM_BASE + adjacent_offset),
            "adjacent_before": adjacent_before,
            "adjacent_after": adjacent_after,
            "adjacent_untouched": adjacent_before == adjacent_after,
            "runtime_status": "pending; static render gate only",
        },
        "gate": {
            "accepted": True,
            "source_hash_match": True,
            "font_hash_match": True,
            "mapping_narrow_only": True,
            "same_length": True,
            "protected_slots_preserved": True,
            "wide_new_slots": 0,
        },
    }


def emit_seed_ledger(source_table: Path, target_offset: int, output: Path) -> None:
    records = read_source_records(source_table)
    record = _record_by_offset(records, target_offset)
    source_text = str(record["text"])
    try:
        source_payload_bytes = source_text.encode("shift_jis", errors="strict")
    except UnicodeEncodeError as exc:
        raise AllocatorReject("source_hash_mismatch", address(target_offset)) from exc
    tokenization = tokenize_payload(source_payload_bytes)
    if not tokenization.supported:
        raise AllocatorReject("opaque_or_control", address(target_offset))
    row = {
        "game": "super-robot-taisen-d",
        "revision": "A6SJ",
        "string_id": target_offset,
        "source_locale": "ja",
        "source_hash": sha256(source_text.encode("utf-8")),
        "decoder_version": DECODER_VERSION,
        "targets": {"zh-Hans": {"text": ""}, "zh-TW": {"text": ""}},
        "context": {
            "max_width": tokenization.line_width,
            "max_lines": 1,
            "control_codes": [],
            "notes": "M1.8 bounded source-shape seed",
        },
        "status": "untranslated",
        "review_notes": "M1.8 static POC seed; source remains local-only.",
    }
    write_jsonl(output, row)
    print(f"seed_ledger string_id=0x{target_offset:08X} output={output}")


def set_target_work(working: Path, output: Path, zh_hans: str, zh_tw: str) -> None:
    row = read_one_jsonl(working)
    row.setdefault("targets", {})
    row["targets"]["zh-Hans"] = {"text": zh_hans, "model": "gpt-5.6-luna"}
    row["targets"]["zh-TW"] = {"text": zh_tw, "model": "gpt-5.6-luna"}
    row["status"] = "ai_draft"
    row["review_notes"] = "M1.8 bounded static POC; no proper-noun terminology decision required."
    write_jsonl(output, row)
    print(f"working_target_set string_id={row.get('string_id')} output={output}")


def build_from_work(args: argparse.Namespace) -> None:
    rom_path = Path(args.rom)
    source_table = Path(args.source_table)
    ledger = read_one_jsonl(Path(args.ledger))
    working = read_one_jsonl(Path(args.working))
    source = working.get("source")
    if not isinstance(source, Mapping):
        raise AllocatorReject("source_hash_mismatch", "working record has no local source")
    if str(working.get("string_id")) != str(ledger.get("string_id")):
        raise AllocatorReject("source_hash_mismatch", "ledger/work string_id differs")
    source_text = str(source.get("text", ""))
    actual_ledger_hash = sha256(source_text.encode("utf-8"))
    if actual_ledger_hash != str(ledger.get("source_hash")):
        raise AllocatorReject("source_hash_mismatch", "working source differs from ledger")
    targets = working.get("targets")
    if not isinstance(targets, Mapping) or not isinstance(targets.get(args.locale), Mapping):
        raise AllocatorReject("missing_translation", args.locale)
    target_text = str(targets[args.locale].get("text", ""))
    rom = rom_path.read_bytes()
    records = read_source_records(source_table)
    source_offset = int(working["string_id"], 0) if isinstance(working["string_id"], str) else int(working["string_id"])
    if source_offset != args.target_offset:
        raise AllocatorReject("source_hash_mismatch", "target offset differs from requested offset")
    source_record = _record_by_offset(records, source_offset)
    if str(source_record["text"]) != source_text:
        raise AllocatorReject("source_hash_mismatch", "working source differs from source table")
    plan = build_plan(
        rom,
        records,
        source_offset,
        target_text,
        Path(args.font),
        Path(args.license),
        ledger_source_hash=str(ledger["source_hash"]),
    )
    patched_rom = patch_rom(rom, plan)
    report = build_report(rom, patched_rom, plan, args.adjacent_offset, Path(args.render_dir) if args.render_dir else None)
    Path(args.patched_rom).parent.mkdir(parents=True, exist_ok=True)
    Path(args.patched_rom).write_bytes(patched_rom)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"m18_gate=accepted string_id=0x{source_offset:08X} target_units={len(plan['allocations'])} "
        f"wide_new_slots=0 patched_rom={args.patched_rom} report={args.report}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed = subparsers.add_parser("seed-ledger")
    seed.add_argument("--source-table", type=Path, required=True)
    seed.add_argument("--target-offset", type=lambda value: int(value, 0), default=TARGET_RECORD_ID)
    seed.add_argument("--output", type=Path, required=True)

    target = subparsers.add_parser("set-target")
    target.add_argument("--working", type=Path, required=True)
    target.add_argument("--output", type=Path, required=True)
    target.add_argument("--zh-hans", required=True)
    target.add_argument("--zh-tw", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--rom", type=Path, required=True)
    build.add_argument("--source-table", type=Path, required=True)
    build.add_argument("--ledger", type=Path, required=True)
    build.add_argument("--working", type=Path, required=True)
    build.add_argument("--target-offset", type=lambda value: int(value, 0), default=TARGET_RECORD_ID)
    build.add_argument("--adjacent-offset", type=lambda value: int(value, 0), default=ADJACENT_OFFSET)
    build.add_argument("--font", type=Path, default=DEFAULT_FONT)
    build.add_argument("--license", type=Path, default=DEFAULT_LICENSE)
    build.add_argument("--locale", default="zh-TW", choices=["zh-TW"])
    build.add_argument("--patched-rom", type=Path, required=True)
    build.add_argument("--report", type=Path, required=True)
    build.add_argument("--render-dir", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "seed-ledger":
            emit_seed_ledger(args.source_table, args.target_offset, args.output)
        elif args.command == "set-target":
            set_target_work(args.working, args.output, args.zh_hans, args.zh_tw)
        else:
            build_from_work(args)
    except (AllocatorReject, M17Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"m18_rejected={exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
