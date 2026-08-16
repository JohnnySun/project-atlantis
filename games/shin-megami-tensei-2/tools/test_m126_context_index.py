#!/usr/bin/env python3
"""Tests for bounded M1.26 context-index evidence."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m126_context_index as probe  # noqa: E402


class M126ContextIndexTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertFalse(report["scan_scope"]["runtime_capture_performed"])
        self.assertFalse(report["scan_scope"]["raw_array_values_emitted"])
        self.assertFalse(report["scan_scope"]["raw_source_emitted"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_index_domain_is_not_unicode_identity(self) -> None:
        report = probe.static_report(bytes(0x100))
        contract = report["source_table_contract"]
        self.assertEqual(contract["index_domain_class"], "bounded_ordinal_plus_one_1_to_27")
        self.assertFalse(contract["semantic_category_confirmed"])
        self.assertFalse(report["scan_scope"]["full_rom_glyph_scan"])

    def test_initializer_and_array_contract_are_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["initializer"]["function"]["default_record_index"], 1)
        array = report["selection_array_writer"]["array_contract"]
        self.assertEqual(array["array_offset_from_context"], 0x15)
        self.assertEqual(array["array_count"], 0x1B)
        self.assertEqual(array["value_min"], 1)
        self.assertEqual(array["value_max"], 0x1B)

    def test_no_raw_or_decoded_fields(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("raw_bytes", report)
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("glyph_bytes", report)


if __name__ == "__main__":
    unittest.main()
