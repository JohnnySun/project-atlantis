#!/usr/bin/env python3
"""Tests for the bounded M1.24 source-table metadata contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m124_source_table as probe  # noqa: E402


class M124SourceTableTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["record_count"], 28)
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertFalse(report["scan_scope"]["decoded_text_emitted"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_addressing_contract_is_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        contract = report["source_table"]["addressing_contract"]
        self.assertEqual(report["scan_scope"]["record_stride"], 0x08)
        self.assertEqual(report["scan_scope"]["pointer_field_offset"], 0x04)
        self.assertEqual(len(report["source_table"]["records"]), 28)
        self.assertEqual(report["source_table"]["records"][0]["stable_id"], "m18-record-0001")

    def test_control_and_unicode_gates_remain_separate(self) -> None:
        report = probe.static_report(bytes(0x100))
        control = report["source_table"]["control_contract"]
        self.assertEqual(control["line_break"], "0x00000300")
        self.assertEqual(control["terminator"], "0x00000301")
        self.assertFalse(control["unicode_identity_confirmed"])
        self.assertFalse(control["width_rule_confirmed"])

    def test_no_raw_or_decoded_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        for record in report["source_table"]["records"]:
            self.assertNotIn("source_bytes", record["source"])


if __name__ == "__main__":
    unittest.main()
