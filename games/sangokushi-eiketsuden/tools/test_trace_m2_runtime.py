#!/usr/bin/env python3
"""ROM-independent tests for the bounded B3EJ M2 trace harness."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("trace_m2_runtime.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_trace_m2_runtime", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load trace_m2_runtime.py")
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


class TraceM2RuntimeTest(unittest.TestCase):
    def test_sequence_expands_without_keeping_source_text(self) -> None:
        phases = TRACE.parse_sequence("none:2,start:3,none:1")
        self.assertEqual(TRACE.expand_sequence(phases), ["none", "none", "start", "start", "start", "none"])
        self.assertEqual(TRACE.key_value("none"), 0x03FF)
        self.assertEqual(TRACE.key_value("start"), 0x03F7)

    def test_candidate_addresses_use_rom_pointer_space(self) -> None:
        candidate = TRACE.candidate_addresses()
        self.assertEqual(candidate["table_gba_address"], 0x080D1FFC)
        self.assertEqual(candidate["record_gba_address"], 0x08078528)
        self.assertEqual(candidate["record_payload_length"], 14)
        self.assertNotIn("text", candidate)

    def test_vram_summary_reports_delta_not_bytes(self) -> None:
        before = bytes(64)
        after = bytearray(before)
        after[0] = 1
        after[33] = 2
        summary = TRACE.vram_summary(before, bytes(after))
        self.assertEqual(summary["changed_bytes"], 2)
        self.assertEqual(summary["changed_4bpp_tile_count"], 2)
        self.assertNotIn("data", summary)


if __name__ == "__main__":
    unittest.main()
