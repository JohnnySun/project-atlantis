#!/usr/bin/env python3
"""Apply a bounded B3EJ fixed-slot patch using the licensed zh-TW glyph map.

This tool is deliberately narrower than a general encoder.  It accepts only
the reviewed system-item-class, Table B, event-system or story-event pointer pools, keeps every record in its
original span, and reuses codepage entries selected by the bounded decoded
source-pool audit.  The selected raw code units are a game-local mapping to
the Unicode characters in the mapping file; the tool never changes the ROM
codepage table.  Licensed Unifont-T 16x16 bitmaps are converted to the two
0x20-byte source planes, with the secondary plane zero-filled.

ROMs, source tables, generated glyph planes and BPS files are caller-owned
ignored outputs.  Reports contain hashes and offsets only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import font_coverage  # noqa: E402
import font_glyph_format  # noqa: E402
import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
POOL_SPECS = {
    "system-item-class": {"file_offset": 0x0CBC54, "entry_count": 183},
    "table-b": {"file_offset": 0x0D1FFC, "entry_count": 44},
    "event-system": {"file_offset": 0x0D4D00, "entry_count": 28},
    "story-event": {"file_offset": 0x0CDB64, "entry_count": 33},
}
ENTRY_PATTERN = re.compile(r"^b3ej:(system-item-class|table-b|event-system|story-event):(\d{3})$")
GLYPH_SOURCE_BASES = font_glyph_format.GLYPH_SOURCE_BASES
GLYPH_STRIDE = font_glyph_format.GLYPH_STRIDE


def _parse_hex(value: object, *, field: str, width: int = 4) -> int:
    text = str(value)
    if text.lower().startswith("0x"):
        number = int(text, 16)
    else:
        number = int(text, 16)
    if not 0 <= number < (1 << (width * 4)):
        raise ValueError(f"{field} outside {width}-digit range: {value!r}")
    return number


def parse_mapping(path: Path) -> dict[str, object]:
    mapping = json.loads(path.read_text(encoding="utf-8"))
    if mapping.get("revision") != "B3EJ":
        raise ValueError("custom glyph mapping is not for B3EJ")
    entries = mapping.get("mappings")
    if not isinstance(entries, list) or not entries:
        raise ValueError("custom glyph mapping has no mappings")
    by_codepoint: dict[int, dict[str, object]] = {}
    by_unit: dict[int, dict[str, object]] = {}
    by_index: dict[int, dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("custom glyph mapping entry is not an object")
        unicode_value = str(entry.get("unicode", ""))
        if not unicode_value.upper().startswith("U+"):
            raise ValueError(f"invalid Unicode mapping: {unicode_value!r}")
        codepoint = int(unicode_value[2:], 16)
        unit = _parse_hex(entry.get("code_unit"), field="code_unit")
        index = int(entry.get("codepage_index"))
        if not 0 <= codepoint <= 0x10FFFF:
            raise ValueError(f"Unicode codepoint outside range: {unicode_value}")
        if not 0 <= index < font_glyph_format.CODEPAGE_COUNT:
            raise ValueError(f"codepage index outside range: {index}")
        if codepoint in by_codepoint or unit in by_unit or index in by_index:
            raise ValueError("custom glyph mapping contains a duplicate codepoint, unit or index")
        normalized = {
            "unicode": f"U+{codepoint:04X}",
            "codepoint": codepoint,
            "code_unit": unit,
            "code_unit_hex": f"0x{unit:04X}",
            "codepage_index": index,
        }
        by_codepoint[codepoint] = normalized
        by_unit[unit] = normalized
        by_index[index] = normalized
    return {
        "metadata": mapping,
        "by_codepoint": by_codepoint,
        "by_unit": by_unit,
        "by_index": by_index,
    }


def _read_font_planes(font_path: Path, codepoints: set[int]) -> dict[int, tuple[bytes, bytes]]:
    found: dict[int, tuple[bytes, bytes]] = {}
    with gzip.open(font_path, "rt", encoding="ascii") as stream:
        for line in stream:
            codepoint_hex, separator, bitmap_hex = line.strip().partition(":")
            if not separator:
                continue
            codepoint = int(codepoint_hex, 16)
            if codepoint not in codepoints or codepoint in found:
                continue
            bitmap = bytes.fromhex(bitmap_hex)
            if len(bitmap) != GLYPH_STRIDE:
                raise ValueError(
                    f"font source is not 16x16 for U+{codepoint:04X}: {len(bitmap)} bytes"
                )
            found[codepoint] = (bitmap, bytes(GLYPH_STRIDE))
            if len(found) == len(codepoints):
                break
    missing = sorted(codepoints - set(found))
    if missing:
        raise ValueError("licensed font source lacks: " + ", ".join(f"U+{cp:04X}" for cp in missing))
    return found


def encode_text(text: str, mapping: dict[int, dict[str, object]]) -> tuple[bytes, list[int]]:
    output = bytearray()
    custom_codepoints: list[int] = []
    for character in text:
        codepoint = ord(character)
        custom = mapping.get(codepoint)
        if custom is not None:
            output.extend(int(custom["code_unit"]).to_bytes(2, "big"))
            custom_codepoints.append(codepoint)
        else:
            try:
                output.extend(character.encode("shift_jis"))
            except UnicodeEncodeError as exc:
                raise ValueError(
                    f"target character U+{codepoint:04X} lacks standard Shift-JIS or custom mapping"
                ) from exc
    return bytes(output), custom_codepoints


def _encoded_code_units(encoded: bytes) -> list[int]:
    units: list[int] = []
    cursor = 0
    while cursor < len(encoded):
        lead = encoded[cursor]
        if lead <= 0x7F or 0xA1 <= lead <= 0xDF:
            cursor += 1
            continue
        if cursor + 1 >= len(encoded):
            raise ValueError("target contains a truncated double-byte code unit")
        units.append((lead << 8) | encoded[cursor + 1])
        cursor += 2
    return units


def _validate_target_codepage(encoded: bytes, codepage: list[int]) -> None:
    available = set(codepage)
    missing = sorted(set(_encoded_code_units(encoded)) - available)
    if missing:
        raise ValueError(
            "target contains raw code units absent from the B3EJ codepage: "
            + ", ".join(f"0x{unit:04X}" for unit in missing)
        )


def fixed_slot_replacement(original_payload: bytes, encoded_target: bytes) -> bytes:
    if len(encoded_target) > len(original_payload):
        raise ValueError(
            f"translated payload is {len(encoded_target)} bytes, "
            f"original slot is {len(original_payload)} bytes"
        )
    return encoded_target + b"\0" + b"\0" * (len(original_payload) - len(encoded_target))


def parse_pool_entry(string_id: object, pool: str) -> int:
    match = ENTRY_PATTERN.match(str(string_id))
    if match is None or match.group(1) != pool:
        raise ValueError(f"not a reviewed {pool} string id: {string_id!r}")
    entry = int(match.group(2))
    if entry >= POOL_SPECS[pool]["entry_count"]:
        raise ValueError(f"{pool} entry outside bounded range: {entry}")
    return entry


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _source_pool_code_units(path: Path) -> set[int]:
    used: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        text = record.get("text")
        if not isinstance(text, str):
            source = record.get("source")
            text = source.get("text") if isinstance(source, dict) else None
        if not isinstance(text, str):
            continue
        try:
            _encoded, units = font_coverage.shift_jis_code_units(text)
        except UnicodeEncodeError as exc:
            raise ValueError(f"source table contains non-Shift-JIS text at {record.get('string_id')}") from exc
        used.update(units)
    return used


def _validate_mapping_against_rom(
    data: bytes, mapping: dict[str, object], source_table: Path
) -> tuple[dict[int, dict[str, object]], dict[int, dict[str, object]]]:
    codepage = font_glyph_format.read_codepage(data)
    used_units = _source_pool_code_units(source_table)
    by_codepoint = mapping["by_codepoint"]
    by_unit = mapping["by_unit"]
    for unit, entry in by_unit.items():
        index = int(entry["codepage_index"])
        if codepage[index] != unit:
            raise ValueError(
                f"codepage mapping mismatch at index {index}: "
                f"ROM has 0x{codepage[index]:04X}, mapping has 0x{unit:04X}"
            )
        if unit in used_units:
            raise ValueError(f"custom raw code unit is used by the bounded source table: 0x{unit:04X}")
    return by_codepoint, by_unit


def _validate_record_controls(source_payload: bytes, target_payload: bytes) -> None:
    source_known, source_unknown = common.format_sequences(source_payload)
    target_known, target_unknown = common.format_sequences(target_payload)
    if source_known != target_known or source_unknown != target_unknown:
        raise ValueError("format sequence contract changed")
    source_controls = bytes(value for value in source_payload if value < 0x20)
    target_controls = bytes(value for value in target_payload if value < 0x20)
    if source_controls != target_controls:
        raise ValueError("control-byte contract changed")


def patch_pool(
    data: bytes,
    records: list[dict[str, object]],
    pool: str,
    mapping: dict[str, object],
    font_path: Path,
    source_table: Path,
) -> tuple[bytes, dict[str, object]]:
    if pool not in POOL_SPECS:
        raise ValueError(f"pool is not explicitly reviewed: {pool}")
    table_offset = POOL_SPECS[pool]["file_offset"]
    entry_count = POOL_SPECS[pool]["entry_count"]
    pointers = []
    for entry in range(entry_count):
        pointer = common.read_u32(data, table_offset + entry * 4)
        if not common.is_rom_pointer(pointer, len(data)):
            raise common.StaticContractError(f"pool pointer outside ROM at entry {entry}")
        pointers.append(pointer)
    pointer_bytes = data[table_offset:table_offset + entry_count * 4]
    codepage = font_glyph_format.read_codepage(data)
    by_codepoint, by_unit = _validate_mapping_against_rom(data, mapping, source_table)
    font_metadata = mapping["metadata"]
    expected_font_sha = font_metadata.get("font_source_sha256")
    actual_font_sha = hashlib.sha256(font_path.read_bytes()).hexdigest()
    if expected_font_sha and expected_font_sha != actual_font_sha:
        raise ValueError("licensed font source SHA-256 does not match mapping metadata")
    custom_planes = _read_font_planes(font_path, set(by_codepoint))
    patched = bytearray(data)
    seen_target_text: dict[int, str] = {}
    used_custom_codepoints: set[int] = set()
    rows = []
    glyph_rows = []
    for record in records:
        entry = parse_pool_entry(record.get("string_id"), pool)
        source = record.get("source")
        targets = record.get("targets")
        if not isinstance(source, dict) or not isinstance(targets, dict):
            raise ValueError(f"record {entry} is not a restored working record")
        source_text = source.get("text")
        target_locale = targets.get("zh-TW")
        target_text = target_locale.get("text") if isinstance(target_locale, dict) else None
        provenance = source.get("provenance", {})
        if not isinstance(source_text, str) or not isinstance(target_text, str) or not isinstance(provenance, dict):
            raise ValueError(f"record {entry} lacks source, target or provenance")
        target = pointers[entry] - ROM_BASE
        original_payload, terminator = common.read_c_string(data, target)
        if source_text != original_payload.decode("shift_jis"):
            raise ValueError(f"source text mismatch at {pool}:{entry}")
        if provenance.get("source_hash") != hashlib.sha256(original_payload).hexdigest():
            raise ValueError(f"raw source hash mismatch at {pool}:{entry}")
        if provenance.get("source_text_hash") != font_coverage.canonical_text_hash(source_text):
            raise ValueError(f"source text hash mismatch at {pool}:{entry}")
        if target in seen_target_text and seen_target_text[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at 0x{target:06X}")
        seen_target_text[target] = target_text
        encoded_target, custom_codepoints = encode_text(target_text, by_codepoint)
        _validate_target_codepage(encoded_target, codepage)
        _validate_record_controls(original_payload, encoded_target)
        patched[target:terminator + 1] = fixed_slot_replacement(original_payload, encoded_target)
        used_custom_codepoints.update(custom_codepoints)
        rows.append({
            "entry": entry,
            "record_file_offset": f"0x{target:06X}",
            "original_payload_length": len(original_payload),
            "translated_payload_length": len(encoded_target),
            "original_payload_sha256": hashlib.sha256(original_payload).hexdigest(),
            "translated_payload_sha256": hashlib.sha256(encoded_target).hexdigest(),
            "target_text_hash": font_coverage.canonical_text_hash(target_text),
            "custom_codepoints": [f"U+{codepoint:04X}" for codepoint in custom_codepoints],
            "relocated": False,
        })
    for codepoint in sorted(used_custom_codepoints):
        entry = by_codepoint[codepoint]
        index = int(entry["codepage_index"])
        first_plane, second_plane = custom_planes[codepoint]
        plane_receipts = []
        for base, plane in zip(GLYPH_SOURCE_BASES, (first_plane, second_plane)):
            offset = base - ROM_BASE + index * GLYPH_STRIDE
            before = data[offset:offset + GLYPH_STRIDE]
            if len(before) != GLYPH_STRIDE:
                raise common.StaticContractError(f"glyph slot outside ROM at index {index}")
            patched[offset:offset + GLYPH_STRIDE] = plane
            plane_receipts.append({
                "source_file_offset": f"0x{offset:06X}",
                "source_gba_address": f"0x{base + index * GLYPH_STRIDE:08X}",
                "byte_length": GLYPH_STRIDE,
                "before_sha256": hashlib.sha256(before).hexdigest(),
                "after_sha256": hashlib.sha256(plane).hexdigest(),
            })
        glyph_rows.append({
            "unicode": f"U+{codepoint:04X}",
            "code_unit": entry["code_unit_hex"],
            "codepage_index": index,
            "planes": plane_receipts,
        })
    return bytes(patched), {
        "read_only_source": True,
        "pool": pool,
        "table_file_offset": f"0x{table_offset:06X}",
        "table_entry_count": entry_count,
        "working_record_count": len(records),
        "unique_patched_target_count": len(seen_target_text),
        "custom_glyph_count": len(glyph_rows),
        "custom_glyph_mapping": "bounded decoded-source-pool unused code units; full-ROM non-use unproven",
        "font_source_sha256": actual_font_sha,
        "font_license": font_metadata.get("font_license"),
        "plane_policy": font_metadata.get("plane_policy"),
        "relocation": "disabled; fixed-slot records and existing glyph slots only",
        "pointer_table_sha256": hashlib.sha256(pointer_bytes).hexdigest(),
        "codepage_table_sha256": hashlib.sha256(data[
            font_glyph_format.CODEPAGE_TABLE_FILE_OFFSET:
            font_glyph_format.CODEPAGE_TABLE_FILE_OFFSET + font_glyph_format.CODEPAGE_COUNT * 2
        ]).hexdigest(),
        "rows": sorted(rows, key=lambda row: row["entry"]),
        "glyphs": glyph_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--pool", choices=sorted(POOL_SPECS), required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    args = parser.parse_args()
    original = args.rom.read_bytes()
    mapping = parse_mapping(args.mapping)
    patched, report = patch_pool(
        original, _records(args.work), args.pool, mapping, args.font, args.source_table
    )
    report["original_rom_sha256"] = hashlib.sha256(original).hexdigest()
    report["patched_rom_sha256"] = hashlib.sha256(patched).hexdigest()
    report["changed_byte_count"] = sum(left != right for left, right in zip(original, patched))
    if len(original) != len(patched):
        raise ValueError("custom glyph patch changed ROM size")
    args.output.write_bytes(patched)
    args.metadata_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        key: report[key]
        for key in ("pool", "table_entry_count", "working_record_count", "unique_patched_target_count", "custom_glyph_count", "changed_byte_count", "relocation")
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
