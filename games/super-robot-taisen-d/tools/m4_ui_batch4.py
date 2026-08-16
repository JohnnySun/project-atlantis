#!/usr/bin/env python3
"""Audit a small source-safe, narrow-only A6SJ UI translation slice.

The selected records are fixed-length UI/status labels whose source shape is
already covered by the M1.8 narrow allocator.  This tool reads the ignored
strict source table and ignored static rebuild reports, but emits only hashes,
codepoint metadata, counts, and gate results.  It never writes source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import m18_narrow_allocator as m18  # noqa: E402


SELECTION = {
    513060: "正在讀取資料",
    513076: "正在儲存資料",
    517848: "確定要覆寫嗎？",
}
EXPECTED_ROM_SHA256 = m18.ROM_SHA256


class Batch4Reject(ValueError):
    """A batch-4 source, target, or static-report gate rejected input."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_jsonl(path: Path) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise Batch4Reject(f"invalid_jsonl_record:{path}:{line_number}")
        rows.append(row)
    return rows


def read_index(path: Path) -> Dict[int, Dict[str, Any]]:
    result: Dict[int, Dict[str, Any]] = {}
    for row in read_jsonl(path):
        try:
            string_id = int(row["string_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Batch4Reject(f"invalid_string_id:{path}") from exc
        if string_id in result:
            raise Batch4Reject(f"duplicate_string_id:{string_id}")
        result[string_id] = row
    return result


def validate_target(target: str, source_units: int) -> None:
    if len(target) != source_units:
        raise Batch4Reject(f"variable_length:{len(target)}!={source_units}")
    if any(ord(char) < 0x20 or char in "\x7f\n\r\t" for char in target):
        raise Batch4Reject("opaque_or_control_target")


def validate_selection(
    rom: bytes,
    source_records: Sequence[Mapping[str, Any]],
    ledger_rows: Mapping[int, Mapping[str, Any]],
    selection: Mapping[int, str] = SELECTION,
) -> list[Dict[str, Any]]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise Batch4Reject("rom_hash_mismatch")
    source_by_offset = {int(row["offset"]): row for row in source_records}
    if set(ledger_rows) != set(selection):
        raise Batch4Reject("selection_set_mismatch")
    result: list[Dict[str, Any]] = []
    for string_id, target in selection.items():
        source = source_by_offset.get(string_id)
        if source is None:
            raise Batch4Reject(f"source_record_missing:{string_id}")
        source_text = str(source["text"])
        try:
            encoded = source_text.encode("shift_jis", errors="strict")
        except UnicodeEncodeError as exc:
            raise Batch4Reject(f"source_not_shift_jis:{string_id}") from exc
        payload, terminator = m18.source_payload(rom, string_id)
        if payload != encoded:
            raise Batch4Reject(f"source_hash_mismatch:{string_id}")
        tokenization = m18.tokenize_payload(payload)
        if not tokenization.supported:
            raise Batch4Reject(f"opaque_or_control_source:{string_id}")
        if any(token.glyph_class != "narrow" for token in tokenization.tokens):
            raise Batch4Reject(f"wide_glyph_source:{string_id}")
        validate_target(target, len(tokenization.tokens))
        ledger = ledger_rows[string_id]
        if "source" in ledger:
            raise Batch4Reject(f"source_text_emitted:{string_id}")
        source_hash = str(ledger.get("source_hash", ""))
        expected_ledger_hash = sha256(source_text.encode("utf-8"))
        if source_hash != expected_ledger_hash:
            raise Batch4Reject(f"ledger_source_hash_mismatch:{string_id}")
        result.append(
            {
                "string_id": string_id,
                "source_raw_sha256": sha256(payload),
                "source_ledger_sha256": source_hash,
                "source_payload_length": len(payload),
                "source_unit_count": len(tokenization.tokens),
                "line_width": tokenization.line_width,
                "terminator": "NUL",
                "control_token_count": 0,
                "glyph_class": "narrow_only",
                "target_codepoints": [f"U+{ord(char):04X}" for char in target],
                "target_unit_count": len(target),
                "source_terminator_offset": terminator,
            }
        )
    return result


def build_report(
    base_rom: bytes,
    patched_rom: bytes,
    selected: Sequence[Mapping[str, Any]],
    ledger_rows: Mapping[int, Mapping[str, Any]],
    reinsert: Mapping[str, Any],
    roundtrip: Mapping[str, Any],
    bps: bytes,
    bps_applied: bytes,
    selection: Mapping[int, str] = SELECTION,
) -> Dict[str, Any]:
    if sha256(base_rom) != EXPECTED_ROM_SHA256:
        raise Batch4Reject("rom_hash_mismatch")
    if sha256(bps_applied) != sha256(patched_rom):
        raise Batch4Reject("bps_apply_mismatch")
    reinsert_ids = {int(row["string_id"]) for row in reinsert.get("records", [])}
    if not set(selection).issubset(reinsert_ids):
        raise Batch4Reject("reinsert_selection_mismatch")
    reinsert_records = {int(row["string_id"]): row for row in reinsert["records"]}
    records = []
    for item in selected:
        string_id = int(item["string_id"])
        reinsert_row = reinsert_records[string_id]
        ledger = ledger_rows[string_id]
        if str(reinsert_row["source_raw_sha256"]) != item["source_raw_sha256"]:
            raise Batch4Reject(f"reinsert_source_hash_mismatch:{string_id}")
        if str(reinsert_row["source_ledger_sha256"]) != str(ledger["source_hash"]):
            raise Batch4Reject(f"reinsert_ledger_hash_mismatch:{string_id}")
        if int(reinsert_row["source_payload_length"]) != item["source_payload_length"]:
            raise Batch4Reject(f"reinsert_length_mismatch:{string_id}")
        records.append(
            {
                key: item[key]
                for key in (
                    "string_id",
                    "source_raw_sha256",
                    "source_ledger_sha256",
                    "line_width",
                    "source_payload_length",
                    "source_unit_count",
                    "terminator",
                    "control_token_count",
                    "glyph_class",
                    "target_codepoints",
                )
            }
            | {
                "target_payload_sha256": reinsert_row["target_payload_sha256"],
                "same_length": bool(reinsert_row["same_length"]),
            }
        )
    allocations = reinsert.get("allocations", [])
    slot_values = sorted(int(row["slot"]) for row in allocations)
    return {
        "schema": "super-robot-taisen-d-m4-ui-batch4-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "translation_status": "ai_draft",
        },
        "selection": {
            "record_count": len(records),
            "records": records,
            "line_widths": sorted({int(row["line_width"]) for row in selected}),
            "control_token_count": 0,
            "glyph_class": "narrow_only",
            "same_length": all(bool(row["same_length"]) for row in records),
        },
        "static_reinsert": {
            "combined_records": int(reinsert["record_count"]),
            "combined_unique_allocations": int(reinsert["allocator"]["allocated_slot_count"]),
            "allocated_slot_range": [slot_values[0], slot_values[-1]] if slot_values else [],
            "protected_blank_slots_preserved": reinsert["allocator"]["protected_blank_referenced_slots"],
            "wide_new_slots": int(reinsert["allocator"]["wide_new_slots"]),
            "base_rom_sha256": sha256(base_rom),
            "patched_rom_sha256": sha256(patched_rom),
            "bps_size": len(bps),
            "bps_sha256": sha256(bps),
            "bps_apply_byte_identical": sha256(bps_applied) == sha256(patched_rom),
        },
        "roundtrip": {
            "source_records": int(roundtrip["source_records"]),
            "base_source_matches": int(roundtrip["base_source_matches"]),
            "target_records": int(roundtrip["target_records"]),
            "target_exact_matches": int(roundtrip["target_exact_matches"]),
            "untouched_records": int(roundtrip["untouched_records"]),
            "untouched_exact_matches": int(roundtrip["untouched_exact_matches"]),
            "actual_changed_bytes": int(roundtrip["actual_changed_bytes"]),
            "allowed_range_count": int(roundtrip["allowed_range_count"]),
            "rom_outside_allowed_ranges_equal": bool(roundtrip["rom_outside_allowed_ranges_equal"]),
            "runtime_status": "pending; static re-extraction only",
        },
        "gate": {
            "source_hash_matches": all(bool(row["source_raw_sha256"]) for row in records),
            "narrow_only": all(row["glyph_class"] == "narrow_only" for row in records),
            "nul_terminated": all(row["terminator"] == "NUL" for row in records),
            "control_tokens_empty": all(row["control_token_count"] == 0 for row in records),
            "same_length": all(bool(row["same_length"]) for row in records),
            "roundtrip_source_2325": roundtrip["base_source_matches"] == 2325,
            "roundtrip_targets_exact": roundtrip["target_exact_matches"] == roundtrip["target_records"],
            "roundtrip_untouched_exact": roundtrip["untouched_exact_matches"] == roundtrip["untouched_records"],
            "bps_apply_byte_identical": sha256(bps_applied) == sha256(patched_rom),
            "rom_outside_allowed_ranges_equal": bool(roundtrip["rom_outside_allowed_ranges_equal"]),
            "wide_new_slots_zero": int(reinsert["allocator"]["wide_new_slots"]) == 0,
            "source_text_emitted": False,
            "runtime_screen_verified": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-rom", type=Path, required=True)
    parser.add_argument("--patched-rom", type=Path, required=True)
    parser.add_argument("--bps", type=Path, required=True)
    parser.add_argument("--bps-applied-rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--reinsert-report", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        base_rom = args.base_rom.read_bytes()
        patched_rom = args.patched_rom.read_bytes()
        bps_applied = args.bps_applied_rom.read_bytes()
        selected = validate_selection(
            base_rom,
            m18.read_source_records(args.source_table),
            read_index(args.ledger),
        )
        report = build_report(
            base_rom,
            patched_rom,
            selected,
            read_index(args.ledger),
            json.loads(args.reinsert_report.read_text(encoding="utf-8")),
            json.loads(args.roundtrip.read_text(encoding="utf-8")),
            args.bps.read_bytes(),
            bps_applied,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, m18.M17Error) as exc:
        print(f"m4_batch4_rejected={exc}", file=sys.stderr)
        return 2
    print(
        f"m4_batch4=accepted records={report['selection']['record_count']} "
        f"combined={report['static_reinsert']['combined_records']} "
        f"allocations={report['static_reinsert']['combined_unique_allocations']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
