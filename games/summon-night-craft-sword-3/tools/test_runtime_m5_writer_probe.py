#!/usr/bin/env python3
"""Unit tests for the B3CJ M5.5 controlled runtime probe."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("runtime_m5_writer_probe.py")
SPEC = importlib.util.spec_from_file_location("runtime_m5_writer_probe", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {TOOL_PATH}")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class RuntimeM5WriterProbeTest(unittest.TestCase):
    def test_glyph_pointer_formula_is_cell_aligned(self) -> None:
        pointer = PROBE.EXPECTED_FONT_BASE + 0x849 * PROBE.FONT_CELL_STRIDE
        self.assertEqual(PROBE.glyph_id_from_pointer(pointer, PROBE.EXPECTED_FONT_BASE), 0x849)

    def test_glyph_pointer_rejects_non_cell_alignment(self) -> None:
        with self.assertRaises(ValueError):
            PROBE.glyph_id_from_pointer(PROBE.EXPECTED_FONT_BASE + 1, PROBE.EXPECTED_FONT_BASE)

    def test_summary_contains_hash_and_no_payload(self) -> None:
        summary = PROBE.summarize(bytes((0, 1, 2, 0)), 0x06010000)
        self.assertEqual(summary["nonzero_bytes"], 2)
        self.assertNotIn("data", summary)
        self.assertNotIn("source_text", summary)

    def test_continue_until_pc_ignores_unwanted_stop(self) -> None:
        class Stops:
            def __init__(self) -> None:
                self.values = [
                    ("S05k", {"pc": 0x08000000, "r0": 0, "r1": 0, "r2": 0}),
                    ("S05k", {"pc": PROBE.RETURN_SENTINEL, "r0": 0, "r1": 0, "r2": 0}),
                ]
                self.current = self.values[0][1]

            def continue_until_stop(self, _timeout: float) -> str:
                packet, self.current = self.values.pop(0)
                return packet

            def read_registers(self) -> dict[str, int]:
                return self.current

        packet, registers = PROBE.continue_until_pc(Stops(), (PROBE.RETURN_SENTINEL,), timeout=0.1)
        self.assertEqual(packet, "S05k")
        self.assertEqual(PROBE._pc(registers), PROBE.RETURN_SENTINEL)

    def test_fixed_runtime_contract_is_explicit(self) -> None:
        self.assertEqual(PROBE.TARGET_ID, "b3cj:t2:024:0x0064")
        self.assertEqual(PROBE.CHANGED_GLYPH_IDS, (0x847, 0x848, 0x849))
        self.assertEqual(PROBE.ADJACENT_GLYPH_ID, 0x846)
        self.assertEqual(PROBE.TARGET_CODEPAGE_BYTES.hex(), "ec64ec65ec660000")
        self.assertEqual(PROBE.VRAM_LENGTH, 0x180)
        self.assertEqual(PROBE.PALETTE_LENGTH, 0x400)


if __name__ == "__main__":
    unittest.main()
