from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from m112_semantic_caller_boundary import BoundaryReject, _cohort, hash_ints, read_ledger_ids


class M112SemanticCallerBoundaryTest(unittest.TestCase):
    def test_cohort_is_source_safe_and_keeps_semantics_unclassified(self) -> None:
        rows = [
            {
                "target_offset": 0x76010,
                "instruction_offset": 0x120,
                "function_start": 0x100,
                "confidence": "high",
                "literal_kind": "literal_pool",
                "following_calls": [{"target": 0x08008724}],
            },
            {
                "target_offset": 0x76020,
                "instruction_offset": 0x124,
                "function_start": 0x100,
                "confidence": "medium",
                "literal_kind": "pointer_table_member",
                "following_calls": [{"target": 0x08008724}],
            },
        ]
        result = _cohort(
            0x100,
            rows,
            {0x76010: "glyph_only_narrow", 0x76020: "glyph_only_wide"},
        )
        self.assertEqual(result["caller_function_start"], "0x08000100")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["semantic_label"], "unclassified")
        self.assertNotIn("text", json.dumps(result, ensure_ascii=False))

    def test_hash_ints_is_order_stable(self) -> None:
        self.assertEqual(hash_ints([3, 1, 3, 2]), hash_ints([2, 1, 3]))

    def test_ledger_source_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            path.write_text(json.dumps({"string_id": 1, "source": {}}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryReject, "source_text_emitted"):
                read_ledger_ids([path])


if __name__ == "__main__":
    unittest.main()
