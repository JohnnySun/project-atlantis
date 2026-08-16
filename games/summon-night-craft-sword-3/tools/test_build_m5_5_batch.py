#!/usr/bin/env python3
"""Tests for the cumulative B3CJ M5.5 repeated prize-header batch."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "build_m5_5_batch.py"
SPEC = importlib.util.spec_from_file_location("build_m5_5_batch", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load build_m5_5_batch.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

PLAN_PATH = GAME_ROOT / "research" / "m5.5-repeated-prize-header-plan.json"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
M55_WORKING = GAME_ROOT / "work" / "m5.5-repeated-prize-header-working.jsonl"
M54_WORKING = GAME_ROOT / "work" / "m5.4-lottery-question-working.jsonl"
M53_WORKING = GAME_ROOT / "work" / "m5.3-repeated-prize-header-working.jsonl"
M52_WORKING = GAME_ROOT / "work" / "m5.2-reward-relocation-working.jsonl"
M43_WORKING = GAME_ROOT / "work" / "m4.3-ellipsis-label-working.jsonl"
M42_WORKING = GAME_ROOT / "work" / "m4.2-warning-label-working.jsonl"
M41_WORKING = GAME_ROOT / "work" / "m4.1-wood-chopping-working.jsonl"
M25_WORKING = GAME_ROOT / "work" / "m2.5-prize-ui-working.jsonl"
FONT_SOURCE = GAME_ROOT.parents[1] / "vendor" / "fonts" / "unifont" / "unifont-17.0.05.hex.gz"


class BuildM55Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(path.is_file() for path in (PLAN_PATH, SOURCE_PATH, ROM_PATH, M55_WORKING, M54_WORKING, M53_WORKING, M52_WORKING, M43_WORKING, M42_WORKING, M41_WORKING, M25_WORKING, FONT_SOURCE))

    def require_artifacts(self) -> None:
        if not self.available:
            self.skipTest("ignored ROM, source, prior working files, or licensed font source unavailable")

    def test_plan_reuses_existing_mapping_without_allocation(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        rows = BUILDER.load_source_rows(SOURCE_PATH)
        row = BUILDER.validate_source_selection(plan, rows)
        self.assertEqual(row["string_id"], BUILDER.M55_TARGET_ID)
        self.assertEqual(plan["allocations"], [])

    def test_relocated_build_reextracts_eight_targets(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        final_rom, summary = BUILDER.build_batch(
            ROM_PATH.read_bytes(),
            SOURCE_PATH,
            plan,
            M55_WORKING,
            M54_WORKING,
            M53_WORKING,
            M52_WORKING,
            M43_WORKING,
            M42_WORKING,
            M41_WORKING,
            M25_WORKING,
            FONT_SOURCE,
        )
        self.assertEqual(len(final_rom), 0x02000000)
        self.assertEqual(len(summary["translated_string_ids"]), 8)
        self.assertEqual(summary["reextract"]["records_total"], 361)
        self.assertEqual(summary["reextract"]["target_records"], 8)
        self.assertEqual(summary["reextract"]["untouched_records"], 353)
        self.assertLessEqual(summary["resource"]["new_compressed_size"], 1536)
        self.assertEqual(summary["pointer"]["relative_units"], "0x8a220")
        self.assertEqual(len(summary["prior_target_proof"]), 7)
        self.assertEqual(summary["font"]["proof"]["inherited_mappings"][-1]["code_unit"], "ec6f")


if __name__ == "__main__":
    unittest.main()
