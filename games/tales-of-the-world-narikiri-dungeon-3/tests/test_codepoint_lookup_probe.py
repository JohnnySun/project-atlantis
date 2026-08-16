#!/usr/bin/env python3
"""Tests for the fixed B3TJ codepoint lookup probe."""

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import codepoint_lookup_probe  # noqa: E402


class CodepointLookupProbeTests(unittest.TestCase):
    def test_lookup_table_summary_is_metadata_only(self):
        data = bytes(range(32)) * 8
        result = codepoint_lookup_probe.summarize_table(
            data, codepoint_lookup_probe.ROM_BASE, window=0x100
        )
        self.assertEqual(result["halfword_count"], 0x80)
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)

    def test_lookup_table_rejects_non_rom_address(self):
        with self.assertRaises(ValueError):
            codepoint_lookup_probe.summarize_table(b"\0" * 0x100, 0x03000060)

    def test_reviewed_pool_and_callsite_are_fixed(self):
        self.assertEqual(len(codepoint_lookup_probe.POINTER_POOL), 5)
        self.assertIn(0x741D80, codepoint_lookup_probe.POINTER_POOL)
        self.assertEqual(codepoint_lookup_probe.LOOKUP_CALLSITES[0], 0x15C4)


if __name__ == "__main__":
    unittest.main()
