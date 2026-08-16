#!/usr/bin/env python3
"""Regression tests for the FE6 M1.26 cross-caller provenance census."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m126_provenance as census  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM126ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = [path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file()]
        cls.report = census.build_report(ROM_PATH, runtime_paths=paths)

    def test_two_disjoint_windows_share_strict_worker_and_roundtrip(self) -> None:
        table = self.report["table"]
        self.assertEqual(table["selected_ranges"], ["2672:16", "3080:16"])
        self.assertEqual(table["selected_record_count"], 32)
        self.assertEqual(table["failure_count"], 0)
        self.assertTrue(table["all_selected_source_spans_match_next_entry"])
        self.assertTrue(self.report["cross_caller_comparison"]["strict_worker_format_shared"])
        self.assertTrue(self.report["encode_guard"]["decode_encode_byte_identical"])
        self.assertFalse(self.report["encode_guard"]["arbitrary_text_encode_enabled"])

    @unittest.skipUnless(
        SHORT_RUNTIME.is_file() and LONG_RUNTIME.is_file(),
        "ignored M1.19 natural receipts are not installed",
    )
    def test_runtime_witnesses_join_two_callers_and_preserve_2679_negative(self) -> None:
        runtime = self.report["runtime"]
        self.assertEqual(runtime["loader_receipt_count"], 4)
        self.assertTrue(runtime["all_observed_indices_in_selected_census"])
        self.assertEqual(runtime["source_pointer_match_count"], 4)
        self.assertEqual(runtime["output_hash_match_count"], 3)
        self.assertEqual(runtime["output_hash_mismatch_indices"], [2679])
        self.assertEqual(
            self.report["cross_caller_comparison"]["natural_caller_families_observed"],
            ["0x08009252", "0x08098b10"],
        )
        self.assertFalse(self.report["cross_caller_comparison"]["same_content_category_proven"])
        self.assertFalse(runtime["category_inferred_from_index_caller_or_route"])

    def test_serialized_report_is_hash_only_and_category_unknown(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("Nintendo", serialized)
        self.assertEqual(self.report["status"]["scene_or_content_category"], "unknown")
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertFalse(self.report["status"]["translation_ready"])

    def test_range_parser_and_safety_bound(self) -> None:
        self.assertEqual(census.parse_range("0x0a:4"), (10, 4))
        with self.assertRaises(Exception):
            census.parse_range("2672")
        with self.assertRaises(ValueError):
            census._selected_indices([(0, 33)], 3342)


if __name__ == "__main__":
    unittest.main()
