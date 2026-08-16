#!/usr/bin/env python3
"""Pure tests for the metadata-only M20 glyph/screen cross-check."""

from __future__ import annotations

import unittest

from m20_glyph_screen_cross_probe import (
    TARGETS,
    gba_4bpp_ink_mask,
    screen_entry,
    tile_id_from_address,
    tile_metadata,
)


class M20GlyphScreenCrossProbeTests(unittest.TestCase):
    def test_tile_address_and_4bpp_mask_are_bounded(self) -> None:
        self.assertEqual(tile_id_from_address(0x060020E0), 0x107)
        tile = bytes([0x01] + [0] * 0x1F)
        mask = gba_4bpp_ink_mask(tile)
        self.assertEqual(len(mask), 64)
        self.assertEqual(sum(mask), 1)
        self.assertNotEqual(tile, mask)

    def test_screen_entry_decodes_tile_and_attributes(self) -> None:
        vram = bytearray(0x800)
        vram[2 * (4 * 32 + 14):2 * (4 * 32 + 14) + 2] = (0xDD07).to_bytes(2, "little")
        entry = screen_entry(bytes(vram), 14, 4)
        self.assertEqual(entry["tile_id"], 0x107)
        self.assertTrue(entry["hflip"])
        self.assertTrue(entry["vflip"])
        self.assertEqual(entry["palette_bank"], 13)

    def test_tile_metadata_emits_hashes_not_bytes(self) -> None:
        vram = bytes(0x20 * 0x108)
        metadata = tile_metadata(vram, 0x060020E0)
        self.assertEqual(metadata["tile_id"], 0x107)
        self.assertIn("tile_sha256", metadata)
        self.assertNotIn("tile", metadata)
        self.assertNotIn("pixels", metadata)

    def test_targets_keep_keyboard_labels_separate_from_addresses(self) -> None:
        self.assertEqual(TARGETS[0x005E]["keyboard_label"], "あ")
        self.assertEqual(TARGETS[0x0066]["keyboard_label"], "い")
        self.assertNotEqual(TARGETS[0x005E]["store_addresses"], TARGETS[0x0066]["store_addresses"])


if __name__ == "__main__":
    unittest.main()
