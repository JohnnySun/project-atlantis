#!/usr/bin/env python3
"""Pure tests for A9PJ M1.8 BG1/DMA metadata arithmetic."""

from __future__ import annotations

import unittest

from m18_bg1_asset_probe import (
    BG1_TILE_1,
    BG1_TILE_2,
    decode_bgcnt,
    dma_transfer_length,
    is_stop_response,
    overlaps,
    thumb_bl_target,
)


class M18Bg1AssetProbeTests(unittest.TestCase):
    def test_bg1cnt_decodes_charbase_and_screenbase(self) -> None:
        decoded = decode_bgcnt(0x0106)
        self.assertEqual(decoded["charblock"], 1)
        self.assertEqual(decoded["charbase_offset"], "0x00004000")
        self.assertEqual(decoded["screenblock"], 1)
        self.assertEqual(decoded["screenbase_offset"], "0x00000800")
        self.assertEqual(decoded["bpp"], 4)

    def test_dma_count_zero_uses_channel_limit(self) -> None:
        self.assertEqual(dma_transfer_length(0, 0x00000000)["length_bytes"], 0x8000)
        self.assertEqual(dma_transfer_length(0, 0x04000000)["length_bytes"], 0x10000)
        self.assertEqual(dma_transfer_length(3, 0x00000000)["length_bytes"], 0x20000)
        self.assertEqual(dma_transfer_length(3, 0x04000000)["length_bytes"], 0x40000)
        self.assertEqual(dma_transfer_length(3, 0x04000000 | (1 << 26))["unit_bytes"], 4)

    def test_bg1_tile_ranges_and_slice_overlap(self) -> None:
        self.assertTrue(overlaps(0x06004000, 0x60, BG1_TILE_1, 0x20))
        self.assertTrue(overlaps(0x06004040, 0x20, BG1_TILE_2, 0x20))
        self.assertFalse(overlaps(0x06005000, 0x20, BG1_TILE_1, 0x20))

    def test_thumb_bl_decoder_handles_zero_offset(self) -> None:
        # BL with zero signed offset: first halfword F000, second F800.
        self.assertEqual(thumb_bl_target(0xF000, 0xF800, 0x08000100), 0x08000105)

    def test_stop_filter_rejects_delayed_data_payloads(self) -> None:
        self.assertTrue(is_stop_response("T05watch:06004020;"))
        self.assertTrue(is_stop_response("S05"))
        self.assertFalse(is_stop_response("OK"))
        self.assertFalse(is_stop_response("1111111111111111"))


if __name__ == "__main__":
    unittest.main()
