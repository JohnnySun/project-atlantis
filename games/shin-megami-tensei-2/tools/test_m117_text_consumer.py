#!/usr/bin/env python3
"""Tests for the bounded M1.17 text-consumer metadata contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m117_text_consumer as probe  # noqa: E402


class M117TextConsumerTests(unittest.TestCase):
    def test_bounded_table_reports_metadata_without_source_bytes(self) -> None:
        data = bytearray(0x200)
        # Map the synthetic byte array at the ROM base for the helper's
        # bounded table address, without asserting or emitting the bytes.
        table_offset = probe.TEXT_TABLE_BASE - probe.ROM_BASE
        data.extend(b"\x00" * (table_offset + 37 * probe.TEXT_TABLE_STRIDE - len(data)))
        for index in range(probe.TEXT_TABLE_ASCII_RECORDS):
            start = table_offset + index * probe.TEXT_TABLE_STRIDE
            data[start : start + probe.TEXT_TABLE_STRIDE] = b"A  \x00\x00\x00\x00\x00\x00\x00"
        report = probe.bounded_table_metadata(bytes(data))
        self.assertEqual(report["stride"], 0x0A)
        self.assertEqual(report["bounded_record_count"], 37)
        self.assertEqual(report["available_record_count"], 37)
        self.assertEqual(report["validated_ascii_padding_record_count"], 37)
        self.assertFalse(report["raw_bytes_emitted"])
        self.assertFalse(report["decoded_text_emitted"])
        self.assertNotIn("A  ", str(report))

    def test_table_metadata_has_no_translation_source_contract(self) -> None:
        report = probe.bounded_table_metadata(bytes(0x200))
        serialized = str(report)
        self.assertIn("raw_bytes_emitted", serialized)
        self.assertIn("decoded_text_emitted", serialized)
        self.assertNotIn("record_bytes", serialized)
        self.assertNotIn("translation_ledger", serialized)

    def test_static_report_scope_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertFalse(report["scan_scope"]["translation_ledger_created"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")


if __name__ == "__main__":
    unittest.main()
