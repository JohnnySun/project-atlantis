#!/usr/bin/env python3
"""Tests for the bounded clean A9HJ text-layout audit."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("audit_text_layout.py")
SPEC = importlib.util.spec_from_file_location("dqmch_audit_text_layout", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TextLayoutAuditTest(unittest.TestCase):
    def test_clean_layout_receipt(self) -> None:
        rom = Path(
            "games/dragon-quest-monsters-caravan-heart/roms/base/"
            "Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba"
        ).read_bytes()
        receipt = MODULE.audit(rom)
        self.assertEqual(receipt["state_pointer"], "0x03002830")
        self.assertEqual(receipt["glyph_stride"]["state_bit_7_clear"], 0x20)
        self.assertEqual(receipt["pair_loop_words"], 8)
        self.assertEqual(receipt["dma3"]["source_register"], "0x040000D4")
        self.assertEqual(receipt["layout_branch"]["alternate_glyph_table"], "0x082E0BD4")
        self.assertEqual(receipt["layout_branch"]["alt_glyph_controls"], ["0xE0", "0xE1"])
        self.assertEqual(
            receipt["layout_branch"]["alt_glyph_bank_by_lead"],
            {"0xE0": "0x0000", "0xE1": "0x4000"},
        )

    def test_wrong_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.audit(b"not a ROM")


if __name__ == "__main__":
    unittest.main()
