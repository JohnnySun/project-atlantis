#!/usr/bin/env python3
"""Unit tests for the bounded A5TJ OBJ analysis helpers."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_obj_tiles as analysis  # noqa: E402


class AnalyzeObjTilesTests(unittest.TestCase):
    def test_bounded_standard_decompressors(self) -> None:
        lz77 = bytes((0x10, 0x04, 0x00, 0x00, 0x00)) + b"ABCD"
        self.assertEqual(analysis.lz77_decompress(lz77, 0, 64), b"ABCD")

        rl = bytes((0x30, 0x04, 0x00, 0x00, 0x03)) + b"ABCD"
        self.assertEqual(analysis.rl_decompress(rl, 0, 64), b"ABCD")

    def test_exact_rom_and_runtime_region_matches(self) -> None:
        vram = bytearray(0x18000)
        glyph = bytes((index * 7 + 3) & 0xFF for index in range(32))
        vram[0x10000 + 32 : 0x10000 + 64] = glyph

        oam = bytearray(0x400)
        for index in range(128):
            struct.pack_into("<H", oam, index * 8, 0x0200)
        struct.pack_into("<HHH", oam, 0, 0x0008, 10, 1)

        rom = bytearray(0x2000)
        rom[0x1000 : 0x1000 + 32] = glyph
        iwram = bytearray(0x8000)
        iwram[0x33F0 : 0x33F0 + 0x400] = oam
        ewram = bytearray(0x4000)
        ewram[0x0200 : 0x0200 + 32] = glyph

        report = analysis.analyze(
            bytes(rom),
            bytes(vram),
            bytes(oam),
            bytes(iwram),
            bytes(ewram),
            max_y=160,
            obj_base=0x10000,
            bpp=4,
            mapping="1d",
            compression_alignment=4,
            compression_max_output=0x400,
            compression_max_candidates=32,
            compression_glyphs_only=True,
            skip_compression=True,
        )

        self.assertEqual(report["capture"]["active_sprite_count"], 1)
        self.assertEqual(report["exact_match_summary"]["sprites_with_exact_match"], 1)
        self.assertIsNone(report["font_table_candidate"])
        self.assertEqual(report["runtime_ram_matches"]["summary"]["oam_exact_count"], 1)
        self.assertEqual(
            report["runtime_ewram_matches"]["summary"]["sprites_with_exact_match"],
            1,
        )
        self.assertEqual(
            report["runtime_ewram_matches"]["sprites"][0]["matches"]["bus_offsets"],
            ["0x02000200"],
        )


if __name__ == "__main__":
    unittest.main()
