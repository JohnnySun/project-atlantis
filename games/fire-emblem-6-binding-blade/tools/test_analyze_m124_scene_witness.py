#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import analyze_m124_scene_witness as witness  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"
SHORT = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file() and SHORT.is_file() and LONG.is_file(), "reviewed local runtime receipts are not installed")
class AfejM124SceneWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = witness.build_report(ROM_PATH, [SHORT, LONG])

    def test_routes_keep_natural_and_caller_provenance_separate(self):
        routes = self.report["routes"]
        self.assertEqual(routes[0]["loader_indices"], [3087])
        self.assertEqual(routes[1]["loader_indices"], [3087, 2678, 2679])
        self.assertEqual(routes[0]["caller_callsites"], ["0x08098b10"])
        self.assertIn("0x08009252", routes[1]["caller_callsites"])
        self.assertTrue(all(route["natural_reachability"] for route in routes))

    def test_same_table_hash_join_and_runtime_static_equality(self):
        table = self.report["table"]
        comparison = self.report["comparison"]
        self.assertEqual(table["domain"], "[0, 3342)")
        self.assertEqual(table["observed_indices"], [2678, 2679, 3087])
        self.assertTrue(comparison["same_proven_table_domain"])
        self.assertTrue(comparison["different_index_sets_observed"])
        self.assertEqual(comparison["shared_indices"], [3087])
        self.assertEqual(comparison["shared_caller_families"], ["0x08098b10"])
        self.assertEqual(self.report["comparison"]["runtime_static_hash_match_count"], 3)
        self.assertEqual(self.report["comparison"]["runtime_static_hash_mismatch_indices"], [2679])
        self.assertFalse(self.report["comparison"]["hash_mismatch_cause_assigned"])

    def test_scene_and_control_semantics_remain_unknown(self):
        self.assertFalse(self.report["comparison"]["scene_classification_proven"])
        self.assertFalse(self.report["comparison"]["control_0x01_semantic_name_assigned"])
        self.assertEqual(self.report["status"]["scene_or_content_category"], "unknown")
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])

    def test_serialized_report_has_no_source_tokens_or_text(self):
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("Nintendo", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertIn("raw_bytes_emitted\": false", serialized)


if __name__ == "__main__":
    unittest.main()
