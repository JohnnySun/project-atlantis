#!/usr/bin/env python3
"""Build the bounded, fail-closed B3CJ M2.3 glyph/record POC.

This encoder is intentionally narrower than a release builder.  It accepts
only the checked-in M2.3 manifest, the verified clean B3CJ ROM, the ignored
source table, and the fixed GNU Unifont source.  It can allocate only
0x845..0x85f, preserves every existing mapping, requires exact source hashes
and record lengths, and refuses an LZ77 result that does not fit the original
resource span.  It writes a copied ROM and optional PGM contact sheet only to
explicit output paths; the input ROM is never modified.

The generated ROM is a static POC, not a translation release.  Its summaries
contain hashes and stable IDs, not the original source text.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys
from typing import Any, Iterable, Mapping, Sequence


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
INSPECT_FONT_PATH = GAME_ROOT / "tools" / "inspect_font.py"
EXTRACT_STATIC_PATH = GAME_ROOT / "tools" / "extract_static.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSPECT_FONT = _load_module("b3cj_inspect_font", INSPECT_FONT_PATH)
EXTRACT_STATIC = _load_module("b3cj_extract_static", EXTRACT_STATIC_PATH)

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
ALLOWED_SLOT_FIRST = 0x845
ALLOWED_SLOT_LAST = 0x85F
MAX_POC_RECORDS = 2


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} is not an integer: {value!r}") from exc
    raise ValueError(f"{field} must be an integer or 0x string")


def parse_code_unit(value: object, field: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a hex string")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not valid hex") from exc
    if len(raw) != 2:
        raise ValueError(f"{field} must contain exactly two bytes")
    return raw


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def validate_manifest(manifest: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Validate all bounded allocation and record contracts before reading ROM."""

    if parse_int(manifest.get("manifest_version"), "manifest_version") != 1:
        raise ValueError("unsupported M2.3 manifest version")
    if manifest.get("game") != EXPECTED_GAME or manifest.get("revision") != EXPECTED_REVISION:
        raise ValueError("manifest is not for the fixed B3CJ game")

    rom = _require_mapping(manifest.get("rom"), "rom")
    if str(rom.get("crc32", "")).lower() != INSPECT_FONT.EXPECTED_CRC32:
        raise ValueError("manifest ROM CRC32 does not match fixed B3CJ")
    if str(rom.get("sha256", "")).lower() != INSPECT_FONT.EXPECTED_SHA256:
        raise ValueError("manifest ROM SHA-256 does not match fixed B3CJ")
    if str(rom.get("source_table_sha256", "")).lower() != EXPECTED_SOURCE_TABLE_SHA256:
        raise ValueError("manifest source-table SHA-256 is not the fixed M2.1 table")

    font = _require_mapping(manifest.get("font"), "font")
    if parse_int(font.get("resource_type"), "font.resource_type") != 3:
        raise ValueError("manifest font resource type must be 3")
    if parse_int(font.get("resource_id"), "font.resource_id") != 2:
        raise ValueError("manifest font resource id must be 2")
    if parse_int(font.get("cell_size"), "font.cell_size") != INSPECT_FONT.FONT_CELL_SIZE:
        raise ValueError("manifest font cell size does not match B3CJ")
    if parse_int(font.get("allowed_slot_first"), "font.allowed_slot_first") != ALLOWED_SLOT_FIRST:
        raise ValueError("manifest may not widen the first allowed slot")
    if parse_int(font.get("allowed_slot_last"), "font.allowed_slot_last") != ALLOWED_SLOT_LAST:
        raise ValueError("manifest may not widen the last allowed slot")
    if str(font.get("source_font_sha256", "")).lower() != INSPECT_FONT.UNIFONT_SOURCE_SHA256:
        raise ValueError("manifest font source SHA-256 is not the fixed GNU Unifont source")

    allocation_values = _require_list(manifest.get("allocations"), "allocations")
    if not allocation_values or len(allocation_values) > ALLOWED_SLOT_LAST - ALLOWED_SLOT_FIRST + 1:
        raise ValueError("allocation count is outside the bounded empty-slot capacity")
    allocations: list[dict[str, object]] = []
    by_code_unit: set[bytes] = set()
    by_glyph_id: set[int] = set()
    for index, value in enumerate(allocation_values):
        item = dict(_require_mapping(value, f"allocations[{index}]"))
        raw = parse_code_unit(item.get("code_unit"), f"allocations[{index}].code_unit")
        if raw in by_code_unit:
            raise ValueError(f"duplicate allocation code unit {raw.hex()}")
        by_code_unit.add(raw)
        glyph_id = parse_int(item.get("glyph_id"), f"allocations[{index}].glyph_id")
        if not ALLOWED_SLOT_FIRST <= glyph_id <= ALLOWED_SLOT_LAST:
            raise ValueError(f"allocation glyph 0x{glyph_id:x} is outside 0x845..0x85f")
        if glyph_id in by_glyph_id:
            raise ValueError(f"duplicate allocation glyph 0x{glyph_id:x}")
        by_glyph_id.add(glyph_id)
        if item.get("code_unit_kind") != "opaque_extension":
            raise ValueError("M2.3 allocations must be explicit opaque_extension code units")
        if INSPECT_FONT.is_strict_shift_jis_pair(raw):
            raise ValueError(f"allocation {raw.hex()} collides with strict Shift-JIS")
        unicode_char = item.get("unicode")
        if not isinstance(unicode_char, str) or len(unicode_char) != 1:
            raise ValueError(f"allocations[{index}].unicode must be one Unicode character")
        codepoint = item.get("codepoint")
        if not isinstance(codepoint, str) or codepoint.upper() != f"U+{ord(unicode_char):04X}":
            raise ValueError(f"allocation {raw.hex()} Unicode/codepoint mismatch")
        allocations.append(
            {
                "code_unit": raw,
                "code_unit_hex": raw.hex(),
                "unicode": unicode_char,
                "codepoint": codepoint.upper(),
                "glyph_id": glyph_id,
                "status": item.get("status"),
            }
        )

    record_values = _require_list(manifest.get("records"), "records")
    if not 1 <= len(record_values) <= MAX_POC_RECORDS:
        raise ValueError(f"M2.3 permits one or two records, got {len(record_values)}")
    records: list[dict[str, object]] = []
    seen_records: set[str] = set()
    allocation_units = {item["code_unit"] for item in allocations}
    for index, value in enumerate(record_values):
        item = dict(_require_mapping(value, f"records[{index}]"))
        string_id = item.get("string_id")
        if not isinstance(string_id, str) or not string_id:
            raise ValueError(f"records[{index}].string_id must be non-empty")
        if string_id in seen_records:
            raise ValueError(f"duplicate record string_id {string_id}")
        seen_records.add(string_id)
        target_values = _require_list(item.get("target_code_units"), f"records[{index}].target_code_units")
        if not target_values:
            raise ValueError(f"records[{index}] has no target code units")
        target_units = [parse_code_unit(raw, f"records[{index}].target_code_units[{unit_index}]") for unit_index, raw in enumerate(target_values)]
        if any(raw not in allocation_units for raw in target_units):
            raise ValueError(f"record {string_id} refers to an unallocated code unit")
        target_byte_length = parse_int(item.get("target_byte_length"), f"records[{index}].target_byte_length")
        if target_byte_length != len(target_units) * 2:
            raise ValueError(f"record {string_id} target length does not match code-unit count")
        if target_byte_length <= 0 or target_byte_length > 0x100:
            raise ValueError(f"record {string_id} target length is outside bounded range")
        records.append(
            {
                "string_id": string_id,
                "locale": item.get("locale"),
                "resource_id": parse_int(item.get("resource_id"), f"records[{index}].resource_id"),
                "decompressed_offset": parse_int(item.get("decompressed_offset"), f"records[{index}].decompressed_offset"),
                "source_raw_sha256": str(item.get("source_raw_sha256", "")).lower(),
                "source_record_sha256": str(item.get("source_record_sha256", "")).lower(),
                "target_code_units": target_units,
                "target_code_units_hex": [raw.hex() for raw in target_units],
                "target_byte_length": target_byte_length,
                "status": item.get("status"),
            }
        )
    return allocations, records


