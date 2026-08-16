from __future__ import annotations

import unittest

from m120_semantic_caller_inventory import build_report, verify_callsite


class M120SemanticCallerInventoryTest(unittest.TestCase):
    def test_callsite_structure_is_not_a_scene_label(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        rom = (root / "games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes()
        result = verify_callsite(rom, 0x08008E1C)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["structural_class"], "queue_entry_drain_loop")
        self.assertNotIn("story", result)

    def test_real_inventory_keeps_semantics_unconfirmed(self) -> None:
        from pathlib import Path
        import json

        root = Path(__file__).resolve().parents[3]
        rom = (root / "games/super-robot-taisen-d/roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes()
        def load(name: str):
            return json.loads((root / "games/super-robot-taisen-d/research" / name).read_text(encoding="utf-8"))
        report = build_report(
            rom,
            load("m115-consumer-callsite.json"),
            load("m117-corpus-coverage.json"),
            load("m118-control-layout-contract.json"),
            load("m119-caller-reroute.json"),
        )
        self.assertEqual(report["consumer_callsites"]["candidate_count"], 5)
        self.assertTrue(report["gate"]["all_callsite_windows_verified"])
        self.assertTrue(report["gate"]["runtime_callsite_matches_static_candidate"])
        self.assertFalse(report["gate"]["semantic_labels_inferred"])
        self.assertFalse(report["gate"]["newline_engine_proven"])
        self.assertEqual(report["corpus_coverage"]["record_count"], 2325)


if __name__ == "__main__":
    unittest.main()
