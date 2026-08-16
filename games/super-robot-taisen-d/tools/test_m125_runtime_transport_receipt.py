#!/usr/bin/env python3
"""Tests for the corrected-port M1.25 transport receipt."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from m125_runtime_transport_receipt import TransportReceiptReject, build_receipt


ROOT = Path(__file__).resolve().parents[1]


class M125RuntimeTransportReceiptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m122 = json.loads((ROOT / "research/m122-runtime-receipt.json").read_text(encoding="utf-8"))
        self.kwargs = {
            "source_literal_port": 2348,
            "binary_sha256": "fe11732d1686b66bb5304cdbe13636e7e9daf648196e13c2b5f110e71841cc9e",
            "log_sha256": "1cb2ae5938e8f62ef172f7846737f83b09c60f21ed58393795590dc1b3a69986",
            "log_bytes": 20,
            "listener_observed": False,
            "rom_descriptor_observed": False,
            "probe_status": "connection_refused",
        }

    def test_corrected_port_remains_transport_negative(self) -> None:
        report = build_receipt(self.m122, **self.kwargs)
        self.assertEqual(report["transport_correction"]["source_listener_port"], 2348)
        self.assertFalse(report["transport_correction"]["config_override_consumed_by_this_build"])
        self.assertFalse(report["runtime_attempt"]["listener_observed"])
        self.assertEqual(report["runtime_attempt"]["result"], "transport_negative_after_port_correction")
        self.assertFalse(report["runtime_attempt"]["rom_or_translation_failure"])
        self.assertFalse(report["source_policy"]["source_text_emitted"])

    def test_port_or_positive_observation_is_rejected(self) -> None:
        with self.assertRaisesRegex(TransportReceiptReject, "source_listener_port_mismatch"):
            build_receipt(self.m122, **{**self.kwargs, "source_literal_port": 24568})
        with self.assertRaisesRegex(TransportReceiptReject, "m122_negative_boundary_changed"):
            build_receipt(self.m122, **{**self.kwargs, "listener_observed": True})


if __name__ == "__main__":
    unittest.main()
