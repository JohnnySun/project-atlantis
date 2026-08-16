#!/usr/bin/env python3
"""Verify a bounded B3EJ Table-B patch by re-decoding clean/patched ROMs.

The verifier reports hashes, entry counts, fixed-slot lengths and byte-identity
counts.  It never prints source or translated text.  It proves only the
selected fixed-slot records and does not claim a whole-ROM insertion path.
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

import patch_table_b  # noqa: E402
import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
TABLE_B_OFFSET = patch_table_b.TABLE_B_OFFSET
TABLE_B_COUNT = patch_table_b.TABLE_B_COUNT


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def _records(path: Path) -> dict[int, dict[str, object]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        result[patch_table_b.parse_table_b_entry(record.get("string_id"))] = record
    return result


def changed_offsets_within(data_before: bytes, data_after: bytes, spans: list[tuple[int, int]]) -> bool:
    allowed = {offset for start, end in spans for offset in range(start, end)}
    return all(index in allowed for index, (left, right) in enumerate(zip(data_before, data_after)) if left != right)


def verify_table_b(clean: bytes, patched: bytes, work_records: dict[int, dict[str, object]]) -> dict[str, object]:
    if len(clean) != len(patched):
        raise ValueError("clean and patched ROM sizes differ")
    clean_boundary = common.parse_table_b_boundary(clean)
    patched_boundary = common.parse_table_b_boundary(patched)
    if clean_boundary["entry_count"] != TABLE_B_COUNT or patched_boundary["entry_count"] != TABLE_B_COUNT:
        raise common.StaticContractError("Table-B entry count changed")
    if clean[TABLE_B_OFFSET:TABLE_B_OFFSET + TABLE_B_COUNT * 4] != patched[TABLE_B_OFFSET:TABLE_B_OFFSET + TABLE_B_COUNT * 4]:
        raise ValueError("Table-B pointer table changed; relocation is outside this verifier")

    spans = []
    rows = []
    selected = set(work_records)
    if not selected:
        raise ValueError("no working records supplied")
    selected_target_text: dict[int, str] = {}
    for entry, record in work_records.items():
        pointer = common.read_u32(clean, TABLE_B_OFFSET + entry * 4)
        target = pointer - ROM_BASE
        target_text = record.get("targets", {}).get("zh-TW", {}).get("text")
        if not isinstance(target_text, str):
            raise ValueError(f"missing target text at entry {entry}")
        if target in selected_target_text and selected_target_text[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at entry {entry}")
        selected_target_text[target] = target_text
    for entry in range(TABLE_B_COUNT):
        pointer = common.read_u32(clean, TABLE_B_OFFSET + entry * 4)
        target = pointer - ROM_BASE
        clean_payload, clean_terminator = common.read_c_string(clean, target)
        patched_payload, patched_terminator = common.read_c_string(patched, target)
        target_selected = target in selected_target_text
        if clean_terminator != patched_terminator and not target_selected:
            raise ValueError(f"unselected record boundary changed at entry {entry}")
        spans.append((target, clean_terminator + 1))
        if target_selected:
            target_text = selected_target_text[target]
            if patched_payload.decode("shift_jis") != target_text:
                raise ValueError(f"patched re-extract mismatch at entry {entry}")
            if entry in selected:
                record = work_records[entry]
                expected_source = record["source"]["provenance"]["source_hash"]
                if expected_source != hashlib.sha256(clean_payload).hexdigest():
                    raise ValueError(f"clean source hash mismatch at entry {entry}")
                rows.append({
                    "entry": entry,
                    "record_file_offset": _offset(target),
                    "clean_payload_length": len(clean_payload),
                    "patched_payload_length": len(patched_payload),
                    "clean_payload_sha256": hashlib.sha256(clean_payload).hexdigest(),
                    "patched_payload_sha256": hashlib.sha256(patched_payload).hexdigest(),
                    "target_text_hash": hashlib.sha256(target_text.encode("utf-8")).hexdigest(),
                    "reextract_target_match": True,
                    "fixed_slot": len(patched_payload) <= len(clean_payload),
                })
        elif clean_payload != patched_payload:
            raise ValueError(f"unselected record changed at entry {entry}")

    changed_count = sum(left != right for left, right in zip(clean, patched))
    if not changed_offsets_within(clean, patched, [spans[entry] for entry in selected]):
        raise ValueError("bytes outside selected record spans changed")
    return {
        "read_only": True,
        "table": "table-b",
        "entry_count": TABLE_B_COUNT,
        "selected_entry_count": len(selected),
        "selected_entries": sorted(selected),
        "pointer_table_byte_identical": True,
        "unselected_records_byte_identical": True,
        "selected_reextract_match_count": sum(row["reextract_target_match"] for row in rows),
        "selected_fixed_slot_count": sum(row["fixed_slot"] for row in rows),
        "changed_byte_count": changed_count,
        "relocation": "not-used; fixed-slot records only",
        "clean_rom_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_rom_sha256": hashlib.sha256(patched).hexdigest(),
        "rows": sorted(rows, key=lambda row: row["entry"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify_table_b(args.clean.read_bytes(), args.patched.read_bytes(), _records(args.work))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("entry_count", "selected_entry_count", "selected_reextract_match_count", "selected_fixed_slot_count", "changed_byte_count", "relocation")}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
