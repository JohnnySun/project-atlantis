#!/usr/bin/env python3
"""Pure tests for the bounded M1.6 source cohort builder."""

from __future__ import annotations

import unittest

from build_m16_cohort import CENTER, build_rows, bounded_candidate, select_cohort


def records() -> dict[int, dict[str, object]]:
    return {
        offset: {"offset": offset, "text": "ラ" if offset == CENTER else "A"}
        for offset in range(CENTER - 7 * 4, CENTER + 8 * 4, 4)
    }


class M16CohortTest(unittest.TestCase):
    def test_selection_is_contiguous_and_contains_center(self) -> None:
        selected = select_cohort(records(), CENTER, 8)
        self.assertEqual(len(selected), 8)
        self.assertIn(CENTER, [int(row["offset"]) for row in selected])

    def test_selection_rejects_unbounded_size(self) -> None:
        with self.assertRaises(ValueError):
            select_cohort(records(), CENTER, 7)
        with self.assertRaises(ValueError):
            select_cohort(records(), CENTER, 33)

    def test_candidate_summary_drops_context_text(self) -> None:
        row = bounded_candidate(
            {
                "mode": "thumb",
                "instruction_offset": 0x120,
                "literal_offset": 0x140,
                "target_offset": CENTER,
                "literal_kind": "literal_pool",
                "source_offset_exact": True,
                "pointer_table_start": None,
                "function_start": 0x100,
                "confidence": "high",
                "score": 8,
                "context": [{"mnemonic": "ldr", "op_str": "r0, [pc]"}],
                "following_calls": [
                    {"address": 0x08000130, "target": 0x08000200, "mnemonic": "bl"}
                ],
            }
        )
        self.assertEqual(row["instruction_offset"], "0x00000120")
        self.assertEqual(row["following_calls"][0]["address"], "0x08000130")
        self.assertNotIn("context", row)

    def test_center_has_m15_runtime_provenance_only(self) -> None:
        rows = build_rows(records(), {}, center=CENTER, size=8)
        center = next(row for row in rows if row["string_id"] == "0x0007B3FC")
        self.assertEqual(
            center["pointer_caller_provenance"]["status"], "positive_direct_copy_m1.5"
        )
        self.assertEqual(center["pointer_caller_provenance"]["runtime"]["consumer"], "0x08007E04")
        self.assertNotIn("text", center)


if __name__ == "__main__":
    unittest.main()
