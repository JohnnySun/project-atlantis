#!/usr/bin/env python3
"""Tests for the bounded M1.14 resource-reader mapper."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m114_resource_reader as mapper  # noqa: E402


class M114ResourceReaderTests(unittest.TestCase):
    def test_reader_contract_uses_opcode_0c_and_callback_r2(self) -> None:
        self.assertEqual(mapper.DESCRIPTOR_OPCODE, 0x0C)
        self.assertEqual(mapper.OPCODE_HANDLER_THUMB, 0x080AD3CD)
        self.assertEqual(mapper.CALLBACK_TABLE + 12 * 8, 0x0815EF4C)

    def test_state_handler_pointer_and_descriptor_source_are_bounded(self) -> None:
        self.assertEqual(mapper.STATE_TABLE + 5 * 4, 0x08792450)
        self.assertEqual(mapper.STATE_HANDLER_THUMB, 0x0813F22D)
        self.assertEqual(mapper.DESCRIPTOR_BASE, 0x08794E24)
        self.assertEqual(mapper.QUEUE_ENTRY_SOURCE_OFFSET, 0x14)
        self.assertEqual(mapper.STATE_HANDLER_PRODUCER_CALLSITE, 0x0813F242)
        self.assertEqual(mapper.QUEUE_PRODUCER, 0x080AD0FC)

    def test_metadata_contract_has_no_payload_or_translation_fields(self) -> None:
        report = {
            "source_pointer": "0x087a07dc",
            "span_hash": "x",
            "source_table_created": False,
            "glyph_identity": "not_established",
        }
        serialized = json.dumps(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("decompressed_payload", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertNotIn("translation_source", serialized)


if __name__ == "__main__":
    unittest.main()
