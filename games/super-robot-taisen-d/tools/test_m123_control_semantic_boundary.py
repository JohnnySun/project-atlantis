#!/usr/bin/env python3
"""Tests for the M1.23 source-safe control/semantic boundary."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from m123_control_semantic_boundary import (
    EXPECTED_RECORD_COUNT,
    SemanticBoundaryReject,
    _control_source_summary,
    _caller_summary,
    build_report,
)


ROOT = Path(__file__).resolve().parents[1]


class M123ControlSemanticBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = json.loads((ROOT / "research/m118-control-layout-contract.json").read_text(encoding="utf-8"))
        self.inventory = json.loads((ROOT / "work/m4-corpus-inventory.json").read_text(encoding="utf-8"))
        self.caller = json.loads((ROOT / "research/m120-semantic-caller-inventory.json").read_text(encoding="utf-8"))

    def test_source_summary_keeps_newline_and_opaque_units_unconfirmed(self) -> None:
        summary = _control_source_summary(self.layout, self.inventory)
        self.assertEqual(summary["record_count"], EXPECTED_RECORD_COUNT)
        self.assertEqual(summary["opaque_newline_candidate_count"], 0)
        self.assertEqual(summary["opaque_unit_count"], 1120)
        self.assertEqual(summary["observed_width_maximum"], 240)
        self.assertFalse(summary["observed_width_is_engine_limit"])

    def test_caller_summary_does_not_promote_structural_classes_to_scene_names(self) -> None:
        summary = _caller_summary(self.caller)
        self.assertEqual(summary["candidate_count"], 5)
        self.assertEqual(summary["verified_structural_class_counts"]["dual_buffer_ui"], 2)
        self.assertFalse(summary["semantic_labels_inferred"])
        self.assertFalse(summary["pointer_report_rescanned"])

    def test_source_text_key_is_rejected(self) -> None:
        bad_layout = dict(self.layout)
        bad_layout["text"] = "forbidden"
        with self.assertRaisesRegex(SemanticBoundaryReject, "source_text_key"):
            build_report(
                (ROOT / "roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes(),
                bad_layout,
                self.inventory,
                self.caller,
            )

    def test_full_report_proves_field_origin_but_not_field_semantics(self) -> None:
        rom_path = ROOT / "roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba"
        report = build_report(rom_path.read_bytes(), self.layout, self.inventory, self.caller)
        self.assertTrue(report["gate"]["two_byte_glyph_loop_verified"])
        self.assertTrue(report["gate"]["dedicated_newline_byte_compare"])
        self.assertTrue(report["gate"]["mode_field_origin_proven"])
        self.assertFalse(report["gate"]["newline_semantics_proven"])
        self.assertFalse(report["gate"]["speaker_semantics_proven"])
        self.assertFalse(report["gate"]["branch_semantics_proven"])
        self.assertEqual(report["proven_control_flow"]["mode_routing_field"]["source"], "stack+0x5C")
        self.assertEqual(report["proven_control_flow"]["mode_routing_field"]["semantic_name"], "opaque_mode_field")
        self.assertEqual(report["mode_paths"]["other_value"]["direct_bl_targets"], ["0x08002418"])


if __name__ == "__main__":
    unittest.main()
