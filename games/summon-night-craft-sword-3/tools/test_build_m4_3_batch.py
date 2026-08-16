#!/usr/bin/env python3
"""Tests for the cumulative B3CJ M4.3 bounded batch builder."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "build_m4_3_batch.py"
SPEC = importlib.util.spec_from_file_location("build_m4_3_batch", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load build_m4_3_batch.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

PLAN_PATH = GAME_ROOT / "research" / "m4.3-ellipsis-label-plan.json"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
M42_WORKING = GAME_ROOT / "work" / "m4.2-warning-label-working.jsonl"
M41_WORKING = GAME_ROOT / "work" / "m4.1-wood-chopping-working.jsonl"
M25_WORKING = GAME_ROOT / "work" / "m2.5-prize-ui-working.jsonl"
FONT_SOURCE = GAME_ROOT.parents[1] / "vendor" / "fonts" / "unifont" / "unifont-17.0.05.hex.gz"


class BuildM43Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(path.is_file() for path in (PLAN_PATH, SOURCE_PATH, ROM_PATH, M42_WORKING, M41_WORKING, M25_WORKING, FONT_SOURCE))

    def require_artifacts(self) -> None:
        if not self.available:
            self.skipTest("ignored ROM, source, prior working files, or licensed font source unavailable")

    def test_plan_is_fail_closed(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        rows = BUILDER.load_source_rows(SOURCE_PATH)
        row = BUILDER.validate_source_selection(plan, rows)
        self.assertEqual(row["string_id"], BUILDER.M43_TARGET_ID)
        self.assertEqual(plan["allocations"][0]["glyph_id"], "0x84c")
        self.assertEqual(plan["target_contract"]["code_units"], ["ec6d", "8163", "8140", "8140"])

    def test_cumulative_build_reextracts_four_targets(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        final_rom, summary = BUILDER.build_batch(
            ROM_PATH.read_bytes(),
            SOURCE_PATH,
            plan,
            GAME_ROOT / "work" / "m4.3-ellipsis-label-working.jsonl",
            M42_WORKING,
            M41_WORKING,
            M25_WORKING,
            FONT_SOURCE,
        )
        self.assertEqual(len(final_rom), 0x02000000)
        self.assertEqual(summary["reextract"]["records_total"], 361)
        self.assertEqual(summary["reextract"]["target_records"], 4)
        self.assertEqual(summary["reextract"]["untouched_records"], 357)
        self.assertEqual(summary["resource"]["new_compressed_size"], 1655)
        self.assertEqual(summary["resource"]["span_bytes"], 1664)
        self.assertEqual(summary["font"]["new_allocations"][0]["glyph_id"], "0x84c")
        self.assertTrue(summary["adjacent_untouched"]["glyph"]["byte_identical_to_clean"])


if __name__ == "__main__":
    unittest.main()
