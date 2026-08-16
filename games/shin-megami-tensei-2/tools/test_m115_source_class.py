#!/usr/bin/env python3
"""Tests for the bounded M1.15 source-class decoder."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m115_source_class as decoder  # noqa: E402


class M115SourceClassTests(unittest.TestCase):
    def test_gba_huffman_4bit_tree_round_trip(self) -> None:
        # Root has both children terminal: bit 0 -> 0xA, bit 1 -> 0xB.
        # The first two MSB-first stream bits are 01, and the BIOS packs the
        # first 4-bit unit into the low nibble of the destination byte.
        payload = bytearray(16)
        payload[0:4] = bytes((0x24, 0x01, 0x00, 0x00))
        payload[4] = 0x03  # tree length = (3 << 1) + 1 = 7; stream aligned
        # The tree starts at an odd address (header + 5); the BIOS aligns the
        # current node down before applying its child offsets.
        payload[5:12] = bytes((0xC0, 0x0A, 0x0B, 0x00, 0x00, 0x00, 0x00))
        payload[12:16] = bytes((0x00, 0x00, 0x00, 0x40))
        output, metadata = decoder._huffman_decode(bytes(payload), decoder.ROM_BASE)
        self.assertEqual(output, bytes((0xBA,)))
        self.assertEqual(metadata["tag"], "0x00000024")
        self.assertEqual(metadata["bit_depth"], 4)
        self.assertEqual(metadata["output_length"], 1)

    def test_nested_lz77_literal_stream(self) -> None:
        payload = bytes((0x10, 0x03, 0x00, 0x00, 0x00, ord("a"), ord("b"), ord("c")))
        output, metadata = decoder._lz77_decode(payload)
        self.assertEqual(output, b"abc")
        self.assertEqual(metadata["status"], "valid")
        self.assertEqual(metadata["declared_output_length"], 3)

    def test_report_contract_never_emits_payload_fields(self) -> None:
        report = decoder.static_report(bytes(0x100))
        serialized = str(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("decompressed_payload", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scan_scope"]["raw_payload_emitted"])


if __name__ == "__main__":
    unittest.main()
