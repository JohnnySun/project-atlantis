#!/usr/bin/env python3
"""Offline tests for the bounded B3TJ state probe."""

import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import state_probe  # noqa: E402


class StateProbeTests(unittest.TestCase):
    def test_signed_state_index_matches_thumb_ldrsb(self):
        self.assertEqual(state_probe.signed_byte(0x04), 4)
        self.assertEqual(state_probe.signed_byte(0xFF), -1)
        self.assertEqual(state_probe.signed_byte(0x80), -128)

    def test_state_metadata_uses_next_byte_for_dispatch_index(self):
        row = state_probe.state_metadata(bytes([4, 4, 0xFF]))
        self.assertEqual(row["next_state"], 4)
        self.assertEqual(row["current_state"], 4)
        self.assertEqual(row["previous_state"], -1)
        self.assertEqual(row["dispatch_index_signed"], 4)
        self.assertEqual(row["dispatch_entry"], "0x08741DA4")

    def test_invalid_signed_index_is_not_expanded_into_a_scan(self):
        row = state_probe.state_metadata(bytes([0xFF, 4, 4]))
        self.assertEqual(row["dispatch_index_signed"], -1)
        self.assertEqual(row["dispatch_status"], "signed-index-out-of-bounds")
        self.assertNotIn("dispatch_entry", row)

    def test_sequence_is_bounded_without_rewriting_key_phases(self):
        bounded = state_probe._sequence_events(
            [("start", 3), ("none", 4), ("a", 2)], 5
        )
        self.assertEqual(bounded, [("start", 3), ("none", 2)])


if __name__ == "__main__":
    unittest.main()
