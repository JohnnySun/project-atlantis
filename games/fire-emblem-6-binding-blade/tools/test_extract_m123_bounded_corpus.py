#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import extract_m123_bounded_corpus as extractor  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"
RUNTIME_PATH = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")


class AfejM123BoundedCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = extractor.build_report(ROM_PATH, runtime_path=RUNTIME_PATH)

    def test_cohort_is_bounded_and_roundtrips(self):
        cohort = self.report["cohort"]
        self.assertEqual(cohort["start"], 3064)
        self.assertEqual(cohort["count_requested"], 32)
        self.assertEqual(cohort["count_extracted"], 32)
        self.assertEqual(cohort["count_failed"], 0)
        self.assertTrue(self.report["status"]["decode_encode_roundtrip"])

    def test_records_keep_provenance_markers_and_candidate_only_codepage(self):
        records = self.report["records"]
        self.assertEqual(records[0]["string_id"], "afej.ptr.3064")
        selected = next(row for row in records if row["table_index"] == 3087)
        self.assertEqual(selected["source_pointer"], "0x080f2256")
        self.assertTrue(selected["source_span_matches_next_entry"])
        self.assertTrue(selected["codepage_candidate"]["strict_decode"])
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertFalse(selected["raw_bytes_emitted"])

    def test_natural_runtime_receipt_matches_index_3087(self):
        runtime = self.report["runtime"]
        self.assertEqual(runtime["loader_receipt_count"], 1)
        receipt = runtime["loader_receipts"][0]
        self.assertEqual(receipt["table_index"], 3087)
        self.assertEqual(receipt["caller_callsite"], "0x08098b10")
        self.assertTrue(receipt["buffer_hash_matches_static"])
        self.assertEqual(runtime["scene_or_content_category"], "unknown_natural_route_context")

    def test_serialized_report_has_no_source_text_or_token_bytes(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("Nintendo", serialized)
        self.assertIn("translation_ready\": false", serialized)


if __name__ == "__main__":
    unittest.main()
