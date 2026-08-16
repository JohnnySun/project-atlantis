#!/usr/bin/env python3
"""Unit tests for the bounded A5TJ runtime trace helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import trace_dma_consumers as dma  # noqa: E402
import trace_swi_consumers as swi  # noqa: E402


class TraceConsumerTests(unittest.TestCase):
    def test_swi_number_and_regions_are_metadata_only(self) -> None:
        rom = bytearray(0x200)
        rom[0x100:0x102] = bytes((0x0B, 0xDF))
        self.assertEqual(swi.swi_number(bytes(rom), 0x08000102), 0x0B)
        self.assertEqual(swi.region(0x06013000), "obj_vram")
        self.assertEqual(swi.region(0x030033F0), "iwram")
        self.assertEqual(swi.source_metadata(0x08000100, len(rom))["rom_offset"], "0x100")

    def test_thumb_dma_store_decode(self) -> None:
        rom = bytearray(0x200)
        # Thumb STR r0, [r1, #4], immediately before the stop PC.
        rom[0x100:0x102] = (0x6048).to_bytes(2, "little")
        decoded = dma.thumb_store_info(bytes(rom), 0x08000102)
        self.assertEqual(decoded["form"], "str_word_imm")
        self.assertEqual(decoded["register"], 0)
        self.assertEqual(decoded["base_register"], 1)
        self.assertEqual(decoded["offset"], 4)
        self.assertEqual(dma.region(0x06013000), "obj_vram")


if __name__ == "__main__":
    unittest.main()
