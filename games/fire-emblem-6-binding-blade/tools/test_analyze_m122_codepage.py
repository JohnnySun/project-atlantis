#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import analyze_m122_codepage as candidate  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"
CORPUS_PATH = Path(__file__).resolve().parents[1] / "research" / "afej-decoded.jsonl"
RUNTIME_PATH = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")


class AfejM122CodepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = candidate.build_report(ROM_PATH, CORPUS_PATH, RUNTIME_PATH)

    def test_map_is_strict_shift_jis_candidate_not_confirmation(self):
        codepage = self.report["map"]["codepage_candidate"]
        self.assertEqual(codepage["entry_count"], 121)
        self.assertEqual(codepage["strictly_decodable_count"], 121)
        self.assertEqual(codepage["invalid_entry_count"], 0)
        self.assertTrue(codepage["candidate_only"])
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])

    def test_runtime_map_and_glyph_correspondence_is_bounded(self):
        runtime = self.report["runtime"]
        self.assertEqual(runtime["lookup_receipt_count_bounded"], 8)
        self.assertEqual(runtime["glyph_field_receipt_count_bounded"], 8)
        self.assertEqual(runtime["lookup_map_pair_and_glyph_equal_count"], 8)
        self.assertEqual(runtime["glyph_field_map_pair_and_glyph_equal_count"], 8)
        self.assertTrue(runtime["natural_runtime_map_correspondence"])
        self.assertTrue(runtime["natural_runtime_glyph_correspondence"])
        self.assertEqual(runtime["natural_runtime_corpus_prefix_match_count"], 4)
        self.assertTrue(runtime["natural_runtime_corpus_prefix_observed"])

    def test_index_3087_corpus_is_strictly_shift_jis_candidate(self):
        corpus = self.report["corpus"]
        self.assertEqual(corpus["table_index"], 3087)
        self.assertEqual(corpus["code_unit_count"], 21)
        self.assertEqual(corpus["opaque_control_count"], 1)
        self.assertTrue(corpus["strict_shift_jis_decode"])
        self.assertTrue(corpus["candidate_only"])

    def test_serialized_report_contains_hashes_not_source_text(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("8251", serialized.lower())
        self.assertNotIn("nintendo", serialized.lower())
        self.assertNotIn("source_bytes", serialized)
        self.assertIn("translation_ready\": false", serialized)


if __name__ == "__main__":
    unittest.main()
