from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_ui_batch5 import SELECTION


ROOT = Path(__file__).resolve().parents[1]


class M4UIBatch5MetadataTest(unittest.TestCase):
    def test_selection_is_one_fixed_length_narrow_prompt(self) -> None:
        self.assertEqual(set(SELECTION), {516324})
        self.assertEqual(len(SELECTION[516324]), 8)
        self.assertNotIn("\n", SELECTION[516324])

    def test_report_is_source_safe_and_static_only(self) -> None:
        report = json.loads((ROOT / "research/m4-ui-batch5.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["selection"]["record_count"], 1)
        self.assertEqual(report["selection"]["glyph_class"], "narrow_only")
        self.assertTrue(report["gate"]["bps_apply_byte_identical"])
        self.assertFalse(report["gate"]["runtime_screen_verified"])
        rows = [
            json.loads(line)
            for line in (ROOT / "translations/m4-ui-batch-5.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 1)
        self.assertNotIn("source", rows[0])


if __name__ == "__main__":
    unittest.main()
