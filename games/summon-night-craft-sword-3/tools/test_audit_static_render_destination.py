#!/usr/bin/env python3
"""Tests for the B3CJ static writer -> DMA -> destination audit."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("audit_static_render_destination.py")
SPEC = importlib.util.spec_from_file_location("audit_static_render_destination", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_static_render_destination.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class StaticRenderDestinationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()

    def require_rom(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM is not available")

    def test_writer_dma_and_vram_chain_is_locally_hash_guarded(self) -> None:
        self.require_rom()
        report = AUDIT.audit_rom(ROM_PATH)
        self.assertEqual(report["evidence_level"], "confirmed-static-writer-dma-vram-palette-oam-copy-and-text-tile-address")
        self.assertEqual(len(report["function_checks"]), 13)
        self.assertEqual(len(report["literal_checks"]), 16)
        self.assertEqual(report["writer"]["per_glyph_stride"], "0x80")
        self.assertEqual(report["dma_queue"]["hardware_dma_register"], "0x040000d4")
        self.assertEqual(report["text_vram_destination"]["gba_address"], "0x06010000")
        self.assertEqual(report["text_tile_address"]["tile_stride"], "0x20 bytes (4bpp)")
        self.assertEqual(report["text_tile_address"]["tile_index_mask"], "0x3ff")

    def test_palette_and_oam_are_static_and_tilemap_remains_unknown(self) -> None:
        self.require_rom()
        report = AUDIT.audit_rom(ROM_PATH)
        self.assertEqual(report["palette"]["hardware_palette_destination"], "0x05000000")
        self.assertEqual(report["palette"]["hardware_copy_source"], "gUnk_03005960 + 0x400 = 0x03005d60")
        self.assertEqual(report["palette"]["hardware_copy_length"], "0x400 bytes")
        self.assertEqual(report["tilemap"]["destination"], "unknown")
        self.assertEqual(report["oam"]["source"], "0x030038b0")
        self.assertEqual(report["oam"]["destination"], "0x07000000")
        self.assertEqual(report["oam"]["length"], "0x400 bytes")
        self.assertEqual(report["oam"]["control"], "0x84000100")
        self.assertFalse(report["runtime"]["consumer_hit"])

    def test_literal_drift_fails_closed(self) -> None:
        self.require_rom()
        data = bytearray(ROM_PATH.read_bytes())
        data[0xD8F8 : 0xD8FC] = (0x06000000).to_bytes(4, "little")
        with self.assertRaises(ValueError):
            AUDIT._literal_checks(bytes(data))

    def test_oam_and_tile_address_drift_fail_closed(self) -> None:
        self.require_rom()
        for offset, value in ((0x92E4, 0x030038B4), (0x9680, 0x06002000)):
            data = bytearray(ROM_PATH.read_bytes())
            data[offset : offset + 4] = value.to_bytes(4, "little")
            with self.subTest(offset=hex(offset)):
                with self.assertRaises(ValueError):
                    AUDIT._literal_checks(bytes(data))


if __name__ == "__main__":
    unittest.main()
