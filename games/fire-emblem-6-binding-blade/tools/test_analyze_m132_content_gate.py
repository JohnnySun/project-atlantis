#!/usr/bin/env python3
"""Regression tests for the FE6 M1.32 full-table content gate."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m132_content_gate as gate  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM132ContentGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = tuple(path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file())
        cls.report = gate.build_report(ROM_PATH, paths)

    def test_full_table_and_failures_remain_explicit(self) -> None:
        table = self.report["table"]
        self.assertEqual(table["record_count"], 3342)
        self.assertEqual(table["strictly_supported_record_count"], 3203)
        self.assertEqual(table["decoder_failure_count"], 139)
        self.assertTrue(table["all_source_spans_match_next_entry"])
        self.assertEqual(len(table["records"]), 3203)
        self.assertEqual(len(table["decoder_failures"]), 139)
        self.assertEqual(table["decoder_failures"][0]["table_index"], 17)
        self.assertTrue(table["source_bytes_emitted"] is False)
        self.assertTrue(table["code_unit_bytes_emitted"] is False)

    def test_natural_receipts_join_static_source_and_hashes(self) -> None:
        runtime = self.report["runtime"]
        self.assertEqual(runtime["natural_loader_receipt_count"], 4)
        self.assertEqual(runtime["source_pointer_static_match_count"], 4)
        self.assertEqual(runtime["output_hash_static_match_count"], 3)
        self.assertEqual(len(runtime["caller_groups"]), 2)
        caller_indices = {
            row["caller_callsite"]: row["observed_indices"]
            for row in runtime["caller_groups"]
        }
        self.assertEqual(caller_indices["0x08098b10"], [3087])
        self.assertEqual(caller_indices["0x08009252"], [2678, 2679])

    def test_category_gate_never_infers_from_index_caller_or_route(self) -> None:
        category = self.report["category_gate"]
        self.assertEqual(category["natural_unique_table_index_count"], 3)
        self.assertEqual(category["natural_unique_caller_count"], 2)
        self.assertEqual(category["content_categories_assigned"], [])
        self.assertTrue(category["caller_or_scene_evidence_present"])
        self.assertFalse(category["index_adjacency_used_as_category_evidence"])
        self.assertFalse(category["route_name_used_as_category_evidence"])
        self.assertFalse(category["translation_ready"])

    def test_report_has_hashes_and_no_tokens_or_source_text(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("tokens", serialized)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn('"source_bytes":', serialized)
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertEqual(len(self.report["table"]["hash_only_table_digest"]), 64)


if __name__ == "__main__":
    unittest.main()
