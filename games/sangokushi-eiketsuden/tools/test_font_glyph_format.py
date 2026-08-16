#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ glyph plane expansion contract."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("font_glyph_format.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_font_glyph_format", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load font_glyph_format.py")
FORMAT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FORMAT)


class FontGlyphFormatTest(unittest.TestCase):
    def test_expansion_emits_four_bytes_per_source_byte(self) -> None:
        first = bytes([0x80]) + bytes(FORMAT.GLYPH_STRIDE - 1)
        second = bytes([0x80]) + bytes(FORMAT.GLYPH_STRIDE - 1)
        expanded = FORMAT.expand_source_planes(first, second)
        self.assertEqual(len(expanded), FORMAT.CACHE_BYTES)
        self.assertEqual(expanded[:4], bytes([0x03, 0, 0, 0]))
        self.assertEqual(expanded[4:], bytes(FORMAT.CACHE_BYTES - 4))

    def test_selector_masks_are_taken_from_selector_plus_two(self) -> None:
        first = bytes(FORMAT.GLYPH_STRIDE)
        second = bytes([0x80, 0x40]) + bytes(FORMAT.GLYPH_STRIDE - 2)
        expanded = FORMAT.expand_source_planes(first, second, selector=0)
        self.assertEqual(expanded[:4], bytes([0x02, 0, 0, 0]))
        self.assertEqual(expanded[4:8], bytes([0x20, 0, 0, 0]))

    def test_contract_constants_are_bounded(self) -> None:
        self.assertEqual(FORMAT.GLYPH_STRIDE, 0x20)
        self.assertEqual(FORMAT.CACHE_BYTES, 0x80)
        self.assertEqual(FORMAT.CODEPAGE_COUNT, 1834)


if __name__ == "__main__":
    unittest.main()
