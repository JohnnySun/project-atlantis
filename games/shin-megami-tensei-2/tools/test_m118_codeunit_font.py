#!/usr/bin/env python3
"""Tests for the bounded M1.18 code-unit/font metadata contract."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m118_codeunit_font as probe  # noqa: E402


class M118CodeUnitFontTests(unittest.TestCase):
    def test_font_address_expression_is_bounded_and_reversible(self) -> None:
        bank = 0x081C3978
        address = probe.font_source_address(0x0102, bank)
        self.assertEqual(address, bank + 0x40)
        self.assertEqual(
            probe.font_source_address(0x0000, bank),
            bank,
        )

    def test_source_record_reports_controls_without_source_bytes(self) -> None:
        data = bytearray(0x2000)
        pointer = probe.ROM_BASE + 0x100
        raw = struct.pack("<HHH", 0x00E0, probe.CODE_UNIT_LINE_BREAK, probe.CODE_UNIT_TERMINATOR)
        offset = pointer - probe.ROM_BASE
        data[offset : offset + len(raw)] = raw
        record_address = probe.SOURCE_TABLE_BASE - probe.ROM_BASE
        # Exercise the helper with a small record-shaped synthetic ROM window
        # by placing the table at its actual mapped offset in a larger buffer.
        large = bytearray(record_address + 0x100)
        large[offset : offset + len(raw)] = raw
        struct.pack_into("<I", large, record_address, 1)
        struct.pack_into("<I", large, record_address + 4, pointer)
        record = probe._source_record_metadata(bytes(large), 0, pointer + 0x20)
        source = record["source"]
        self.assertIsInstance(source, dict)
        self.assertEqual(source["termination"], "terminator_0301")
        self.assertEqual(source["line_break_count"], 1)
        self.assertFalse(source["raw_source_emitted"])
        self.assertNotIn("00e0", str(record))

    def test_bounded_table_has_stable_ids_and_no_decoded_text(self) -> None:
        table_offset = probe.SOURCE_TABLE_BASE - probe.ROM_BASE
        source_base = 0x1000
        size = table_offset + probe.SOURCE_TABLE_RECORD_COUNT * 8 + 0x200
        data = bytearray(size)
        for index in range(probe.SOURCE_TABLE_RECORD_COUNT):
            pointer = probe.ROM_BASE + source_base + index * 0x20
            source_offset = pointer - probe.ROM_BASE
            raw = struct.pack("<HH", 0x0100 + index, probe.CODE_UNIT_TERMINATOR)
            data[source_offset : source_offset + len(raw)] = raw
            struct.pack_into("<I", data, table_offset + index * 8, index + 1)
            struct.pack_into("<I", data, table_offset + index * 8 + 4, pointer)
        report = probe.bounded_source_table_metadata(bytes(data))
        self.assertEqual(report["bounded_record_count"], 28)
        self.assertEqual(report["available_record_count"], 28)
        self.assertTrue(report["record_id_contiguous_1_to_28"])
        self.assertEqual(report["source_terminated_record_count"], 28)
        self.assertFalse(report["raw_source_emitted"])
        self.assertNotIn("unit_values", report["records"][0]["source"])
        self.assertNotIn("raw_bytes", report["records"][0]["source"])

    def test_static_report_is_fail_closed_on_short_input(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["full_rom_string_scan"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertFalse(report["scan_scope"]["translation_ledger_created"])
        self.assertEqual(report["source_table"]["available_record_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")


if __name__ == "__main__":
    unittest.main()