def load_source_table(path: pathlib.Path, expected_sha256: str) -> dict[str, dict[str, object]]:
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(f"source table SHA-256 mismatch: {actual_sha256}")
    records: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"source table line {line_number} is not an object")
        string_id = value.get("string_id")
        if not isinstance(string_id, str):
            continue
        if string_id in records:
            raise ValueError(f"duplicate source string_id {string_id}")
        records[string_id] = value
    return records


def lz77_compress(decoded: bytes) -> bytes:
    """Deterministic greedy standard GBA LZ77 encoder for bounded resources."""

    if not 0 < len(decoded) <= 0xFFFFFF:
        raise ValueError("decoded resource size is outside GBA LZ77 header range")
    output = bytearray(b"\x10" + len(decoded).to_bytes(3, "little"))
    positions: dict[int, list[int]] = {}
    cursor = 0
    while cursor < len(decoded):
        flags = 0
        tokens: list[bytes] = []
        for bit in range(8):
            if cursor >= len(decoded):
                break
            window_start = max(0, cursor - 0x1000)
            max_length = min(18, len(decoded) - cursor)
            best_length = 0
            best_distance = 0
            candidates = positions.get(decoded[cursor], [])
            for candidate in reversed(candidates):
                if candidate < window_start:
                    break
                length = 0
                while length < max_length and decoded[candidate + length] == decoded[cursor + length]:
                    length += 1
                if length >= 3 and length > best_length:
                    best_length = length
                    best_distance = cursor - candidate
                    if length == max_length:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - bit)
                distance_minus_one = best_distance - 1
                tokens.append(bytes(((best_length - 3) << 4 | (distance_minus_one >> 8), distance_minus_one & 0xFF)))
                for position in range(cursor, cursor + best_length):
                    positions.setdefault(decoded[position], []).append(position)
                cursor += best_length
            else:
                tokens.append(bytes((decoded[cursor],)))
                positions.setdefault(decoded[cursor], []).append(cursor)
                cursor += 1
        output.append(flags)
        output.extend(b"".join(tokens))
    return bytes(output)


