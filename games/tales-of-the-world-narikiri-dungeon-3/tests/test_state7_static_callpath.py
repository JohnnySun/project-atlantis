#!/usr/bin/env python3
"""Tests for the fixed state-7 static callpath verifier."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import state7_static_callpath  # noqa: E402


class State7StaticCallpathTests(unittest.TestCase):
    def test_thumb_bl_decoder_rejects_non_call(self):
        self.assertIsNone(state7_static_callpath.decode_thumb_bl(b"\0" * 4, 0))

    def test_fixed_chains_end_at_reviewed_entries(self):
        self.assertEqual(
            state7_static_callpath.STATE7_TO_FORMATTER[-1][1],
            state7_static_callpath.FORMATTER_ENTRY,
        )
        self.assertEqual(
            state7_static_callpath.STATE7_TO_PARSER[-1][1],
            state7_static_callpath.PARSER_ENTRY,
        )
        self.assertEqual(len(state7_static_callpath.STATE7_TO_FORMATTER), 6)
        self.assertEqual(len(state7_static_callpath.STATE7_TO_PARSER), 5)

    def test_edge_row_rejects_wrong_expected_target(self):
        data = b"\0" * 16
        with self.assertRaisesRegex(ValueError, "fixed BL edge changed"):
            state7_static_callpath._edge_row(
                data,
                state7_static_callpath.ROM_BASE,
                state7_static_callpath.PARSER_ENTRY,
            )


if __name__ == "__main__":
    unittest.main()
