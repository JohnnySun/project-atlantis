#!/usr/bin/env python3
"""Tests for the source-free clean A9HJ storage-form audit."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("audit_storage_form.py")
SPEC = importlib.util.spec_from_file_location("dqmch_audit_storage_form", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StorageFormAuditTest(unittest.TestCase):
    def test_pointer_summary_is_source_free_and_keeps_duplicates(self) -> None:
        report = MODULE.summarize_pointer_records(
            [
                {"group": 0, "variant": 0, "pointer": 0x08001000},
                {"group": 0, "variant": 1, "pointer": 0x08001000},
                {"group": 1, "variant": 0, "pointer": 0x08002000},
            ]
        )
        self.assertEqual(report["groups"], [0, 1])
        self.assertEqual(report["variants"], 3)
        self.assertEqual(report["records"], 3)
        self.assertEqual(report["unique_pointers"], 2)
        self.assertEqual(report["duplicate_pointer_records"], 1)
        self.assertTrue(report["all_targets_are_rom"])
        self.assertNotIn("raw_hex", str(report))

    def test_clean_storage_receipt_keeps_compression_and_boundary_open(self) -> None:
        rom = Path(
            "games/dragon-quest-monsters-caravan-heart/roms/base/"
            "Dragon_Quest_Monsters_Caravan_Heart_JP_A9HJ.gba"
        ).read_bytes()
        report = MODULE.audit(rom)
        self.assertEqual(report["storage_form"], "direct-rom-pointer-pool-plus-mixed-byte-stream")
        self.assertEqual(report["pointer_pool"]["groups"], list(range(8)))
        self.assertEqual(report["pointer_pool"]["variants"], 83)
        self.assertEqual(report["pointer_pool"]["records"], 37600)
        self.assertEqual(report["pointer_pool"]["unique_pointers"], 4879)
        self.assertEqual(report["parser"]["control_read_signature_count"], 24)
        self.assertEqual(report["compression_status"], "not-proven-absent")
        self.assertEqual(report["boundary_status"], "next-pointer-is-candidate-only")

    def test_wrong_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.audit(b"not a ROM")


if __name__ == "__main__":
    unittest.main()
