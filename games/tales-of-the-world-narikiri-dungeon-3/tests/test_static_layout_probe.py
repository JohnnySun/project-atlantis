#!/usr/bin/env python3
"""Tests for the fixed-offset, metadata-only layout probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import static_layout_probe  # noqa: E402


class StaticLayoutProbeTests(unittest.TestCase):
    def test_pair_summary_is_metadata_only_and_deterministic(self):
        result = static_layout_probe.summarize_pairs(bytes((1, 0, 2, 1, 1, 0)))
        self.assertEqual(result["byte_length"], 6)
        self.assertEqual(result["pair_count"], 3)
        self.assertEqual(result["unique_pair_count"], 2)
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)

    def test_pair_summary_rejects_odd_or_empty_input(self):
        with self.assertRaises(ValueError):
            static_layout_probe.summarize_pairs(b"")
        with self.assertRaises(ValueError):
            static_layout_probe.summarize_pairs(b"\x01")


if __name__ == "__main__":
    unittest.main()
