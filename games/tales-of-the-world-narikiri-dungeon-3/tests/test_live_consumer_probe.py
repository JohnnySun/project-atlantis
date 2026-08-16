#!/usr/bin/env python3
"""Offline tests for the bounded parser-to-glyph runtime probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import live_consumer_probe  # noqa: E402


class LiveConsumerProbeTests(unittest.TestCase):
    def test_fixed_consumer_edges_are_narrow_and_thumb_aligned(self):
        self.assertEqual(live_consumer_probe.PARSER_ENTRY, 0x080025CC)
        self.assertEqual(live_consumer_probe.FORMATTER_ENTRY, 0x080014F4)
        self.assertEqual(live_consumer_probe.GLYPH_ENTRY, 0x08001414)
        self.assertEqual(
            live_consumer_probe.GLYPH_STORE_POINTS,
            {
                0x080011F6: "glyph_store_011F6",
                0x08001236: "glyph_store_01236",
                0x08001278: "glyph_store_01278",
                0x080012BE: "glyph_store_012BE",
            },
        )
        self.assertTrue(all(address & 1 == 0 for address in live_consumer_probe.GLYPH_STORE_POINTS))

    def test_classification_requires_exact_strict_start(self):
        rom = bytearray(0x1C4000)
        rom[0x140D68:0x140D6D] = b"\x82\xa0\x82\xa2\0"
        records = {
            0x140D68: {
                "string_id": "sjis:0x140D68",
                "source_span_sha256": "hash",
            }
        }
        exact = live_consumer_probe.classify_pointer(0x08140D68, bytes(rom), records)
        self.assertEqual(exact["status"], "strict-record-start")
        self.assertEqual(exact["record"]["string_id"], "sjis:0x140D68")
        adjacent = live_consumer_probe.classify_pointer(0x08140D69, bytes(rom), records)
        self.assertEqual(adjacent["status"], "strict-window-nonstrict-offset")

    def test_ram_and_outside_pointers_do_not_become_text(self):
        rom = bytes(0x1C4000)
        self.assertEqual(
            live_consumer_probe.classify_pointer(0x03001468, rom, {})["status"],
            "ram-pointer",
        )
        self.assertEqual(
            live_consumer_probe.classify_pointer(0x08001234, rom, {})["status"],
            "rom-outside-tested-text-windows",
        )

    def test_stop_metadata_does_not_include_memory_bytes(self):
        row = live_consumer_probe.stop_metadata(
            "S05k",
            None,
            None,
            {"pc": 0x080025CC, "r0": 0x03001468, "lr": 0x08001651},
        )
        rendered = repr(row)
        self.assertNotIn("bytes", rendered)
        self.assertNotIn("raw", rendered)


if __name__ == "__main__":
    unittest.main()
