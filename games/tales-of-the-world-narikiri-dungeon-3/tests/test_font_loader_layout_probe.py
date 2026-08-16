#!/usr/bin/env python3
"""Offline tests for the bounded static font-loader geometry probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import font_loader_layout_probe  # noqa: E402


class FontLoaderLayoutProbeTests(unittest.TestCase):
    def test_output_geometry_is_four_bounded_groups(self):
        row = font_loader_layout_probe.output_geometry(0x02001000)
        self.assertEqual(row["group_count"], 4)
        self.assertEqual(row["group_bytes"], 0x20)
        self.assertEqual(row["total_bytes"], 0x80)
        self.assertEqual(row["group_addresses"], [
            "0x02001000", "0x02001020", "0x02001040", "0x02001060"
        ])
        self.assertNotIn("bytes", row)

    def test_asset_geometry_keeps_two_half_offsets(self):
        row = font_loader_layout_probe.asset_read_geometry(0x080DDCC4)
        self.assertEqual(row["asset_bytes"], 0x20)
        self.assertEqual(row["half_bytes"], 0x10)
        self.assertEqual(row["half_offsets"], ["0x00", "0x10"])
        self.assertNotIn("raw", row)

    def test_addresses_are_32_bit_bounded(self):
        with self.assertRaises(ValueError):
            font_loader_layout_probe.output_geometry(-1)
        with self.assertRaises(ValueError):
            font_loader_layout_probe.asset_read_geometry(0x100000000)


if __name__ == "__main__":
    unittest.main()
