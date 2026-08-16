#!/usr/bin/env python3
"""ROM-independent tests for B3EJ translation encoding boundaries."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("font_coverage.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_font_coverage", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load font_coverage.py")
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


class FontCoverageTest(unittest.TestCase):
    def test_shift_jis_code_units_separate_ascii_from_double_byte_units(self) -> None:
        encoded, units = COVERAGE.shift_jis_code_units("A多個・")
        self.assertEqual(encoded[0], ord("A"))
        self.assertEqual(units, [0x91BD, 0x8CC2, 0x8145])

    def test_canonical_hash_is_utf8_text_hash(self) -> None:
        self.assertEqual(
            COVERAGE.canonical_text_hash("多個部隊"),
            "25fa5b62ff89103b66f344c8355a6ddeda33080500d6cce00d474494be274ac2",
        )

    def test_reviewed_font_geometry_is_explicit(self) -> None:
        self.assertEqual(COVERAGE.CODEPAGE_COUNT, 1834)
        self.assertEqual(COVERAGE.GLYPH_STRIDE, 0x20)
        self.assertEqual(COVERAGE.GLYPH_BANK_BYTES, 1834 * 0x20)


if __name__ == "__main__":
    unittest.main()
