#!/usr/bin/env python3
"""Tests for bounded M1.30 demon-record evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m130_demon_crossmap as probe  # noqa: E402


class M130DemonCrossmapTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["category_crossmap"]["complete_codepage"])
        self.assertEqual(report["category_crossmap"]["prefix_identity_status"], "unconfirmed")
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_record_contract_is_separate_from_category_extent(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["table_stride"], 0x60)
        self.assertEqual(report["scan_scope"]["field_offset"], 0x22)
        self.assertEqual(report["category_crossmap"]["bounded_prefix_records"], 16)
        self.assertFalse(report["scan_scope"]["table_extent_proven"])
        self.assertIn(
            "full_demon_table_extent_and_category_spans_are_not_proven",
            report["conclusions"]["provisional"],
        )

    def test_reader_edge_contract_is_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        contract = report["static_provenance"]["consumer_contract"]
        self.assertEqual(contract["object_id_array_offset"], 0x26)
        self.assertEqual(contract["slot_count"], 5)
        self.assertEqual(contract["copied_unit_count"], 8)
        self.assertEqual(contract["stack_buffer_offset"], 0x0C)
        self.assertEqual(contract["appended_terminator"], "0x0000")

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