def _record_region(decoded: bytes, offset: int, raw_length: int) -> bytes:
    end = offset + 2 + raw_length + 2
    if offset < EXTRACT_STATIC.SCRIPT_HEADER_SIZE or end > len(decoded):
        raise ValueError(f"record region 0x{offset:x}..0x{end:x} is outside PSI3")
    if EXTRACT_STATIC.read_u16(decoded, offset) != EXTRACT_STATIC.TEXT_START_WORD:
        raise ValueError(f"record at 0x{offset:x} is not 0x0308")
    if EXTRACT_STATIC.read_u16(decoded, offset + 2 + raw_length) != EXTRACT_STATIC.TEXT_END_WORD:
        raise ValueError(f"record at 0x{offset:x} has no 0x0000 terminator at expected length")
    return decoded[offset:end]


def _ranges_contain(offset: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start <= offset < end for start, end in ranges)


def build_poc(
    rom_data: bytes,
    source_path: pathlib.Path,
    font_source_path: pathlib.Path,
    manifest: Mapping[str, object],
    manifest_sha256: str,
) -> tuple[bytes, dict[str, object], tuple[bytes, ...]]:
    """Build and fully verify an in-memory M2.3 POC before any write."""

    rom_identity = INSPECT_FONT.verify_rom(rom_data)
    INSPECT_FONT.verify_static_evidence(rom_data)
    allocations, record_specs = validate_manifest(manifest)
    manifest_rom = _require_mapping(manifest["rom"], "rom")
    if str(manifest_rom["source_table_sha256"]).lower() != EXPECTED_SOURCE_TABLE_SHA256:
        raise ValueError("manifest/source-table contract is not fixed")
    source_rows = load_source_table(source_path, EXPECTED_SOURCE_TABLE_SHA256)
    font_source_sha256 = INSPECT_FONT.verify_unifont_source(font_source_path)
    if font_source_sha256 != INSPECT_FONT.UNIFONT_SOURCE_SHA256:
        raise ValueError("font source is not fixed GNU Unifont 17.0.05")

    font = INSPECT_FONT.parse_font_resource(rom_data)
    slot_count = int(font["slot_count"])
    if slot_count <= ALLOWED_SLOT_LAST:
        raise ValueError("ROM font does not contain the entire allowed slot range")
    source_units, _source_meta = INSPECT_FONT.source_code_units_from_jsonl(source_path)
    source_unit_set = set(source_units)
    codepoints = [ord(str(item["unicode"])) for item in allocations]
    source_glyphs = INSPECT_FONT.load_unifont_glyphs(font_source_path, codepoints)
    patched = bytearray(rom_data)
    allocation_reports: list[dict[str, object]] = []
    changed_ranges: list[tuple[int, int]] = []
    allocated_slots: set[int] = set()
    for item in allocations:
        raw = item["code_unit"]
        glyph_id = int(item["glyph_id"])
        if raw in source_unit_set:
            raise ValueError(f"allocation code unit {raw.hex()} already occurs in source corpus")
        lookup = INSPECT_FONT.lookup_code_unit(
            rom_data,
            raw,
            slot_count=slot_count,
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        if lookup["status"] != "fallback" or lookup["table_value"] != "0x0000":
            raise ValueError(f"allocation code unit {raw.hex()} would overwrite an existing mapping")
        if glyph_id in allocated_slots:
            raise ValueError(f"duplicate allocation slot 0x{glyph_id:x}")
        allocated_slots.add(glyph_id)
        cell_offset = int(font["font_base_file_offset"]) + glyph_id * INSPECT_FONT.FONT_CELL_SIZE
        old_cell = rom_data[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE]
        if old_cell != bytes(INSPECT_FONT.FONT_CELL_SIZE):
            raise ValueError(f"allocation slot 0x{glyph_id:x} is not physically blank")
        unicode_codepoint = ord(str(item["unicode"]))
        cell = INSPECT_FONT.unifont_bitmap_to_cell(source_glyphs[unicode_codepoint])
        table_offset = int(str(lookup["table_entry_file_offset"]), 16)
        old_table_value = struct.unpack_from("<H", rom_data, table_offset)[0]
        struct.pack_into("<H", patched, table_offset, glyph_id + 1)
        patched[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE] = cell
        changed_ranges.extend(((table_offset, table_offset + 2), (cell_offset, cell_offset + INSPECT_FONT.FONT_CELL_SIZE)))
        allocation_reports.append(
            {
                "code_unit": raw.hex(),
                "unicode": item["unicode"],
                "codepoint": item["codepoint"],
                "glyph_id": glyph_id,
                "table_entry_file_offset": f"0x{table_offset:x}",
                "old_table_value": f"0x{old_table_value:04x}",
                "new_table_value": f"0x{glyph_id + 1:04x}",
                "cell_file_offset": f"0x{cell_offset:x}",
                "cell_sha256": sha256_bytes(cell),
                "static_source": "GNU Unifont 17.0.05; deterministic 16x16 to 12x12 downsample",
            }
        )

    resource_states: dict[int, dict[str, object]] = {}
    record_reports: list[dict[str, object]] = []
    for spec in record_specs:
        string_id = str(spec["string_id"])
        source_row = source_rows.get(string_id)
        if source_row is None:
            raise ValueError(f"manifest source string_id is missing: {string_id}")
        if source_row.get("raw_sha256") != spec["source_raw_sha256"]:
            raise ValueError(f"source raw hash mismatch for {string_id}")
        if source_row.get("record_sha256") != spec["source_record_sha256"]:
            raise ValueError(f"source record hash mismatch for {string_id}")
        source_text = source_row.get("source_text")
        if not isinstance(source_text, str):
            raise ValueError(f"source text is missing for {string_id}")
        source_payload = source_text.encode("shift_jis")
        if sha256_bytes(source_payload) != spec["source_raw_sha256"]:
            raise ValueError(f"source text re-encode hash mismatch for {string_id}")
        resource_id = int(spec["resource_id"])
        decompressed_offset = int(spec["decompressed_offset"])
        state = resource_states.get(resource_id)
        if state is None:
            resolved = EXTRACT_STATIC.resolve_script_resource(rom_data, resource_id)
            decoded, compressed_size = EXTRACT_STATIC.decode_lz77(rom_data, resolved["payload_file_offset"])
            state = {
                "resource_id": resource_id,
                "resolved": resolved,
                "original_decoded": decoded,
                "decoded": bytearray(decoded),
                "original_compressed_size": compressed_size,
                "original_compressed_sha256": sha256_bytes(rom_data[resolved["payload_file_offset"] : resolved["payload_file_offset"] + compressed_size]),
                "patches": [],
            }
            resource_states[resource_id] = state
        original_decoded = bytes(state["original_decoded"])
        raw_length = parse_int(source_row.get("raw_length"), f"{string_id}.raw_length")
        original_record = _record_region(original_decoded, decompressed_offset, raw_length)
        if sha256_bytes(original_record) != spec["source_record_sha256"]:
            raise ValueError(f"decoded record hash mismatch for {string_id}")
        if original_record[2:-2] != source_payload:
            raise ValueError(f"decoded/source payload mismatch for {string_id}")
        target_units = list(spec["target_code_units"])
        target_payload = b"".join(target_units)
        if len(target_payload) != raw_length or len(target_payload) != int(spec["target_byte_length"]):
            raise ValueError(f"byte-length contract mismatch for {string_id}")
        target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
        end = decompressed_offset + len(target_record)
        decoded_mutable = state["decoded"]
        assert isinstance(decoded_mutable, bytearray)
        decoded_mutable[decompressed_offset:end] = target_record
        state["patches"].append(
            {
                "string_id": string_id,
                "offset": decompressed_offset,
                "end": end,
                "source_record_sha256": spec["source_record_sha256"],
                "source_raw_sha256": spec["source_raw_sha256"],
                "target_code_units": list(spec["target_code_units_hex"]),
                "target_payload_sha256": sha256_bytes(target_payload),
                "target_record_sha256": sha256_bytes(target_record),
                "target_record": target_record,
            }
        )

    resource_reports: list[dict[str, object]] = []
    for resource_id in sorted(resource_states):
        state = resource_states[resource_id]
        resolved = state["resolved"]
        assert isinstance(resolved, dict)
        decoded_mutable = state["decoded"]
        assert isinstance(decoded_mutable, bytearray)
        compressed = lz77_compress(bytes(decoded_mutable))
        span_bytes = int(resolved["span_units"]) * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
        if len(compressed) > span_bytes:
            raise ValueError(f"resource {resource_id} compressed output {len(compressed)} exceeds span {span_bytes}")
        payload_offset = int(resolved["payload_file_offset"])
        patched[payload_offset : payload_offset + span_bytes] = compressed + bytes(span_bytes - len(compressed))
        changed_ranges.append((payload_offset, payload_offset + span_bytes))
        resource_reports.append(
            {
                "resource_id": resource_id,
                "payload_file_offset": f"0x{payload_offset:x}",
                "span_bytes": span_bytes,
                "original_compressed_size": state["original_compressed_size"],
                "new_compressed_size": len(compressed),
                "original_compressed_sha256": state["original_compressed_sha256"],
                "new_compressed_sha256": sha256_bytes(compressed),
                "decoded_size": len(decoded_mutable),
                "decoded_stream_sha256": sha256_bytes(bytes(decoded_mutable)[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]),
                "record_count": len(state["patches"]),
            }
        )

    patched_bytes = bytes(patched)
    diff_offsets = [index for index, (before, after) in enumerate(zip(rom_data, patched_bytes)) if before != after]
    if any(not _ranges_contain(offset, changed_ranges) for offset in diff_offsets):
        raise ValueError("POC changed a byte outside the manifest font/resource regions")

    post_font = INSPECT_FONT.parse_font_resource(patched_bytes)
    post_allocations: list[dict[str, object]] = []
    for item in allocations:
        lookup = INSPECT_FONT.lookup_code_unit(
            patched_bytes,
            item["code_unit"],
            slot_count=int(post_font["slot_count"]),
            font_base_file_offset=int(post_font["font_base_file_offset"]),
        )
        if lookup["status"] != "mapped" or int(lookup["glyph_id"]) != int(item["glyph_id"]):
            raise ValueError(f"post-patch font mapping failed for {item['code_unit_hex']}")
        post_allocations.append(
            {
                "code_unit": item["code_unit_hex"],
                "glyph_id": int(lookup["glyph_id"]),
                "table_value": lookup["table_value"],
                "cell_sha256": lookup["cell_sha256"],
            }
        )

    post_records: list[dict[str, object]] = []
    for resource_id in sorted(resource_states):
        state = resource_states[resource_id]
        resolved = state["resolved"]
        assert isinstance(resolved, dict)
        decoded_after, consumed_after = EXTRACT_STATIC.decode_lz77(patched_bytes, int(resolved["payload_file_offset"]))
        state_decoded = bytes(state["decoded"])
        if decoded_after != state_decoded:
            raise ValueError(f"resource {resource_id} LZ77 decode does not reproduce patched PSI3")
        parsed = EXTRACT_STATIC.parse_script_stream(decoded_after, resource_id)
        if EXTRACT_STATIC.encode_script_stream(parsed) != decoded_after[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]:
            raise ValueError(f"resource {resource_id} PSI3 opaque/record stream is not byte-identical")
        for patch in state["patches"]:
            target_record = patch["target_record"]
            assert isinstance(target_record, bytes)
            actual_record = decoded_after[int(patch["offset"]) : int(patch["end"])]
            if actual_record != target_record:
                raise ValueError(f"post-patch target record mismatch for {patch['string_id']}")
            post_records.append(
                {
                    "string_id": patch["string_id"],
                    "resource_id": resource_id,
                    "decompressed_offset": f"0x{int(patch['offset']):04x}",
                    "target_code_units": patch["target_code_units"],
                    "target_payload_sha256": patch["target_payload_sha256"],
                    "target_record_sha256": patch["target_record_sha256"],
                    "post_lz77_consumed_size": consumed_after,
                    "post_stream_roundtrip": "byte_identical",
                }
            )

    untouched_id = min(int(item["glyph_id"]) for item in allocations) - 1
    if untouched_id < 0 or untouched_id in {int(item["glyph_id"]) for item in allocations}:
        raise ValueError("allocation manifest has no adjacent untouched glyph")
    untouched_cell = bytes(
        patched_bytes[
            int(post_font["font_base_file_offset"]) + untouched_id * INSPECT_FONT.FONT_CELL_SIZE :
            int(post_font["font_base_file_offset"]) + (untouched_id + 1) * INSPECT_FONT.FONT_CELL_SIZE
        ]
    )
    changed_cells = [
        bytes(
            patched_bytes[
                int(post_font["font_base_file_offset"]) + int(item["glyph_id"]) * INSPECT_FONT.FONT_CELL_SIZE :
                int(post_font["font_base_file_offset"]) + (int(item["glyph_id"]) + 1) * INSPECT_FONT.FONT_CELL_SIZE
            ]
        )
        for item in allocations
    ]
    render_cells = (untouched_cell,) + tuple(changed_cells)
    summary: dict[str, object] = {
        "static_only": True,
        "runtime_qa": False,
        "manifest_sha256": manifest_sha256,
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "font_source_sha256": font_source_sha256,
        "clean_rom_identity": rom_identity,
        "font": {
            "resource_type": 3,
            "resource_id": 2,
            "font_base_file_offset": f"0x{int(post_font['font_base_file_offset']):x}",
            "cell_size": INSPECT_FONT.FONT_CELL_SIZE,
            "allowed_slot_first": f"0x{ALLOWED_SLOT_FIRST:03x}",
            "allowed_slot_last": f"0x{ALLOWED_SLOT_LAST:03x}",
            "post_allocations": post_allocations,
            "untouched_adjacent_glyph_id": untouched_id,
            "untouched_adjacent_cell_sha256": sha256_bytes(untouched_cell),
        },
        "records": post_records,
        "resources": resource_reports,
        "byte_level": {
            "changed_byte_count": len(diff_offsets),
            "changed_region_count": len(changed_ranges),
            "changed_outside_manifest_regions": False,
            "font_mapping_and_cell_roundtrip": "byte_identical",
            "record_and_psi3_stream_roundtrip": "byte_identical",
            "lz77_container": "repacked_in_original_resource_spans",
        },
        "note": "Bounded M2.3 POC only; target glyphs are static proof data, not reviewed translation.",
    }
    return patched_bytes, summary, render_cells


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="verified clean Japanese B3CJ ROM")
    parser.add_argument("--source-jsonl", type=pathlib.Path, required=True, help="ignored M2.1 source table")
    parser.add_argument("--manifest", type=pathlib.Path, required=True, help="tracked fail-closed M2.3 manifest")
    parser.add_argument("--font-source", type=pathlib.Path, required=True, help="fixed GNU Unifont .hex.gz")
    parser.add_argument("--output", type=pathlib.Path, required=True, help="ignored copied POC ROM")
    parser.add_argument("--summary-output", type=pathlib.Path, required=True, help="ignored bounded summary JSON")
    parser.add_argument("--render-output", type=pathlib.Path, required=True, help="ignored static PGM contact sheet")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean input ROM")
        manifest_bytes = args.manifest.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("manifest root must be an object")
        patched, summary, render_cells = build_poc(
            args.rom.read_bytes(),
            args.source_jsonl,
            args.font_source,
            manifest,
            sha256_bytes(manifest_bytes),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        render_sha256 = INSPECT_FONT.write_pgm(args.render_output, render_cells)
        summary["output_rom"] = str(args.output)
        summary["patched_rom_sha256"] = sha256_bytes(patched)
        summary["render_output"] = str(args.render_output)
        summary["render_sha256"] = render_sha256
        summary_text = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(summary_text, encoding="utf-8")
        print(
            "B3CJ_M2_3_POC_OK "
            f"records={len(summary['records'])} "
            f"allocations={len(summary['font']['post_allocations'])} "
            f"changed_bytes={summary['byte_level']['changed_byte_count']} "
            f"patched_sha256={summary['patched_rom_sha256']}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"encode_m2_3_poc.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
