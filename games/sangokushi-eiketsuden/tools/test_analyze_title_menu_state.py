#!/usr/bin/env python3
"""ROM-independent contract tests for the bounded title/menu state analyzer."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("analyze_title_menu_state.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_title_menu_state", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load analyze_title_menu_state.py")
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


class TitleMenuStateTest(unittest.TestCase):
    def test_dispatcher_and_data_gap_are_separate(self) -> None:
        self.assertEqual(STATE.STATE_DISPATCH_SPAN, (0x05D2EC, 0x05D310))
        self.assertEqual(STATE.STATE_DATA_GAP, (0x05D310, 0x05D348))
        self.assertLess(STATE.STATE_DISPATCH_SPAN[1], STATE.STATE_DATA_GAP[1])
        self.assertEqual(STATE.STATE_BYTE_ADDRESS, 0x030042D1)

    def test_state_table_has_twelve_bounded_targets(self) -> None:
        self.assertEqual(STATE.STATE_COUNT, 12)
        self.assertEqual(STATE.STATE_TABLE_OFFSET, 0x05D318)
        self.assertEqual(STATE.STATE_TABLE_END, 0x05D348)
        self.assertEqual(len(STATE.EXPECTED_HANDLER_TARGETS), 12)
        self.assertEqual(len(set(STATE.EXPECTED_HANDLER_TARGETS)), 10)
        self.assertEqual(STATE.EXPECTED_HANDLER_TARGETS[0], 0x0805D348)
        self.assertEqual(STATE.EXPECTED_HANDLER_TARGETS[-1], 0x0805DF74)

    def test_direct_callers_and_owner_are_explicit(self) -> None:
        self.assertEqual(
            [probe["file_offset"] for probe in STATE.STATE_CALLER_PROBES],
            [0x05E07C, 0x05FB06],
        )
        self.assertEqual(STATE.TITLE_MENU_OWNER_CALLER["file_offset"], 0x05CA94)
        self.assertEqual(STATE.TITLE_MENU_OWNER_CALLER["target"], 0x0805D10C)
        self.assertEqual(STATE.STATE_RESET_HANDLER_SPAN, (0x05DF74, 0x05DF88))

    def test_scope_does_not_claim_event_index_or_semantics(self) -> None:
        self.assertNotEqual(STATE.STATE_COUNT, 44)
        self.assertEqual(STATE.HANDLER_ENTRY_PROBE_BYTES, 8)
        self.assertEqual(STATE.HANDLER_CODE_REGION, (0x05D348, 0x05E078))


if __name__ == "__main__":
    unittest.main()
