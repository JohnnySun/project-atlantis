#!/usr/bin/env python3
"""Tests for the bounded format-loop strict-record runtime probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import format_record_runtime_probe  # noqa: E402


class FormatRecordRuntimeProbeTests(unittest.TestCase):
    def test_format_callsite_is_limited_to_reviewed_direct_callers(self):
        self.assertEqual(
            format_record_runtime_probe.format_callsite_from_lr(0x08001656),
            0x08001652,
        )
        self.assertIsNone(
            format_record_runtime_probe.format_callsite_from_lr(0x08009999)
        )

    def test_source_classification_requires_exact_record_start(self):
        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 4,
            }
        }
        row = format_record_runtime_probe.classify_source_pointer(
            0x08146EE0, records
        )
        self.assertEqual(row["status"], "strict-record-start")
        self.assertEqual(
            format_record_runtime_probe.classify_source_pointer(
                0x08146EE1, records
            )["status"],
            "strict-window-nonstrict-offset",
        )

    def test_asset_contract_is_bounded_and_metadata_only(self):
        row = format_record_runtime_probe.classify_asset_pointer(0x080E1644)
        self.assertEqual(row["status"], "asset-slot-address-shaped")
        self.assertNotIn("bytes", row)
        self.assertNotIn("raw", row)


if __name__ == "__main__":
    unittest.main()
