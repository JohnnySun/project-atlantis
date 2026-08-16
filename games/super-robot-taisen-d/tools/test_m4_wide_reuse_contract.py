from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m4_wide_reuse_contract import WidePolicyReject, resolve_existing_wide


ROOT = Path(__file__).resolve().parents[1]


class M4WideReuseContractTest(unittest.TestCase):
    def test_unknown_codepoint_is_rejected(self) -> None:
        with self.assertRaisesRegex(WidePolicyReject, "unmapped_target_codepoint"):
            resolve_existing_wide(0x4E00, {})

    def test_report_is_source_safe_and_no_new_wide_slots(self) -> None:
        report = json.loads((ROOT / "research/m4-wide-reuse-contract.json").read_text(encoding="utf-8"))
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertEqual(report["identity_map"]["count"], 743)
        self.assertEqual(report["identity_map"]["runtime_confirmed_identity_count"], 1)
        self.assertEqual(report["policy"]["new_wide_slot_allocation"], "reject")
        self.assertTrue(report["gate"]["unknown_target_rejectable"])
        self.assertTrue(report["gate"]["wide_new_slots_zero"])


if __name__ == "__main__":
    unittest.main()
