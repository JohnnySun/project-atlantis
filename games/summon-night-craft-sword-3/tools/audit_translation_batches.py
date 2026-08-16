#!/usr/bin/env python3
"""Audit the bounded B3CJ zh-TW ledgers without loading the source table.

This is a target-side QA gate for the committed ledger boundary.  It checks
stable IDs, target hashes, code-unit/byte-length/layout contracts, control
metadata, allowed glyph allocations, and a small explicit Simplified-Chinese
leak guard.  Source hash correctness and restore/strip are intentionally
delegated to ``validate_ledger.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
TARGET_LOCALE = "zh-TW"
ALLOWED_SLOT_FIRST = 0x845
ALLOWED_SLOT_LAST = 0x85F
EXPECTED_BATCHES = (
    (GAME_ROOT / "research" / "m2.5-batch-plan.json", GAME_ROOT / "translations" / "m2.5-prize-ui.jsonl"),
    (GAME_ROOT / "research" / "m4.1-wood-chopping-plan.json", GAME_ROOT / "translations" / "m4.1-wood-chopping.jsonl"),
    (GAME_ROOT / "research" / "m4.2-warning-label-plan.json", GAME_ROOT / "translations" / "m4.2-warning-label.jsonl"),
    (GAME_ROOT / "research" / "m4.3-ellipsis-label-plan.json", GAME_ROOT / "translations" / "m4.3-ellipsis-label.jsonl"),
)
# Bounded guard for the characters that have already appeared in this game's
# zh-TW batches.  It is deliberately not presented as a full dictionary.
KNOWN_SIMPLIFIED_LEAKS = {"这", "奖"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} is not an integer: {value!r}") from exc
    raise ValueError(f"{field} must be an integer or 0x string")


def load_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path} root is not an object")
    return value


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        _require(isinstance(value, dict), f"{path}:{line_number} is not an object")
        rows.append(value)
    return rows


def _contains_source(value: Any) -> bool:
    if isinstance(value, dict):
        if "source" in value or "source_text" in value:
            return True
        return any(_contains_source(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_source(child) for child in value)
    return False


def _allocation_map(plan: dict[str, Any], plan_path: pathlib.Path) -> dict[str, bytes]:
    allocations = plan.get("allocations")
    _require(isinstance(allocations, list), f"{plan_path} allocations are missing")
    by_char: dict[str, bytes] = {}
    units: set[bytes] = set()
    slots: set[int] = set()
    for index, item in enumerate(allocations):
        _require(isinstance(item, dict), f"{plan_path} allocations[{index}] is malformed")
        unit_text = item.get("code_unit")
        char = item.get("unicode")
        _require(isinstance(unit_text, str) and isinstance(char, str) and len(char) == 1, f"{plan_path} allocation {index} has malformed code unit/unicode")
        try:
            unit = bytes.fromhex(unit_text)
        except ValueError as exc:
            raise ValueError(f"{plan_path} allocation {index} code unit is not hex") from exc
        _require(len(unit) == 2 and unit not in units, f"{plan_path} allocation code units must be unique")
        slot = parse_int(item.get("glyph_id"), f"{plan_path} allocation {index}.glyph_id")
        _require(ALLOWED_SLOT_FIRST <= slot <= ALLOWED_SLOT_LAST and slot not in slots, f"{plan_path} allocation slot is outside unique allowed range")
        _require(item.get("code_unit_kind") == "opaque_extension", f"{plan_path} allocation kind is not opaque_extension")
        units.add(unit)
        slots.add(slot)
        _require(char not in by_char, f"{plan_path} allocation unicode is duplicated")
        by_char[char] = unit
    return by_char


def audit_batch(plan_path: pathlib.Path, ledger_path: pathlib.Path) -> dict[str, Any]:
    plan = load_json(plan_path)
    rows = load_jsonl(ledger_path)
    _require(len(rows) == 1, f"{ledger_path} must contain exactly one bounded record")
    ledger = rows[0]
    _require(not _contains_source(ledger), f"{ledger_path} contains source-bearing data")
    _require(plan.get("game") == EXPECTED_GAME and plan.get("revision") == EXPECTED_REVISION, f"{plan_path} identity mismatch")
    _require(ledger.get("game") == EXPECTED_GAME and ledger.get("revision") == EXPECTED_REVISION, f"{ledger_path} identity mismatch")
    string_id = plan.get("records", [{}])[0].get("string_id")
    _require(isinstance(string_id, str) and ledger.get("string_id") == string_id, f"{ledger_path} stable ID mismatch")
    _require(ledger.get("source_locale") == "ja-JP" and len(str(ledger.get("source_hash"))) == 64, f"{ledger_path} source metadata malformed")
    _require(ledger.get("status") == "ai_draft" and plan.get("status") == "ai_draft", f"{ledger_path} status is not ai_draft")

    context = plan.get("context")
    contract = plan.get("target_contract")
    controls = plan.get("control_contract")
    _require(isinstance(context, dict) and isinstance(contract, dict) and isinstance(controls, dict), f"{plan_path} contracts are incomplete")
    _require(context.get("max_lines") == 1 and isinstance(context.get("max_width"), int), f"{plan_path} line/width contract is incomplete")
    _require(context.get("control_codes") == ["0x0308", "0x0000"], f"{plan_path} control code contract drifted")
    _require(controls.get("opaque_control_count") == 0, f"{plan_path} selected record has opaque controls")
    _require(contract.get("record_terminator") == "0x0000", f"{plan_path} record terminator drifted")

    targets = plan.get("targets")
    ledger_targets = ledger.get("targets")
    _require(isinstance(targets, dict) and isinstance(ledger_targets, dict), f"{ledger_path} target metadata is missing")
    target = targets.get(TARGET_LOCALE)
    ledger_target = ledger_targets.get(TARGET_LOCALE)
    _require(isinstance(target, dict) and isinstance(ledger_target, dict), f"{ledger_path} zh-TW target is missing")
    text = target.get("text")
    _require(isinstance(text, str) and ledger_target.get("text") == text, f"{ledger_path} target text differs from plan")
    _require(target.get("utf8_sha256") == sha256_bytes(text.encode("utf-8")), f"{plan_path} target UTF-8 hash drifted")
    _require(not any(char in KNOWN_SIMPLIFIED_LEAKS for char in text), f"{plan_path} target contains a known Simplified-Chinese leak")

    unit_texts = contract.get("code_units")
    _require(isinstance(unit_texts, list) and len(unit_texts) == len(text), f"{plan_path} code-unit count does not match target width")
    payload = b""
    allocations = _allocation_map(plan, plan_path)
    extension_units = {bytes.fromhex(str(value)) for value in contract.get("extension_units", [])}
    for char, unit_text in zip(text, unit_texts):
        _require(isinstance(unit_text, str) and len(unit_text) == 4, f"{plan_path} code unit is malformed")
        unit = bytes.fromhex(unit_text)
        if char in allocations:
            _require(unit == allocations[char] and unit in extension_units, f"{plan_path} allocation does not encode {char}")
        else:
            encoded = char.encode("shift_jis")
            _require(encoded == unit, f"{plan_path} existing Shift-JIS unit drifted for a target character")
        payload += unit
    _require(len(payload) == parse_int(contract.get("byte_length"), f"{plan_path} target byte_length"), f"{plan_path} target byte length drifted")
    _require(len(payload) <= int(context["max_width"]) * 2, f"{plan_path} target exceeds bounded width")

    return {"batch_id": plan.get("batch_id"), "string_id": string_id, "status": ledger.get("status"), "code_units": len(unit_texts), "byte_length": len(payload), "allocation_count": len(allocations), "target_utf8_sha256": target["utf8_sha256"]}


def audit(paths: Iterable[tuple[pathlib.Path, pathlib.Path]] = EXPECTED_BATCHES) -> dict[str, Any]:
    reports = [audit_batch(plan_path, ledger_path) for plan_path, ledger_path in paths]
    string_ids = [str(report["string_id"]) for report in reports]
    _require(len(string_ids) == len(set(string_ids)), "bounded batch IDs are duplicated")
    return {"audit_version": "m4-target-qa-v1", "batches": len(reports), "records": reports, "known_simplified_guard": sorted(KNOWN_SIMPLIFIED_LEAKS)}


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-output", type=pathlib.Path)
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        report = audit()
        if args.summary_output is not None:
            args.summary_output.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_TARGET_QA_OK batches={report['batches']} records={sum(1 for _ in report['records'])} audit_version={report['audit_version']}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"audit_translation_batches.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
