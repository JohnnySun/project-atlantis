#!/usr/bin/env python3
"""Tests for the bounded M1.22 state-route metadata contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m122_state_routes as probe  # noqa: E402


class M122StateRoutesTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertFalse(report["handlers"]["0x080ce760"]["state_load"]["contract_match"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_family_size_and_field_offset_are_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["family"]["pointer_count"], 15)
        self.assertEqual(report["scan_scope"]["per_pointer_probe_limit"], 0x100)
        for handler in report["handlers"].values():
            self.assertEqual(handler["state_field_offset"], 0x1E)

    def test_route_contract_has_no_unicode_or_raw_payload(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["family"]["unicode_identity_confirmed"])
        self.assertNotIn("unit_values", report["family"])
        self.assertNotIn("raw_bytes", report["family"])


if __name__ == "__main__":
    unittest.main()
