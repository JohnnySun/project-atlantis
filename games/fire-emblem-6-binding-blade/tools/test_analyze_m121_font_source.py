#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import analyze_m121_font_source as provenance  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"


class AfejM121FontSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = provenance.build_report(ROM_PATH)

    def test_literals_and_composer_callers_are_static_provenance(self):
        static = self.report["static"]
        composer = static["composer"]
        values = {row["literal_value"] for row in composer["literal_provenance"]}
        self.assertIn("0x02000000", values)
        self.assertIn("0x06010000", values)
        self.assertIn("0x02002800", values)
        self.assertEqual(composer["direct_callers_of_entry"], ["0x08098f7a"])
        self.assertIn("0x08099462", composer["direct_callers_of_renderer"])
        self.assertFalse(static["raw_bytes_emitted"])

    def test_candidate_addresses_are_computed_not_literals(self):
        model = self.report["static"]["address_model"]
        self.assertEqual(model["source_candidate_offset"], "0x000020c0")
        self.assertEqual(model["destination_candidate_offset"], "0x00004000")
        self.assertFalse(model["candidate_addresses_are_single_literals"])
        self.assertFalse(model["unicode_identity_confirmed"])

    def test_runtime_pair_summary_keeps_writer_negative_separate(self):
        runtime = {
            "runtime": {
                "renderer_entries": [
                    {"source_register_r0": "0x020020c0", "destination_register_r1": "0x06014000"},
                    {"source_register_r0": "0x02002100", "destination_register_r1": "0x06014040"},
                ],
                "writer_receipts": [],
            }
        }
        result = provenance._runtime_report(runtime)
        self.assertEqual(result["address_pair_count"], 2)
        self.assertTrue(result["source_candidate_observed"])
        self.assertTrue(result["destination_candidate_observed"])
        self.assertEqual(result["source_hash_receipt_count"], 0)
        self.assertEqual(result["writer_receipt_count"], 0)
        self.assertFalse(result["same_run_writer_hash_pairing_confirmed"])

    def test_serialized_report_has_no_source_or_unicode_claim(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("unicode_identity_confirmed\": true", serialized)
        self.assertIn("raw_bytes_emitted\": false", serialized)


if __name__ == "__main__":
    unittest.main()
