#!/usr/bin/env python3
"""Tests for the bounded M1.20 selector/source metadata contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m120_inline_dispatch as probe  # noqa: E402


class M120InlineDispatchTests(unittest.TestCase):
    def test_short_input_fails_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["caller"]["jump_table_load"]["literal_match"])
        self.assertEqual(report["inline_source_family"]["bounded_record_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_route_metadata_keeps_ids_separate_from_unicode(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["inline_source_family"]["stable_unicode_identity"])
        self.assertNotIn("decoded_text", report["routes"])
        self.assertNotIn("unit_values", report["inline_source_family"])

    def test_contract_shape_has_explicit_field_offsets(self) -> None:
        report = probe.static_report(bytes(0x100))
        caller = report["caller"]
        self.assertEqual(caller["primary_selector_field"]["offset"], 0x24)
        self.assertEqual(caller["secondary_selector_field"]["offset"], 0x14)
        self.assertEqual(caller["subselector_field"]["offset"], 0x0C)
        self.assertEqual(caller["jump_table"]["entry_count"], 5)


if __name__ == "__main__":
    unittest.main()
