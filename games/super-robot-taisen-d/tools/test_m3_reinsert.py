from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("m3_reinsert", HERE / "m3_reinsert.py")
assert SPEC and SPEC.loader
m3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m3)


class M3ReinsertTest(unittest.TestCase):
    def occupancy(self):
        return {
            "free_blank_slots": [543, 542, 541],
            "slot_to_units": {543: (0xE883,), 542: (0xE783,), 541: (0xE683,)},
        }

    def rows(self, codepoints):
        return {codepoint: tuple(0xFFFF if row in (2, 3) else 0 for row in range(16)) for codepoint in codepoints}

    def test_batch_reuses_one_slot_for_repeated_codepoint(self) -> None:
        allocations = m3.allocate_batch(("存在", "在有"), self.occupancy(), self.rows(map(ord, "存在有")))
        self.assertEqual(len(allocations), 3)
        self.assertEqual(allocations[ord("在")].slot, 542)
        self.assertEqual(allocations[ord("有")].slot, 541)

    def test_batch_fails_closed_when_capacity_is_exhausted(self) -> None:
        with self.assertRaisesRegex(m3.ReinsertReject, "capacity_exceeded"):
            m3.allocate_batch(("存在有無",), self.occupancy(), self.rows(map(ord, "存在有無")))

    def test_report_shape_is_source_safe(self) -> None:
        report = m3.build_report(
            b"base",
            b"patched",
            [
                {
                    "string_id": 1,
                    "source_raw_sha256": "a" * 64,
                    "source_ledger_sha256": "b" * 64,
                    "source_payload_length": 2,
                    "source_unit_count": 1,
                    "source_line_width": 8,
                    "source_terminator": "NUL",
                }
            ],
            {},
            {"source_sha256": "font", "license_sha256": "license"},
            {"free_blank_slots": [543], "protected_blank_referenced_slots": [0, 57, 58]},
            {1: b"ab"},
        )
        self.assertFalse(report["source_text_emitted"])
        self.assertNotIn("source", report)


if __name__ == "__main__":
    unittest.main()
