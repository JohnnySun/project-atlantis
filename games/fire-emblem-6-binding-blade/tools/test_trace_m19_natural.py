#!/usr/bin/env python3
"""Regression tests for the FE6 M1.9 natural-trace boundaries."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/trace_m19_natural.py"

spec = importlib.util.spec_from_file_location("fe6_m19_trace", TOOL_PATH)
assert spec and spec.loader
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM19StaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = ROM_PATH.read_bytes()
        cls.report = trace.static_candidate_report(cls.rom)

    def test_candidate_direct_callers_are_arm7_thumb_bl_rows(self) -> None:
        functions = self.report["candidate_functions"]
        primary = functions["0x080985d8"]
        alternate = functions["0x08098624"]
        primary_calls = {row["callsite"] for row in primary["direct_callers"]}
        alternate_calls = {row["callsite"] for row in alternate["direct_callers"]}
        self.assertEqual(len(primary_calls), 10)
        self.assertIn("0x0809829e", primary_calls)
        self.assertIn("0x0809853e", primary_calls)
        self.assertEqual(alternate_calls, {"0x0809837c"})
        for row in primary["direct_callers"]:
            self.assertEqual(row["target"], "0x080985d8")
            self.assertTrue(row["callsite"].startswith("0x080"))
            self.assertEqual(len(row["halfwords"]), 2)
        for row in alternate["direct_callers"]:
            self.assertEqual(row["target"], "0x08098624")
            self.assertTrue(row["callsite"].startswith("0x080"))
            self.assertEqual(len(row["halfwords"]), 2)

    def test_m19_keeps_requested_hit_addresses_distinct(self) -> None:
        self.assertEqual(
            trace.HIT_ADDRESSES,
            (0x080985EC, 0x08098624, 0x08098B10, 0x08013AD0),
        )
        self.assertNotIn(0x08013B04, trace.HIT_ADDRESSES)

    def test_runtime_breakpoints_include_consumer_and_actual_cpu_writer(self) -> None:
        client = object.__new__(trace.NaturalTrace)
        self.assertIn(trace.CONSUMER_BYTE_READ, client.runtime_breakpoints)
        self.assertIn(trace.CONSUMER_CONTROL_BRANCH, client.runtime_breakpoints)
        self.assertIn(trace.RENDERER_KERNEL, client.runtime_breakpoints)
        self.assertIn(trace.RENDERER_WRITE, client.runtime_breakpoints)
        self.assertEqual(trace.RENDERER_WRITE, 0x080995A6)

    def test_source_window_and_gba_ram_validation_are_bounded(self) -> None:
        self.assertTrue(trace._valid_region(0x080F2256, 0x100))
        self.assertTrue(trace._valid_region(trace.BUFFER, 4))
        self.assertTrue(trace._valid_region(0x06014000, 4))
        self.assertFalse(trace._valid_region(0x00000000, 4))

    def test_sequence_parser_is_input_only(self) -> None:
        self.assertEqual(trace.parse_sequence("start,a,down"), ["start", "a", "down"])
        with self.assertRaises(ValueError):
            trace.parse_sequence("start,3086")

    def test_transport_drains_duplicate_watch_stop_before_register_or_memory(self) -> None:
        class FakeClient:
            def __init__(self, responses: list[str]) -> None:
                self.responses = responses

            def request(self, _payload: str) -> str:
                return self.responses.pop(0)

        register_packet = "00" * (len(trace.REG_NAMES) * 4)
        registers = trace.read_registers_after_stop(
            FakeClient(["T05rwatch:02029404;", register_packet])
        )
        self.assertEqual(registers["pc"], 0)
        memory = trace.read_memory_after_stop(
            FakeClient(["S05", "aabb"]), 0x02029404, 2
        )
        self.assertEqual(memory, b"\xaa\xbb")


if __name__ == "__main__":
    unittest.main()
