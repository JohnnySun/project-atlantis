#!/usr/bin/env python3
"""Tests for the bounded M1.35 adjacent-record probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m135_adjacent_records as probe  # noqa: E402


class M135AdjacentRecordTests(unittest.TestCase):
    def test_short_input_fails_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["record_count"], 3)
        self.assertFalse(report["adjacency_contract"]["all_three_identity_matches"])
        self.assertFalse(report["adjacency_contract"]["table_extent_proven"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_selected_namespaces_and_ordinals_are_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(
            [(record["family"], record["ordinal"]) for record in report["records"]],
            [("item", 8), ("demon", 16), ("skill", 32)],
        )
        self.assertEqual(report["scan_scope"]["field_unit_count"], 8)
        self.assertEqual(report["scan_scope"]["field_bytes"], 16)

    def test_no_raw_or_decoded_payload(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("source_bytes", report)
        for record in report["records"]:
            self.assertFalse(record["raw_field_emitted"])
            self.assertFalse(record["raw_units_emitted"])
            self.assertFalse(record["decoded_text_emitted"])

    def test_manifest_hash_is_deterministic(self) -> None:
        first = probe.static_report(bytes(0x100))
        second = probe.static_report(bytes(0x100))
        self.assertEqual(
            first["adjacency_contract"]["record_manifest_hash"],
            second["adjacency_contract"]["record_manifest_hash"],
        )


if __name__ == "__main__":
    unittest.main()
