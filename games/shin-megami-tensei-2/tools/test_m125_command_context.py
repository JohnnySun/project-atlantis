#!/usr/bin/env python3
"""Tests for the bounded M1.25 command/context contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m125_command_context as probe  # noqa: E402


class M125CommandContextTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["raw_command_words_emitted"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertEqual(report["command_stream"]["target_command_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_static_scope_never_claims_identity(self) -> None:
        report = probe.static_report(bytes(0x100))
        edge = report["context"]["source_table_reader_edge"]
        self.assertFalse(edge["selected_record_known_at_static_time"])
        self.assertFalse(edge["glyph_identity_confirmed"])
        self.assertFalse(edge["unicode_identity_confirmed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])

    def test_contract_constants_are_named_and_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["callback"]["table"]["entry_index"], 0x13)
        self.assertEqual(report["queue"]["entry_contract"]["staged_function_field"], "0x00000020")
        self.assertEqual(
            report["context"]["source_table_reader_edge"]["record_stride"], 0x08
        )
        self.assertEqual(
            report["context"]["source_table_reader_edge"]["pointer_field_offset"],
            0x04,
        )

    def test_no_raw_or_decoded_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("glyph_bytes", report)
        self.assertNotIn("source_bytes", report["context"])


if __name__ == "__main__":
    unittest.main()
