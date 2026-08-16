#!/usr/bin/env python3
"""Pure tests for the bounded M1.9 probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from m19_gate_transfer_probe import (  # noqa: E402
    KNOWN_TILE1_SHA256,
    KNOWN_TILE2_SHA256,
    RESET_TILE1_SHA256,
    dma_tile_window,
    gate_status,
    region,
    response_kind,
)


class M19HelpersTest(unittest.TestCase):
    def test_response_classes_do_not_expose_packet_payload(self) -> None:
        self.assertEqual(response_kind("OK"), "ok")
        self.assertEqual(response_kind("T05watch:06004020;"), "stop")
        self.assertEqual(response_kind("E01"), "error")
        self.assertEqual(response_kind("00" * 32), "hex")
        self.assertEqual(response_kind("queued-answer"), "other")

    def test_gate_requires_layout_and_both_known_tile_hashes(self) -> None:
        screen = {
            "keyboard_layout": {"confirmed": True},
            "gate_confirmed": True,
            "tile_hashes_match_known": True,
            "keyboard_tile_hashes": {
                "tile1": KNOWN_TILE1_SHA256,
                "tile2": KNOWN_TILE2_SHA256,
            },
        }
        self.assertTrue(gate_status(screen))
        screen["tile_hashes_match_known"] = False
        self.assertFalse(gate_status(screen))

    def test_runtime_regions_exclude_vram_and_register_aliases(self) -> None:
        self.assertEqual(region(0x08089E00), "rom")
        self.assertEqual(region(0x02004014), "ewram")
        self.assertEqual(region(0x03000020), "iwram")
        self.assertIsNone(region(0x06004020))
        self.assertIsNone(region(0x0203FFF0))

    def test_reset_hash_is_distinct_from_keyboard_hash(self) -> None:
        self.assertNotEqual(RESET_TILE1_SHA256, KNOWN_TILE1_SHA256)
        self.assertNotEqual(RESET_TILE1_SHA256, KNOWN_TILE2_SHA256)

    def test_dma3_window_maps_tile_offset_and_width(self) -> None:
        window = dma_tile_window(0x08010000, 0x06004000, 0x20, 0x8400)
        self.assertEqual(window["transfer_width"], 4)
        self.assertEqual(window["byte_count"], 0x80)
        self.assertEqual(window["tile_offset"], 0x20)
        self.assertEqual(window["source_tile_address"], 0x08010020)


if __name__ == "__main__":
    unittest.main()
