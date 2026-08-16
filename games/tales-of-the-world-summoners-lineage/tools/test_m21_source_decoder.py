#!/usr/bin/env python3
"""Tests for the private M21 candidate decoder."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m21_source_decoder import build_keyboard_map, decode_units, keyboard_labels  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
