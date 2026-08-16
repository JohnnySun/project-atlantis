#!/usr/bin/env python3
"""Tests for bounded M1.27 accessor-to-reader evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m127_name_accessor as probe  # noqa: E402


class M127NameAccessorTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["raw_field_units_emitted"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_accessor_contract_is_separate_from_semantics(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(len(report["accessors"]), 3)
        self.assertEqual(report["accessors"][0]["record_stride"], 0x24)
        self.assertEqual(report["accessors"][2]["record_stride"], 0x20)
        self.assertEqual(report["tables"]["shared_0x24"]["record_count"], 0xD0)
        self.assertIn(
            "main_event_demon_skill_item_or_system_category",
            report["conclusions"]["unknown"],
        )

    def test_source_edge_has_fixed_copy_and_reader_contract(self) -> None:
        report = probe.static_report(bytes(0x100))
        edge = report["source_edge"]
        self.assertEqual(edge["copied_unit_count"], 8)
        self.assertEqual(edge["appended_terminator"], "0x0000")
        self.assertEqual(edge["reader_targets"], ["0x080ac334", "0x080ac3ac"])
        self.assertEqual(report["consumer"]["stack_buffer"]["offset"], 0x0C)

    def test_no_raw_or_decoded_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("glyph_bytes", report)
        self.assertNotIn("translation_ledger", report["scan_scope"])


if __name__ == "__main__":
    unittest.main()
