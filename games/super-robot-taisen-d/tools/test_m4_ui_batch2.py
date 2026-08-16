import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class M4UIBatch2MetadataTest(unittest.TestCase):
    def test_batch_report_is_source_safe_and_roundtripped(self) -> None:
        report = json.loads((ROOT / "research/m4-ui-batch2.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["selection"]["string_id"], 512228)
        self.assertEqual(report["selection"]["unit_count"], 2)
        self.assertEqual(report["selection"]["line_width"], 16)
        self.assertTrue(report["selection"]["target_length_equal"])
        self.assertEqual(report["duplicate_codepoint_reuse"]["reused_codepoints"], ["U+6C92", "U+6709"])
        self.assertEqual(report["duplicate_codepoint_reuse"]["batch2_new_unique_allocations_against_m3_batch"], 0)
        self.assertTrue(report["static_reinsert"]["bps_apply_byte_identical"])
        self.assertEqual(report["roundtrip"]["base_source_matches"], 2325)
        self.assertEqual(report["roundtrip"]["target_exact_matches"], 3)
        self.assertEqual(report["roundtrip"]["untouched_exact_matches"], 2322)
        self.assertTrue(report["roundtrip"]["rom_outside_allowed_ranges_equal"])
        self.assertFalse(report["gate"]["runtime_screen_verified"])

    def test_tracked_ledger_has_no_source_object(self) -> None:
        path = ROOT / "translations/m4-ui-batch-2.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertNotIn("source", row)
        self.assertEqual(row["string_id"], 512228)
        self.assertEqual(row["status"], "ai_draft")
        self.assertEqual(row["targets"]["zh-TW"]["text"], "沒有")
        self.assertEqual(len(row["source_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
