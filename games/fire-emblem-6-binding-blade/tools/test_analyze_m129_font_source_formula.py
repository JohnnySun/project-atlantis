#!/usr/bin/env python3
"""Regression tests for the FE6 M1.29 font-source formula census."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m129_font_source_formula as formula  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM129FontSourceFormulaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = [path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file()]
        cls.report = formula.build_report(ROM_PATH, paths)

    def test_static_literals_and_formula_cover_map_domain(self) -> None:
        static = self.report["static"]
        self.assertEqual(static["map_entry_count"], 121)
        self.assertEqual(static["map_terminator"], "0x08691736")
        self.assertEqual(static["literal_values"]["source_base"], "0x02000000")
        self.assertEqual(static["literal_values"]["destination_base"], "0x06010000")
        self.assertEqual(static["literal_values"]["config_address"], "0x02002800")
        self.assertEqual(static["literal_values"]["offset_mask"], "0x000003ff")
        self.assertEqual(len(self.report["font_source_formula_rows"]), 121)

    def test_observed_indices_resolve_without_claiming_runtime_source_bytes(self) -> None:
        self.assertEqual(formula.source_offset_for_map_index(67), 0x20C0)
        self.assertEqual(formula.source_offset_for_map_index(68), 0x2100)
        runtime = self.report["runtime"]
        self.assertEqual(runtime["observed_lookup_count"], 16)
        self.assertEqual(runtime["formula_resolved_count"], 16)
        self.assertFalse(runtime["renderer_source_address_observed"])
        self.assertFalse(runtime["same_run_writer_pairing_confirmed"])
        self.assertFalse(runtime["source_address_bytes_observed"])

    def test_formula_candidate_not_font_or_unicode_identity(self) -> None:
        status = self.report["status"]
        self.assertEqual(status["font_source_address_formula"], "static_candidate")
        self.assertFalse(status["font_identity_confirmed"])
        self.assertFalse(status["unicode_identity_confirmed"])
        self.assertFalse(status["translation_ready"])

    def test_serialized_report_has_no_source_code_units_or_bitmap(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("8251", serialized.lower())
        self.assertNotIn("824f", serialized.lower())
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("bitmap_bytes", serialized)
        self.assertNotIn("decoded_text", serialized)


if __name__ == "__main__":
    unittest.main()
