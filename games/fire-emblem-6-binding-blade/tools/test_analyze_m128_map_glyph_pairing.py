#!/usr/bin/env python3
"""Regression tests for the FE6 M1.28 map/glyph pairing receipt."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m128_map_glyph_pairing as pairing  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM128MapGlyphPairingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = [path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file()]
        cls.report = pairing.build_report(ROM_PATH, paths)

    def test_static_map_span_is_bounded_and_hash_only(self) -> None:
        static = self.report["static_map"]
        self.assertEqual(static["map_base"], "0x08691644")
        self.assertEqual(static["entry_count"], 121)
        self.assertEqual(static["terminator_address"], "0x08691736")
        self.assertEqual(static["span_length"], 244)
        self.assertFalse(static["raw_bytes_emitted"])

    @unittest.skipUnless(
        SHORT_RUNTIME.is_file() and LONG_RUNTIME.is_file(),
        "ignored M1.19 natural receipts are not installed",
    )
    def test_both_routes_pair_eight_map_and_glyph_receipts(self) -> None:
        comparison = self.report["comparison"]
        self.assertEqual(comparison["route_count"], 2)
        self.assertTrue(comparison["all_routes_have_8_paired_receipts"])
        self.assertTrue(comparison["all_paired_map_entries_match_formula"])
        self.assertTrue(comparison["all_paired_map_indices_equal_glyph_indices"])
        self.assertFalse(comparison["font_source_pairing_observed"])
        for route in self.report["routes"]:
            self.assertEqual(route["paired_receipt_count"], 8)
            self.assertEqual(route["map_entry_formula_equal_count"], 8)
            self.assertEqual(route["map_glyph_equal_count"], 8)
            self.assertEqual(route["renderer_entry_count"], 0)
            self.assertEqual(route["writer_receipt_count"], 0)

    def test_serialized_report_has_hashes_not_code_units_or_text(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("8251", serialized.lower())
        self.assertNotIn("824f", serialized.lower())
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertFalse(self.report["status"]["font_identity_confirmed"])


if __name__ == "__main__":
    unittest.main()
