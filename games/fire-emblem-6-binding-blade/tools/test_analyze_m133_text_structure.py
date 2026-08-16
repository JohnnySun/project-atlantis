#!/usr/bin/env python3
"""Regression tests for the FE6 M1.33 text-structure census."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m133_text_structure as structure  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM133TextStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = structure.build_report(ROM_PATH)

    def test_full_table_roundtrip_and_explicit_decoder_negative(self) -> None:
        table = self.report["table"]
        self.assertEqual(table["record_count"], 3342)
        self.assertEqual(table["strict_record_count"], 3203)
        self.assertEqual(table["failure_count"], 139)
        self.assertTrue(table["all_supported_source_spans_match_next_entry"])
        self.assertEqual(table["stable_sequence_sha256"], "1ba455e3054c374571f18968c2fcaa552dc25b6f05cea28b11d304158b52409b")
        self.assertEqual(table["failures"][0]["table_index"], 17)

    def test_width_and_terminator_structure_is_not_unicode_identity(self) -> None:
        widths = self.report["widths"]
        self.assertEqual(widths["two_byte_code_unit_total"], 227209)
        self.assertEqual(widths["one_byte_leaf_total"], 49742)
        self.assertEqual(widths["opaque_single_byte_total"], 26818)
        self.assertFalse(widths["unicode_identity_confirmed"])
        terminator = self.report["terminator"]
        self.assertEqual(terminator["records_with_last_single_byte_zero"], 3203)
        self.assertTrue(terminator["all_supported_records_end_with_single_byte_zero"])

    def test_marker_and_codepage_candidate_keep_negative_boundary(self) -> None:
        markers = self.report["markers"]["single_byte_token_occurrences"]
        self.assertEqual(markers, {"0x00": 3203, "0x01": 19585, "0x04": 136, "0xff": 0})
        candidate = self.report["codepage_candidate"]
        self.assertEqual(candidate["strict_record_count"], 3081)
        self.assertEqual(candidate["invalid_record_count"], 122)
        self.assertTrue(candidate["candidate_only"])
        self.assertEqual(self.report["status"]["control_semantics"], "opaque")

    def test_no_arbitrary_encode_or_raw_source_payload(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn('"source_bytes":', serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("unicode_text", serialized)
        self.assertFalse(self.report["round_trip"]["arbitrary_text_encode_enabled"])
        self.assertFalse(self.report["round_trip"]["rom_insertion_enabled"])
        self.assertIn("source_hash", serialized)


if __name__ == "__main__":
    unittest.main()
