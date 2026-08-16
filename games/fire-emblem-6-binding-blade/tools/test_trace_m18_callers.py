#!/usr/bin/env python3
"""Regression tests for the FE6 M1.8 static caller proof."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/trace_m18_callers.py"

spec = importlib.util.spec_from_file_location("fe6_m18_trace", TOOL_PATH)
assert spec and spec.loader
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM18StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.records = trace.static_callsite_records(cls.rom)
        cls.by_callsite = {
            row["callsite"]: row for row in cls.records
        }

    def test_arm7_thumb_bl_targets_and_exact_scan_count(self) -> None:
        self.assertEqual(
            trace.thumb_bl_target(0xF77A, 0xFFDE, 0x08098B10),
            0x08013AD0,
        )
        self.assertEqual(
            trace.thumb_bl_target(0xF7EF, 0xFEA3, 0x08013B02),
            0x0800384C,
        )
        self.assertEqual(len(self.records), 163)
        self.assertIn("0x08098b10", self.by_callsite)
        self.assertIn("0x080985ec", self.by_callsite)

    def test_old_second_halfword_is_not_a_direct_callsite(self) -> None:
        self.assertNotIn("0x08013b04", self.by_callsite)
        self.assertTrue(trace.is_prologue_halfword(0xB5F0))
        self.assertTrue(trace.is_return_halfword(0x4770))

    def test_non_selector_candidate_has_local_function_bounds(self) -> None:
        row = self.by_callsite["0x080985ec"]
        self.assertEqual(row["function_start"], "0x080985d8")
        self.assertEqual(row["function_return"], "0x08098620")
        self.assertEqual(row["index_source"], "caller_argument_or_stack_word")
        self.assertIn("str r0, [r7]", " ".join(row["index_source_disassembly"]))

    def test_selector_candidate_remains_separate_function_group(self) -> None:
        row = self.by_callsite["0x08098b10"]
        self.assertEqual(row["function_start"], "0x08098afc")
        self.assertNotEqual(row["function_start"], self.by_callsite["0x080985ec"]["function_start"])

    def test_table_provenance_for_controlled_probe_index(self) -> None:
        provenance = trace.table_provenance(self.rom, 3086)
        self.assertEqual(provenance["table_entry"], "0x080f9394")
        self.assertEqual(provenance["source_pointer"], "0x080f2241")
        self.assertTrue(provenance["within_proven_table"])


if __name__ == "__main__":
    unittest.main()
