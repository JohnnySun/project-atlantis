#!/usr/bin/env python3
"""Tests for the bounded, metadata-only B3TJ control-parser probe."""

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import control_parser_probe  # noqa: E402


class ControlParserProbeTests(unittest.TestCase):
    def test_dispatch_table_is_bounded_and_hashed(self):
        data = bytearray(0x200)
        base = 0x40
        values = [
            control_parser_probe.ROM_BASE + control_parser_probe.PARSER_CASE_START,
            control_parser_probe.ROM_BASE + control_parser_probe.PARSER_LOOP,
            control_parser_probe.ROM_BASE + control_parser_probe.PARSER_CASE_START + 2,
        ]
        values.extend([values[1]] * (control_parser_probe.PARSER_DISPATCH_COUNT - len(values)))
        struct.pack_into(f"<{len(values)}I", data, base, *values)
        result = control_parser_probe.parse_dispatch_table(
            bytes(data), table_offset=base, count=len(values)
        )
        self.assertEqual(result["entry_count"], len(values))
        self.assertEqual(result["unique_target_count"], 3)
        self.assertEqual(result["fallthrough_case_count"], len(values) - 2)
        self.assertNotIn("targets", result)
        self.assertNotIn("raw", result)

    def test_dispatch_table_rejects_escape(self):
        data = bytearray(0x80)
        struct.pack_into("<I", data, 0x20, control_parser_probe.ROM_BASE + 0x1000)
        with self.assertRaises(ValueError):
            control_parser_probe.parse_dispatch_table(data, table_offset=0x20, count=1)

    def test_parser_contract_constants_match_percent_range(self):
        self.assertEqual(control_parser_probe.PARSER_DISPATCH_COUNT, 0x54)
        self.assertEqual(
            control_parser_probe.PARSER_DISPATCH_MAX
            - control_parser_probe.PARSER_DISPATCH_MIN
            + 1,
            control_parser_probe.PARSER_DISPATCH_COUNT,
        )
        self.assertEqual(control_parser_probe.PARSER_CURSOR_GLOBAL, 0x03001588)
        self.assertEqual(control_parser_probe.WIDTH_HELPER_ENTRY, 0x2844)


if __name__ == "__main__":
    unittest.main()
