from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_full_corpus_gate import hash_ints


ROOT = Path(__file__).resolve().parents[1]


class M4FullCorpusGateTest(unittest.TestCase):
    def test_id_hash_is_source_safe(self) -> None:
        self.assertEqual(hash_ints([10, 2, 10]), hash_ints([2, 10]))
        self.assertEqual(len(hash_ints([1])), 64)

    def test_real_gate_preserves_rejected_partition_counts(self) -> None:
        report = json.loads((ROOT / "research/m4-full-corpus-gate.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["source_corpus"]["record_count"], 2325)
        self.assertEqual(report["source_corpus"]["token_encode_noop_count"], 2325)
        self.assertEqual(report["translation_boundary"]["ledger_record_count"], 12)
        self.assertEqual(report["translation_boundary"]["translated_narrow_only_count"], 12)
        self.assertEqual(report["translation_boundary"]["rejected_mixed_count"], 833)
        self.assertEqual(report["translation_boundary"]["rejected_wide_count"], 417)
        self.assertEqual(report["translation_boundary"]["rejected_opaque_or_unaligned_count"], 136)
        self.assertEqual(report["gate"]["full_encoder_status"], "fail_closed_subset_only")
        self.assertFalse(report["gate"]["full_semantic_translation"])


if __name__ == "__main__":
    unittest.main()
