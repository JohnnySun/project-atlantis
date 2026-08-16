#!/usr/bin/env python3
"""Regression tests for the FE6 M1.7 caller/provenance tracer."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/trace_m17_callers.py"

spec = importlib.util.spec_from_file_location("fe6_m17_trace", TOOL_PATH)
assert spec and spec.loader
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM17StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()

    def test_static_call_targets_and_table_boundary(self) -> None:
        proof = trace.static_proof(self.rom)
        self.assertEqual(proof["high_callsite_bl_target"], "0x08013ad0")
        self.assertEqual(proof["loader_bl_target"], "0x0800384c")
        self.assertEqual(proof["pointer_table_domain"], [0, 3342])
        self.assertEqual(proof["caller_index_table_values_0_7"], [
            3080, 3081, 3082, 3084, 3085, 3086, 3087, 3083
        ])

    def test_actual_bl_start_is_not_old_second_halfword(self) -> None:
        self.assertEqual(trace.LOADER_BL, 0x08013B02)
        self.assertNotEqual(trace.LOADER_BL, 0x08013B04)
        self.assertEqual(trace.static_proof(self.rom)["old_provenance_halfwords"], [
            "0xb084", "0x466f"
        ])

    def test_loader_return_lr_proves_high_callsite(self) -> None:
        self.assertEqual(
            trace.loader_caller_from_lr(0x08098B15), "0x08098b10"
        )
        self.assertIsNone(trace.loader_caller_from_lr(0x08002B06))

    def test_buffer_marker_offsets_are_bounded_to_logical_payload(self) -> None:
        summary = trace.buffer_summary(bytes((0x12, 0x01, 0x34, 0x00)) + bytes(32))
        self.assertEqual(summary["buffer_length"], 36)
        self.assertEqual(summary["logical_terminator_offset"], 3)
        self.assertEqual(summary["control_marker_offsets"]["0x00"], [3])
        self.assertEqual(summary["control_marker_offsets"]["0x01"], [1])


if __name__ == "__main__":
    unittest.main()
