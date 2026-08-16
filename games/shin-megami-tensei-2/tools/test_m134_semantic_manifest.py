#!/usr/bin/env python3
"""Tests for the bounded M1.34 semantic manifest."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m134_semantic_manifest as probe  # noqa: E402


class M134SemanticManifestTests(unittest.TestCase):
    def test_short_input_is_fail_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["family_count"], 4)
        self.assertEqual(report["scan_scope"]["anchor_count"], 59)
        self.assertEqual(report["scan_scope"]["identity_match_count"], 0)
        self.assertFalse(report["semantic_manifest"]["source_table_complete"])
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_family_namespaces_and_counts_are_separate(self) -> None:
        report = probe.static_report(bytes(0x100))
        counts = report["semantic_manifest"]["family_anchor_counts"]
        self.assertEqual(counts, {"item": 8, "item-boundary": 3, "demon": 16, "skill": 32})
        self.assertEqual(
            [family["family"] for family in report["families"]],
            ["item", "item-boundary", "demon", "skill"],
        )
        self.assertFalse(report["semantic_manifest"]["complete_codepage"])

    def test_manifest_has_no_source_payload(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertNotIn("unit_values", report)
        self.assertNotIn("decoded_text", report)
        self.assertNotIn("source_bytes", report)
        self.assertNotIn("raw_bytes", report)
        for family in report["families"]:
            for anchor in family["anchors"]:
                self.assertFalse(anchor["raw_field_emitted"])
                self.assertFalse(anchor["raw_units_emitted"])
                self.assertFalse(anchor["decoded_text_emitted"])

    def test_manifest_hash_is_reproducible(self) -> None:
        first = probe.static_report(bytes(0x100))
        second = probe.static_report(bytes(0x100))
        self.assertEqual(
            first["semantic_manifest"]["manifest_hash"],
            second["semantic_manifest"]["manifest_hash"],
        )


if __name__ == "__main__":
    unittest.main()
