#!/usr/bin/env python3
"""Tests for the bounded M1.10 ROM table shape mapper."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m110_rom_table_shape as shape  # noqa: E402


class M110RomTableShapeTests(unittest.TestCase):
    def test_table_b_pair_run_stops_at_non_rom_pointer(self) -> None:
        rom = bytearray(0x100)
        base = shape.ROM_BASE + 0x20
        struct.pack_into("<II", rom, 0x20, 0x2217, shape.ROM_BASE + 0x80)
        struct.pack_into("<II", rom, 0x28, 0x2218, shape.ROM_BASE + 0x84)
        struct.pack_into("<II", rom, 0x30, 0x2219, 0x1234)
        old = shape.TABLE_B
        shape.TABLE_B = base
        try:
            result = shape._bounded_table_b(bytes(rom))
        finally:
            shape.TABLE_B = old
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(result["record_stride"], 8)
        self.assertEqual(result["first_break_offset"], "0x00000010")

    def test_table_a_reports_variable_sentinel_stream(self) -> None:
        rom = bytearray(0x200)
        base = shape.ROM_BASE + 0x20
        struct.pack_into("<IIII", rom, 0x20, shape.ROM_BASE + 0x80, 4, shape.SENTINEL, 7)
        old = shape.TABLE_A
        shape.TABLE_A = base
        try:
            result = shape._bounded_table_a(bytes(rom))
        finally:
            shape.TABLE_A = old
        self.assertEqual(result["shape"], "variable_word_stream_with_sentinels")
        self.assertEqual(result["sentinel_offsets"], ["0x00000008"])
        self.assertEqual(result["fixed_stride_status"], "not_established")

    def test_report_contract_is_metadata_only(self) -> None:
        report = {
            "scan_scope": {"glyph_pattern_scan": False, "raw_payload_emitted": False},
            "tables": {},
            "literal_readers": {},
            "bounded_target_windows": {},
        }
        serialized = shape.json.dumps(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("full_source", serialized)
        self.assertNotIn("translation_ledger", serialized)


if __name__ == "__main__":
    unittest.main()
