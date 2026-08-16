#!/usr/bin/env python3
"""Validate B3EJ translation glyph coverage without emitting font bytes.

The game uses a linear 16-bit Shift-JIS membership table followed by a
0x20-byte glyph slot lookup.  This tool validates a local working ledger
against that table and both reviewed font banks.  It reports hashes, indexes,
lengths and missing-code counts only; it never writes a font or a ROM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
CODEPAGE_TABLE_FILE_OFFSET = 0x024110C
CODEPAGE_COUNT = 0x729 + 1
GLYPH_SOURCE_BASES = (0x08232BCC, 0x0822468C)
GLYPH_STRIDE = 0x20
GLYPH_BANK_BYTES = CODEPAGE_COUNT * GLYPH_STRIDE


def _hex(value: int) -> str:
    return f"0x{value:04X}"


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def canonical_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shift_jis_code_units(text: str) -> tuple[bytes, list[int]]:
    """Encode strict SJIS and return only double-byte units for the codepage."""

    encoded = text.encode("shift_jis")
    units: list[int] = []
    cursor = 0
    while cursor < len(encoded):
        lead = encoded[cursor]
        if lead <= 0x7F or 0xA1 <= lead <= 0xDF:
            cursor += 1
            continue
        if cursor + 1 >= len(encoded):
            raise ValueError("truncated Shift-JIS double-byte unit")
        units.append((lead << 8) | encoded[cursor + 1])
        cursor += 2
    return encoded, units


def read_codepage(data: bytes) -> list[int]:
    end = CODEPAGE_TABLE_FILE_OFFSET + CODEPAGE_COUNT * 2
    if end > len(data):
        raise common.StaticContractError("codepage table exceeds ROM")
    return [struct.unpack_from("<H", data, CODEPAGE_TABLE_FILE_OFFSET + index * 2)[0] for index in range(CODEPAGE_COUNT)]


def glyph_slot_receipts(data: bytes, index: int) -> list[dict[str, object]]:
    if not 0 <= index < CODEPAGE_COUNT:
        raise common.StaticContractError(f"codepage index outside reviewed range: {index}")
    receipts = []
    for base in GLYPH_SOURCE_BASES:
        source_file_offset = base - ROM_BASE + index * GLYPH_STRIDE
        glyph = data[source_file_offset:source_file_offset + GLYPH_STRIDE]
        if len(glyph) != GLYPH_STRIDE:
            raise common.StaticContractError(f"glyph slot outside ROM: {_offset(source_file_offset)}")
        receipts.append({
            "source_file_offset": _offset(source_file_offset),
            "source_gba_address": f"0x{base + index * GLYPH_STRIDE:08X}",
            "byte_length": GLYPH_STRIDE,
            "nonzero_byte_count": sum(value != 0 for value in glyph),
            "sha256": hashlib.sha256(glyph).hexdigest(),
        })
    return receipts


def coverage_for_text(data: bytes, text: str, *, max_payload_bytes: int | None = None) -> dict[str, object]:
    encoded, units = shift_jis_code_units(text)
    codepage = read_codepage(data)
    first_index = {value: index for index, value in reversed(list(enumerate(codepage)))}
    unique_units = list(dict.fromkeys(units))
    missing = [unit for unit in unique_units if unit not in first_index]
    indices = [first_index[unit] for unit in unique_units if unit in first_index]
    slots = []
    for index in indices:
        slots.append({"codepage_index": index, "glyph_banks": glyph_slot_receipts(data, index)})
    result: dict[str, object] = {
        "source_text_hash": canonical_text_hash(text),
        "encoded_byte_length": len(encoded),
        "code_unit_count": len(units),
        "unique_code_unit_count": len(unique_units),
        "codepage_table_count": CODEPAGE_COUNT,
        "codepage_indices": indices,
        "missing_code_unit_count": len(missing),
        "missing_code_units": [_hex(unit) for unit in missing],
        "glyph_slots": slots,
        "status": "covered" if not missing else "missing-codepage-entry",
    }
    if max_payload_bytes is not None:
        result["max_payload_bytes"] = max_payload_bytes
        result["fits_original_record"] = len(encoded) <= max_payload_bytes
        if len(encoded) > max_payload_bytes:
            result["status"] = "too-long"
    return result


def validate_work(data: bytes, work_path: Path) -> dict[str, object]:
    rows = []
    for line in work_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        source = record.get("source", {})
        target = record.get("targets", {}).get("zh-TW", {}).get("text")
        if not isinstance(target, str):
            raise ValueError(f"record has no zh-TW target: {record.get('string_id')!r}")
        max_payload = source.get("provenance", {}).get("payload_length")
        coverage = coverage_for_text(data, target, max_payload_bytes=max_payload)
        rows.append({
            "string_id": record.get("string_id"),
            "source_hash": source.get("provenance", {}).get("source_hash"),
            "target_text_hash": canonical_text_hash(target),
            "coverage": coverage,
        })
    return {
        "read_only": True,
        "work_record_count": len(rows),
        "covered_count": sum(row["coverage"]["status"] == "covered" for row in rows),
        "fit_count": sum(row["coverage"].get("fits_original_record", True) for row in rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate_work(args.rom.read_bytes(), args.work)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("read_only", "work_record_count", "covered_count", "fit_count")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
