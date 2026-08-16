#!/usr/bin/env python3
"""Tests for bounded M1.12 OBJ source-class mapping."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m112_obj_source_map as mapper  # noqa: E402


def put_ldr_literal(rom: bytearray, address: int, register: int, literal: int) -> None:
    pc_base = (address + 4) & ~3
    immediate = (literal - pc_base) // 4
    assert 0 <= immediate <= 0xFF
    struct.pack_into("<H", rom, address - mapper.ROM_BASE, 0x4800 | (register << 8) | immediate)


class M112ObjSourceMapTests(unittest.TestCase):
    def test_standard_dma_shape_recovers_metadata(self) -> None:
        rom = bytearray(0x300)
        target = mapper.ROM_BASE + 0x100
        entry = target - 6
        literals = {
            mapper.ROM_BASE + 0x140: mapper.DMA3,
            mapper.ROM_BASE + 0x144: 0x02001000,
            mapper.ROM_BASE + 0x148: mapper.OBJ_VRAM_BASE,
            mapper.ROM_BASE + 0x14C: 0x84001000,
        }
        put_ldr_literal(rom, entry, 1, mapper.ROM_BASE + 0x140)
        put_ldr_literal(rom, target - 4, 0, mapper.ROM_BASE + 0x144)
        struct.pack_into("<H", rom, target - mapper.ROM_BASE - 2, 0x6008)
        put_ldr_literal(rom, target, 0, mapper.ROM_BASE + 0x148)
        struct.pack_into("<H", rom, target - mapper.ROM_BASE + 2, 0x6048)
        put_ldr_literal(rom, target + 4, 0, mapper.ROM_BASE + 0x14C)
        struct.pack_into("<H", rom, target - mapper.ROM_BASE + 6, 0x6088)
        struct.pack_into("<H", rom, target - mapper.ROM_BASE + 8, 0x6888)
        struct.pack_into("<H", rom, target - mapper.ROM_BASE + 10, 0x4770)
        for address, value in literals.items():
            struct.pack_into("<I", rom, address - mapper.ROM_BASE, value)

        item = mapper._decode_standard_dma(bytes(rom), target)
        self.assertIsNotNone(item)
        self.assertEqual(item["source"]["address"], "0x02001000")
        self.assertEqual(item["destination"]["address"], "0x06010000")
        self.assertEqual(item["transfer_units"], 0x1000)
        self.assertEqual(item["source_class"], "ewram_runtime_or_staging_candidate")

    def test_source_class_does_not_assign_text_identity(self) -> None:
        self.assertEqual(mapper._source_class(0x02001000), "ewram_runtime_or_staging_candidate")
        self.assertEqual(mapper._source_class(0x081B13B8), "rom_data_pointer_candidate")
        self.assertNotIn("text", mapper._source_class(0x02001000))


if __name__ == "__main__":
    unittest.main()
