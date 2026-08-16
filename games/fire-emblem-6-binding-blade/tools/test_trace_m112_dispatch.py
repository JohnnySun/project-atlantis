#!/usr/bin/env python3
"""Regression tests for the FE6 M1.12 dispatch tracer boundaries."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/trace_m112_dispatch.py"

spec = importlib.util.spec_from_file_location("fe6_m112_dispatch", TOOL_PATH)
assert spec and spec.loader
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)


class AfejM112DispatchTests(unittest.TestCase):
    def test_sequence_parser_is_input_only(self) -> None:
        self.assertEqual(dispatch.parse_sequence("start,a,down"), ["start", "a", "down"])
        with self.assertRaises(ValueError):
            dispatch.parse_sequence("start,0x08098340")

    def test_callback_pointer_candidates_keep_thumb_bit_and_word_provenance(self) -> None:
        self.assertEqual(dispatch.CALLBACKS[0x08098340]["stored_pointer"], 0x08098341)
        self.assertEqual(dispatch.CALLBACKS[0x08098340]["pointer_word"], 0x08691230)
        self.assertEqual(dispatch.CALLBACKS[0x080984A8]["stored_pointer"], 0x080984A9)
        self.assertEqual(dispatch.CALLBACKS[0x080984A8]["pointer_word"], 0x08691358)

    def test_natural_generic_loader_candidate_has_static_boundary(self) -> None:
        self.assertEqual(dispatch.NATURAL_GENERIC_CALLSITE, 0x08009252)
        if not ROM_PATH.is_file():
            self.skipTest("local reviewed AFEJ ROM is not installed")
        candidate = dispatch._generic_loader_gate(ROM_PATH.read_bytes())
        self.assertTrue(candidate["direct_loader_callsite"])
        self.assertEqual(candidate["function_start"], "0x08009240")
        self.assertEqual(candidate["function_return"], "0x0800926e")

    def test_generic_call_chain_has_two_static_thumb_bl_boundaries(self) -> None:
        if not ROM_PATH.is_file():
            self.skipTest("local reviewed AFEJ ROM is not installed")
        chain = dispatch._generic_call_chain_gate(ROM_PATH.read_bytes())
        self.assertTrue(chain["wrapper_direct_callsite"])
        self.assertEqual(chain["wrapper_callsite"], "0x080117ba")
        self.assertEqual(chain["high_caller_function_start"], "0x08011778")
        self.assertEqual(chain["high_caller_function_return"], "0x0801180a")
        self.assertEqual(chain["wrapper_function_start"], "0x08009240")
        self.assertEqual(chain["all_wrapper_direct_callsite_count"], 6)
        self.assertEqual((0x080117BF & ~1) - 4, 0x080117BA)
        pointer = chain["high_caller_dispatch_pointer"]
        self.assertEqual(pointer["pointer_word"], "0x085c4414")
        self.assertEqual(pointer["file_offset"], "0x5c4414")
        self.assertEqual(pointer["stored_thumb_pointer"], "0x08011779")
        self.assertEqual(pointer["aligned_match_count"], 1)
        self.assertEqual(chain["dispatch_callsite"], "0x0800e02a")
        self.assertEqual(chain["dispatch_thunk"], "0x0809df14")
        self.assertEqual(chain["dispatch_thunk_instruction"], "bx r1")
        self.assertEqual(chain["dispatch_table_base"], "0x085c4164")
        self.assertEqual(chain["dispatch_table_stride"], 8)
        self.assertEqual(chain["high_pointer_table_index"], 86)
        self.assertEqual(dispatch.DISPATCH_OBJECT_ADDRESS, 0x02024750)
        self.assertEqual(chain["dispatch_object_writer_function"], "0x08003a04")
        self.assertEqual(chain["dispatch_object_writer_function_return"], "0x08003ad6")
        self.assertEqual(chain["dispatch_object_writer_instruction"], "0x08003a18")
        self.assertEqual(chain["dispatch_object_writer_instruction_text"], "str r1,[r0]")
        self.assertEqual(chain["dispatch_object_allocator_callsite"], "0x08003a0e")
        self.assertEqual(chain["dispatch_object_allocator_target"], "0x08003c54")
        allocator = chain["dispatch_object_allocator"]
        self.assertEqual(allocator["entry"], "0x08003c54")
        self.assertEqual(allocator["return"], "0x08003c7e")
        self.assertEqual(allocator["direct_callsite_count"], 1)
        self.assertEqual(allocator["direct_callsites"], ["0x08003a0e"])
        self.assertEqual(allocator["function_boundary"]["function_start"], "0x08003c54")
        self.assertEqual(allocator["function_boundary"]["function_return"], "0x08003c7e")
        self.assertEqual(allocator["global_address"], "0x020258c8")
        self.assertEqual(allocator["literal_pool_word"]["address"], "0x08003c74")
        self.assertEqual(allocator["literal_pool_word"]["value"], "0x020258c8")
        self.assertEqual(
            [row["literal_address"] for row in allocator["literal_loads"]],
            ["0x08003c74"] * 4,
        )
        self.assertEqual(
            [row["literal_value"] for row in allocator["literal_loads"]],
            ["0x020258c8"] * 4,
        )
        self.assertEqual(allocator["semantic_name_assigned"], False)
        entry = next(
            row for row in pointer["record_window"] if row["file_offset"] == "0x5c4414"
        )
        self.assertEqual(entry["stored_pointer"], "0x08011779")
        self.assertEqual(entry["flag"], "0x00000002")

    def test_stale_packet_filters_are_bounded(self) -> None:
        self.assertTrue(dispatch._packet_is_registers("0" * (len(dispatch.REG_NAMES) * 8)))
        self.assertFalse(dispatch._packet_is_registers("0e16"))

    def test_allocator_receipt_summary_checks_adjacent_invariants(self) -> None:
        receipts = [
            {
                "kind": "dispatch_object_allocator_entry",
                "pc": "0x08003c54",
                "derived_callsite": "0x08003a0e",
                "global_word_before": "0x020257c4",
                "pointed_value_before": "0x02023cc4",
            },
            {
                "kind": "dispatch_object_allocator_return",
                "pc": "0x08003c7e",
                "global_word_after": "0x020257c8",
                "return_value_r0": "0x02023cc4",
            },
        ]
        summary = dispatch._allocator_receipt_summary(receipts)
        self.assertEqual(summary["paired_count"], 1)
        self.assertTrue(summary["pair_order_ok"])
        self.assertEqual(summary["cursor_increment_ok_count"], 1)
        self.assertEqual(summary["return_value_matches_pointed_ok_count"], 1)
        self.assertTrue(summary["all_pairs_consistent"])


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM112StaticIntegrationTests(unittest.TestCase):
    def test_static_gate_is_reused_without_runtime_or_source_emission(self) -> None:
        report = dispatch.static_gate_report(ROM_PATH)
        self.assertEqual(report["loader"]["direct_callsite_count"], 163)
        self.assertFalse(report["semantic_boundary"]["source_bytes_emitted"])
        self.assertEqual(len(dispatch.CALLBACKS), 2)


if __name__ == "__main__":
    unittest.main()
