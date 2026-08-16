#!/usr/bin/env python3
"""Tests for bounded M1.32 font-bank provenance."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m132_font_edge as probe  # noqa: E402


class M132FontEdgeTests(unittest.TestCase):
    def test_swizzle_inverse_is_reversible(self) -> None:
        source = bytes((index * 37 + 11) & 0xFF for index in range(0x20))
        transformed = probe.swizzle_block(source)
        self.assertEqual(len(transformed), 0x40)
        self.assertEqual(probe.inverse_swizzle_block(transformed), source)

    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["identity"]["complete_codepage"])
        self.assertEqual(report["identity"]["anchored_glyph_edge_count"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_transform_contract_has_no_payload_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        contract = report["static_provenance"]["font_builder_contract"]
        self.assertEqual(contract["source_block_bytes"], 0x20)
        self.assertEqual(contract["paired_source_offset"], 0x200)
        self.assertEqual(contract["swizzle_output_bytes_per_source_block"], 0x40)
        self.assertTrue(contract["transform_inverse_tested"])
        self.assertNotIn("source_bytes", report)
        self.assertNotIn("font_bytes", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("glyph_bytes", report)

    def test_anchor_records_never_emit_units_or_font_bytes(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(len(report["glyph_edges"]), 5)
        for edge in report["glyph_edges"]:
            self.assertFalse(edge["raw_field_emitted"])
            self.assertFalse(edge["raw_unit_emitted"])
            self.assertFalse(edge["raw_font_bytes_emitted"])
            self.assertFalse(edge["decoded_text_emitted"])


if __name__ == "__main__":
    unittest.main()
