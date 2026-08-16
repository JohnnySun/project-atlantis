#!/usr/bin/env python3
"""Pure tests for the bounded M1.9 runtime metadata and tile renderer."""

from __future__ import annotations

import unittest

from m19_runtime_qa import (
    RuntimeQAError,
    code_units,
    expected_tile_layout,
    record_metadata,
    writer_pixel_render,
)


class M19RuntimeQATest(unittest.TestCase):
    def test_narrow_code_units_are_strict_and_opaque_units_fail_closed(self) -> None:
        self.assertEqual(code_units(bytes.fromhex("814083e8")), (0x4081, 0xE883))
        with self.assertRaisesRegex(RuntimeQAError, "narrow-only"):
            code_units(bytes.fromhex("8840"))
        with self.assertRaisesRegex(RuntimeQAError, "opaque/control"):
            code_units(b"AB")
        with self.assertRaisesRegex(RuntimeQAError, "opaque/control"):
            code_units(bytes.fromhex("8140ff"))

    def test_record_metadata_keeps_nul_and_width_as_metadata_only(self) -> None:
        rom = bytearray(32)
        rom[8:12] = bytes.fromhex("814083e8")
        rom[12] = 0
        metadata = record_metadata(bytes(rom), 8, source_ledger_sha256="a" * 64, role="synthetic")
        self.assertEqual(metadata["payload_length"], 4)
        self.assertEqual(metadata["unit_count"], 2)
        self.assertEqual(metadata["line_width"], 16)
        self.assertEqual(metadata["terminator"], "NUL")
        self.assertEqual(metadata["terminator_address"], "0x0800000C")
        self.assertNotIn("text", metadata)

    def test_two_narrow_glyph_layout_has_two_tiles_and_two_tile_rows(self) -> None:
        first = bytes([0x80] * 12)
        second = bytes([0x01] * 12)
        layout = expected_tile_layout((first, second))
        self.assertEqual(len(layout), 128)
        # The first row of each glyph occupies the first byte of its tile row.
        self.assertEqual(layout[0], 0x01)
        self.assertEqual(layout[35], 0x10)
        self.assertEqual(layout[64], 0x01)
        self.assertEqual(layout[99], 0x10)

    def test_writer_metadata_renders_exact_nibbles_without_outside_pixels(self) -> None:
        base = 0x02019010
        calls = []
        for y in range(12):
            for glyph_index, value in enumerate((0x0001, 0x1000)):
                tile_y = y // 8
                tile_index = tile_y * 2 + glyph_index
                calls.append(
                    {
                        "writer_base": f"0x{base:08X}",
                        "destination": f"0x{base + tile_index * 32 + (y % 8) * 4:08X}",
                        "tile_value": f"0x{value:04X}",
                    }
                )
        rendered = writer_pixel_render(calls, expected_width=16)
        pixels = rendered["pixels"]
        self.assertEqual(rendered["outside_nonzero_pixels"], 0)
        self.assertEqual(rendered["width"], 16)
        self.assertEqual(rendered["height"], 12)
        self.assertEqual(pixels[0], 1)
        self.assertEqual(pixels[8], 0)
        self.assertEqual(pixels[9], 0)
        self.assertEqual(pixels[11], 1)
        self.assertEqual(len(pixels), 16 * 12)


if __name__ == "__main__":
    unittest.main()
