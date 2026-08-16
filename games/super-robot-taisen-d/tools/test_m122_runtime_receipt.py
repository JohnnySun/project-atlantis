#!/usr/bin/env python3
"""Tests for the source-safe M1.22 runtime receipt boundary."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from m122_runtime_receipt import ReceiptError, build_receipt


class M122RuntimeReceiptTest(unittest.TestCase):
    def setUp(self) -> None:
        report_path = Path(__file__).resolve().parents[1] / "research/m19-runtime-qa.json"
        self.m19 = json.loads(report_path.read_text(encoding="utf-8"))
        self.kwargs = {
            "port": 24568,
            "sandbox_probe_status": "operation_not_permitted_before_connection",
            "authorized_probe_status": "connection_refused",
            "launcher_log_sha256": "2d11849c75e2beaeb000bb10893664a38d8db8ab524e0204a15fa1564af44d24",
            "launcher_log_bytes": 40,
        }

    def test_receipt_is_transport_negative_and_source_safe(self) -> None:
        receipt = build_receipt(self.m19, **self.kwargs)
        runtime = receipt["runtime_attempt"]
        self.assertEqual(runtime["result"], "transport_negative")
        self.assertFalse(runtime["listener_observed"])
        self.assertFalse(runtime["connection_established"])
        self.assertFalse(runtime["controlled_consumer_attempted"])
        self.assertFalse(receipt["source_policy"]["source_text_emitted"])
        self.assertFalse(receipt["source_policy"]["raw_memory_emitted"])
        self.assertFalse(receipt["source_policy"]["screenshots_emitted"])

    def test_static_target_and_adjacent_metadata_are_preserved(self) -> None:
        receipt = build_receipt(self.m19, **self.kwargs)
        self.assertEqual(receipt["source_policy"]["target_source_offset"], 526424)
        self.assertEqual(receipt["static_target"]["code_units"], ["0xE883", "0xE783"])
        self.assertTrue(receipt["static_adjacent"]["untouched"])
        self.assertEqual(receipt["rom_and_bps"]["bps_roundtrip"], "byte-identical; inherited static M1.8/M1.9 gate")
        self.assertNotIn('"text":', json.dumps(receipt, ensure_ascii=False))

    def test_unexpected_port_or_hash_is_rejected(self) -> None:
        with self.assertRaisesRegex(ReceiptError, "unexpected_dedicated_port"):
            build_receipt(self.m19, **{**self.kwargs, "port": 24567})
        altered = dict(self.m19)
        altered["game_code"] = "OTHER"
        with self.assertRaisesRegex(ReceiptError, "mismatch_game_code"):
            build_receipt(altered, **self.kwargs)


if __name__ == "__main__":
    unittest.main()
