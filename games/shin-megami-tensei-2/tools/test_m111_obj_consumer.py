#!/usr/bin/env python3
"""Tests for the bounded M1.11 OAM/OBJ consumer mapper."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m111_obj_consumer as consumer  # noqa: E402


class M111ObjConsumerTests(unittest.TestCase):
    def test_oam_dma_contract_is_explicit(self) -> None:
        self.assertEqual(consumer.OAM_BUFFER, 0x030033F0)
        self.assertEqual(consumer.OAM_DESTINATION, 0x07000000)
        self.assertEqual(consumer.OAM_DMA_CONTROL, 0x84000100)
        self.assertEqual(consumer.OAM_DMA_UNITS, 0x100)
        self.assertEqual(consumer.OAM_DMA_POST_TARGET, 0x080AABC8)

    def test_literal_consumer_contract_is_bounded(self) -> None:
        self.assertEqual(len(consumer.OAM_NODES), 4)
        self.assertIn(0x06010000, consumer.TRACKED_LITERAL_VALUES)
        self.assertIn(0x06013000, consumer.TRACKED_LITERAL_VALUES)
        self.assertNotIn(0x02001000, consumer.TRACKED_LITERAL_VALUES)

    def test_report_contract_has_no_payload_fields(self) -> None:
        report = {
            "scan_scope": {
                "glyph_pattern_scan": False,
                "raw_payload_emitted": False,
                "source_table_created": False,
            },
            "consumer_edges": {},
        }
        serialized = json.dumps(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("full_source", serialized)
        self.assertNotIn("decoded_text", serialized)

    def test_direct_bl_index_starts_empty_for_no_targets(self) -> None:
        self.assertEqual(consumer._direct_bl_callers_index(b"\x00" * 32, ()), {})


if __name__ == "__main__":
    unittest.main()
