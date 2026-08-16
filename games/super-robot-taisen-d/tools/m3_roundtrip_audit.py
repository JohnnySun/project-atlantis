#!/usr/bin/env python3
"""Source-safe bounded re-extraction audit for an A6SJ static rebuild.

The audit reads ignored ROM/source/working artifacts and emits only counts,
hashes, record IDs, and allowed changed ranges.  It proves the narrow static
reinsert contract without claiming that the rest of the engine or text pool
has been rebuilt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import m18_narrow_allocator as m18  # noqa: E402


class RoundtripReject(ValueError):
    """A re-extraction invariant failed closed."""


def read_jsonl(paths: Sequence[Path]) -> Dict[int, Dict[str, Any]]:
    rows: Dict[int, Dict[str, Any]] = {}
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or "string_id" not in row:
                raise RoundtripReject(f"invalid record {path}:{line_number}")
            string_id = int(row["string_id"])
            if string_id in rows:
                raise RoundtripReject(f"duplicate record {string_id}")
            rows[string_id] = row
    if not rows:
        raise RoundtripReject("no records")
    return rows


def read_nul_record(rom: bytes, offset: int) -> Tuple[bytes, int]:
    if offset < 0 or offset >= len(rom):
        raise RoundtripReject(f"record offset outside ROM: 0x{offset:x}")
    terminator = rom.find(b"\x00", offset)
    if terminator < 0:
        raise RoundtripReject(f"record has no NUL: 0x{offset:x}")
    return rom[offset:terminator], terminator


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expected_target_payload(
    target_text: str,
    allocations: Mapping[int, Mapping[str, Any]],
) -> bytes:
    output = bytearray()
    for char in target_text:
        codepoint = ord(char)
        metadata = allocations.get(codepoint)
        if metadata is None:
            raise RoundtripReject(f"missing allocation U+{codepoint:04X}")
        code_unit = int(str(metadata["code_unit_little_endian"]), 16)
        raw = m18.code_unit_bytes(code_unit)
        if raw[0] > 0x87:
            raise RoundtripReject(f"wide allocation U+{codepoint:04X}")
        output.extend(raw)
    return bytes(output)


def coalesce_ranges(changed: Iterable[int]) -> List[Tuple[int, int]]:
    ordered = sorted(set(changed))
    if not ordered:
        return []
    result: List[Tuple[int, int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value != previous + 1:
            result.append((start, previous + 1))
            start = value
        previous = value
    result.append((start, previous + 1))
    return result


def within_ranges(offset: int, length: int, ranges: Sequence[Tuple[int, int]]) -> bool:
    end_offset = offset + length
    cursor = offset
    for start, end in sorted(ranges):
        if end <= cursor:
            continue
        if start > cursor:
            return False
        cursor = max(cursor, end)
        if cursor >= end_offset:
            return True
    return cursor >= end_offset


def audit(
    base: bytes,
    patched: bytes,
    source_table: Path,
    working_paths: Sequence[Path],
    reinsert_report: Path,
) -> Dict[str, Any]:
    if sha256(base) != m18.ROM_SHA256:
        raise RoundtripReject("base_rom_hash_mismatch")
    if len(base) != len(patched):
        raise RoundtripReject("rom_size_mismatch")
    source_rows = m18.read_source_records(source_table)
    workings = read_jsonl(working_paths)
    report = json.loads(reinsert_report.read_text(encoding="utf-8"))
    if report.get("schema") != "super-robot-taisen-d-m3-reinsert-v1":
        raise RoundtripReject("reinsert_report_schema_mismatch")
    report_records = {int(row["string_id"]): row for row in report.get("records", [])}
    target_ids = set(workings)
    if target_ids != set(report_records):
        raise RoundtripReject("working_report_set_mismatch")
    allocation_by_codepoint = {
        int(str(row["codepoint"])[2:], 16): row for row in report.get("allocations", [])
    }
    expected_record_ranges = [
        (int(item["string_id"]), int(item["source_payload_length"]))
        for item in report_records.values()
    ]
    glyph_ranges = [
        (
            int(m18.NARROW_RESOURCE_START - m18.ROM_BASE + int(row["slot"]) * m18.NARROW_STRIDE),
            m18.NARROW_GLYPH_BYTES,
        )
        for row in report.get("allocations", [])
    ]
    allowed_ranges = [(offset, offset + length) for offset, length in expected_record_ranges]
    allowed_ranges.extend(offset_length for offset, length in glyph_ranges for offset_length in [(offset, offset + length)])

    base_source_matches = 0
    target_exact_matches = 0
    untouched_exact_matches = 0
    target_summaries: List[Dict[str, Any]] = []
    for source_row in source_rows:
        offset = int(source_row["offset"])
        source_text = str(source_row["text"])
        source_payload, source_terminator = read_nul_record(base, offset)
        patched_payload, patched_terminator = read_nul_record(patched, offset)
        try:
            expected_source = source_text.encode("shift_jis", errors="strict")
        except UnicodeEncodeError as exc:
            raise RoundtripReject(f"source_encode_failed:{offset}") from exc
        if source_payload != expected_source:
            raise RoundtripReject(f"base_source_mismatch:{offset}")
        base_source_matches += 1
        if offset in target_ids:
            working = workings[offset]
            source = working.get("source")
            if not isinstance(source, Mapping) or str(source.get("text")) != source_text:
                raise RoundtripReject(f"working_source_mismatch:{offset}")
            target_text = str(working.get("targets", {}).get("zh-TW", {}).get("text", ""))
            expected_target = expected_target_payload(target_text, allocation_by_codepoint)
            if patched_payload != expected_target:
                raise RoundtripReject(f"target_payload_mismatch:{offset}")
            if len(expected_target) != len(source_payload):
                raise RoundtripReject(f"target_length_mismatch:{offset}")
            if patched_terminator != source_terminator:
                raise RoundtripReject(f"target_terminator_moved:{offset}")
            declared_hash = str(report_records[offset]["target_payload_sha256"])
            if sha256(patched_payload) != declared_hash:
                raise RoundtripReject(f"target_hash_mismatch:{offset}")
            target_exact_matches += 1
            target_summaries.append(
                {
                    "string_id": offset,
                    "source_raw_sha256": sha256(source_payload),
                    "target_payload_sha256": sha256(patched_payload),
                    "payload_length": len(patched_payload),
                    "terminator": "NUL",
                }
            )
        else:
            if patched_payload != source_payload or patched_terminator != source_terminator:
                raise RoundtripReject(f"untouched_record_changed:{offset}")
            untouched_exact_matches += 1
    changed_offsets = [index for index, (left, right) in enumerate(zip(base, patched)) if left != right]
    actual_ranges = coalesce_ranges(changed_offsets)
    for start, end in actual_ranges:
        if not within_ranges(start, end - start, allowed_ranges):
            raise RoundtripReject(f"unexpected_rom_change:0x{start:x}..0x{end:x}")
    outside_equal = all(base[index] == patched[index] for index in range(len(base)) if not any(start <= index < end for start, end in allowed_ranges))
    if not outside_equal:
        raise RoundtripReject("rom_outside_allowed_ranges_changed")
    return {
        "schema": "super-robot-taisen-d-m3-roundtrip-audit-v1",
        "source_text_emitted": False,
        "source_records": len(source_rows),
        "base_source_matches": base_source_matches,
        "target_records": len(target_ids),
        "target_exact_matches": target_exact_matches,
        "untouched_records": len(source_rows) - len(target_ids),
        "untouched_exact_matches": untouched_exact_matches,
        "actual_changed_bytes": len(changed_offsets),
        "actual_changed_ranges": [
            {"start": start, "end_exclusive": end, "length": end - start}
            for start, end in actual_ranges
        ],
        "allowed_range_count": len(allowed_ranges),
        "rom_outside_allowed_ranges_equal": outside_equal,
        "target_summaries": target_summaries,
        "runtime_status": "pending; static re-extraction only",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-rom", type=Path, required=True)
    parser.add_argument("--patched-rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--working", type=Path, action="append", required=True)
    parser.add_argument("--reinsert-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.parent.name != "work":
        raise SystemExit("refusing non-work output; use games/.../work/")
    try:
        result = audit(
            args.base_rom.read_bytes(),
            args.patched_rom.read_bytes(),
            args.source_table,
            args.working,
            args.reinsert_report,
        )
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, m18.M17Error) as exc:
        print(f"m3_roundtrip_rejected={exc}", file=sys.stderr)
        return 2
    print(
        f"m3_roundtrip=accepted source={result['base_source_matches']}/{result['source_records']} "
        f"targets={result['target_exact_matches']}/{result['target_records']} "
        f"untouched={result['untouched_exact_matches']}/{result['untouched_records']} "
        f"changed_bytes={result['actual_changed_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
