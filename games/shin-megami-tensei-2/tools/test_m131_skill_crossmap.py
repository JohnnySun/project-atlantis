#!/usr/bin/env python3
"""Tests for bounded M1.31 skill-record evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m131_skill_crossmap as probe  # noqa: E402


class M131SkillCrossmapTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["category_crossmap"]["complete_codepage"])
        self.assertEqual(report["category_crossmap"]["prefix_identity_status"], "unconfirmed")
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_record_contract_is_bounded_and_separate(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["table_stride"], 0x1C)
        self.assertEqual(report["scan_scope"]["field_offset"], 0x06)
        self.assertEqual(report["category_crossmap"]["bounded_prefix_records"], 32)
        self.assertFalse(report["scan_scope"]["table_extent_proven"])
        self.assertIn(
            "full_skill_table_extent_and_category_spans_are_not_proven",
            report["conclusions"]["provisional"],
        )

    def test_render_edge_contract_is_explicit(self) -> None:
        report = probe.static_report(bytes(0x100))
        contract = report["static_provenance"]["consumer_contract"]
        self.assertEqual(contract["accessor_callsite"], "0x080bf606")
        self.assertEqual(contract["copied_unit_count_max"], 8)
        self.assertEqual(contract["field_termination"], "zero_0000_or_eight_units")
        self.assertEqual(contract["render_target"], "0x080ac218")

    def test_no_raw_or_decoded_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("glyph_bytes", report)
        self.assertNotIn("translation_ledger", report["scan_scope"])
        for anchor in report["anchors"]:
            self.assertFalse(anchor["raw_field_emitted"])
            self.assertFalse(anchor["raw_units_emitted"])
            self.assertFalse(anchor["decoded_text_emitted"])


if __name__ == "__main__":
    unittest.main()
