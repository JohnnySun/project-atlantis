#!/usr/bin/env python3
"""Inspect and statically render the B3CJ glyph resource.

The tool is deliberately read-only by default.  It follows only the B3CJ
font callsites reviewed in csm3 commit 7e388ac and refuses a ROM whose fixed
identity, lookup literals, or reviewed function bytes do not match.  The
``--poc-rom`` mode writes an explicitly named, ignored copy and never edits
the input ROM.  It is a static proof of cell packing and table insertion, not
runtime or translation QA.

The Japanese source table and any generated POC ROM/image must stay under the
game's ignored ``research/`` or ``work/`` paths.  This module emits summaries,
hashes, and bounded samples rather than the source corpus or a raw font dump.
"""

from __future__ import annotations

import argparse
import binascii
import gzip
import hashlib
import json
import pathlib
import struct
import sys
from collections import defaultdict
from typing import Iterable, Iterator, Mapping, Sequence


EXPECTED_GAME_CODE = "B3CJ"
EXPECTED_FILE_SIZE = 0x02000000
EXPECTED_CRC32 = "12afae5d"
EXPECTED_SHA1 = "3f5253fcf57e07ce52472bd29a61d16b98a12376"
EXPECTED_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_HEADER_CHECKSUM = 0x6B
ROM_BASE_GBA = 0x08000000

# csm3 src/main.c:480-505 and sub_08003620.  This type-3 directory is the
# local ROM representation of gUnk_094D446C; entry 2 is the BIT font.
TYPE3_TABLE_FILE_OFFSET = 0x014D446C
TYPE3_RESOURCE_ID = 2
TYPE3_POINTER_SCALE = 16

FONT_MAGIC = b"BIT\0"
FONT_HEADER_SIZE = 0x1C
FONT_CELL_WIDTH = 12
FONT_CELL_HEIGHT = 12
FONT_CELL_ROW_STRIDE = 2
FONT_CELL_SIZE = FONT_CELL_HEIGHT * FONT_CELL_ROW_STRIDE

# csm3 asm/code_main.s:2868-2934, sub_0800348C.  These are GBA addresses,
# while the tool reports both GBA and file offsets for every table access.
MAP_TABLE_A_GBA = 0x08B6D624
MAP_TABLE_B_GBA = 0x08B704A4
FALLBACK_GLYPH_GBA = 0x08B6D5D0
FONT_BASE_RUNTIME_GBA = 0x03002984

REVIEWED_FUNCTIONS = (
    ("sub_0800D084", 0x0000D084, 0x0000D0B4, "4e6e33f072507741a23439defbe1c3ab64be1eafee8db055c94e7593b34fc40a"),
    ("sub_08001F14", 0x00001F14, 0x000020E4, "1a43c57ba0c56b974e1d14b0e11c4bb67742b8107402c1ac26f11247b09fad4d"),
    ("sub_0800348C", 0x0000348C, 0x0000350C, "84bcc98e25933a1b2707c35e58517a3132701243a657f594c09f84d38189e778"),
    ("sub_08003620", 0x00003620, 0x000036C4, "50c6d0ae857a3ee21235378435195c4865784e66947a1eba92de26d659702e3a"),
    ("sub_080036F8", 0x000036F8, 0x0000382E, "8593bbedfbfa610d0411f09ac808ccb4191ab7ff8b570f66168b94ddd639ee35"),
    ("sub_08003BC0_sub_08003EB8", 0x00003BC0, 0x00003EB4, "12735ec396cbe534d81f6daa89847594b1a645b86dcc50bba69563c33425c36d"),
    ("sub_0800B730", 0x0000B730, 0x0000B7DE, "d4807052a062cb7b57e436f9cf1ffdec0b74ce6537a57fc8e5557845d395fcb0"),
)

