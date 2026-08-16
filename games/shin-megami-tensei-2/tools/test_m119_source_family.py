#!/usr/bin/env python3
"""Tests for the bounded M1.19 reader-family metadata contract."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m119_source_family as probe  # noqa: E402


class M119SourceFamilyTests(unittest.TestCase):
    def test_zero_terminated_code_units_are_metadata_only(self) -> None:
        data = bytearray(0x80)
        pointer = probe.ROM_BASE + 0x20
        struct.pack_into("<HHH", data, pointer - probe.ROM_BASE, 0x0123, 0x0300, 0)
        result = probe._source_terminator_metadata(data, pointer, pointer + 0x20)
        self.assertEqual(result["termination"], "zero_0000")
        self.assertEqual(result["length"], 6)
        self.assertEqual(result["line_break_count"], 1)
        self.assertFalse(result["raw_source_emitted"])
        self.assertNotIn("unit_values", result)

    def test_inline_family_fails_closed_on_short_input(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertEqual(report["inline_source_family"]["bounded_pointer_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_report_contract_does_not_emit_source_or_decoded_text(self) -> None:
        report = probe.static_report(bytes(0x100))
        family = report["inline_source_family"]
        self.assertFalse(family["raw_source_emitted"])
        self.assertFalse(family["decoded_text_emitted"])
        self.assertNotIn("unit_values", family)
        self.assertNotIn("raw_bytes", family)
        self.assertFalse(report["inline_source_family"]["stable_unicode_identity"])


if __name__ == "__main__":
    unittest.main()
