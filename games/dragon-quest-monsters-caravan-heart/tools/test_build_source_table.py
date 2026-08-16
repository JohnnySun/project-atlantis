#!/usr/bin/env python3
"""Tests for the conservative local A9HJ source-table stage."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("build_source_table.py")
SPEC = importlib.util.spec_from_file_location("dqmch_build_source_table", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildSourceTableTest(unittest.TestCase):
    def test_confirmed_ascii_and_kana_region(self) -> None:
        mapping = MODULE.direct_map()
        self.assertEqual(mapping[0x00], "0")
        self.assertEqual(mapping[0x1F], "V")
        self.assertEqual(mapping[0x26], "い")
        self.assertEqual(mapping[0x60], "ゥ")
        self.assertEqual(mapping[0x61], "エ")
        self.assertEqual(mapping[0x7F], "マ")
        self.assertEqual(mapping[0x85], "ャ")
        self.assertEqual(mapping[0x8A], "ラ")
        self.assertEqual(mapping[0x8C], "ル")
        self.assertEqual(mapping[0x5A], "ん")
        self.assertEqual(mapping[0x59], "を")
        self.assertEqual(mapping[0x5B], "ア")
        self.assertEqual(mapping[0x5C], "ァ")
        self.assertEqual(mapping[0x90], "ヲ")
        self.assertEqual(mapping[0x91], "ン")
        self.assertEqual(mapping[0x94], "。")
        self.assertEqual(mapping[0x9B], "？")
        self.assertEqual(mapping[0x9C], "！")
        self.assertEqual(mapping[0xA0], "・")
        self.assertEqual(mapping[0xA1], "ー")
        self.assertEqual(mapping[0xA2], "～")
        self.assertEqual(mapping[0xBF], " ")

    def test_pair_identity_uses_known_kana_diacritic_bases(self) -> None:
        mapping = MODULE.direct_map()
        text, resolved = MODULE.pair_text(0x92, 0x34, mapping)
        self.assertEqual((text, resolved), ("じ", True))
        text, resolved = MODULE.pair_text(0x92, 0x69, mapping)
        self.assertEqual((text, resolved), ("ゴ", True))
        text, resolved = MODULE.pair_text(0x93, 0x7C, mapping)
        self.assertEqual((text, resolved), ("プ", True))
        text, resolved = MODULE.pair_text(0x92, 0xBF, mapping)
        self.assertEqual((text, resolved), ("{U92BF}", False))

    def test_unknown_and_control_are_explicit(self) -> None:
        mapping = MODULE.direct_map()
        text, stats = MODULE.token_text(
            [
                {"kind": "single-byte-candidate", "value": 0x26},
                {"kind": "single-byte-candidate", "value": 0xA0},
                {"kind": "control-candidate", "value": 0xFF},
            ],
            mapping,
        )
        self.assertEqual(text, "い・{FF}")
        self.assertEqual(stats, {"mapped": 2, "unresolved": 0, "controls": 1, "pairs": 0, "alt_glyphs": 0})

    def test_alt_glyph_remains_explicit_until_alt_pool_is_mapped(self) -> None:
        text, stats = MODULE.token_text(
            [{"kind": "alt-glyph", "lead": 0xE0, "value": 0x8D}],
            MODULE.direct_map(),
        )
        self.assertEqual(text, "{GE08D}")
        self.assertEqual(stats["alt_glyphs"], 1)
        self.assertEqual(stats["unresolved"], 1)

    def test_source_row_is_never_eligible_without_full_context_gate(self) -> None:
        row, receipt = MODULE.source_record(
            {
                "group": 6,
                "variant": 0,
                "message_index": 0,
                "pointer_cpu": "0x0828647C",
                "pointer_file": "0x28647C",
                "span_end_file": "0x2866A9",
                "boundary": "next-pointer-in-table",
                "control_values": [0xFF],
                "tokens": [{"kind": "single-byte-candidate", "value": 0x26}],
            },
            MODULE.direct_map(),
        )
        self.assertFalse(receipt["eligible"])
        self.assertEqual(row["locale"], "ja-JP")
        self.assertIn("ledger_eligible=false", row["provenance"])


if __name__ == "__main__":
    unittest.main()
