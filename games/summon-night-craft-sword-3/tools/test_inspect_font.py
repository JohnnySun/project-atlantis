#!/usr/bin/env python3
"""Tests for the B3CJ static font inspector and renderer."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("inspect_font.py")
SPEC = importlib.util.spec_from_file_location("inspect_font", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load inspect_font.py")
INSPECT_FONT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT_FONT)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"
UNIFONT_PATH = TOOL_PATH.parents[3] / "vendor" / "fonts" / "unifont" / "unifont-17.0.05.hex.gz"


class InspectFontTest(unittest.TestCase):
    def test_table_index_reports_gba_and_file_offsets_separately(self) -> None:
        base, index, file_offset = INSPECT_FONT.table_index(bytes.fromhex("90b3"))
        self.assertEqual(base, 0x08B6D624)
        self.assertEqual(index, 2995)
        self.assertEqual(file_offset, 0xB6ED8A)

    def test_cell_renderer_is_msb_first_and_12_pixels_wide(self) -> None:
        cell = bytes.fromhex("ff e0") + bytes(22)
        self.assertEqual(INSPECT_FONT.cell_rows(cell)[0], "###########.")
        self.assertEqual(len(INSPECT_FONT.cell_rows(cell)), 12)
        self.assertEqual(len(INSPECT_FONT.cell_rows(cell)[0]), 12)

    def test_aligned_shift_jis_iteration_does_not_create_overlap_pairs(self) -> None:
        encoded = "正a直".encode("shift_jis")
        self.assertEqual(
            list(INSPECT_FONT.iter_shift_jis_code_units(encoded)),
            [bytes.fromhex("90b3"), bytes.fromhex("92bc")],
        )

    def test_unifont_conversion_returns_one_12_by_12_cell(self) -> None:
        bitmap = bytes([0xFF, 0xFF] * 16)
        cell = INSPECT_FONT.unifont_bitmap_to_cell(bitmap)
        self.assertEqual(len(cell), INSPECT_FONT.FONT_CELL_SIZE)
        self.assertEqual(INSPECT_FONT.render_cell(cell), "\n".join(["############"] * 12))

    @unittest.skipUnless(ROM_PATH.is_file(), "local ignored B3CJ ROM is not available")
    def test_local_rom_font_identity_and_sample_mapping(self) -> None:
        data = ROM_PATH.read_bytes()
        identity = INSPECT_FONT.verify_rom(data)
        self.assertEqual(identity["crc32"], "12afae5d")
        font = INSPECT_FONT.parse_font_resource(data)
        self.assertEqual(font["slot_count"], 0x860)
        mapped = INSPECT_FONT.lookup_code_unit(
            data,
            bytes.fromhex("90b3"),
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        self.assertEqual(mapped["status"], "mapped")
        self.assertEqual(mapped["glyph_id"], 0x4D1)
        self.assertEqual(mapped["cell_file_offset"], "0x14dd020")
        rendered = INSPECT_FONT.render_glyph(data, font, int(mapped["glyph_id"]))
        self.assertEqual(len(rendered["rows"]), 12)
        self.assertEqual(len(rendered["rows"][0]), 12)
        self.assertNotEqual(set("".join(rendered["rows"])), {"."})

    @unittest.skipUnless(ROM_PATH.is_file() and UNIFONT_PATH.is_file(), "local ROM/font source is not available")
    def test_static_poc_changes_only_requested_table_and_blank_cells(self) -> None:
        data = ROM_PATH.read_bytes()
        patched, report, render_cells = INSPECT_FONT.build_static_poc(data, UNIFONT_PATH)
        self.assertEqual(len(patched), len(data))
        self.assertTrue(report["static_only"])
        self.assertFalse(report["runtime_qa"])
        self.assertEqual(len(report["changed_mappings"]), 2)
        self.assertEqual(report["untouched_adjacent_glyph_id"], 0x844)
        self.assertEqual(report["source_font_sha256"], INSPECT_FONT.UNIFONT_SOURCE_SHA256)
        self.assertEqual(report["changed_region_byte_count"], 52)
        self.assertEqual(report["changed_byte_count"], 43)
        self.assertEqual(len(render_cells), 3)
        self.assertNotEqual(patched, data)
        for entry in report["changed_mappings"]:
            self.assertEqual(entry["old_table_value"], "0x0000")
            self.assertIn(entry["glyph_id"], (0x845, 0x846))


if __name__ == "__main__":
    unittest.main()
