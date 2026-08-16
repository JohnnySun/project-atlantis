#!/usr/bin/env python3
"""Regression tests for the FE6 M1.10 hash-only table census."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/analyze_m110_corpus.py"

spec = importlib.util.spec_from_file_location("fe6_m110_census", TOOL_PATH)
assert spec and spec.loader
census_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(census_tool)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM110CensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.census = census_tool.build_census(census_tool.load_rom(ROM_PATH))

    def test_full_proven_table_and_round_trip(self) -> None:
        table = self.census["table"]
        round_trip = self.census["round_trip"]
        self.assertEqual(table["record_count"], 3342)
        self.assertEqual(table["strictly_supported_record_count"], 3203)
        self.assertEqual(table["decoder_failure_count"], 139)
        self.assertTrue(table["all_source_spans_match_next_entry"])
        self.assertEqual(
            round_trip,
            {
                "decode_encode_byte_identical": 3203,
                "records": 3203,
                "unsupported_records": 139,
            },
        )
        self.assertEqual(self.census["decoder_failures"][0]["table_index"], 17)
        self.assertEqual(
            self.census["decoder_failures"][0]["failure_kind"],
            "decoder_buffer_limit_no_terminator",
        )

    def test_census_is_hash_only_not_source_or_code_units(self) -> None:
        self.assertFalse(self.census["semantic_boundary"]["source_bytes_emitted"])
        self.assertFalse(self.census["semantic_boundary"]["code_unit_bytes_emitted"])
        row = self.census["records"][0]
        self.assertNotIn("tokens", row)
        self.assertNotIn("bytes_hex", row)
        self.assertIn("source_hash", row)
        self.assertIn("output_hash", row)

    def test_markers_remain_structural(self) -> None:
        markers = self.census["marker_records"]
        self.assertGreater(markers["0x00"], 0)
        self.assertIn("0x01", markers)
        self.assertIn("0x04", markers)
        self.assertIn("0xff", markers)
        self.assertEqual(
            self.census["semantic_boundary"]["control_marker_semantics"],
            "opaque",
        )


if __name__ == "__main__":
    unittest.main()