# Literal-pool offsets are local B3CJ file offsets.  The values are the
# independent ROM evidence for the csm3 names above; they are not imported as
# an unverified external address map.
REVIEWED_LITERALS = (
    ("sub_0800348C.table_a", 0x000034B8, MAP_TABLE_A_GBA),
    ("sub_0800348C.table_b", 0x000034F0, MAP_TABLE_B_GBA),
    ("sub_0800348C.fallback", 0x000034F4, FALLBACK_GLYPH_GBA),
    ("sub_0800348C.font_base_global", 0x00003508, FONT_BASE_RUNTIME_GBA),
    ("sub_08003620.font_base_global", 0x00003654, FONT_BASE_RUNTIME_GBA),
    ("sub_08003620.font_resource_callsite", 0x00003658, 0x03002988),
    ("sub_08003620.font_resource_base", 0x0000365C, 0x02001800),
    ("sub_08003620.font_resource_type", 0x00003660, 0x05000200),
    ("sub_080036F8.macro_table", 0x00003760, 0x03005580),
    ("sub_080036F8.macro_end", 0x00003764, 0x0000F0FF),
    ("sub_080036F8.macro_marker", 0x00003768, 0x0000C083),
)

KNOWN_SAMPLE_CHARS = ("正", "直", "同", "部", "屋", "ら", "す", "γ")
UNIFONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
POC_MAPPINGS = (
    # ec48/ec49 are unused zero table entries and are intentionally opaque
    # project code units, not claimed Japanese Unicode code points.
    (bytes.fromhex("ec48"), "的", 0x845),
    (bytes.fromhex("ec49"), "你", 0x846),
)


def read_u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"u16 read outside input at 0x{offset:x}")
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 read outside input at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def gba_to_file_offset(address: int) -> int:
    if address < ROM_BASE_GBA:
        raise ValueError(f"address 0x{address:08x} is not a ROM address")
    return address - ROM_BASE_GBA


def gba_header_checksum(data: bytes) -> int:
    if len(data) < 0xBE:
        raise ValueError("ROM is too short to contain a GBA header")
    return (0x100 - 0x19 - sum(data[0xA0:0xBD])) & 0xFF


