#!/usr/bin/env python3
"""Tests for the bounded M1.36 source/index provenance probe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m136_source_index_provenance as probe  # noqa: E402


class M136SourceIndexProvenanceTests(unittest.TestCase):
    def test_short_input_fails_closed(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(report["scan_scope"]["path_count"], 3)
        self.assertFalse(report["evidence_summary"]["all_named_calls_match"])
        self.assertEqual(report["evidence_summary"]["natural_runtime_edges"], 0)
        self.assertEqual(report["conclusions"]["translation_ledger"], "blocked")

    def test_paths_keep_separate_families(self) -> None:
        report = probe.static_report(bytes(0x100))
        self.assertEqual(
            [path["family"] for path in report["paths"]],
            ["item", "skill", "demon"],
        )
        self.assertEqual(
            [
                path["source_index_contract"]["source_class"]
                for path in report["paths"]
            ],
            [
                "EWRAM_halfword_index_list",
                "EWRAM_byte_index_list",
                "EWRAM_object_halfword_slot_array",
            ],
        )

    def test_scope_does_not_emit_source_or_graphics(self) -> None:
        report = probe.static_report(bytes(0x100))
        scope = report["scan_scope"]
        self.assertFalse(scope["full_rom_string_scan"])
        self.assertFalse(scope["full_rom_glyph_scan"])
        self.assertFalse(scope["graphics_resource_scan"])
        self.assertFalse(scope["runtime_capture_performed"])
        self.assertFalse(scope["raw_source_emitted"])
        self.assertFalse(scope["decoded_text_emitted"])
        self.assertFalse(scope["translation_ledger_created"])

    def test_layer_depth_is_bounded(self) -> None:
        report = probe.static_report(bytes(0x100))
        for path in report["paths"]:
            self.assertLessEqual(
                max((layer["depth"] for layer in path["upward_layers"]), default=0),
                probe.MAX_UPWARD_LAYERS,
            )


if __name__ == "__main__":
    unittest.main()
