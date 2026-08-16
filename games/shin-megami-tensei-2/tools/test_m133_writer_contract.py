#!/usr/bin/env python3
"""Tests for the bounded M1.33 writer/control/layout contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m133_writer_contract as probe  # noqa: E402


class M133WriterContractTests(unittest.TestCase):
    def test_short_input_fails_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["identity"]["named_writer_layout_confirmed"])
        self.assertFalse(report["identity"]["complete_width_contract"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_writer_layout_uses_only_oam_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        layout = report["layout_contract"]
        self.assertEqual(layout["oam_record_bytes"], 6)
        self.assertEqual(layout["fields"]["attr0"]["delta_mask"], "0x000000ff")
        self.assertEqual(layout["fields"]["attr1"]["delta_mask"], "0x000001ff")
        self.assertEqual(layout["fields"]["attr2"]["tile_delta_mask"], "0x000003ff")
        self.assertNotIn("oam_bytes", report)
        self.assertNotIn("source_bytes", report)
        self.assertNotIn("decoded_text", report)

    def test_synthetic_modulo_layout_roundtrip(self) -> None:
        result = probe._synthetic_roundtrip()
        self.assertTrue(result["modulo_fields_roundtrip"])
        self.assertEqual(result["canonical_field_count"], 6)
        self.assertFalse(result["raw_fixture_emitted"])

    def test_control_gate_stays_separate_from_width(self) -> None:
        report = probe.static_report(bytes(0x100))
        controls = report["control_contract"]
        self.assertEqual(controls["line_break_unit"], "0x00000300")
        self.assertEqual(controls["terminator_units"], ["0x0000", "0x00000301"])
        self.assertEqual(controls["reader_unit_width"], 2)
        self.assertFalse(controls["translated_pixel_width_confirmed"])


if __name__ == "__main__":
    unittest.main()
