#!/usr/bin/env python3

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from render_oam import composite_oam  # noqa: E402
from render_vram import (  # noqa: E402
    bgr15_to_rgb,
    decode_tile_4bpp,
    render_bg_tilemap,
    render_mode3,
)


class RendererTest(unittest.TestCase):
    def test_color_and_4bpp_nibble_order(self):
        self.assertEqual(bgr15_to_rgb(0x001F), (255, 0, 0))
        tile = decode_tile_4bpp(bytes([0x21] + [0] * 31), 0)
        self.assertEqual(tile[0][:2], [1, 2])

    def test_tilemap_horizontal_flip(self):
        vram = bytearray(0x100)
        vram[0] = 0x01
        struct.pack_into("<H", vram, 0x80, 0x0400)
        palette = [(index, 0, 0) for index in range(256)]
        pixels = render_bg_tilemap(
            bytes(vram), palette, charbase=0, screenbase=0x80,
            bpp=4, map_width=1, map_height=1,
        )
        self.assertEqual(pixels[0][7], (1, 0, 0))
        self.assertEqual(pixels[0][0], (0, 0, 0))

    def test_mode3(self):
        pixels = render_mode3(struct.pack("<HH", 0x001F, 0x03E0), width=2, height=1)
        self.assertEqual(pixels, [[(255, 0, 0), (0, 255, 0)]])

    def test_oam_1d_non_affine_sprite(self):
        vram = bytearray(0x10020)
        vram[0x10000] = 0x01
        oam = bytearray(b"\x00" * 0x400)
        # Hide all entries, then enable one 8x8 OBJ at (0,0), tile 0.
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0, 0, 0)
        palette = [(index, index, index) for index in range(256)]
        pixels, count = composite_oam(bytes(vram), palette, bytes(oam))
        self.assertEqual(count, 1)
        self.assertEqual(pixels[0][0], (1, 1, 1))
        self.assertEqual(pixels[0][1], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
