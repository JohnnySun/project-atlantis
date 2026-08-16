#!/usr/bin/env python3
"""ROM-independent tests for the bounded M2.9 state runtime harness."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("trace_m2_9_state_runtime.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_trace_m2_9_state_runtime", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load trace_m2_9_state_runtime.py")
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class M29StateRuntimeTest(unittest.TestCase):
    def test_breakpoint_map_is_bounded_and_game_specific(self) -> None:
        self.assertEqual(STATE.BREAKPOINTS["state_dispatch"], 0x0805D2EC)
        self.assertEqual(STATE.BREAKPOINTS["state_gate"], 0x0801A738)
        self.assertEqual(STATE.BREAKPOINTS["consumer_entry"], 0x08026054)
        self.assertEqual(STATE.breakpoint_name(0x0805D2ED), "state_dispatch")
        self.assertEqual(STATE.breakpoint_name(0x08026055), "consumer_entry")
        self.assertIsNone(STATE.breakpoint_name(0x0800D3FC))

    def test_index_gate_summary_does_not_turn_empty_cohort_into_proof(self) -> None:
        self.assertEqual(STATE.summarize_index_gate([]), "not-observed")
        self.assertEqual(
            STATE.summarize_index_gate([{"index_less_than_table_b_count": True}]),
            "bounded-observed-all-indexes-less-than-44",
        )
        self.assertEqual(
            STATE.summarize_index_gate([{"index_less_than_table_b_count": None}]),
            "bounded-observed-unknown-or-out-of-range",
        )

    def test_scope_constants_are_separate_from_state_byte(self) -> None:
        self.assertEqual(STATE.STATE_BYTE_ADDRESS, 0x030042D1)
        self.assertNotEqual(STATE.STATE_BYTE_ADDRESS, STATE.STATE_DISPATCH_ADDRESS)
        self.assertEqual(STATE.MAX_INDEX_HITS, 32)
        self.assertLessEqual(STATE.MAX_STOPS, 512)

    def test_runtime_receipt_schema_is_source_free(self) -> None:
        sample = {
            "state_values_observed": [0, 3],
            "natural_index_gate_status": "not-observed",
            "vram_before_sha256": "hash",
            "vram_after_sha256": "hash",
        }
        self.assertNotIn("source", sample)
        self.assertNotIn("bytes", sample)


if __name__ == "__main__":
    unittest.main()
