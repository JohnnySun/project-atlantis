from __future__ import annotations

import json
import unittest
from pathlib import Path

from m126_full_encoder_ledger_audit import (
    EXPECTED_LEDGER_COUNT,
    FullEncoderAuditReject,
    _source_safe_ledger_rows,
)


ROOT = Path(__file__).resolve().parents[1]


class M126FullEncoderLedgerAuditTest(unittest.TestCase):
    def test_tracked_audit_is_source_safe_and_fail_closed(self) -> None:
        path = ROOT / "research/m126-full-encoder-ledger-audit.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertFalse(report["source_policy"]["target_text_emitted"])
        self.assertFalse(report["gate"]["full_semantic_translation"])
        self.assertFalse(report["gate"]["release_ready"])
        self.assertEqual(report["source_corpus"]["record_count"], 2325)
        self.assertEqual(report["translation_ledger"]["accepted_count"], EXPECTED_LEDGER_COUNT)
        self.assertEqual(report["translation_ledger"]["record_count"], EXPECTED_LEDGER_COUNT)
        self.assertEqual(report["fail_closed_boundary"]["rejected_total_count"], 2313)
        self.assertEqual(report["encoder_status"]["full_encoder_status"], "fail_closed_subset_only")
        self.assertEqual(report["inputs"]["wide_new_slot_capacity"], 0)
        serialized = path.read_text(encoding="utf-8")
        self.assertNotIn('"source":', serialized)
        self.assertNotIn('"source_text":', serialized)
        self.assertNotIn('"targets":', serialized)

    def test_ledger_source_text_and_duplicate_ids_fail_closed(self) -> None:
        row = {
            "string_id": 1,
            "source_hash": "0" * 64,
            "targets": {"zh-TW": {"text": "A"}},
        }
        with self.assertRaisesRegex(FullEncoderAuditReject, "source_text_emitted"):
            _source_safe_ledger_rows([{**row, "source": "forbidden"}])
        with self.assertRaisesRegex(FullEncoderAuditReject, "duplicate_ledger_id"):
            _source_safe_ledger_rows([row, row])


if __name__ == "__main__":
    unittest.main()
