#!/usr/bin/env python3
"""Tests for the bounded M1.23 indirect-handler metadata contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m123_handler_dispatch as probe  # noqa: E402


class M123HandlerDispatchTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_command_scan"])
        self.assertFalse(report["scan_scope"]["raw_command_words_emitted"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")
        self.assertEqual(len(report["streams"]), 2)
        for stream in report["streams"]:
            self.assertEqual(stream["stream"]["target_command_count"], 0)

    def test_scope_is_two_streams_and_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["stream_count"], 2)
        self.assertEqual(report["scan_scope"]["callback_table_entry_count"], 25)
        self.assertEqual(report["scan_scope"]["callback_table_stride"], 8)
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["translation_ledger_created"])

    def test_no_payload_or_unicode_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("raw_words", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("unicode_identity", report)
        self.assertFalse(report["scan_scope"]["decoded_text_emitted"])

    def test_input_contract_does_not_emit_argument_values(self) -> None:
        report = probe.static_report(bytes(0x100))
        for stream in report["streams"]:
            contract = stream["stream"]["queue_entry_input_contract"]
            self.assertEqual(contract["stream_source_field"], "0x14")
            self.assertEqual(contract["stream_index_field"], "0x10")
            self.assertFalse(contract["source_is_text_pointer"])
            for command in stream["stream"]["target_commands"]:
                self.assertNotIn("distinct_domain_value", command.get("argument_metadata", {}))


if __name__ == "__main__":
    unittest.main()
