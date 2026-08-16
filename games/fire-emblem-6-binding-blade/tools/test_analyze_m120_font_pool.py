#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import analyze_m120_font_pool as census  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"


class AfejM120FontPoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = census.build_report(ROM_PATH)

    def test_two_byte_map_census_is_bounded_and_hash_only(self):
        mapping = self.report["static"]["map"]
        self.assertEqual(mapping["map_base"], "0x08691644")
        self.assertEqual(mapping["entry_count"], 121)
        self.assertEqual(mapping["terminator_address"], "0x08691736")
        self.assertEqual(mapping["next_data_address"], "0x08691738")
        self.assertEqual(mapping["span_length"], 244)
        self.assertEqual(mapping["span_sha256"], "c98d4a7d0b187d82acd29c2cae4524f3f7322dda3ec12aa15644fc0f006efa8e")
        self.assertFalse(mapping["raw_bytes_emitted"])

    def test_wrapper_literal_and_index_window_remain_opaque(self):
        wrapper = self.report["static"]["lookup_wrapper"]
        indexed = self.report["static"]["indexed_byte_window"]
        self.assertEqual(wrapper["literal_value"], "0x086916e5")
        self.assertTrue(wrapper["literal_matches_indexed_window"])
        self.assertEqual(indexed["length"], 121)
        self.assertEqual(indexed["min_value"], 0)
        self.assertEqual(indexed["max_value"], 15)
        self.assertFalse(wrapper["semantic_name_assigned"])

    def test_runtime_census_derives_stride_without_raw_dump(self):
        runtime_report = {
            "runtime": {
                "renderer_entries": [
                    {"source_register_r0": "0x020020c0", "destination_register_r1": "0x06014000", "source_hash_window": {"sha256": "a"}},
                    {"source_register_r0": "0x02002100", "destination_register_r1": "0x06014040", "source_hash_window": {"sha256": "b"}},
                    {"source_register_r0": "0x02002140", "destination_register_r1": "0x06014080", "source_hash_window": {"sha256": "c"}},
                ],
                "composer_receipts": [{"source_register_r0": "0x43"}],
                "writer_receipts": [],
            }
        }
        result = census._runtime_census(runtime_report)
        self.assertEqual(result["renderer_entry_count"], 3)
        self.assertEqual(result["source_stride_values"], ["0x00000040"])
        self.assertEqual(result["destination_stride_values"], ["0x00000040"])
        self.assertTrue(result["source_020020c0_observed"])
        self.assertTrue(result["destination_06014000_observed"])
        self.assertEqual(result["source_hash_receipt_count"], 3)
        self.assertFalse(result["raw_bytes_emitted"])

    def test_output_contains_no_source_bytes(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("82a0", serialized)
        self.assertNotIn("raw_bytes", serialized.replace("raw_bytes_emitted", ""))


if __name__ == "__main__":
    unittest.main()
