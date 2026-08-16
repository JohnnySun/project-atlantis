#!/usr/bin/env python3
"""Pure tests for the bounded A9PJ M1.7 trace arithmetic."""

from __future__ import annotations

import unittest

from m17_font_tile_probe import (
    FONT_RECORD_TABLE_BASE,
    FONT_RECORD_STRIDE,
    STORE_POINTS,
    classify_pc,
    code_unit_from_record,
    font_record_address,
    keyboard_tile_for_address,
    renderer_destination,
    store_address,
)


class M17FontTileProbeTests(unittest.TestCase):
    def test_record_formula_round_trip(self) -> None:
        for code_unit in (0x005E, 0x0066):
            address = font_record_address(code_unit)
            self.assertEqual(
                address,
                FONT_RECORD_TABLE_BASE + code_unit * FONT_RECORD_STRIDE,
            )
            self.assertEqual(code_unit_from_record(address), code_unit)

    def test_renderer_formula_reaches_bg1_first_two_tiles(self) -> None:
        self.assertEqual(
            renderer_destination(0x02004000, 1, 0, 0x4000, 0, 0),
            0x06004020,
        )
        self.assertEqual(
            renderer_destination(0x02004000, 2, 0, 0x4000, 0, 0),
            0x06004040,
        )

    def test_store_instruction_effective_addresses(self) -> None:
        regs = {"r2": 0x06004000, "r3": 0x06004020}
        self.assertEqual(store_address(regs, 0x08004C82), 0x06004020)
        self.assertEqual(store_address(regs, 0x08004D1A), 0x06004020)
        self.assertEqual(set(STORE_POINTS), {0x08004C82, 0x08004D1A})

    def test_keyboard_position_requires_tile_range(self) -> None:
        self.assertEqual(keyboard_tile_for_address(0x06004020)["slot"], "a-row-1")
        self.assertEqual(keyboard_tile_for_address(0x0600403F)["tile_id"], 1)
        self.assertEqual(keyboard_tile_for_address(0x06004040)["slot"], "a-row-2")
        self.assertIsNone(keyboard_tile_for_address(0x06005000))

    def test_pc_classification_keeps_bios_separate(self) -> None:
        self.assertEqual(classify_pc(0x00000100), "bios")
        self.assertEqual(classify_pc(0x08004C82), "cpu-game-rom")
        self.assertNotEqual(classify_pc(0x00000100), classify_pc(0x08004C82))


if __name__ == "__main__":
    unittest.main()
