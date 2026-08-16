#!/usr/bin/env python3
"""Regression tests for the FE6 M1.11 static gate report."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
TOOL_PATH = GAME_ROOT / "tools/analyze_m111_gates.py"

spec = importlib.util.spec_from_file_location("fe6_m111_gates", TOOL_PATH)
assert spec and spec.loader
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM111GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = gates.build_report(ROM_PATH)

    def test_loader_and_candidate_callsite_counts(self) -> None:
        self.assertEqual(self.report["loader"]["direct_callsite_count"], 163)
        functions = self.report["candidate_functions"]
        self.assertEqual(len(functions["0x080985d8"]["direct_callers"]), 10)
        self.assertEqual(len(functions["0x08098624"]["direct_callers"]), 1)
        self.assertEqual(functions["0x080985d8"]["loader_callsites"], ["0x080985ec"])
        self.assertEqual(
            functions["0x08098624"]["loader_callsites"],
            ["0x0809867a", "0x08098694"],
        )

    def test_gate_report_keeps_primary_and_alternate_separate(self) -> None:
        functions = self.report["candidate_functions"]
        primary = functions["0x080985d8"]["direct_callers"]
        alternate = functions["0x08098624"]["direct_callers"][0]
        self.assertEqual(primary[0]["target_function"], "0x080985d8")
        self.assertEqual(primary[0]["function_start"], "0x08098290")
        self.assertEqual(alternate["callsite"], "0x0809837c")
        self.assertEqual(alternate["target_function"], "0x08098624")

    def test_static_report_does_not_claim_scene_or_unicode(self) -> None:
        boundary = self.report["semantic_boundary"]
        self.assertEqual(boundary["scene_or_content_category"], "not_inferred_from_static_gate")
        self.assertEqual(boundary["natural_reachability"], "requires_runtime_receipt")
        self.assertFalse(boundary["source_bytes_emitted"])

    def test_dispatch_pointer_candidates_are_structural_only(self) -> None:
        candidates = self.report["dispatch_pointer_candidates"]
        by_target = {row["target_function"]: row for row in candidates}
        self.assertEqual(
            by_target["0x08098340"]["file_offset"], "0x691230"
        )
        self.assertEqual(
            by_target["0x080984a8"]["file_offset"], "0x691358"
        )
        self.assertEqual(
            by_target["0x08098340"]["stored_thumb_pointer"], "0x08098341"
        )
        self.assertEqual(
            by_target["0x080984a8"]["stored_thumb_pointer"], "0x080984a9"
        )
        self.assertNotIn("scene", candidates[0])
        self.assertNotIn("text", candidates[0])


if __name__ == "__main__":
    unittest.main()
