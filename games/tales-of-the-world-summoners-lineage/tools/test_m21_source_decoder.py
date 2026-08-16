#!/usr/bin/env python3
"""Tests for the private M21 candidate decoder."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m21_source_decoder import (  # noqa: E402
    KNOWN_UI_MAPPING,
    KNOWN_UI_ROWS,
    STATIC_PHRASE_MAPPING,
    STATIC_UI_ROWS,
    build_keyboard_map,
    decode_known_ui_rows,
    decode_known_static_ui_rows,
    decode_units,
    keyboard_labels,
)


class M21SourceDecoderTests(unittest.TestCase):
    def test_keyboard_labels_keep_unproven_tail_unresolved(self) -> None:
        hiragana, katakana = keyboard_labels()
        self.assertEqual(len(hiragana), 65)
        self.assertEqual(len(katakana), 65)
        self.assertEqual(hiragana[:5], tuple("あいうえお"))
        self.assertIsNone(hiragana[50])
        self.assertIsNone(katakana[56])

    def test_mapping_status_separates_confirmed_and_provisional(self) -> None:
        data = bytearray(0x8A000)
        table = 0x8884C
        values = [0x005E, 0x0062, 0x0066, 0x006B, 0x006F, 0x0073]
        for index, value in enumerate(values):
            data[table + index * 2:table + index * 2 + 2] = value.to_bytes(2, "little")
        # The row-1 reads also need to be in-bounds; zero is intentionally blank.
        mapping = build_keyboard_map(bytes(data))
        self.assertEqual(mapping[0x005E]["mapping_status"], "confirmed-system-row0-first-five")
        self.assertEqual(mapping[0x0073]["mapping_status"], "provisional-keyboard-order")

    def test_decode_keeps_controls_and_unknown_units_visible(self) -> None:
        mapping = {
            0x005E: {"text": "あ", "mapping_status": "confirmed-system-row0-first-five"},
        }
        result = decode_units([0x005E, 0xFF70, 0x0123, 0x0000, 0x0042], mapping)
        self.assertEqual(result["text"], "あ{FF70}{U0123}")
        self.assertTrue(result["terminated_by_0000"])
        self.assertEqual(result["control_candidates"], ["0xFF70"])
        self.assertEqual(result["unresolved_code_units"], ["0x0123"])
        self.assertFalse(result["complete_codepage"])

    def test_source_checksum_is_deterministic_for_normalized_text(self) -> None:
        result = decode_units([0x005E, 0xFF70, 0x0000], {
            0x005E: {"text": "あ", "mapping_status": "confirmed"},
        })
        self.assertEqual(result["text"], "あ{FF70}")
        self.assertEqual(
            __import__("hashlib").sha256(result["text"].encode("utf-8")).hexdigest(),
            "cb8e0950a2a3a86d3887d8fefd6f61d0aa97e96ad1e44e7749c52e7581c01ab3",
        )

    def test_decode_does_not_mark_unterminated_stream_complete(self) -> None:
        result = decode_units([0x005E], {0x005E: {"text": "あ", "mapping_status": "confirmed"}})
        self.assertFalse(result["terminated_by_0000"])
        self.assertEqual(result["text"], "あ")

    def test_known_ui_rows_are_fixed_and_eligible_only_by_explicit_proof(self) -> None:
        self.assertEqual(len(KNOWN_UI_ROWS), 2)
        self.assertEqual({row["scene_role"] for row in KNOWN_UI_ROWS}, {
            "ui-name-entry",
            "ui-name-entry-protagonist-name-field",
        })
        decoded = decode_units(
            [0x00C8, 0x00F6, 0x0063, 0x00FE, 0x0000],
            {unit: {"text": text, "mapping_status": "confirmed-known-screen"}
             for unit, text in KNOWN_UI_MAPPING.items()},
        )
        self.assertEqual(decoded["text"], "フレイン")
        self.assertTrue(decoded["complete_codepage"])
        self.assertEqual(decoded["unresolved_code_units"], [])

    def test_known_ui_decoder_rejects_non_a9pj_input(self) -> None:
        with self.assertRaises(ValueError):
            decode_known_ui_rows(bytes(0x100))

    def test_static_phrase_rows_are_fixed_and_ineligible(self) -> None:
        self.assertEqual(len(STATIC_UI_ROWS), 3)
        self.assertEqual(STATIC_PHRASE_MAPPING[0x0003], "。")
        self.assertEqual(STATIC_PHRASE_MAPPING[0x000C], "ー")
        self.assertEqual(STATIC_PHRASE_MAPPING[0x028B], "最")
        self.assertEqual(STATIC_PHRASE_MAPPING[0x0311], "初")
        self.assertEqual(STATIC_PHRASE_MAPPING[0x03A8], "選")
        self.assertFalse(any("eligible_for_ledger" in row for row in STATIC_UI_ROWS))
        mapping = {
            **{0x008F: {"text": "す", "mapping_status": "keyboard"},
               0x0073: {"text": "か", "mapping_status": "keyboard"},
               0x00EF: {"text": "ら", "mapping_status": "keyboard"},
               0x00F3: {"text": "る", "mapping_status": "keyboard"},
               0x00E8: {"text": "ユ", "mapping_status": "keyboard"},
               0x00B4: {"text": "ニ", "mapping_status": "keyboard"},
               0x00AE: {"text": "ト", "mapping_status": "keyboard"},
               0x009C: {"text": "タ", "mapping_status": "keyboard"},
               0x008B: {"text": "し", "mapping_status": "keyboard"},
               0x00D9: {"text": "ま", "mapping_status": "keyboard"},
               0x007B: {"text": "く", "mapping_status": "keyboard"},
               0x0087: {"text": "さ", "mapping_status": "keyboard"},
               0x0062: {"text": "い", "mapping_status": "keyboard"},
               0x007C: {"text": "ク", "mapping_status": "keyboard"},
               0x00F0: {"text": "ラ", "mapping_status": "keyboard"},
               0x0090: {"text": "ス", "mapping_status": "keyboard"}},
            **{unit: {"text": text, "mapping_status": "static"}
               for unit, text in STATIC_PHRASE_MAPPING.items()},
        }
        first = decode_units(list(STATIC_UI_ROWS[0]["units"]) + [0], mapping)
        second = decode_units(list(STATIC_UI_ROWS[1]["units"]) + [0], mapping)
        third = decode_units(list(STATIC_UI_ROWS[2]["units"]) + [0], mapping)
        self.assertEqual(first["text"], "攻撃するユニットを選んでください。")
        self.assertEqual(second["text"], "クラスを選んでください。")
        self.assertEqual(third["text"], "最初からスタートします")
        self.assertTrue(first["complete_codepage"])
        self.assertTrue(second["complete_codepage"])
        self.assertTrue(third["complete_codepage"])

    def test_known_static_ui_decoder_rejects_non_a9pj_input(self) -> None:
        with self.assertRaises(ValueError):
            decode_known_static_ui_rows(bytes(0x100))


if __name__ == "__main__":
    unittest.main()
