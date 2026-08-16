#!/usr/bin/env python3
"""Pure tests for bounded M1.11 layout-contract helpers."""

from __future__ import annotations

import unittest

from m111_layout_contract import LayoutContractError, width_summary


class M111LayoutContractTest(unittest.TestCase):
    def test_width_summary_is_observed_bound_not_engine_limit(self) -> None:
        summary = width_summary((8, 12, 20))
        self.assertEqual(summary["minimum_pixels"], 8)
        self.assertEqual(summary["maximum_pixels"], 20)
        self.assertEqual(summary["maximum_observed_tile_columns"], 3)
        self.assertEqual(summary["maximum_observed_tile_bytes"], 192)
        self.assertFalse(summary["engine_limit_proven"])

    def test_width_summary_rejects_empty_evidence(self) -> None:
        with self.assertRaisesRegex(LayoutContractError, "width set is empty"):
            width_summary(())


if __name__ == "__main__":
    unittest.main()
