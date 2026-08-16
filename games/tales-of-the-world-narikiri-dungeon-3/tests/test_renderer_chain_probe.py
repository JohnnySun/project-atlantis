#!/usr/bin/env python3
"""Tests for the bounded B3TJ parser-to-renderer static chain."""

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import renderer_chain_probe  # noqa: E402


class RendererChainProbeTests(unittest.TestCase):
    def test_double_byte_index_follows_reviewed_arithmetic(self):
        self.assertEqual(renderer_chain_probe.double_byte_index(0x82, 0xA0), 0x120)
        self.assertEqual(renderer_chain_probe.double_byte_index(0x88, 0x40), 0x240)
        with self.assertRaises(ValueError):
            renderer_chain_probe.double_byte_index(0x80, 0x40)

    def test_tilemap_address_is_bounded_formula(self):
        self.assertEqual(renderer_chain_probe.tilemap_address(0, 0), 0x03000060)
        self.assertEqual(renderer_chain_probe.tilemap_address(3, 2), 0x030000E6)

    def test_thumb_bl_decoder_rejects_non_call_bytes(self):
        self.assertIsNone(renderer_chain_probe.decode_thumb_bl(b"\x00\x00\x00\x00", 0))
        self.assertEqual(renderer_chain_probe.PARSER_ENTRY, 0x080025CC)
        self.assertEqual(renderer_chain_probe.FONT_ASSET_STRIDE, 0x20)


if __name__ == "__main__":
    unittest.main()
