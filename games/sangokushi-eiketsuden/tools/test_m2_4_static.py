#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ M2.4 caller/state gate."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("m2_4_static.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_m2_4_static", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load m2_4_static.py")
STATIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATIC)


class M24StaticTest(unittest.TestCase):
    def test_reviewed_spans_leave_jump_table_out_of_disassembly(self) -> None:
        self.assertEqual(STATIC.DISPATCHER_DATA_GAP, (0x01A51C, 0x01A588))
        self.assertEqual(STATIC.INITIALIZER_DATA_GAPS[0], (0x026546, 0x026554))
        self.assertEqual(STATIC.DESCRIPTOR_WRAPPER_SPAN, (0x01A4B8, 0x01A4CC))
        self.assertLess(STATIC.DESCRIPTOR_WRAPPER_SPAN[0], STATIC.DESCRIPTOR_WRAPPER_SPAN[1])

    def test_normal_chain_is_indirect_and_keeps_event_bound_open(self) -> None:
        self.assertEqual(STATIC.CONSUMER_ENTRY, 0x026054)
        self.assertEqual(STATIC.DESCRIPTOR_CONSUMER_FIELD, 0x10)
        self.assertEqual(STATIC.DESCRIPTOR_COUNT_FIELD, 0x02)
        self.assertEqual(STATIC.DESCRIPTOR_EVENT_BUFFER_FIELD, 0x1C)
        self.assertEqual(STATIC.EVENT_SELECTOR_VALUES[0], 0)
        self.assertEqual(STATIC.EVENT_SELECTOR_VALUES[-1], 17)
        self.assertNotIn(44, STATIC.EVENT_SELECTOR_VALUES)

    def test_state_and_poll_gate_addresses_are_separate_from_table_index(self) -> None:
        self.assertEqual(STATIC.STATE_LOOP_ENTRY, 0x01A738)
        self.assertEqual(STATIC.EVENT_POLL_ENTRY, 0x01A12C)
        self.assertEqual(STATIC.STATE_OWNER_ENTRY, 0x021A44)
        self.assertEqual(STATIC.STATE_OWNER_TABLE, 0x0203544C)
        self.assertEqual(STATIC.DISPATCH_VENEER, 0x0806ED80)
        self.assertEqual(STATIC.STATE_CHECK_VENEER, 0x0806ED7C)
        self.assertEqual(STATIC.TABLE_B_COUNT, 44)


if __name__ == "__main__":
    unittest.main()
