#!/usr/bin/env python3
"""Verify a bounded fixed-slot patch for a reviewed B3EJ fixed-slot pool."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import patch_fixed_pool  # noqa: E402
import table_b_common as common  # noqa: E402


def _records(path: Path, pool: str) -> dict[int, dict[str, object]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            result[patch_fixed_pool.parse_pool_entry(record.get("string_id"), pool)] = record
    return result


def _changed_offsets_inside(clean: bytes, patched: bytes, spans: list[tuple[int, int]]) -> bool:
    allowed = {offset for start, end in spans for offset in range(start, end)}
    return all(index in allowed for index, (left, right) in enumerate(zip(clean, patched)) if left != right)


def verify_pool(clean: bytes, patched: bytes, records: dict[int, dict[str, object]], pool: str) -> dict[str, object]:
    if len(clean) != len(patched):
        raise ValueError("clean and patched ROM sizes differ")
    spec = patch_fixed_pool.POOL_SPECS[pool]
    table_offset = spec["file_offset"]
    entry_count = spec["entry_count"]
    clean_table = clean[table_offset:table_offset + entry_count * 4]
    patched_table = patched[table_offset:table_offset + entry_count * 4]
    if clean_table != patched_table:
        raise ValueError("pointer table changed; relocation is outside this verifier")
    selected_targets = {}
    for entry, record in records.items():
        pointer = common.read_u32(clean, table_offset + entry * 4)
        target = pointer - common.ROM_BASE
        target_text = record.get("targets", {}).get("zh-TW", {}).get("text")
        if not isinstance(target_text, str):
            raise ValueError(f"missing target text at entry {entry}")
        if target in selected_targets and selected_targets[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at entry {entry}")
        selected_targets[target] = target_text
    if not records:
        raise ValueError("no working records supplied")
    spans = []
    rows = []
    for entry in range(entry_count):
        pointer = common.read_u32(clean, table_offset + entry * 4)
        target = pointer - common.ROM_BASE
        clean_payload, clean_terminator = common.read_c_string(clean, target)
        patched_payload, patched_terminator = common.read_c_string(patched, target)
        selected = target in selected_targets
        spans.append((target, clean_terminator + 1))
        if selected:
            target_text = selected_targets[target]
            if patched_payload.decode("shift_jis") != target_text:
                raise ValueError(f"patched re-extract mismatch at entry {entry}")
            if entry in records:
                expected_source = records[entry]["source"]["provenance"]["source_hash"]
                if expected_source != hashlib.sha256(clean_payload).hexdigest():
                    raise ValueError(f"clean source hash mismatch at entry {entry}")
                rows.append({
                    "entry": entry,
                    "record_file_offset": f"0x{target:06X}",
                    "clean_payload_length": len(clean_payload),
                    "patched_payload_length": len(patched_payload),
                    "clean_payload_sha256": hashlib.sha256(clean_payload).hexdigest(),
                    "patched_payload_sha256": hashlib.sha256(patched_payload).hexdigest(),
                    "target_text_hash": hashlib.sha256(target_text.encode("utf-8")).hexdigest(),
                    "reextract_target_match": True,
                    "fixed_slot": len(patched_payload) <= len(clean_payload),
                })
        elif clean_payload != patched_payload or clean_terminator != patched_terminator:
            raise ValueError(f"unselected record changed at entry {entry}")
    if not _changed_offsets_inside(clean, patched, spans):
        raise ValueError("bytes outside selected record spans changed")
    return {
        "read_only": True,
        "pool": pool,
        "entry_count": entry_count,
        "selected_entry_count": len(records),
        "pointer_table_byte_identical": True,
        "unselected_records_byte_identical": True,
        "selected_reextract_match_count": sum(row["reextract_target_match"] for row in rows),
        "selected_fixed_slot_count": sum(row["fixed_slot"] for row in rows),
        "changed_byte_count": sum(left != right for left, right in zip(clean, patched)),
        "relocation": "not-used; fixed-slot records only",
        "clean_rom_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_rom_sha256": hashlib.sha256(patched).hexdigest(),
        "rows": sorted(rows, key=lambda row: row["entry"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=Path)
    parser.add_argument("patched", type=Path)
    parser.add_argument("--pool", choices=sorted(patch_fixed_pool.POOL_SPECS), default="event-system")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify_pool(args.clean.read_bytes(), args.patched.read_bytes(), _records(args.work, args.pool), args.pool)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("pool", "entry_count", "selected_entry_count", "selected_reextract_match_count", "selected_fixed_slot_count", "changed_byte_count", "relocation")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
