#!/usr/bin/env python3
"""Small ROM-independent tests for the B3CJ reconnaissance helper."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("inspect_rom.py")
SPEC = importlib.util.spec_from_file_location("inspect_rom", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load inspect_rom.py")
INSPECT_ROM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECT_ROM)


class InspectRomTest(unittest.TestCase):
    def test_gba_header_checksum_uses_a0_through_bc(self) -> None:
        data = bytearray(0x200)
        data[0xA0:0xAC] = b"CRAFTSWORD H"
        data[0xAC:0xB0] = b"B3CJ"
        expected = (0x19 - sum(data[0xA0:0xBD])) & 0xFF
        self.assertEqual(INSPECT_ROM.gba_header_checksum(data), expected)

    def test_shift_jis_probe_reports_only_bounded_offsets(self) -> None:
        data = b"x" + "はい".encode("shift_jis") + b"y" + "はい".encode("shift_jis")
        self.assertEqual(INSPECT_ROM.scan_sjis_probes(data)["yes"], [1, 6])

    def test_pointer_runs_require_four_words(self) -> None:
        pointer = (0x08000000).to_bytes(4, "little")
        self.assertEqual(
            INSPECT_ROM.scan_pointer_runs(pointer * 3)["runs_at_least_4_words"],
            0,
        )
        self.assertEqual(
            INSPECT_ROM.scan_pointer_runs(pointer * 4)["runs_at_least_4_words"],
            1,
        )

    def test_thumb_swi_candidates_are_counted_by_immediate(self) -> None:
        report = INSPECT_ROM.scan_thumb_swi_candidates(bytes.fromhex("00 df 10 df"))
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["by_immediate"], {"0x00": 1, "0x10": 1})


if __name__ == "__main__":
    unittest.main()
