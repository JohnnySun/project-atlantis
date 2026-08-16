#!/usr/bin/env python3
"""Tests for the B3CJ ledger/source split validator."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "validate_ledger.py"
SPEC = importlib.util.spec_from_file_location("validate_ledger", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load validate_ledger.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

LEDGER_PATH = GAME_ROOT / "translations" / "m2.5-prize-ui.jsonl"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
TARGET_ID = "b3cj:t2:024:0x0064"


class ValidateLedgerTest(unittest.TestCase):
    def require_artifacts(self) -> None:
        if not LEDGER_PATH.is_file() or not SOURCE_PATH.is_file():
            self.skipTest("ignored source table or tracked ledger is unavailable")

    def test_real_ledger_roundtrips_through_core_codec(self) -> None:
        self.require_artifacts()
        report = VALIDATOR.validate(LEDGER_PATH, SOURCE_PATH, {TARGET_ID})
        self.assertEqual(report["source_rows"], 361)
        self.assertEqual(report["ledger_records"], 1)
        self.assertEqual(report["restore_strip_roundtrip"], "json_value_identical")
        self.assertEqual(report["string_ids"], [TARGET_ID])

    def test_embedded_source_key_is_rejected(self) -> None:
        self.require_artifacts()
        rows = [json.loads(line) for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines() if line]
        rows[0]["source"] = {"text": "temporary test value"}
        with tempfile.TemporaryDirectory(prefix="b3cj-ledger-test-") as temporary:
            path = pathlib.Path(temporary) / "bad.jsonl"
            path.write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                VALIDATOR.validate(path, SOURCE_PATH, {TARGET_ID})

    def test_source_hash_drift_is_rejected(self) -> None:
        self.require_artifacts()
        rows = [json.loads(line) for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines() if line]
        rows[0]["source_text"] = str(rows[0]["source_text"]) + "x"
        with tempfile.TemporaryDirectory(prefix="b3cj-ledger-test-") as temporary:
            path = pathlib.Path(temporary) / "drifted.jsonl"
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                VALIDATOR.validate(LEDGER_PATH, path, {TARGET_ID})


if __name__ == "__main__":
    unittest.main()
