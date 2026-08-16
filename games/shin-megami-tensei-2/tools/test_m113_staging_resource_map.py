#!/usr/bin/env python3
"""Tests for the bounded M1.13 staging/resource mapper."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m113_staging_resource_map as mapper  # noqa: E402


class M113StagingResourceMapTests(unittest.TestCase):
    def test_callback_group_shape_is_bounded(self) -> None:
        positions = [0x08000100 + index * mapper.RESOURCE_RECORD_STRIDE for index in range(8)]
        groups = mapper._groups_from_positions(
            positions,
            stride=mapper.RESOURCE_RECORD_STRIDE,
            record_count=mapper.RESOURCE_RECORDS_PER_GROUP,
        )
        self.assertEqual(groups, [positions])

    def test_staging_contract_keeps_arguments_provisional(self) -> None:
        self.assertEqual(mapper.STAGING_WRITER_THUMB, 0x0813EF65)
        self.assertEqual(mapper.STAGING_INTERMEDIATE, 0x0200AFC8)
        self.assertEqual(mapper.STAGING_BASE, 0x02001000)
        self.assertEqual(mapper.RESOURCE_RECORD_STRIDE, 0x18)

    def test_report_contract_has_no_payload_fields(self) -> None:
        report = {
            "scan_scope": {"raw_payload_emitted": False, "source_table_created": False},
            "resource_record_groups": [{"span_hash": "x", "span_length": 192}],
        }
        serialized = json.dumps(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("decompressed_payload", serialized)
        self.assertNotIn("decoded_text", serialized)


if __name__ == "__main__":
    unittest.main()
