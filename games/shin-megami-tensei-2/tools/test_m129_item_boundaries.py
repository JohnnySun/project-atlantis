#!/usr/bin/env python3
"""Tests for bounded M1.29 item boundary evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m129_item_boundaries as probe  # noqa: E402


class M129ItemBoundariesTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["subcategory_crossmap"]["boundary_anchor_matches"], 0)
        self.assertFalse(report["scan_scope"]["raw_units_emitted"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_boundary_family_does_not_claim_full_table(self) -> None:
        report = probe.static_report(bytes(0x100))
        crossmap = report["subcategory_crossmap"]
        self.assertEqual(crossmap["candidate_family"], "item_equipment")
        self.assertEqual(crossmap["boundary_anchor_count"], 3)
        self.assertEqual(crossmap["full_table_category_status"], "provisional")
        self.assertFalse(crossmap["secondary_table_decoded"])

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
