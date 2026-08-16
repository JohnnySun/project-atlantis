#!/usr/bin/env python3
"""Regression tests for the FE6 M1.34 title/font contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m134_title_contract as title  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM134TitleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = tuple(path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file())
        cls.report = title.build_report(ROM_PATH, paths)

    def test_bounded_title_class_is_not_index_adjacency_only(self) -> None:
        gate = self.report["content_class_gate"]
        self.assertEqual(gate["label"], "title_splash_bounded_candidate")
        self.assertTrue(gate["category_assigned"])
        self.assertTrue(gate["category_is_provisional"])
        self.assertFalse(gate["index_adjacency_used_as_category_evidence"])
        records = self.report["title_records"]
        self.assertEqual(records["table_domain"], "[3080,3088)")
        self.assertEqual(records["record_count"], 8)
        self.assertEqual(records["strict_shift_jis_candidate_count"], 8)
        self.assertTrue(records["map_prefix_set_equal"])

    def test_map_prefix_and_font_source_domain_close_at_80(self) -> None:
        mapping = self.report["map_contract"]
        self.assertEqual(mapping["base"], "0x08691644")
        self.assertEqual(mapping["terminator"], "0x08691736")
        self.assertEqual(mapping["full_entry_count"], 121)
        self.assertEqual(mapping["valid_sjis_prefix_count"], 80)
        self.assertEqual(mapping["prefix_unique_entry_count"], 78)
        source = self.report["font_source_contract"]
        self.assertEqual(source["formula_input_bounds_valid_count"], 80)
        self.assertEqual(source["formula_input_bounds_invalid_count"], 0)
        self.assertEqual(len(source["source_slots"]), 80)
        self.assertEqual(source["unique_four_plane_composite_hash_count"], 67)
        self.assertEqual(source["source_offset_stride_histogram"], {
            "0x00000040": 75,
            "0x00000440": 4,
        })

    def test_natural_runtime_joins_title_loader_and_map_hashes(self) -> None:
        runtime = self.report["runtime"]
        if runtime is None:
            self.skipTest("ignored natural runtime receipts are not installed")
        self.assertGreaterEqual(runtime["natural_title_loader_receipt_count"], 1)
        self.assertEqual(runtime["title_loader_source_pointer_match_count"], 2)
        self.assertEqual(runtime["title_loader_buffer_hash_match_count"], 2)
        self.assertEqual(runtime["lookup_count_bounded"], 16)
        self.assertEqual(runtime["lookup_map_hash_match_count"], 16)
        self.assertEqual(runtime["lookup_glyph_index_match_count"], 16)
        self.assertFalse(runtime["renderer_source_bytes_observed"])
        self.assertFalse(runtime["writer_receipts_observed"])

    def test_report_keeps_font_unicode_and_arbitrary_encode_negative(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn('"source_bytes"', serialized)
        self.assertNotIn("code_unit_bytes", serialized)
        self.assertNotIn('"decoded_text"', serialized)
        self.assertNotIn('"bitmap_bytes"', serialized)
        status = self.report["status"]
        self.assertFalse(status["font_identity_confirmed"])
        self.assertFalse(status["unicode_identity_confirmed"])
        self.assertFalse(status["translation_ready"])
        self.assertFalse(status["arbitrary_text_encode_enabled"])
        self.assertFalse(status["rom_insertion_enabled"])


if __name__ == "__main__":
    unittest.main()
