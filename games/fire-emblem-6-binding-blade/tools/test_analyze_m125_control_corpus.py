#!/usr/bin/env python3
"""Regression tests for the FE6 M1.25 control-structure corpus."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m125_control_corpus as corpus  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
SHORT_RUNTIME = Path("/private/tmp/afej-m119-natural-start-a-detail-released.json")
LONG_RUNTIME = Path("/private/tmp/afej-m119-natural-long-menu.json")


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM125ControlCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        paths = [path for path in (SHORT_RUNTIME, LONG_RUNTIME) if path.is_file()]
        cls.report = corpus.build_report(ROM_PATH, runtime_paths=paths)

    def test_bounded_records_keep_marker_structure_and_roundtrip(self) -> None:
        cohort = self.report["cohort"]
        self.assertEqual(cohort["start"], 3064)
        self.assertEqual(cohort["count_requested"], 32)
        self.assertEqual(cohort["count_extracted"], 32)
        self.assertEqual(cohort["count_failed"], 0)
        self.assertTrue(self.report["encode_guard"]["decode_encode_byte_identical"])
        self.assertEqual(self.report["encode_guard"]["scope"], "original_decoded_leaf_sequence_only")
        self.assertFalse(self.report["encode_guard"]["arbitrary_text_encode_enabled"])
        self.assertEqual(cohort["marker_total_counts"]["0x00"], 32)
        self.assertGreaterEqual(cohort["marker_record_counts"]["0x01"], 1)

    def test_static_branch_gate_is_exact_and_semantics_stay_opaque(self) -> None:
        gate = self.report["static_consumer_branch_gate"]
        self.assertEqual(gate["function_start"], "0x08098c00")
        self.assertEqual(gate["byte_read_instruction"], "0x08098c24: ldrb r0, [r6]")
        rows = {row["classification"]: row["target"] for row in gate["branch_rows"]}
        self.assertEqual(rows["byte_less_or_equal_one"], "0x08098c78")
        self.assertEqual(rows["control_handler_call"], "0x08003e60")
        self.assertFalse(gate["semantic_name_assigned"])
        self.assertFalse(self.report["runtime"]["control_0x01_semantic_name_assigned"])

    @unittest.skipUnless(
        SHORT_RUNTIME.is_file() and LONG_RUNTIME.is_file(),
        "ignored M1.19 natural receipts are not installed",
    )
    def test_runtime_read_and_branch_hits_are_not_over_paired(self) -> None:
        runtime = self.report["runtime"]
        self.assertEqual(runtime["route_count"], 2)
        self.assertEqual(runtime["dynamic_branch_source_pairing_route_count"], 0)
        self.assertFalse(runtime["cross_route_behavioral_contrast_observed"])
        for route in runtime["routes"]:
            markers = route["marker_reads"]
            self.assertTrue(any(row["marker"] == "0x01" for row in markers))
            self.assertTrue(any(
                row["static_target_for_read"] == "0x08098c78"
                for row in markers
                if row["marker"] == "0x01"
            ))
            self.assertGreaterEqual(
                route["consumer_branch_hit_counts"]["0x08098c78"],
                1,
            )
            self.assertFalse(route["semantic_name_assigned"])

    def test_serialized_report_is_hash_only_and_not_insertion_ready(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("Nintendo", serialized)
        self.assertFalse(self.report["status"]["translation_ready"])
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])
        self.assertFalse(self.report["encode_guard"]["rom_reinsert_enabled"])


if __name__ == "__main__":
    unittest.main()
