#!/usr/bin/env python3
"""Tests for the bounded M1.21 source inventory contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m121_source_inventory as probe  # noqa: E402


class M121SourceInventoryTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertEqual(report["summary"]["caller_family_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_inventory_contract_has_no_raw_payload_keys(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertFalse(report["scan_scope"]["decoded_text_emitted"])
        self.assertNotIn("unit_values", report["summary"])
        self.assertNotIn("raw_bytes", report["summary"])

    def test_pointer_probe_limit_is_explicit(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["per_pointer_probe_limit"], 0x100)
        self.assertEqual(report["scan_scope"]["direct_caller_cap"], probe.MAX_DIRECT_CALLERS)


if __name__ == "__main__":
    unittest.main()
