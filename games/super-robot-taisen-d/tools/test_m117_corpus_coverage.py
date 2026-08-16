from __future__ import annotations

import unittest

from m117_corpus_coverage import summarize_coverage


class M117CorpusCoverageTest(unittest.TestCase):
    def test_partition_and_caller_coverage_is_hash_only(self) -> None:
        partitions = {0x76000: "glyph_only_narrow", 0x76010: "glyph_only_wide"}
        candidates = [
            {
                "target_offset": 0x76000,
                "function_start": 0x100,
                "instruction_offset": 0x120,
            },
            {
                "target_offset": 0x76000,
                "function_start": 0x100,
                "instruction_offset": 0x124,
            },
        ]
        report = summarize_coverage(partitions, candidates)
        self.assertEqual(report["pointer_join"]["exact_source_candidate_count"], 2)
        self.assertEqual(report["pointer_join"]["exact_source_record_count"], 1)
        self.assertEqual(report["partition_coverage"]["glyph_only_narrow"]["uncovered_record_count"], 0)
        self.assertEqual(report["partition_coverage"]["glyph_only_wide"]["uncovered_record_count"], 1)
        self.assertTrue(report["pointer_join"]["all_cohort_candidates_covered"])
        self.assertNotIn("source", report)
        self.assertNotIn("text", report)


if __name__ == "__main__":
    unittest.main()
