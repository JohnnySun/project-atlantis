#!/usr/bin/env python3
"""Tests for the bounded static record-to-asset arithmetic probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from static_record_font_path_probe import (  # noqa: E402
    StaticPathReject,
    asset_address,
    double_byte_index,
    _halfwidth_lookup_location,
)


class StaticRecordFontPathProbeTests(unittest.TestCase):
    def test_reviewed_double_byte_arithmetic(self):
        self.assertEqual(double_byte_index(0x83, 0x8C), 0x01CC)
        self.assertEqual(double_byte_index(0x83, 0x78), 0x01B8)
        self.assertEqual(double_byte_index(0xE0, 0x40), 0x4440)

    def test_halfwidth_lookup_handles_combining_dakuten_shape(self):
        self.assertEqual(_halfwidth_lookup_location(0xDA, 0xCD), (0x741D84, 0x39))
        self.assertEqual(_halfwidth_lookup_location(0xCD, 0xDE), (0x741D88, 0x17))
        self.assertEqual(_halfwidth_lookup_location(0xDE, 0xD9), (0x741D84, 0x3D))

    def test_invalid_units_and_asset_bounds_fail_closed(self):
        with self.assertRaises(StaticPathReject):
            double_byte_index(0x80, 0x40)
        with self.assertRaises(StaticPathReject):
            double_byte_index(0xDA, 0x7F)
        self.assertEqual(asset_address(0x404D), 0x0815E664)
        with self.assertRaises(StaticPathReject):
            asset_address(0x100000)


if __name__ == "__main__":
    unittest.main()
