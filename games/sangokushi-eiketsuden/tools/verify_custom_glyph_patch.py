#!/usr/bin/env python3
"""Verify a bounded B3EJ custom-glyph fixed-slot patch.

Unlike the ordinary verifier, this compares re-extracted payload bytes with
the explicit game-local Unicode-to-code-unit encoder.  It therefore does not
mistake a custom raw code unit for the Unicode character it represents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import custom_glyph_patch  # noqa: E402
import font_glyph_format  # noqa: E402
import table_b_common as common  # noqa: E402


def _records(path: Path, pool: str) -> dict[int, dict[str, object]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            result[custom_glyph_patch.parse_pool_entry(record.get("string_id"), pool)] = record
    return result


def _changed_offsets_inside(clean: bytes, patched: bytes, spans: list[tuple[int, int]]) -> bool:
    allowed = {offset for start, end in spans for offset in range(start, end)}
    return all(index in allowed for index, (left, right) in enumerate(zip(clean, patched)) if left != right)


def verify_pool(
    clean: bytes,
    patched: bytes,
    records: dict[int, dict[str, object]],
    pool: str,
    mapping: dict[str, object],
    font_path: Path,
    source_table: Path,
) -> dict[str, object]:
    if len(clean) != len(patched):
        raise ValueError("clean and patched ROM sizes differ")
    spec = custom_glyph_patch.POOL_SPECS[pool]
    table_offset = spec["file_offset"]
    entry_count = spec["entry_count"]
    clean_table = clean[table_offset:table_offset + entry_count * 4]
    patched_table = patched[table_offset:table_offset + entry_count * 4]
    if clean_table != patched_table:
        raise ValueError("pointer table changed; relocation is outside this verifier")
    codepage_start = font_glyph_format.CODEPAGE_TABLE_FILE_OFFSET
    codepage_end = codepage_start + font_glyph_format.CODEPAGE_COUNT * 2
    if clean[codepage_start:codepage_end] != patched[codepage_start:codepage_end]:
        raise ValueError("codepage table changed; custom mapping expects existing raw units")
    by_codepoint, _by_unit = custom_glyph_patch._validate_mapping_against_rom(clean, mapping, source_table)
    font_metadata = mapping["metadata"]
    actual_font_sha = hashlib.sha256(font_path.read_bytes()).hexdigest()
    if font_metadata.get("font_source_sha256") != actual_font_sha:
        raise ValueError("licensed font source SHA-256 does not match mapping metadata")
    custom_planes = custom_glyph_patch._read_font_planes(font_path, set(by_codepoint))
    selected_targets: dict[int, str] = {}
    selected_records: dict[int, dict[str, object]] = {}
    for entry, record in records.items():
        target_text = record.get("targets", {}).get("zh-TW", {}).get("text")
        if not isinstance(target_text, str):
            raise ValueError(f"missing target text at entry {entry}")
        pointer = common.read_u32(clean, table_offset + entry * 4)
        target = pointer - common.ROM_BASE
        if target in selected_targets and selected_targets[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at entry {entry}")
        selected_targets[target] = target_text
        selected_records[target] = record
    if not records:
        raise ValueError("no working records supplied")
    spans = [(codepage_start, codepage_end)]
    rows_result = []
    for entry in range(entry_count):
        pointer = common.read_u32(clean, table_offset + entry * 4)
        target = pointer - common.ROM_BASE
        clean_payload, clean_terminator = common.read_c_string(clean, target)
        patched_payload, patched_terminator = common.read_c_string(patched, target)
        selected = target in selected_targets
        spans.append((target, clean_terminator + 1))
        if selected:
            target_text = selected_targets[target]
            encoded_target, custom_codepoints = custom_glyph_patch.encode_text(target_text, by_codepoint)
            if patched_payload != encoded_target:
                raise ValueError(f"patched byte re-extract mismatch at entry {entry}")
            source = selected_records[target]["source"]
            expected_source = source["provenance"]["source_hash"]
            if expected_source != hashlib.sha256(clean_payload).hexdigest():
                raise ValueError(f"clean source hash mismatch at entry {entry}")
            rows_result.append({
                "entry": entry,
                "record_file_offset": f"0x{target:06X}",
                "clean_payload_length": len(clean_payload),
                "patched_payload_length": len(patched_payload),
                "clean_payload_sha256": hashlib.sha256(clean_payload).hexdigest(),
                "patched_payload_sha256": hashlib.sha256(patched_payload).hexdigest(),
                "target_text_hash": custom_glyph_patch.font_coverage.canonical_text_hash(target_text),
                "custom_codepoints": [f"U+{codepoint:04X}" for codepoint in custom_codepoints],
                "reextract_target_match": True,
                "fixed_slot": len(patched_payload) <= len(clean_payload),
            })
        elif clean_payload != patched_payload or clean_terminator != patched_terminator:
            raise ValueError(f"unselected record changed at entry {entry}")
    used_custom_codepoints = set()
    for target_text in selected_targets.values():
        _encoded, custom_codepoints = custom_glyph_patch.encode_text(target_text, by_codepoint)
        used_custom_codepoints.update(custom_codepoints)
    glyph_rows = []
    for codepoint in sorted(used_custom_codepoints):
        entry = by_codepoint[codepoint]
        index = int(entry["codepage_index"])
        first_plane, second_plane = custom_planes[codepoint]
        for base, plane in zip(custom_glyph_patch.GLYPH_SOURCE_BASES, (first_plane, second_plane)):
            offset = base - common.ROM_BASE + index * custom_glyph_patch.GLYPH_STRIDE
            spans.append((offset, offset + custom_glyph_patch.GLYPH_STRIDE))
            if patched[offset:offset + custom_glyph_patch.GLYPH_STRIDE] != plane:
                raise ValueError(f"custom glyph plane mismatch at U+{codepoint:04X}, index {index}")
        glyph_rows.append({
            "unicode": f"U+{codepoint:04X}",
            "code_unit": entry["code_unit_hex"],
            "codepage_index": index,
            "match": True,
        })
    if not _changed_offsets_inside(clean, patched, spans):
        raise ValueError("bytes outside selected records, codepage table or custom glyph slots changed")
    return {
        "read_only": True,
        "pool": pool,
        "entry_count": entry_count,
        "selected_entry_count": len(records),
        "pointer_table_byte_identical": True,
        "codepage_table_byte_identical": True,
        "unselected_records_byte_identical": True,
        "selected_reextract_match_count": sum(row["reextract_target_match"] for row in rows_result),
        "selected_fixed_slot_count": sum(row["fixed_slot"] for row in rows_result),
        "custom_glyph_match_count": len(glyph_rows),
        "changed_byte_count": sum(left != right for left, right in zip(clean, patched)),
        "relocation": "not-used; fixed-slot records and existing glyph slots only",
        "clean_rom_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_rom_sha256": hashlib.sha256(patched).hexdigest(),
        "glyphs": glyph_rows,
        "rows": sorted(rows_result, key=lambda row: row["entry"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("--pool", choices=sorted(custom_glyph_patch.POOL_SPECS), required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify_pool(
        args.clean.read_bytes(), args.patched.read_bytes(), _records(args.work, args.pool), args.pool,
        custom_glyph_patch.parse_mapping(args.mapping), args.font, args.source_table
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        key: report[key]
        for key in ("pool", "entry_count", "selected_entry_count", "selected_reextract_match_count", "selected_fixed_slot_count", "custom_glyph_match_count", "changed_byte_count", "relocation")
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
