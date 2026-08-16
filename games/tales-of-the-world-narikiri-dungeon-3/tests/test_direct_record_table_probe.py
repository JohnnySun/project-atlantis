#!/usr/bin/env python3
"""Tests for the fixed B3TJ direct-record table probe."""

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import direct_record_table_probe  # noqa: E402


class DirectRecordTableProbeTests(unittest.TestCase):
    def test_parser_normalizes_absolute_pointers(self):
        data = bytearray(0x80)
        values = [0x10, 0x20, 0x30]
        for index, target in enumerate(values):
            struct.pack_into("<I", data, 0x20 + index * 4, direct_record_table_probe.ROM_BASE + target)
        self.assertEqual(
            direct_record_table_probe.parse_table_targets(data, table_start=0x20, count=3),
            values,
        )

    def test_parser_rejects_non_rom_pointer(self):
        data = bytearray(0x40)
        struct.pack_into("<I", data, 0x10, 0x03000060)
        with self.assertRaises(ValueError):
            direct_record_table_probe.parse_table_targets(data, table_start=0x10, count=1)

    def test_summary_contains_metadata_not_source(self):
        class Row:
            region = "text-pool"
            raw_length = 4
            end = 0x24
            newline_units = 0
            control_units = 0

        result = direct_record_table_probe.summarize_targets([0x20], {0x20: Row()})
        self.assertEqual(result["strict_target_count"], 1)
        self.assertNotIn("text", result)
        self.assertNotIn("raw", result)


if __name__ == "__main__":
    unittest.main()
