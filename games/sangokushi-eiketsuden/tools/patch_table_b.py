#!/usr/bin/env python3
"""Apply a bounded, fixed-slot B3EJ Table-B translation working ledger.

This encoder is intentionally narrow: it accepts only ``b3ej:table-b:NNN``
records, requires the current source text and raw source hash to match the
clean B3EJ ROM, requires strict Shift-JIS/codepage/font coverage, and refuses
relocation or overlong records.  The patched ROM and metadata are caller-owned
ignored outputs; no ROM bytes are printed or tracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import font_coverage  # noqa: E402
import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
TABLE_B_OFFSET = 0x0D1FFC
TABLE_B_COUNT = 44
ENTRY_PATTERN = re.compile(r"^b3ej:table-b:(\d{3})$")


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def fixed_slot_replacement(original_payload: bytes, encoded_target: bytes) -> bytes:
    """Return a same-span NUL-terminated replacement, rejecting overflow."""

    if len(encoded_target) > len(original_payload):
        raise ValueError(
            f"translated payload is {len(encoded_target)} bytes, "
            f"original slot is {len(original_payload)} bytes"
        )
    return encoded_target + b"\0" + b"\0" * (len(original_payload) - len(encoded_target))


def parse_table_b_entry(string_id: object) -> int:
    match = ENTRY_PATTERN.match(str(string_id))
    if match is None:
        raise ValueError(f"not a Table-B string id: {string_id!r}")
    entry = int(match.group(1))
    if entry >= TABLE_B_COUNT:
        raise ValueError(f"Table-B entry outside bounded range: {entry}")
    return entry


def _records(path: Path) -> list[dict[str, object]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def patch_table_b(data: bytes, records: list[dict[str, object]]) -> tuple[bytes, dict[str, object]]:
    boundary = common.parse_table_b_boundary(data)
    if boundary["entry_count"] != TABLE_B_COUNT:
        raise common.StaticContractError("Table-B boundary changed")
    patched = bytearray(data)
    pointer_targets = {
        index: common.read_u32(data, TABLE_B_OFFSET + index * 4) - ROM_BASE
        for index in range(TABLE_B_COUNT)
    }
    seen_target_text: dict[int, str] = {}
    rows = []
    for record in records:
        entry = parse_table_b_entry(record.get("string_id"))
        source = record.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"record {entry} is not a restored working record")
        source_text = source.get("text")
        target_text = record.get("targets", {}).get("zh-TW", {}).get("text")
        if not isinstance(source_text, str) or not isinstance(target_text, str):
            raise ValueError(f"record {entry} lacks source or zh-TW text")
        source_provenance = source.get("provenance", {})
        if not isinstance(source_provenance, dict):
            raise ValueError(f"record {entry} lacks source provenance")
        target = pointer_targets[entry]
        original_payload, terminator = common.read_c_string(data, target)
        if source_text != original_payload.decode("shift_jis"):
            raise ValueError(f"source text mismatch at Table-B entry {entry}")
        if source_provenance.get("source_hash") != hashlib.sha256(original_payload).hexdigest():
            raise ValueError(f"raw source hash mismatch at Table-B entry {entry}")
        if source_provenance.get("source_text_hash") != font_coverage.canonical_text_hash(source_text):
            raise ValueError(f"source text hash mismatch at Table-B entry {entry}")
        if target in seen_target_text and seen_target_text[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at 0x{target:06X}")
        seen_target_text[target] = target_text
        encoded_target, _ = font_coverage.shift_jis_code_units(target_text)
        coverage = font_coverage.coverage_for_text(
            data, target_text, max_payload_bytes=len(original_payload)
        )
        if coverage["status"] != "covered" or not coverage["fits_original_record"]:
            raise ValueError(f"font/slot gate failed at Table-B entry {entry}: {coverage['status']}")
        replacement = fixed_slot_replacement(original_payload, encoded_target)
        patched[target:terminator + 1] = replacement
        rows.append({
            "entry": entry,
            "record_file_offset": _offset(target),
            "original_payload_length": len(original_payload),
            "translated_payload_length": len(encoded_target),
            "original_payload_sha256": hashlib.sha256(original_payload).hexdigest(),
            "translated_payload_sha256": hashlib.sha256(encoded_target).hexdigest(),
            "target_text_hash": font_coverage.canonical_text_hash(target_text),
            "coverage": coverage,
            "relocated": False,
        })
    return bytes(patched), {
        "read_only_source": True,
        "table": "table-b",
        "table_file_offset": _offset(TABLE_B_OFFSET),
        "table_entry_count": TABLE_B_COUNT,
        "working_record_count": len(records),
        "unique_patched_target_count": len(seen_target_text),
        "relocation": "disabled; fixed-slot only",
        "rows": sorted(rows, key=lambda row: row["entry"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    args = parser.parse_args()
    original = args.rom.read_bytes()
    patched, report = patch_table_b(original, _records(args.work))
    report["original_rom_sha256"] = hashlib.sha256(original).hexdigest()
    report["patched_rom_sha256"] = hashlib.sha256(patched).hexdigest()
    report["changed_byte_count"] = sum(left != right for left, right in zip(original, patched))
    args.output.write_bytes(patched)
    args.metadata_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("table_entry_count", "working_record_count", "unique_patched_target_count", "relocation", "changed_byte_count")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
