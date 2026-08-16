#!/usr/bin/env python3
"""Offline tests for the bounded B3TJ consumer probe."""

import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import consumer_probe  # noqa: E402


class ConsumerProbeTests(unittest.TestCase):
    def test_active_low_key_values(self):
        self.assertEqual(consumer_probe.key_value("none"), 0x03FF)
        self.assertEqual(consumer_probe.key_value("start"), 0x03F7)
        self.assertEqual(consumer_probe.key_value("a"), 0x03FE)

    def test_sequence_parser(self):
        self.assertEqual(
            consumer_probe.parse_sequence("start:2,none:3,a:1"),
            [("start", 2), ("none", 3), ("a", 1)],
        )
        with self.assertRaises(ValueError):
            consumer_probe.parse_sequence("bad:1")

    def test_render_parameters_follow_gba_register_bits(self):
        params = consumer_probe.render_parameters(0x1260, 0xD001)
        self.assertEqual(params["bg1_charbase"], 0)
        self.assertEqual(params["bg1_screenbase"], 0x8000)
        self.assertEqual(params["bg1_bpp"], 4)
        self.assertEqual(params["obj_mapping"], "1d")

    def test_exact_tile_match_requires_nonzero_32_byte_tile(self):
        rom = b"\x00" * 16 + bytes(range(32)) + b"\x00" * 16
        vram = b"\x00" * 32 + bytes(range(32))
        rows = consumer_probe.exact_tile_matches(rom, vram)
        self.assertEqual(rows[0]["vram_offset"], "0x00020")
        self.assertEqual(rows[0]["rom_offsets"], ["0x000010"])


if __name__ == "__main__":
    unittest.main()
