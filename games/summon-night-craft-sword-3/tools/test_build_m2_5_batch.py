#!/usr/bin/env python3
"""Tests for the bounded B3CJ M2.5 ledger/static builder."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("build_m2_5_batch.py")
SPEC = importlib.util.spec_from_file_location("build_m2_5_batch", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load build_m2_5_batch.py")
M25 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M25)

GAME_ROOT = TOOL_PATH.parents[1]
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
PLAN_PATH = GAME_ROOT / "research" / "m2.5-batch-plan.json"
FONT_PATH = pathlib.Path("vendor/fonts/unifont/unifont-17.0.05.hex.gz")
WORK_PATH = GAME_ROOT / "work" / "m2.5-prize-ui-working.jsonl"


class BuildM25Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(path.is_file() for path in (ROM_PATH, SOURCE_PATH, PLAN_PATH, FONT_PATH, WORK_PATH))
        if cls.available:
            cls.rom_data = ROM_PATH.read_bytes()
            cls.plan = M25.load_plan(PLAN_PATH)
            cls.source_rows = M25.load_source_rows(SOURCE_PATH)

    def require_local_inputs(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM/source/working inputs are not available")

    def test_prepare_contract_has_no_source_in_seed_ledger(self) -> None:
        self.require_local_inputs()
        seed, adapter = M25.make_seed_ledger(self.plan, self.source_rows)
        self.assertEqual(len(seed), 1)
        self.assertNotIn("source", seed[0])
        self.assertEqual(seed[0]["status"], "ai_draft")
        self.assertEqual(len(adapter), 1)
        self.assertIn("text", adapter[0])

    def test_static_build_reextracts_target_and_untouched_records(self) -> None:
        self.require_local_inputs()
        patched, summary = M25.build_batch(self.rom_data, SOURCE_PATH, FONT_PATH, self.plan, WORK_PATH)
        self.assertEqual(len(patched), len(self.rom_data))
        self.assertEqual(summary["translated_string_ids"], ["b3cj:t2:024:0x0064"])
        self.assertEqual(summary["reextract"]["records_total"], 361)
        self.assertEqual(summary["reextract"]["target_records"], 1)
        self.assertEqual(summary["reextract"]["untouched_records"], 360)
        self.assertEqual(summary["resource"]["new_compressed_size"], 1392)
        self.assertEqual(summary["resource"]["span_bytes"], 1392)
        self.assertTrue(summary["byte_level"]["changed_outside_font_or_resource24"] is False)
        self.assertEqual([item["code_unit"] for item in summary["font"]["allocations"]], ["ec64", "ec65", "ec66"])
        self.assertEqual(summary["font"]["adjacent_untouched_glyph_id"], "0x846")
        self.assertTrue(all(item["byte_identical_to_clean"] for item in summary["reextract"]["adjacent_untouched"]))

    def test_bps_round_trip_for_bounded_build(self) -> None:
        self.require_local_inputs()
        patched, _summary = M25.build_batch(self.rom_data, SOURCE_PATH, FONT_PATH, self.plan, WORK_PATH)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "clean.gba"
            target = root / "target.gba"
            bps = root / "target.bps"
            applied = root / "applied.gba"
            source.write_bytes(self.rom_data)
            target.write_bytes(patched)
            receipt = M25.run_bps(source, target, bps, applied)
            self.assertTrue(receipt["applied_byte_identical"])
            self.assertEqual(applied.read_bytes(), patched)
            self.assertGreater(receipt["bps_size"], 0)

    def test_working_source_drift_is_rejected(self) -> None:
        self.require_local_inputs()
        rows = [json.loads(line) for line in WORK_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows[0]["source"]["text"] = "drift"
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "drift.jsonl"
            path.write_text(json.dumps(rows[0], ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "working source mismatch"):
                M25.build_batch(self.rom_data, SOURCE_PATH, FONT_PATH, self.plan, path)

    def test_plan_rejects_slot_widening(self) -> None:
        self.require_local_inputs()
        widened = copy.deepcopy(self.plan)
        widened["allocations"][0]["glyph_id"] = "0x860"
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "widened-plan.json"
            path.write_text(json.dumps(widened, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mapping mismatch"):
                M25.load_plan(path)


if __name__ == "__main__":
    unittest.main()
