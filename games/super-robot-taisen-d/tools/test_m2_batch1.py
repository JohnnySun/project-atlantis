from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class M2Batch1MetadataTest(unittest.TestCase):
    def test_static_batch_report_is_source_safe_and_fail_closed(self) -> None:
        report = json.loads((ROOT / "research/m2-ui-batch1.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_text_emitted"])
        self.assertEqual(report["translation_status"], "ai_draft")
        self.assertEqual(report["target"]["string_id"], 526432)
        self.assertEqual(report["target"]["unit_count"], 2)
        self.assertEqual(report["target"]["line_width"], 16)
        self.assertTrue(report["allocator"]["same_length"])
        self.assertEqual(report["allocator"]["wide_new_slots"], 0)
        self.assertEqual(report["target"]["allocations"][0]["slot"], 543)
        self.assertEqual(report["target"]["allocations"][1]["slot"], 542)
        self.assertTrue(report["adjacent_untouched"]["base_payload_sha256"] == report["adjacent_untouched"]["patched_payload_sha256"])
        self.assertTrue(report["bps"]["apply_byte_identical"])
        rejected = report["rejected_candidate"]
        self.assertEqual(rejected["reason"], "wide_glyph")
        self.assertFalse(rejected["translation_created"])

    def test_tracked_ledger_has_no_source_object(self) -> None:
        path = ROOT / "translations/m2-ui-batch-1.jsonl"
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        record = lines[0]
        self.assertNotIn("source", record)
        self.assertEqual(record["string_id"], 526432)
        self.assertEqual(record["status"], "ai_draft")
        self.assertEqual(record["targets"]["zh-TW"]["text"], "存在")
        self.assertEqual(len(record["source_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
