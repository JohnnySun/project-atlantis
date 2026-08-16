#!/usr/bin/env python3
"""Pure tests for the A9PJ M1.6 keyboard metadata arithmetic."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from m16_keyboard_metadata import (  # noqa: E402
    BG1_CHARBASE,
    BG1_SCREENBASE,
    KNOWN_KANA,
    TILE_BYTES,
    analyze,
    tile_bytes,
    tilemap_entry,
)
from m16_name_entry_probe import (  # noqa: E402
    EWRAM,
    append_candidates,
    diff_ranges,
    font_record_address,
)


class KeyboardMetadataTest(unittest.TestCase):
    def make_vram(self) -> bytes:
        vram = bytearray(0x18000)
        for index, (_slot, _label, x, y) in enumerate(KNOWN_KANA):
            tile_id = index + 1
            entry = tile_id | (1 << 12)
            offset = BG1_SCREENBASE + 2 * (y * 32 + x)
            vram[offset:offset + 2] = entry.to_bytes(2, "little")
            start = BG1_CHARBASE + tile_id * TILE_BYTES
            vram[start:start + TILE_BYTES] = bytes([index + 1]) * TILE_BYTES
        return bytes(vram)

    def test_tilemap_fields_and_address(self) -> None:
        vram = self.make_vram()
        entry = tilemap_entry(vram, 1, 7)
        self.assertEqual(entry["tile_id"], 1)
        self.assertEqual(entry["hflip"], 0)
        self.assertEqual(entry["vflip"], 0)
        self.assertEqual(entry["palette_bank"], 1)
        self.assertEqual(tile_bytes(vram, 1), bytes([1]) * TILE_BYTES)

    def test_analyze_requires_more_than_a_single_byte_match(self) -> None:
        vram = self.make_vram()
        tile = tile_bytes(vram, 1)
        rom = bytearray(0x400)
        rom[0x120:0x120 + TILE_BYTES] = tile
        report = analyze(bytes(rom), vram)
        self.assertEqual(report["selected_position_count"], 8)
        self.assertEqual(report["exact_match_position_count"], 1)
        self.assertEqual(report["confirmed_identity_count"], 0)

    def test_hash_is_metadata_only(self) -> None:
        vram = self.make_vram()
        expected = hashlib.sha256(bytes([1]) * TILE_BYTES).hexdigest()
        report = analyze(b"", vram)
        self.assertEqual(report["records"][0]["tile_sha256"], expected)

    def test_font_record_address_uses_observed_stride(self) -> None:
        self.assertEqual(font_record_address(0x005E), 0x0808A6D0)
        self.assertEqual(font_record_address(0x0066), 0x0808A790)

    def test_diff_and_append_filter_keep_two_slot_candidate(self) -> None:
        before = bytearray(0x30)
        first = bytearray(before)
        first[0x14:0x16] = (0x005E).to_bytes(2, "little")
        second = bytearray(first)
        second[0x16:0x18] = (0x0066).to_bytes(2, "little")
        first[0x02] = 0xAA
        second[0x08] = 0xBB

        summary = diff_ranges(bytes(before), bytes(first), EWRAM)
        self.assertEqual(summary["changed_bytes"], 2)
        self.assertEqual(summary["changed_run_count"], 2)

        candidates = append_candidates(bytes(before), bytes(first), bytes(second), EWRAM)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["address"], "0x02000014")
        self.assertEqual(candidates[0]["first_code_unit_le"], "0x005E")
        self.assertEqual(candidates[0]["second_code_unit_le"], "0x0066")


if __name__ == "__main__":
    unittest.main()
