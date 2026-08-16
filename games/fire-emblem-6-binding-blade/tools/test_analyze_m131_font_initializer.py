#!/usr/bin/env python3
"""Regression tests for the FE6 M1.31 font initializer contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m131_font_initializer as initializer  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM131FontInitializerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = tuple(path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file())
        cls.report = initializer.build_report(ROM_PATH, paths)

    def test_initializer_and_dispatcher_provenance(self) -> None:
        static = self.report["static"]
        self.assertEqual(static["initializer_callsite"], "0x08098aee: bl #0x8099404")
        self.assertEqual(static["literal_values"]["source_asset"], "0x0837f478")
        self.assertEqual(static["literal_values"]["destination"], "0x02000000")
        self.assertEqual(static["literal_values"]["config_address"], "0x02002800")
        self.assertEqual(static["dispatcher_table_entry"], "0x0809dcf5")
        self.assertEqual(static["dispatcher_svc"], "0x0809dcf4: svc #0x11")
        self.assertEqual(static["dispatcher_table_index"], 3)

    def test_lz77_stream_is_bounded_and_expands_to_source_base_size(self) -> None:
        source = self.report["lz77_source"]
        self.assertEqual(source["header_class"], "0x00000010")
        self.assertEqual(source["expanded_size"], 0x2800)
        self.assertEqual(source["compressed_length"], 0x1A53)
        self.assertEqual(source["compressed_end_exclusive"], "0x08380ecb")
        self.assertEqual(source["next_asset_address"], "0x08380ecc")
        self.assertEqual(source["alignment_padding_length"], 1)
        self.assertEqual(source["compressed_span_sha256"], initializer.EXPECTED_COMPRESSED_SHA256)
        self.assertEqual(source["expanded_payload_sha256"], initializer.EXPECTED_EXPANDED_SHA256)

    def test_formula_bounds_correctly_retain_out_of_window_negative(self) -> None:
        bounds = self.report["source_formula_bounds"]
        self.assertEqual(bounds["bounds_valid_count"], 80)
        self.assertEqual(bounds["bounds_invalid_count"], 41)
        self.assertEqual(bounds["bounds_valid_input_min"], 0)
        self.assertEqual(bounds["bounds_valid_input_max"], 79)
        row_67 = next(row for row in bounds["rows"] if row["formula_input"] == 67)
        row_80 = next(row for row in bounds["rows"] if row["formula_input"] == 80)
        self.assertTrue(row_67["expanded_source_bounds_valid"])
        self.assertFalse(row_80["expanded_source_bounds_valid"])

    def test_natural_lookup_rows_fit_without_claiming_source_bytes(self) -> None:
        runtime = self.report["runtime"]
        if not runtime["route_count"]:
            self.skipTest("ignored natural runtime receipts are not installed")
        self.assertEqual(runtime["lookup_count_bounded"], 16)
        self.assertEqual(runtime["bounds_valid_count"], 16)
        self.assertFalse(runtime["source_address_bytes_observed"])

    def test_report_has_no_compressed_or_expanded_payload(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("compressed_bytes", serialized)
        self.assertNotIn("expanded_bytes", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertFalse(self.report["status"]["font_identity_confirmed"])
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertFalse(self.report["status"]["translation_ready"])


if __name__ == "__main__":
    unittest.main()