def verify_rom(data: bytes) -> dict[str, object]:
    """Return fixed B3CJ identity evidence and fail closed on mismatch."""

    if len(data) != EXPECTED_FILE_SIZE:
        raise ValueError(f"expected 0x{EXPECTED_FILE_SIZE:x}-byte B3CJ ROM, got 0x{len(data):x}")
    game_code = data[0xAC:0xB0].decode("ascii", "replace")
    if game_code != EXPECTED_GAME_CODE:
        raise ValueError(f"expected game code {EXPECTED_GAME_CODE}, got {game_code!r}")
    crc32 = f"{binascii.crc32(data) & 0xFFFFFFFF:08x}"
    sha1 = hashlib.sha1(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()
    stored_checksum = data[0xBD]
    calculated_checksum = gba_header_checksum(data)
    checks = {
        "size": len(data) == EXPECTED_FILE_SIZE,
        "crc32": crc32 == EXPECTED_CRC32,
        "sha1": sha1 == EXPECTED_SHA1,
        "sha256": sha256 == EXPECTED_SHA256,
        "header_checksum": stored_checksum == EXPECTED_HEADER_CHECKSUM == calculated_checksum,
    }
    if not all(checks.values()):
        failed = ", ".join(name for name, matched in checks.items() if not matched)
        raise ValueError(f"B3CJ ROM identity mismatch: {failed}")
    return {
        "game_code": game_code,
        "size": len(data),
        "crc32": crc32,
        "sha1": sha1,
        "sha256": sha256,
        "stored_header_checksum": f"{stored_checksum:02x}",
        "calculated_header_checksum": f"{calculated_checksum:02x}",
        "matches": checks,
    }


def verify_static_evidence(data: bytes) -> dict[str, object]:
    """Check local literals and function bytes against reviewed csm3 ranges."""

    literal_checks: list[dict[str, object]] = []
    for name, file_offset, expected in REVIEWED_LITERALS:
        actual = read_u32(data, file_offset)
        matched = actual == expected
        literal_checks.append(
            {
                "name": name,
                "file_offset": f"0x{file_offset:x}",
                "expected_gba_value": f"0x{expected:08x}",
                "actual_value": f"0x{actual:08x}",
                "matched": matched,
            }
        )
        if not matched:
            raise ValueError(f"static literal mismatch at 0x{file_offset:x}: {name}")

    function_checks: list[dict[str, object]] = []
    for name, start, end, expected_hash in REVIEWED_FUNCTIONS:
        actual_hash = hashlib.sha256(data[start:end]).hexdigest()
        matched = actual_hash == expected_hash
        function_checks.append(
            {
                "name": name,
                "file_range": f"0x{start:x}..0x{end:x}",
                "sha256": actual_hash,
                "matched": matched,
            }
        )
        if not matched:
            raise ValueError(f"reviewed function hash mismatch: {name}")
    return {
        "csm3_commit": "7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2",
        "literal_checks": literal_checks,
        "function_checks": function_checks,
        "note": "Local B3CJ bytes, not external symbol names alone, promote this chain to confirmed.",
    }


def resolve_type3_resource(
    data: bytes,
    resource_id: int = TYPE3_RESOURCE_ID,
    table_file_offset: int = TYPE3_TABLE_FILE_OFFSET,
) -> dict[str, int]:
    """Resolve the csm3 type-3 directory entry using 16-byte units."""

    if resource_id < 0:
        raise ValueError("resource id must be non-negative")
    directory_file_offset = table_file_offset + 4 * (resource_id * 2 + 2)
    relative_units = read_u32(data, directory_file_offset)
    span_units = read_u32(data, directory_file_offset + 4)
    payload_file_offset = table_file_offset + relative_units * TYPE3_POINTER_SCALE
    span_bytes = span_units * TYPE3_POINTER_SCALE
    if payload_file_offset + span_bytes > len(data):
        raise ValueError("type-3 resource points outside the input ROM")
    if span_bytes < FONT_HEADER_SIZE:
        raise ValueError("type-3 font resource is shorter than its BIT header")
    return {
        "resource_id": resource_id,
        "directory_file_offset": directory_file_offset,
        "relative_units": relative_units,
        "span_units": span_units,
        "span_bytes": span_bytes,
        "payload_file_offset": payload_file_offset,
        "payload_end_file_offset": payload_file_offset + span_bytes,
    }


def parse_font_resource(
    data: bytes,
    resource: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Read BIT metadata and bound the 24-byte cell array."""

    resolved = resolve_type3_resource(data) if resource is None else dict(resource)
    payload = int(resolved["payload_file_offset"])
    resource_end = int(resolved["payload_end_file_offset"])
    if data[payload : payload + 4] != FONT_MAGIC:
        raise ValueError(f"font resource at 0x{payload:x} is not BIT")
    data_size = read_u32(data, payload + 0x18)
    if data_size % FONT_CELL_SIZE:
        raise ValueError(f"BIT data size 0x{data_size:x} is not divisible by cell size")
    font_base = payload + FONT_HEADER_SIZE
    font_end = font_base + data_size
    if font_end > resource_end or font_end > len(data):
        raise ValueError("BIT glyph data exceeds its type-3 resource span")
    padding = data[font_end:resource_end]
    return {
        "resource": resolved,
        "magic": FONT_MAGIC.decode("ascii", "replace"),
        "header_file_offset": payload,
        "header_size": FONT_HEADER_SIZE,
        "cell_width": FONT_CELL_WIDTH,
        "cell_height": FONT_CELL_HEIGHT,
        "cell_row_stride": FONT_CELL_ROW_STRIDE,
        "cell_size": FONT_CELL_SIZE,
        "font_base_file_offset": font_base,
        "font_data_size": data_size,
        "font_end_file_offset": font_end,
        "slot_count": data_size // FONT_CELL_SIZE,
        "resource_padding_size": len(padding),
        "resource_padding_sha256": hashlib.sha256(padding).hexdigest(),
        "header_words": {
            "version": read_u32(data, payload + 4),
            "cell_metrics": data[payload + 0x14 : payload + 0x18].hex(),
            "data_size": data_size,
        },
    }


def is_strict_shift_jis_pair(raw: bytes) -> bool:
    if len(raw) != 2:
        return False
    lead, trail = raw
    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC):
        return False
    if not (0x40 <= trail <= 0x7E or 0x80 <= trail <= 0xFC):
        return False
    try:
        raw.decode("shift_jis")
    except UnicodeDecodeError:
        return False
    return True


def iter_formula_pairs() -> Iterator[bytes]:
    for lead in tuple(range(0x81, 0xA0)) + tuple(range(0xE0, 0xFD)):
        for trail in tuple(range(0x40, 0x7F)) + tuple(range(0x80, 0xFD)):
            yield bytes((lead, trail))


def iter_shift_jis_code_units(encoded: bytes) -> Iterator[bytes]:
    """Yield aligned strict Shift-JIS double-byte units from encoded text."""

    index = 0
    while index < len(encoded):
        if index + 1 < len(encoded) and is_strict_shift_jis_pair(encoded[index : index + 2]):
            yield encoded[index : index + 2]
            index += 2
        else:
            index += 1


def table_index(raw: bytes) -> tuple[int, int, int]:
    """Return (table GBA base, entry index, table entry file offset)."""

    if len(raw) != 2:
        raise ValueError("a B3CJ code unit must contain exactly two bytes")
    lead, trail = raw
    if lead <= 0x9F:
        if lead < 0x81:
            raise ValueError(f"lead byte 0x{lead:02x} is outside sub_0800348C's first range")
        base = MAP_TABLE_A_GBA
        row = lead - 0x81
    else:
        if lead < 0xE0:
            raise ValueError(f"lead byte 0x{lead:02x} is outside sub_0800348C's second range")
        base = MAP_TABLE_B_GBA
        row = lead - 0xE0
    column = trail - 0x40
    index = row * 0xC0 + column
    entry_gba = base + index * 2
    return base, index, gba_to_file_offset(entry_gba)


def lookup_code_unit(
    data: bytes,
    raw: bytes,
    slot_count: int,
    font_base_file_offset: int | None = None,
) -> dict[str, object]:
    """Apply sub_0800348C to one raw memory-order two-byte code unit."""

    base_gba, index, table_file_offset = table_index(raw)
    table_value = read_u16(data, table_file_offset)
    result: dict[str, object] = {
        "raw_hex": raw.hex(),
        "code_unit": f"0x{int.from_bytes(raw, 'little'):04x}",
        "lead": f"0x{raw[0]:02x}",
        "trail": f"0x{raw[1]:02x}",
        "table_base_gba": f"0x{base_gba:08x}",
        "table_index": index,
        "table_entry_gba": f"0x{base_gba + index * 2:08x}",
        "table_entry_file_offset": f"0x{table_file_offset:x}",
        "table_value": f"0x{table_value:04x}",
    }
    if table_value == 0:
        result.update(
            {
                "status": "fallback",
                "fallback_gba": f"0x{FALLBACK_GLYPH_GBA:08x}",
                "fallback_file_offset": f"0x{gba_to_file_offset(FALLBACK_GLYPH_GBA):x}",
            }
        )
        return result
    glyph_id = table_value - 1
    result["glyph_id"] = glyph_id
    if glyph_id >= slot_count:
        result["status"] = "out_of_resource"
        return result
    result["status"] = "mapped"
    if font_base_file_offset is not None:
        cell_offset = font_base_file_offset + glyph_id * FONT_CELL_SIZE
        cell = data[cell_offset : cell_offset + FONT_CELL_SIZE]
        result.update(
            {
                "cell_file_offset": f"0x{cell_offset:x}",
                "cell_resource_offset": FONT_HEADER_SIZE + glyph_id * FONT_CELL_SIZE,
                "cell_sha256": hashlib.sha256(cell).hexdigest(),
            }
        )
    return result


def cell_rows(cell: bytes) -> tuple[str, ...]:
    """Decode the static 12x12 active bits, MSB-first, from a 24-byte cell."""

    if len(cell) != FONT_CELL_SIZE:
        raise ValueError(f"expected {FONT_CELL_SIZE} cell bytes, got {len(cell)}")
    rows: list[str] = []
    for row in range(FONT_CELL_HEIGHT):
        first, second = cell[row * 2 : row * 2 + 2]
        bits = (first << 8) | second
        rows.append("".join("#" if bits & (1 << (15 - column)) else "." for column in range(FONT_CELL_WIDTH)))
    return tuple(rows)


def render_cell(cell: bytes) -> str:
    return "\n".join(cell_rows(cell))


def render_glyph(data: bytes, font: Mapping[str, object], glyph_id: int) -> dict[str, object]:
    slot_count = int(font["slot_count"])
    if not 0 <= glyph_id < slot_count:
        raise ValueError(f"glyph id 0x{glyph_id:x} outside 0..0x{slot_count - 1:x}")
    cell_offset = int(font["font_base_file_offset"]) + glyph_id * FONT_CELL_SIZE
    cell = data[cell_offset : cell_offset + FONT_CELL_SIZE]
    rows = cell_rows(cell)
    return {
        "glyph_id": glyph_id,
        "cell_file_offset": f"0x{cell_offset:x}",
        "cell_sha256": hashlib.sha256(cell).hexdigest(),
        "render_sha256": hashlib.sha256("\n".join(rows).encode("ascii")).hexdigest(),
        "rows": rows,
    }


def _font_cell_bytes(data: bytes, font: Mapping[str, object], glyph_id: int) -> bytes:
    slot_count = int(font["slot_count"])
    if not 0 <= glyph_id < slot_count:
        raise ValueError(f"glyph id 0x{glyph_id:x} outside font resource")
    start = int(font["font_base_file_offset"]) + glyph_id * FONT_CELL_SIZE
    return data[start : start + FONT_CELL_SIZE]


def _summary_slot_ids(values: Sequence[int], max_items: int = 64) -> dict[str, object]:
    return {
        "count": len(values),
        "first": [f"0x{value:03x}" for value in values[:max_items]],
        "truncated": len(values) > max_items,
    }


def scan_font(data: bytes, source_code_units: Iterable[bytes] | None = None) -> dict[str, object]:
    """Scan the actually addressable strict Shift-JIS code-unit space."""

    font = parse_font_resource(data)
    slot_count = int(font["slot_count"])
    mapped_by_slot: dict[int, list[bytes]] = defaultdict(list)
    fallback_count = 0
    out_of_resource: list[dict[str, object]] = []
    strict_pair_count = 0
    invalid_pair_count = 0
    for raw in iter_formula_pairs():
        if not is_strict_shift_jis_pair(raw):
            invalid_pair_count += 1
            continue
        strict_pair_count += 1
        lookup = lookup_code_unit(
            data,
            raw,
            slot_count=slot_count,
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        status = lookup["status"]
        if status == "fallback":
            fallback_count += 1
        elif status == "mapped":
            mapped_by_slot[int(lookup["glyph_id"])].append(raw)
        elif status == "out_of_resource":
            identity = raw.decode("shift_jis")
            out_of_resource.append(
                {
                    "raw_hex": raw.hex(),
                    "unicode": identity,
                    "codepoint": f"U+{ord(identity):04X}",
                    "table_entry_file_offset": lookup["table_entry_file_offset"],
                    "table_value": lookup["table_value"],
                    "target_glyph_id": lookup["glyph_id"],
                }
            )

    used_slots = sorted(mapped_by_slot)
    all_zero_slots = [
        glyph_id
        for glyph_id in range(slot_count)
        if _font_cell_bytes(data, font, glyph_id) == bytes(FONT_CELL_SIZE)
    ]
    unreferenced_slots = [glyph_id for glyph_id in range(slot_count) if glyph_id not in mapped_by_slot]
    blank_unreferenced = [glyph_id for glyph_id in unreferenced_slots if glyph_id in all_zero_slots]
    nonblank_unaddressable = [glyph_id for glyph_id in unreferenced_slots if glyph_id not in all_zero_slots]

    sample_rows: list[dict[str, object]] = []
    for char in KNOWN_SAMPLE_CHARS:
        raw = char.encode("shift_jis")
        addressing = lookup_code_unit(
            data,
            raw,
            slot_count=slot_count,
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        identity = {
            "unicode": char,
            "codepoint": f"U+{ord(char):04X}",
            "raw_shift_jis_hex": raw.hex(),
            "strict_decode": raw.decode("shift_jis"),
        }
        sample_rows.append(
            {
                "identity_evidence": identity,
                "addressing_evidence": addressing,
            }
        )

    source_summary: dict[str, object] | None = None
    if source_code_units is not None:
        source_list = list(source_code_units)
        source_lookup = [
            lookup_code_unit(
                data,
                raw,
                slot_count=slot_count,
                font_base_file_offset=int(font["font_base_file_offset"]),
            )
            for raw in source_list
        ]
        source_summary = {
            "unique_double_byte_units": len(source_list),
            "mapped_units": sum(item["status"] == "mapped" for item in source_lookup),
            "fallback_units": sum(item["status"] == "fallback" for item in source_lookup),
            "out_of_resource_units": sum(item["status"] == "out_of_resource" for item in source_lookup),
        }

    result: dict[str, object] = {
        "rom_scope": "B3CJ fixed Japanese ROM; static only",
        "font_resource": font,
        "addressing": {
            "formula": "sub_0800348C: table[(((lead-row)*0xc0)+((trail-0x40)))] u16; glyph_id=table_value-1",
            "input_byte_order": "raw memory order [lead, trail], read by the renderer as a little-endian u16",
            "table_a_gba": f"0x{MAP_TABLE_A_GBA:08x}",
            "table_a_file_offset": f"0x{gba_to_file_offset(MAP_TABLE_A_GBA):x}",
            "table_b_gba": f"0x{MAP_TABLE_B_GBA:08x}",
            "table_b_file_offset": f"0x{gba_to_file_offset(MAP_TABLE_B_GBA):x}",
            "fallback_gba": f"0x{FALLBACK_GLYPH_GBA:08x}",
            "font_base_runtime_gba": f"0x{FONT_BASE_RUNTIME_GBA:08x}",
            "font_base_file_offset": f"0x{int(font['font_base_file_offset']):x}",
            "cell_stride_bytes": FONT_CELL_SIZE,
            "cell_layout": "12 rows x 2 bytes; first 12 bits per row are MSB-first active pixels",
        },
        "strict_code_format_scan": {
            "formula_pair_candidates": sum(1 for _ in iter_formula_pairs()),
            "strict_shift_jis_pairs": strict_pair_count,
            "python_shift_jis_rejected_pairs": invalid_pair_count,
            "fallback_table_entries": fallback_count,
            "mapped_code_units": sum(len(values) for values in mapped_by_slot.values()),
            "mapped_unique_physical_slots": len(used_slots),
            "out_of_resource_code_units": out_of_resource,
        },
        "physical_slot_scan": {
            "total_slots": slot_count,
            "physical_id_range": ["0x000", f"0x{slot_count - 1:03x}"],
            "mapped_slot_ids": _summary_slot_ids(used_slots),
            "all_zero_slot_ids": _summary_slot_ids(all_zero_slots),
            "blank_unreferenced_slots": _summary_slot_ids(blank_unreferenced),
            "nonblank_unaddressable_slots": _summary_slot_ids(nonblank_unaddressable),
            "note": "Zero table entries use the renderer fallback and are not counted as safe free mappings.",
        },
        "source_samples": sample_rows,
    }
    if source_summary is not None:
        result["bounded_source_corpus"] = source_summary
    return result


def source_code_units_from_jsonl(path: pathlib.Path) -> tuple[list[bytes], dict[str, int]]:
    """Read only source_text to count code units; never include it in output."""

    units: set[bytes] = set()
    records = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        text = record.get("source_text")
        if not isinstance(text, str):
            continue
        records += 1
        encoded = text.encode("shift_jis")
        units.update(iter_shift_jis_code_units(encoded))
    return sorted(units), {"records": records, "unique_code_units": len(units)}


def _parse_unifont_line(line: str) -> tuple[int, bytes] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    codepoint_text, bitmap_text = stripped.split(":", 1)
    try:
        codepoint = int(codepoint_text, 16)
        bitmap = bytes.fromhex(bitmap_text)
    except ValueError:
        return None
    if len(bitmap) != 32:
        return None
    return codepoint, bitmap


def load_unifont_glyphs(path: pathlib.Path, codepoints: Iterable[int]) -> dict[int, bytes]:
    wanted = set(codepoints)
    found: dict[int, bytes] = {}
    with gzip.open(path, "rt", encoding="ascii") as handle:
        for line in handle:
            parsed = _parse_unifont_line(line)
            if parsed is None:
                continue
            codepoint, bitmap = parsed
            if codepoint in wanted:
                found[codepoint] = bitmap
                if len(found) == len(wanted):
                    break
    missing = sorted(wanted - set(found))
    if missing:
        raise ValueError("Unifont source is missing codepoints: " + ", ".join(f"U+{cp:04X}" for cp in missing))
    return found


def verify_unifont_source(path: pathlib.Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != UNIFONT_SOURCE_SHA256:
        raise ValueError(f"GNU Unifont source SHA-256 mismatch: {digest}")
    return digest


def unifont_bitmap_to_cell(bitmap: bytes) -> bytes:
    """Deterministically downsample a 16x16 Unifont bitmap to 12x12 MSB rows."""

    if len(bitmap) != 32:
        raise ValueError("expected a 16x16 Unifont bitmap (32 bytes)")
    rows = bytearray()
    for dst_y in range(FONT_CELL_HEIGHT):
        src_y = (dst_y * 16) // FONT_CELL_HEIGHT
        src_row = int.from_bytes(bitmap[src_y * 2 : src_y * 2 + 2], "big")
        bits = 0
        for dst_x in range(FONT_CELL_WIDTH):
            src_x = (dst_x * 16) // FONT_CELL_WIDTH
            if src_row & (1 << (15 - src_x)):
                bits |= 1 << (FONT_CELL_WIDTH - 1 - dst_x)
        # The ROM cell keeps the active 12 pixels in the high 12 bits; the
        # low four bits are padding, matching cell_rows() and observed cells.
        rows.extend((bits << 4).to_bytes(2, "big"))
    return bytes(rows)


def write_pgm(path: pathlib.Path, cells: Sequence[bytes], scale: int = 4) -> str:
    """Write a tiny grayscale contact sheet for static inspection only."""

    if not cells:
        raise ValueError("at least one glyph cell is required")
    if scale < 1:
        raise ValueError("PGM scale must be positive")
    width = len(cells) * FONT_CELL_WIDTH + len(cells) - 1
    height = FONT_CELL_HEIGHT
    pixels = bytearray(width * height)
    x_offset = 0
    for index, cell in enumerate(cells):
        rows = cell_rows(cell)
        for y, row in enumerate(rows):
            for x, value in enumerate(row):
                pixels[y * width + x_offset + x] = 0 if value == "#" else 255
        x_offset += FONT_CELL_WIDTH + 1
    if scale != 1:
        scaled = bytearray(width * scale * height * scale)
        scaled_width = width * scale
        for y in range(height):
            for x in range(width):
                value = pixels[y * width + x]
                for dy in range(scale):
                    start = (y * scale + dy) * scaled_width + x * scale
                    scaled[start : start + scale] = bytes((value,)) * scale
        width *= scale
        height *= scale
        pixels = scaled
    payload = f"P5\n{width} {height}\n255\n".encode("ascii") + bytes(pixels)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def build_static_poc(
    data: bytes,
    font_source: pathlib.Path,
    mappings: Sequence[tuple[bytes, str, int]] = POC_MAPPINGS,
) -> tuple[bytes, dict[str, object], tuple[bytes, ...]]:
    """Return a copied ROM with two blank slots mapped to generated glyph cells."""

    font = parse_font_resource(data)
    slot_count = int(font["slot_count"])
    source_font_sha256 = verify_unifont_source(font_source)
    codepoints = [ord(char) for _, char, _ in mappings]
    source_glyphs = load_unifont_glyphs(font_source, codepoints)
    patched = bytearray(data)
    changed: list[dict[str, object]] = []
    rendered_cells: list[bytes] = []
    for raw, char, glyph_id in mappings:
        addressing = lookup_code_unit(
            data,
            raw,
            slot_count=slot_count,
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        if addressing["status"] != "fallback":
            raise ValueError(f"POC code unit {raw.hex()} is not an unused zero mapping")
        if not 0 <= glyph_id < slot_count:
            raise ValueError(f"POC glyph id 0x{glyph_id:x} outside font")
        cell_offset = int(font["font_base_file_offset"]) + glyph_id * FONT_CELL_SIZE
        if data[cell_offset : cell_offset + FONT_CELL_SIZE] != bytes(FONT_CELL_SIZE):
            raise ValueError(f"POC slot 0x{glyph_id:x} is not physically blank")
        cell = unifont_bitmap_to_cell(source_glyphs[ord(char)])
        struct.pack_into("<H", patched, int(addressing["table_entry_file_offset"], 16), glyph_id + 1)
        patched[cell_offset : cell_offset + FONT_CELL_SIZE] = cell
        rendered_cells.append(cell)
        changed.append(
            {
                "raw_code_unit": raw.hex(),
                "identity": "custom opaque code unit; source character is POC-only",
                "poc_character": char,
                "poc_codepoint": f"U+{ord(char):04X}",
                "table_entry_file_offset": addressing["table_entry_file_offset"],
                "old_table_value": addressing["table_value"],
                "new_table_value": f"0x{glyph_id + 1:04x}",
                "glyph_id": glyph_id,
                "cell_file_offset": f"0x{cell_offset:x}",
                "cell_sha256": hashlib.sha256(cell).hexdigest(),
            }
        )

    untouched_id = min(int(item["glyph_id"]) for item in changed) - 1
    if untouched_id < 0 or untouched_id in {int(item["glyph_id"]) for item in changed}:
        raise ValueError("POC mappings do not leave an adjacent untouched glyph")
    untouched = _font_cell_bytes(data, font, untouched_id)
    render_cells = (untouched,) + tuple(rendered_cells)
    changed_byte_count = sum(before != after for before, after in zip(data, patched))
    report = {
        "static_only": True,
        "runtime_qa": False,
        "source_font": str(font_source),
        "source_font_sha256": source_font_sha256,
        "font_resource_sha256": hashlib.sha256(
            data[int(font["header_file_offset"]) : int(font["resource"]["payload_end_file_offset"])]
        ).hexdigest(),
        "changed_mappings": changed,
        "changed_region_byte_count": len(mappings) * (2 + FONT_CELL_SIZE),
        "changed_byte_count": changed_byte_count,
        "untouched_adjacent_glyph_id": untouched_id,
        "untouched_adjacent_cell_sha256": hashlib.sha256(untouched).hexdigest(),
        "patched_rom_sha256": hashlib.sha256(patched).hexdigest(),
        "note": "Static cell/table proof only; no script translation or runtime rendering claim.",
    }
    return bytes(patched), report, render_cells


def _render_requested_text(data: bytes, font: Mapping[str, object], text: str) -> str:
    if len(text) > 8:
        raise ValueError("--render-text is limited to 8 characters")
    blocks: list[str] = []
    for char in text:
        raw = char.encode("shift_jis")
        addressing = lookup_code_unit(
            data,
            raw,
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        if addressing["status"] != "mapped":
            blocks.append(f"{char}: {addressing['status']}")
            continue
        glyph = render_glyph(data, font, int(addressing["glyph_id"]))
        blocks.append(f"{char} {addressing['raw_hex']} -> glyph 0x{int(addressing['glyph_id']):03x}\n" + "\n".join(glyph["rows"]))
    return "\n\n".join(blocks)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="verified local Japanese B3CJ ROM")
    parser.add_argument("--source-jsonl", type=pathlib.Path, help="ignored extracted source table; count only")
    parser.add_argument("--render-text", help="render at most eight mapped source characters as ASCII")
    parser.add_argument("--summary-output", type=pathlib.Path, help="write bounded JSON summary to an explicit path")
    parser.add_argument("--poc-rom", type=pathlib.Path, help="write a static POC copy; never overwrites the input ROM")
    parser.add_argument("--font-source", type=pathlib.Path, help="GNU Unifont .hex.gz used only by --poc-rom")
    parser.add_argument("--poc-render", type=pathlib.Path, help="write the POC contact sheet as ignored PGM")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        data = args.rom.read_bytes()
        identity = verify_rom(data)
        evidence = verify_static_evidence(data)
        source_units = None
        source_meta = None
        if args.source_jsonl is not None:
            source_units, source_meta = source_code_units_from_jsonl(args.source_jsonl)
        report = scan_font(data, source_units)
        report["rom_identity"] = identity
        report["static_callsite_evidence"] = evidence
        if source_meta is not None:
            report["bounded_source_corpus"] = {
                **dict(report.get("bounded_source_corpus", {})),
                **source_meta,
            }
        if args.render_text:
            report["render_text"] = args.render_text
            report["rendered_ascii"] = _render_requested_text(data, report["font_resource"], args.render_text)
        if args.poc_rom is not None:
            if args.font_source is None:
                raise ValueError("--poc-rom requires --font-source")
            patched, poc_report, render_cells = build_static_poc(data, args.font_source)
            args.poc_rom.parent.mkdir(parents=True, exist_ok=True)
            args.poc_rom.write_bytes(patched)
            poc_report["output_rom"] = str(args.poc_rom)
            if args.poc_render is not None:
                poc_report["render_output"] = str(args.poc_render)
                poc_report["render_sha256"] = write_pgm(args.poc_render, render_cells)
            report["static_poc"] = poc_report
        output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        if args.summary_output is not None:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"inspect_font.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
