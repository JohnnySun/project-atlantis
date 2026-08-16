#!/usr/bin/env python3
"""ROM-independent tests for the bounded story layout gate."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("audit_story_layout.py")
SPEC = importlib.util.spec_from_file_location("audit_story_layout", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_story_layout.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class StoryLayoutAuditTest(unittest.TestCase):
    def test_line_metrics_counts_trailing_and_internal_lines(self) -> None:
        self.assertEqual(AUDIT._line_metrics("甲\n乙\n"), [1, 1, 0])

    def test_control_signature_keeps_lf_only(self) -> None:
        self.assertEqual(AUDIT._control_signature(b"A\nB\0"), [10, 0])

    def test_batch7_ledger_is_source_free_and_bounded(self) -> None:
        ledger_path = pathlib.Path(__file__).parents[1] / "translations" / "story-event-batch-7.jsonl"
        rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(
            [row["string_id"] for row in rows],
            ["b3ej:story-event:009", "b3ej:story-event:010"],
        )
        for row in rows:
            self.assertNotIn("source", row)
            self.assertEqual(row["source_locale"], "ja-JP")
            self.assertEqual(len(row["source_hash"]), 64)
            self.assertEqual(row["context"]["max_width"], 12)
            self.assertIn(row["context"]["max_lines"], (4, 5))


if __name__ == "__main__":
    unittest.main()
