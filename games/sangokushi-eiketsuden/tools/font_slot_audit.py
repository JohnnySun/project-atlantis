#!/usr/bin/env python3
"""Audit bounded candidate codepage slots for future custom zh-TW glyphs.

This is a read-only planning tool.  It counts code units used by the local,
ignored decoded source table and reports unused reviewed codepage slots with
hash-only glyph receipts.  It does not choose a final mapping, generate font
bytes, patch a ROM, or emit source text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import font_coverage  # noqa: E402
import font_glyph_format  # noqa: E402


def _parse_codepoints(value: str) -> list[int]:
    result = []
    for token in value.split(","):
        token = token.strip().upper()
        if not token:
            continue
        if token.startswith("U+"):
            token = token[2:]
        codepoint = int(token, 16)
        if not 0 <= codepoint <= 0x10FFFF:
            raise ValueError(f"Unicode codepoint outside range: {token}")
        result.append(codepoint)
    if not result:
        raise ValueError("at least one Unicode codepoint is required")
    return list(dict.fromkeys(result))


def _source_text(record: dict[str, object]) -> str | None:
    text = record.get("text")
    if isinstance(text, str):
        return text
    source = record.get("source")
    if isinstance(source, dict) and isinstance(source.get("text"), str):
        return source["text"]
    return None


def used_code_units(source_table: Path) -> dict[str, object]:
    used: set[int] = set()
    record_count = 0
    undecodable_count = 0
    for line in source_table.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        text = _source_text(record)
        if text is None:
            continue
        record_count += 1
        try:
            _encoded, units = font_coverage.shift_jis_code_units(text)
        except UnicodeEncodeError:
            undecodable_count += 1
            continue
        used.update(units)
    return {
        "source_record_count": record_count,
        "undecodable_source_record_count": undecodable_count,
        "used_double_byte_code_unit_count": len(used),
        "used_double_byte_code_units": sorted(used),
    }


def _is_shift_jis_pair(code_unit: int) -> bool:
    lead, trail = code_unit >> 8, code_unit & 0xFF
    return (
        (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xEF)
        and (0x40 <= trail <= 0x7E or 0x80 <= trail <= 0xFC)
    )


def audit_slots(
    rom: bytes,
    source_usage: dict[str, object],
    requested_codepoints: list[int],
    *,
    candidate_limit: int = 16,
) -> dict[str, object]:
    if candidate_limit < 1 or candidate_limit > 64:
        raise ValueError("candidate_limit must be between 1 and 64")
    used = set(source_usage["used_double_byte_code_units"])
    codepage = font_glyph_format.read_codepage(rom)
    seen: set[int] = set()
    candidates = []
    for index, code_unit in enumerate(codepage):
        if code_unit in seen or code_unit in used or not _is_shift_jis_pair(code_unit):
            continue
        seen.add(code_unit)
        receipt = font_glyph_format.glyph_receipt(rom, index, selector=0)
        candidates.append({
            "codepage_index": index,
            "code_unit": f"0x{code_unit:04X}",
            "source_pool_use": False,
            "plane_sha256": [row["sha256"] for row in receipt["source_planes"]],
            "expanded_selector_zero_sha256": receipt["cache_sha256"],
        })
        if len(candidates) >= candidate_limit:
            break
    requested = []
    for codepoint in requested_codepoints:
        character = chr(codepoint)
        try:
            encoded = character.encode("shift_jis")
            standard_units = [
                int.from_bytes(encoded[offset:offset + 2], "big")
                for offset in range(0, len(encoded), 2)
                if len(encoded[offset:offset + 2]) == 2
            ]
            status = "standard-shift-jis"
        except UnicodeEncodeError:
            standard_units = []
            status = "missing-standard-shift-jis"
        requested.append({
            "unicode_codepoint": f"U+{codepoint:04X}",
            "status": status,
            "standard_code_units": [f"0x{unit:04X}" for unit in standard_units],
            "candidate_slots_are_unapproved": True,
        })
    return {
        "read_only": True,
        "candidate_selection": "bounded source-pool-unused; not final mapping",
        "requested_codepoints": requested,
        "source_usage": {
            key: value for key, value in source_usage.items()
            if key != "used_double_byte_code_units"
        },
        "codepage_count": len(codepage),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--unicode", required=True, help="comma-separated codepoints, e.g. U+7D93,U+9A57")
    parser.add_argument("--candidate-limit", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    usage = used_code_units(args.source_table)
    report = audit_slots(
        args.rom.read_bytes(), usage, _parse_codepoints(args.unicode), candidate_limit=args.candidate_limit
    )
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("read_only", "candidate_selection", "codepage_count", "candidate_count")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
