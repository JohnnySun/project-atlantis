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

    def test_m22_breakpoints_normalize_thumb_addresses(self) -> None:
        self.assertEqual(TRACE.M22_BREAKPOINTS["output_writer"], 0x0800CAD8)
        self.assertEqual(TRACE.M22_BREAKPOINTS["glyph_expand"], 0x080650DC)
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x0800CAD9), "output_writer")
        self.assertEqual(TRACE._pipeline_breakpoint_name(0x080650DD), "glyph_expand")
        self.assertEqual(TRACE.M22_SENTINEL_CODES[0x9594], "U+90E8")
        self.assertNotIn("text", TRACE.M22_BREAKPOINTS)

    def test_m22_index_metadata_keeps_local_and_table_bounds_separate(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int) -> bytes:
                fields = {
                    0x02000100: (2).to_bytes(2, "little"),
                    0x02000102: (6).to_bytes(2, "little"),
                    0x02000104: (1).to_bytes(2, "little"),
                    0x02000106: (1).to_bytes(2, "little"),
                    0x02000108: (1).to_bytes(2, "little"),
                    0x02000124: (0).to_bytes(2, "little"),
                    0x0200011C: (0x03000200).to_bytes(4, "little"),
                    0x03000205: bytes([0x85]),
                }
                return fields[address][:length]

        metadata = TRACE._r6_metadata(
            FakeClient(),
            {
                "r6": 0x02000100,
                "r7": 0x03000205,
                "r0": 0,
                "lr": 0x08026040,
            },
            entry_pc=False,
        )
        self.assertEqual(metadata["event_array_index"], 5)
        self.assertEqual(metadata["actual_index"], 5)
        self.assertTrue(metadata["event_array_index_less_than_local_length"])
        self.assertTrue(metadata["index_less_than_table_b_count"])
        self.assertEqual(metadata["bound_status"], "runtime-observed-only; not-static-proof")


if __name__ == "__main__":
    unittest.main()
