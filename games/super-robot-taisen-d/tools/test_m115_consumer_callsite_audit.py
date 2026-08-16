from __future__ import annotations

import unittest

from m115_consumer_callsite_audit import build_report


class M115ConsumerCallsiteAuditTest(unittest.TestCase):
    def test_real_bounded_audit_requires_runtime_when_no_direct_target(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        rom = (root / "games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes()
        report = build_report(rom)
        self.assertTrue(report["gate"]["rom_hash_match"])
        self.assertEqual(report["gate"]["direct_call_candidate_count"], 0)
        self.assertEqual(report["gate"]["pc_relative_literal_candidate_count"], 0)
        self.assertTrue(report["gate"]["runtime_caller_required"])
        self.assertFalse(report["source_policy"]["source_text_emitted"])


if __name__ == "__main__":
    unittest.main()
