#!/usr/bin/env python3
"""Unit tests for the clean-only pointer/token extractor."""

from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("extract_text.py")
SPEC = importlib.util.spec_from_file_location("dqmch_extract_text", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtractTextTest(unittest.TestCase):
    def test_mixed_byte_tokenisation(self) -> None:
        tokens, truncated = MODULE.tokenise(bytes((0x8B, 0xA1, 0x92, 0x6F, 0xDF, 0xFF)), 0, 6)
        self.assertFalse(truncated)
        self.assertEqual(
            [token["kind"] for token in tokens],
            ["single-byte-candidate", "single-byte-candidate", "pair", "control-candidate", "control-candidate"],
        )
        self.assertEqual((tokens[2]["lead"], tokens[2]["trail"]), (0x92, 0x6F))

    def test_truncated_pair_is_explicit(self) -> None:
        tokens, truncated = MODULE.tokenise(bytes((0x92,)), 0, 1)
        self.assertTrue(truncated)
        self.assertEqual(tokens[0]["kind"], "pair-truncated")

    def test_alt_glyph_control_consumes_one_byte(self) -> None:
        tokens, truncated = MODULE.tokenise(bytes((0xE0, 0x8D, 0x26)), 0, 3)
        self.assertFalse(truncated)
        self.assertEqual(
            [token["kind"] for token in tokens],
            ["alt-glyph", "single-byte-candidate"],
        )
        self.assertEqual((tokens[0]["lead"], tokens[0]["value"]), (0xE0, 0x8D))

    def test_pointer_run_stops_at_non_pointer(self) -> None:
        data = bytearray(0x20)
        struct.pack_into("<I", data, 0x00, 0x08000010)
        struct.pack_into("<I", data, 0x04, 0x08000011)
        struct.pack_into("<I", data, 0x08, 0)
        self.assertEqual(MODULE.pointer_run(bytes(data), 0x08000000, limit=4), [0x08000010, 0x08000011])

    def test_clean_validation_rejects_wrong_size(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.validate_rom(b"not a clean A9HJ ROM")


if __name__ == "__main__":
    unittest.main()
