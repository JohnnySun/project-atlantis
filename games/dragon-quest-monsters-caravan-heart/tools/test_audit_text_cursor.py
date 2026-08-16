#!/usr/bin/env python3
"""Tests for the bounded clean A9HJ text-cursor audit."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("audit_text_cursor.py")
SPEC = importlib.util.spec_from_file_location("dqmch_audit_text_cursor", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TextCursorAuditTest(unittest.TestCase):
    def test_clean_cursor_contract(self) -> None:
        rom = Path(
            "games/dragon-quest-monsters-caravan-heart/roms/base/"
            "Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba"
        ).read_bytes()
        report = MODULE.audit(rom)
        self.assertEqual(report["schema"], "dqmch-text-cursor-contract-v1")
        self.assertEqual(report["signature_count"], 7)
        self.assertEqual(report["advance_signature_count"], 2)
        self.assertEqual(report["source_cursor_contract"]["default_field"], "state+0x18")
        self.assertEqual(report["output_slot_contract"]["field"], "state+0x16")
        self.assertTrue(report["separation"]["fields_are_distinct"])
        self.assertEqual(report["separation"]["semantic_width_or_vwf"], "not-proven")

    def test_signature_mutation_is_rejected(self) -> None:
        rom = bytearray(
            Path(
                "games/dragon-quest-monsters-caravan-heart/roms/base/"
                "Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba"
            ).read_bytes()
        )
        rom[0x12628] ^= 0x01
        with self.assertRaises(ValueError):
            MODULE.audit(bytes(rom))

    def test_wrong_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.audit(b"not a ROM")


if __name__ == "__main__":
    unittest.main()
