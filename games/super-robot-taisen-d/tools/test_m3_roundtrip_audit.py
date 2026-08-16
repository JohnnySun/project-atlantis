from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("m3_roundtrip_audit", HERE / "m3_roundtrip_audit.py")
assert SPEC and SPEC.loader
m3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m3)


class M3RoundtripAuditTest(unittest.TestCase):
    def test_expected_payload_uses_little_endian_code_units(self) -> None:
        allocations = {
            0x5B58: {"code_unit_little_endian": "0xE883"},
            0x5728: {"code_unit_little_endian": "0xE783"},
        }
        self.assertEqual(m3.expected_target_payload("存在", allocations), bytes.fromhex("83e883e7"))

    def test_expected_payload_rejects_missing_or_wide_allocation(self) -> None:
        with self.assertRaisesRegex(m3.RoundtripReject, "missing allocation"):
            m3.expected_target_payload("存", {})
        with self.assertRaisesRegex(m3.RoundtripReject, "wide allocation"):
            m3.expected_target_payload("存", {0x5B58: {"code_unit_little_endian": "0x408A"}})

    def test_changed_ranges_are_coalesced(self) -> None:
        self.assertEqual(m3.coalesce_ranges([5, 4, 6, 10, 12, 11]), [(4, 7), (10, 13)])
        self.assertTrue(m3.within_ranges(5, 2, [(4, 7)]))
        self.assertTrue(m3.within_ranges(5, 5, [(4, 7), (7, 10)]))
        self.assertFalse(m3.within_ranges(5, 3, [(4, 7)]))


if __name__ == "__main__":
    unittest.main()
