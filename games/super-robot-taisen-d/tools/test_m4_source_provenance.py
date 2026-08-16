from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_source_provenance import hash_ints


ROOT = Path(__file__).resolve().parents[1]


class M4SourceProvenanceTest(unittest.TestCase):
    def test_integer_hash_is_order_stable_and_source_safe(self) -> None:
        self.assertEqual(hash_ints([3, 1, 2, 1]), hash_ints([2, 3, 1]))
        self.assertNotIn("日本", hash_ints([1, 2]))

    def test_real_join_keeps_semantic_partition_unclassified(self) -> None:
        report = json.loads((ROOT / "research/m4-source-provenance.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertFalse(report["source_policy"]["semantic_labels_inferred"])
        self.assertEqual(report["source_corpus"]["record_count"], 2325)
        self.assertEqual(report["source_corpus"]["token_encode_noop_count"], 2325)
        self.assertEqual(report["source_corpus"]["translated_static_record_count"], 12)
        self.assertEqual(report["pointer_report"]["exact_source_candidate_count"], 609)
        self.assertEqual(report["pointer_report"]["exact_source_record_count"], 370)
        self.assertEqual(report["semantic_boundary"]["semantic_partition_status"], "unclassified")

    def test_report_partitions_have_hashes_not_source_text(self) -> None:
        report = json.loads((ROOT / "research/m4-source-provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report["structural_partitions"]), {
            "glyph_only_mixed",
            "glyph_only_narrow",
            "glyph_only_wide",
            "opaque_or_unaligned",
        })
        for partition in report["structural_partitions"].values():
            self.assertEqual(len(partition["record_id_index_sha256"]), 64)
            self.assertNotIn("text", partition)


if __name__ == "__main__":
    unittest.main()
