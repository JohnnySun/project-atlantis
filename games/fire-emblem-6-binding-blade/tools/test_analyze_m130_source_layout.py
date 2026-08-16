#!/usr/bin/env python3
"""Regression tests for the FE6 M1.30 source-layout/code-unit gate."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m130_source_layout as layout  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM130SourceLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = tuple(path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file())
        cls.report = layout.build_report(ROM_PATH, runtime_paths=paths)

    def test_formula_layout_has_no_collisions_and_expected_stride_gaps(self) -> None:
        static = self.report["static"]
        self.assertEqual(static["map_entry_count"], 121)
        self.assertEqual(static["map_terminator"], "0x08691736")
        source_layout = static["layout"]
        self.assertEqual(source_layout["unique_source_address_count"], 121)
        self.assertEqual(source_layout["source_address_collision_group_count"], 0)
        self.assertEqual(
            source_layout["consecutive_source_offset_stride_counts"],
            {"0x00000040": 113, "0x00000440": 7},
        )
        self.assertEqual(source_layout["formula_bank_count"], 8)
        self.assertEqual(
            [bank["slot_count"] for bank in source_layout["formula_banks"]],
            [16, 16, 16, 16, 16, 16, 16, 9],
        )

    def test_bounded_windows_are_roundtrippable_shift_jis_candidates_only(self) -> None:
        gate = self.report["code_unit_gate"]
        self.assertEqual(gate["unique_record_count"], 32)
        self.assertEqual(gate["strict_shift_jis_candidate_record_count"], 32)
        self.assertEqual(gate["decode_encode_byte_identical_count"], 32)
        self.assertEqual(gate["total_code_unit_count"], 938)
        self.assertTrue(gate["strict_shift_jis_candidate_all_records"])
        self.assertTrue(gate["decode_encode_all_records"])
        self.assertFalse(gate["unicode_identity_confirmed"])
        self.assertFalse(gate["translation_ready"])
        self.assertEqual(
            gate["windows"][0]["marker_occurrence_counts"],
            {"0x00": 16, "0x01": 31, "0x04": 1, "0xff": 0},
        )
        self.assertEqual(
            gate["windows"][1]["marker_occurrence_counts"],
            {"0x00": 16, "0x01": 9, "0x04": 0, "0xff": 0},
        )

    def test_runtime_rows_join_formula_without_claiming_font_bytes(self) -> None:
        runtime = self.report["runtime"]
        if not runtime["route_count"]:
            self.skipTest("ignored natural runtime receipts are not installed")
        self.assertEqual(runtime["lookup_count_bounded"], 16)
        self.assertEqual(runtime["formula_resolved_count"], 16)
        self.assertFalse(runtime["source_address_bytes_observed"])
        self.assertFalse(runtime["same_run_writer_pairing_confirmed"])
        observed = [row for route in runtime["routes"] for row in route["observed"]]
        by_index = {row["map_index"]: row for row in observed}
        self.assertEqual(by_index[67]["source_formula_address"], "0x020020c0")
        self.assertEqual(by_index[68]["source_formula_address"], "0x02002100")

    def test_serialized_report_has_no_raw_source_or_decoded_text(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("bitmap_bytes", serialized)
        self.assertIn("translation_ready\": false", serialized)


if __name__ == "__main__":
    unittest.main()
