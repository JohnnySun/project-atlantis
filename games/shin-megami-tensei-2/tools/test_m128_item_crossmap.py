#!/usr/bin/env python3
"""Tests for bounded M1.28 item cross-map evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m128_item_crossmap as probe  # noqa: E402


class M128ItemCrossmapTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["raw_units_emitted"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")
        self.assertEqual(report["category_crossmap"]["consecutive_identity_matches"], 0)

    def test_category_and_identity_gates_are_separate(self) -> None:
        report = probe.static_report(bytes(0x100))
        crossmap = report["category_crossmap"]
        self.assertEqual(crossmap["candidate_category"], "item")
        self.assertEqual(crossmap["stable_id_formula"], "m28-item-record-{ordinal:04d}")
        self.assertFalse(crossmap["complete_codepage"])
        self.assertEqual(crossmap["full_table_category_status"], "provisional")

    def test_no_source_or_decoded_payload_is_reported(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("raw_source", report)
        for anchor in report["anchors"]:
            self.assertNotIn("observed_text", anchor)
            self.assertFalse(anchor["raw_field_emitted"])
            self.assertFalse(anchor["raw_units_emitted"])
            self.assertFalse(anchor["decoded_text_emitted"])


if __name__ == "__main__":
    unittest.main()
