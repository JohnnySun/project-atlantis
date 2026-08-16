#!/usr/bin/env python3
"""Audit bounded story-event layout and control invariants without emitting text.

This is a conservative record-level gate.  It checks source/target LF and other
control bytes, target line count, a declared character-count budget, encoded
payload fit, and B3EJ codepage membership.  It reports hashes and counts only;
it is not a natural-screen or pixel-width proof.
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
import table_b_common as common  # noqa: E402


def _control_signature(payload: bytes) -> list[int]:
    return [value for value in payload if value < 0x20]


def _line_metrics(text: str) -> list[int]:
    return [len(line) for line in text.split("\n")]


def audit_work(data: bytes, records: list[dict[str, object]], mapping_path: Path) -> dict[str, object]:
    mapping = custom_glyph_patch.parse_mapping(mapping_path)
    codepage = custom_glyph_patch.font_glyph_format.read_codepage(data)
    rows = []
    for record in records:
        source = record.get("source")
        target = record.get("targets", {}).get("zh-TW", {})
        context = record.get("context", {})
        if not isinstance(source, dict) or not isinstance(target, dict) or not isinstance(context, dict):
            raise ValueError(f"record lacks source, target or context: {record.get('string_id')!r}")
        source_text = source.get("text")
        target_text = target.get("text")
        provenance = source.get("provenance", {})
        if not isinstance(source_text, str) or not isinstance(target_text, str) or not isinstance(provenance, dict):
            raise ValueError(f"record lacks text or provenance: {record.get('string_id')!r}")
        encoded, custom_codepoints = custom_glyph_patch.encode_text(
            target_text, mapping["by_codepoint"]
        )
        custom_glyph_patch._validate_target_codepage(encoded, codepage)
        source_payload = source_text.encode("shift_jis")
        source_controls = _control_signature(source_payload)
        target_controls = _control_signature(encoded)
        max_width = context.get("max_width")
        max_lines = context.get("max_lines")
        if not isinstance(max_width, int) or not isinstance(max_lines, int):
            raise ValueError(f"record has no integer layout budget: {record.get('string_id')!r}")
        source_lines = _line_metrics(source_text)
        target_lines = _line_metrics(target_text)
        line_budget_ok = len(target_lines) <= max_lines and max(target_lines, default=0) <= max_width
        row = {
            "string_id": record.get("string_id"),
            "source_text_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "source_payload_length": len(source_payload),
            "source_line_count": len(source_lines),
            "source_line_char_counts": source_lines,
            "source_control_bytes": source_controls,
            "target_text_hash": hashlib.sha256(target_text.encode("utf-8")).hexdigest(),
            "target_payload_length": len(encoded),
            "target_line_count": len(target_lines),
            "target_line_char_counts": target_lines,
            "target_control_bytes": target_controls,
            "max_width": max_width,
            "max_lines": max_lines,
            "line_budget_ok": line_budget_ok,
            "control_invariant": source_controls == target_controls,
            "fixed_slot_fit": len(encoded) <= len(source_payload),
            "custom_codepoints": [f"U+{value:04X}" for value in custom_codepoints],
            "target_codepage_membership": True,
        }
        if not row["line_budget_ok"] or not row["control_invariant"] or not row["fixed_slot_fit"]:
            raise ValueError(f"story layout gate failed: {record.get('string_id')!r}")
        rows.append(row)
    return {
        "read_only": True,
        "record_count": len(rows),
        "line_budget_pass_count": sum(row["line_budget_ok"] for row in rows),
        "control_invariant_count": sum(row["control_invariant"] for row in rows),
        "fixed_slot_fit_count": sum(row["fixed_slot_fit"] for row in rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [
        json.loads(line)
        for line in args.work.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = audit_work(args.rom.read_bytes(), records, args.mapping)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("read_only", "record_count", "line_budget_pass_count", "control_invariant_count", "fixed_slot_fit_count")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
