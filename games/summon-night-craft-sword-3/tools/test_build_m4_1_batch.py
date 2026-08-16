#!/usr/bin/env python3
"""Tests for the cumulative B3CJ M4.1 bounded batch builder."""

from __future__ import annotations

import importlib.util
import pathlib
import tempfile
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "build_m4_1_batch.py"
SPEC = importlib.util.spec_from_file_location("build_m4_1_batch", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load build_m4_1_batch.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)

PLAN_PATH = GAME_ROOT / "research" / "m4.1-wood-chopping-plan.json"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
M25_WORKING = GAME_ROOT / "work" / "m2.5-prize-ui-working.jsonl"
FONT_SOURCE = GAME_ROOT.parents[1] / "vendor" / "fonts" / "unifont" / "unifont-17.0.05.hex.gz"


class BuildM41Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(path.is_file() for path in (PLAN_PATH, SOURCE_PATH, ROM_PATH, M25_WORKING, FONT_SOURCE))

    def require_artifacts(self) -> None:
        if not self.available:
            self.skipTest("ignored ROM, source, M2.5 working file, or licensed font source unavailable")

    def test_plan_is_fail_closed(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        rows = BUILDER.load_source_rows(SOURCE_PATH)
        row = BUILDER.validate_source_selection(plan, rows)
        self.assertEqual(row["string_id"], BUILDER.M4_TARGET_ID)
        self.assertEqual(plan["target_contract"]["code_units"], ["ec67", "ec6c", "9056", "8ee8", "8140", "8140"])
        self.assertEqual(plan["adjacent_untouched_glyph_id"], "0x84c")

    def test_cumulative_build_reextracts_both_targets(self) -> None:
        self.require_artifacts()
        plan = BUILDER.load_plan(PLAN_PATH)
        with tempfile.TemporaryDirectory(prefix="b3cj-m4.1-build-test-"):
            final_rom, summary = BUILDER.build_batch(
                ROM_PATH.read_bytes(),
                SOURCE_PATH,
                plan,
                GAME_ROOT / "work" / "m4.1-wood-chopping-working.jsonl",
                M25_WORKING,
                FONT_SOURCE,
            )
        self.assertEqual(len(final_rom), 0x02000000)
        self.assertEqual(summary["reextract"]["records_total"], 361)
        self.assertEqual(summary["reextract"]["target_records"], 2)
        self.assertEqual(summary["reextract"]["untouched_records"], 359)
        self.assertEqual(summary["resource"]["new_compressed_size"], 493)
        self.assertEqual(summary["resource"]["span_bytes"], 496)
        self.assertEqual(summary["font"]["post_allocations"][0]["glyph_id"], "0x84a")


if __name__ == "__main__":
    unittest.main()
