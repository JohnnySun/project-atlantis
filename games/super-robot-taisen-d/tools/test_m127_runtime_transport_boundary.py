from __future__ import annotations

import json
import unittest
from pathlib import Path

from m127_runtime_transport_boundary import build_report


ROOT = Path(__file__).resolve().parents[1]


class M127RuntimeTransportBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m125 = json.loads(
            (ROOT / "research/m125-runtime-transport-receipt.json").read_text(encoding="utf-8")
        )

    def test_receipt_keeps_listener_and_runtime_evidence_separate(self) -> None:
        report = build_report(self.m125)
        self.assertEqual(report["runtime_coverage"]["listener_connect_success_count"], 2)
        self.assertFalse(report["runtime_coverage"]["font_base_observed"])
        self.assertFalse(report["runtime_coverage"]["target_record_verified"])
        self.assertFalse(report["gate"]["gdb_stop_protocol_verified"])
        self.assertFalse(report["gate"]["rom_or_translation_failure"])
        self.assertEqual(report["external_blocker"]["status"], "runtime_stop_protocol_unavailable")

    def test_tracked_receipt_is_source_safe_and_not_release_ready(self) -> None:
        report = json.loads(
            (ROOT / "research/m127-runtime-transport-boundary.json").read_text(encoding="utf-8")
        )
        self.assertFalse(report["source_policy"]["source_text_emitted"])
        self.assertFalse(report["source_policy"]["raw_memory_emitted"])
        self.assertFalse(report["gate"]["m127_complete"])
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn('"source":', serialized)
        self.assertNotIn('"targets":', serialized)


if __name__ == "__main__":
    unittest.main()
