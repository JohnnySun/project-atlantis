#!/usr/bin/env python3
"""Fail-closed multi-record static reinsertor for the A6SJ narrow font POC.

This is the next bounded step after the single-record M1.8 allocator.  It
accepts one or more restored local working records plus their source-safe
ledgers, allocates a single global narrow code-unit/glyph map, and writes only
an ignored patched ROM and metadata report.  It deliberately has no wide,
opaque, control-code, variable-length, or runtime path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import m18_narrow_allocator as m18  # noqa: E402


class ReinsertReject(ValueError):
    """A multi-record reinsert invariant rejected its input."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(f"{reason}: {detail}" if detail else reason)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReinsertReject("invalid_json", f"{path}:{line_number}") from exc
        if not isinstance(row, dict):
            raise ReinsertReject("invalid_record", f"{path}:{line_number}")
        rows.append(row)
    if not rows:
        raise ReinsertReject("record_count", str(path))
    return rows


def read_index(paths: Sequence[Path], label: str) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for path in paths:
        for row in read_jsonl(path):
            try:
                string_id = int(row["string_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ReinsertReject("record_id", f"{label}:{path}") from exc
            if string_id in result:
                raise ReinsertReject("duplicate_record", f"{label}:{string_id}")
            result[string_id] = row
    return result


def validate_inputs(
    rom: bytes,
    source_records: Sequence[Mapping[str, Any]],
    ledgers: Mapping[int, Mapping[str, Any]],
    workings: Mapping[int, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    if m18.sha256(rom) != m18.ROM_SHA256:
        raise ReinsertReject("rom_hash_mismatch", m18.sha256(rom))
    if set(ledgers) != set(workings):
        raise ReinsertReject("ledger_work_set_mismatch")
    source_by_offset = {int(row["offset"]): row for row in source_records}
    if len(source_by_offset) != len(source_records):
        raise ReinsertReject("duplicate_source_record")
    validated: List[Dict[str, Any]] = []
    for string_id in sorted(ledgers):
        ledger = ledgers[string_id]
        working = workings[string_id]
        if "source" not in working or not isinstance(working["source"], Mapping):
            raise ReinsertReject("source_hash_mismatch", f"working record {string_id} has no source")
        source = working["source"]
        try:
            source_offset = int(working["string_id"])
            source_text = str(source["text"])
            source_locale = str(source["locale"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ReinsertReject("source_hash_mismatch", str(string_id)) from exc
        if source_offset != string_id or source_locale != "ja":
            raise ReinsertReject("source_hash_mismatch", f"record {string_id}")
        source_row = source_by_offset.get(source_offset)
        if source_row is None or str(source_row["text"]) != source_text:
            raise ReinsertReject("source_hash_mismatch", f"record {string_id}")
        try:
            source_encoded = source_text.encode("shift_jis", errors="strict")
        except UnicodeEncodeError as exc:
            raise ReinsertReject("source_hash_mismatch", f"record {string_id}") from exc
        payload, terminator = m18.source_payload(rom, source_offset)
        if payload != source_encoded:
            raise ReinsertReject("source_hash_mismatch", f"record {string_id}")
        ledger_hash = str(ledger.get("source_hash", ""))
        if ledger_hash != m18.sha256(source_text.encode("utf-8")):
            raise ReinsertReject("source_hash_mismatch", f"ledger {string_id}")
        try:
            unit_count, tokenization = m18.validate_source_shape(source_encoded)
        except m18.AllocatorReject as exc:
            raise ReinsertReject(exc.reason, f"record {string_id}") from exc
        if len(source_encoded) != unit_count * 2:
            raise ReinsertReject("source_format_mismatch", f"record {string_id}")
        targets = working.get("targets")
        if not isinstance(targets, Mapping) or not isinstance(targets.get("zh-TW"), Mapping):
            raise ReinsertReject("missing_translation", f"record {string_id}")
        target_text = str(targets["zh-TW"].get("text", ""))
        if not target_text or len(target_text) != unit_count:
            raise ReinsertReject("variable_length", f"record {string_id}")
        if any(ord(char) < 0x20 or char in "\x7f\n\r\t" for char in target_text):
            raise ReinsertReject("opaque_or_control", f"record {string_id}")
        validated.append(
            {
                "string_id": string_id,
                "source_offset": source_offset,
                "source_raw_sha256": m18.sha256(source_encoded),
                "source_ledger_sha256": ledger_hash,
                "source_payload_length": len(source_encoded),
                "source_unit_count": unit_count,
                "source_line_width": tokenization.line_width,
                "source_terminator": "NUL",
                "source_terminator_address": m18.address(m18.ROM_BASE + terminator),
                "target_text": target_text,
            }
        )
    ranges = sorted((item["source_offset"], item["source_payload_length"], item["string_id"]) for item in validated)
    for (start, length, string_id), (next_start, _next_length, next_id) in zip(ranges, ranges[1:]):
        if start + length >= next_start:
            raise ReinsertReject("record_overlap", f"{string_id}/{next_id}")
    return validated


def allocate_batch(
    target_texts: Iterable[str],
    occupancy: Mapping[str, Any],
    font_rows: Mapping[int, Sequence[int]],
) -> Dict[int, m18.Allocation]:
    free_slots = sorted((int(slot) for slot in occupancy["free_blank_slots"]), reverse=True)
    slot_to_units = occupancy["slot_to_units"]
    by_codepoint: Dict[int, m18.Allocation] = {}
    for target_text in target_texts:
        for char in target_text:
            codepoint = ord(char)
            if codepoint in by_codepoint:
                continue
            if codepoint not in font_rows:
                raise ReinsertReject("missing_glyph", f"U+{codepoint:04X}")
            if not free_slots:
                raise ReinsertReject("capacity_exceeded")
            slot = free_slots.pop(0)
            units = tuple(slot_to_units.get(slot, ()))
            if len(units) != 1:
                raise ReinsertReject("code_unit_slot_collision", f"slot={slot}")
            code_unit = int(units[0])
            raw_unit = m18.code_unit_bytes(code_unit)
            if raw_unit[0] > 0x87:
                raise ReinsertReject("wide_glyph", raw_unit.hex())
            glyph_bytes = m18.downsample_16x16_to_8x12(font_rows[codepoint])
            if not any(glyph_bytes):
                raise ReinsertReject("missing_glyph", f"U+{codepoint:04X}")
            by_codepoint[codepoint] = m18.Allocation(
                character=char,
                codepoint=codepoint,
                slot=slot,
                code_unit=code_unit,
                raw_code_unit=raw_unit,
                font_source_sha256=m18.source_bitmap_sha256(font_rows[codepoint]),
                glyph_bytes=glyph_bytes,
            )
    return by_codepoint


def patch_batch(
    rom: bytes,
    validated: Sequence[Mapping[str, Any]],
    allocations: Mapping[int, m18.Allocation],
    occupancy: Mapping[str, Any],
) -> Tuple[bytes, Dict[int, bytes]]:
    patched = bytearray(rom)
    target_payloads: Dict[int, bytes] = {}
    for item in validated:
        payload = b"".join(allocations[ord(char)].raw_code_unit for char in str(item["target_text"]))
        if len(payload) != int(item["source_payload_length"]):
            raise ReinsertReject("variable_length", f"record {item['string_id']}")
        offset = int(item["source_offset"])
        patched[offset : offset + len(payload)] = payload
        target_payloads[int(item["string_id"])] = payload
    for allocation in allocations.values():
        begin = int(occupancy["resource_start"]) - m18.ROM_BASE + allocation.slot * m18.NARROW_STRIDE
        if any(patched[begin : begin + m18.NARROW_GLYPH_BYTES]):
            raise ReinsertReject("slot_collision", f"slot={allocation.slot}")
        patched[begin : begin + m18.NARROW_GLYPH_BYTES] = allocation.glyph_bytes
    return bytes(patched), target_payloads


def allocation_metadata(allocation: m18.Allocation) -> Dict[str, Any]:
    return {
        "codepoint": f"U+{allocation.codepoint:04X}",
        "slot": allocation.slot,
        "code_unit_little_endian": f"0x{allocation.code_unit:04X}",
        "glyph_bytes_sha256": m18.sha256(allocation.glyph_bytes),
        "render_4bpp_sha256": m18.sha256(m18.render_narrow_4bpp(allocation.glyph_bytes)),
        "font_glyph_source_sha256": allocation.font_source_sha256,
    }


def build_report(
    rom: bytes,
    patched: bytes,
    validated: Sequence[Mapping[str, Any]],
    allocations: Mapping[int, m18.Allocation],
    font: Mapping[str, Any],
    occupancy: Mapping[str, Any],
    target_payloads: Mapping[int, bytes],
) -> Dict[str, Any]:
    return {
        "schema": "super-robot-taisen-d-m3-reinsert-v1",
        "source_text_emitted": False,
        "game_code": "A6SJ",
        "record_count": len(validated),
        "records": [
            {
                "string_id": item["string_id"],
                "source_raw_sha256": item["source_raw_sha256"],
                "source_ledger_sha256": item["source_ledger_sha256"],
                "source_payload_length": item["source_payload_length"],
                "source_unit_count": item["source_unit_count"],
                "source_line_width": item["source_line_width"],
                "source_terminator": item["source_terminator"],
                "target_payload_sha256": m18.sha256(target_payloads[item["string_id"]]),
                "same_length": len(target_payloads[item["string_id"]]) == item["source_payload_length"],
                "control_tokens": [],
            }
            for item in validated
        ],
        "allocator": {
            "mode": "narrow_only",
            "free_blank_slots_before": len(occupancy["free_blank_slots"]),
            "allocated_slot_count": len(allocations),
            "allocated_slots": sorted(allocation.slot for allocation in allocations.values()),
            "protected_blank_referenced_slots": occupancy["protected_blank_referenced_slots"],
            "wide_new_slots": 0,
            "font_hash_match": True,
            "source_hash_matches": True,
            "same_length": all(
                len(target_payloads[item["string_id"]]) == item["source_payload_length"]
                for item in validated
            ),
        },
        "allocations": [allocation_metadata(allocations[codepoint]) for codepoint in sorted(allocations)],
        "font": dict(font),
        "rom": {
            "source_sha256": m18.sha256(rom),
            "patched_sha256": m18.sha256(patched),
            "modified": rom != patched,
        },
        "runtime_status": "pending; static reinsert only",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--working", type=Path, action="append", required=True)
    parser.add_argument("--font", type=Path, default=m18.DEFAULT_FONT)
    parser.add_argument("--license", type=Path, default=m18.DEFAULT_LICENSE)
    parser.add_argument("--patched-rom", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if len(args.ledger) != len(args.working):
        raise SystemExit("--ledger and --working counts must match")
    if args.patched_rom.parent.name != "work" or args.report.parent.name != "work":
        raise SystemExit("refusing non-work output; use games/.../work/")
    try:
        rom = args.rom.read_bytes()
        source_records = m18.read_source_records(args.source_table)
        ledgers = read_index(args.ledger, "ledger")
        workings = read_index(args.working, "working")
        validated = validate_inputs(rom, source_records, ledgers, workings)
        occupancy = m18.narrow_occupancy(rom, source_records)
        codepoints = {ord(char) for item in validated for char in str(item["target_text"])}
        font = m18.load_font_metadata(args.font, args.license)
        font_rows = m18.load_unifont_rows(args.font, codepoints)
        allocations = allocate_batch((str(item["target_text"]) for item in validated), occupancy, font_rows)
        patched, target_payloads = patch_batch(rom, validated, allocations, occupancy)
        report = build_report(rom, patched, validated, allocations, font, occupancy, target_payloads)
        args.patched_rom.write_bytes(patched)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, m18.M17Error) as exc:
        print(f"m3_rejected={exc}", file=sys.stderr)
        return 2
    print(
        f"m3_reinsert=accepted records={len(validated)} "
        f"allocations={len(allocations)} patched_rom={args.patched_rom} report={args.report}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
