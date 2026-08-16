#!/usr/bin/env python3
"""Tests for target-side M4 bounded translation QA."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "audit_translation_batches.py"
SPEC = importlib.util.spec_from_file_location("audit_translation_batches", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_translation_batches.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditTranslationBatchesTest(unittest.TestCase):
    def test_real_bounded_batches_pass(self) -> None:
        report = AUDIT.audit()
        self.assertEqual(report["batches"], 4)
        self.assertEqual([row["code_units"] for row in report["records"]], [7, 6, 5, 4])
        self.assertEqual([row["allocation_count"] for row in report["records"]], [3, 2, 0, 1])
        self.assertEqual({row["status"] for row in report["records"]}, {"ai_review"})

    def test_approved_status_is_still_rejected_until_human_gate(self) -> None:
        plan_path, ledger_path = AUDIT.EXPECTED_BATCHES[0]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["status"] = "approved"
        with tempfile.TemporaryDirectory(prefix="b3cj-target-qa-") as directory:
            root = pathlib.Path(directory)
            plan_copy = root / "plan.json"
            ledger_copy = root / "ledger.jsonl"
            plan_copy.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            ledger_copy.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                AUDIT.audit_batch(plan_copy, ledger_copy)

    def test_source_bearing_ledger_is_rejected(self) -> None:
        plan_path, ledger_path = AUDIT.EXPECTED_BATCHES[0]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["source"] = {"text": "must not be tracked"}
        with tempfile.TemporaryDirectory(prefix="b3cj-target-qa-") as directory:
            root = pathlib.Path(directory)
            plan_copy = root / "plan.json"
            ledger_copy = root / "ledger.jsonl"
            plan_copy.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            ledger_copy.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                AUDIT.audit_batch(plan_copy, ledger_copy)

    def test_target_hash_or_length_drift_is_rejected(self) -> None:
        plan_path, ledger_path = AUDIT.EXPECTED_BATCHES[3]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        drifted = copy.deepcopy(plan)
        drifted["targets"]["zh-TW"]["utf8_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="b3cj-target-qa-") as directory:
            root = pathlib.Path(directory)
            plan_copy = root / "plan.json"
            ledger_copy = root / "ledger.jsonl"
            plan_copy.write_text(json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
            ledger_copy.write_text(json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                AUDIT.audit_batch(plan_copy, ledger_copy)


if __name__ == "__main__":
    unittest.main()
