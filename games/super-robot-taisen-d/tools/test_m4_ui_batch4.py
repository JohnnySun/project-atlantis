from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_ui_batch4 import SELECTION, Batch4Reject, validate_target


ROOT = Path(__file__).resolve().parents[1]


class M4UIBatch4MetadataTest(unittest.TestCase):
    def test_selected_targets_are_fixed_length_and_source_safe(self) -> None:
        self.assertEqual({513060, 513076, 517848}, set(SELECTION))
        self.assertEqual(len(SELECTION[513060]), 6)
        self.assertEqual(len(SELECTION[513076]), 6)
        self.assertEqual(len(SELECTION[517848]), 7)
        for string_id, target in SELECTION.items():
            validate_target(target, len(target))
            self.assertNotIn("\n", target)
            self.assertNotIn("\r", target)

    def test_target_length_gate_fails_closed(self) -> None:
        with self.assertRaisesRegex(Batch4Reject, "variable_length"):
            validate_target(SELECTION[513060][:-1], len(SELECTION[513060]))

    def test_report_and_ledger_are_source_safe_static_only(self) -> None:
        report = json.loads((ROOT / "research/m4-ui-batch4.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["selection"]["record_count"], 3)
        self.assertEqual(report["selection"]["glyph_class"], "narrow_only")
        self.assertEqual(report["selection"]["control_token_count"], 0)
        self.assertTrue(report["gate"]["bps_apply_byte_identical"])
        self.assertFalse(report["gate"]["runtime_screen_verified"])
        rows = [
            json.loads(line)
            for line in (ROOT / "translations/m4-ui-batch-4.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertNotIn("source", row)
            self.assertEqual(row["status"], "ai_draft")
            self.assertEqual(len(row["source_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
