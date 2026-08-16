#!/usr/bin/env python3
"""Tests for the source-free A9HJ codepage inventory."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("audit_codepage_inventory.py")
SPEC = importlib.util.spec_from_file_location("dqmch_audit_codepage_inventory", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CodepageInventoryTest(unittest.TestCase):
    def test_inventory_separates_four_code_unit_classes(self) -> None:
        report = MODULE.inventory(
            [
                {
                    "schema": MODULE.EXTRACTOR_SCHEMA,
                    "rom_sha256": MODULE.EXPECTED_SHA256,
                    "group": 1,
                    "variant": 2,
                    "pointer_cpu": "0x08001000",
                    "boundary": "next-pointer-in-table",
                    "truncated_pair": False,
                    "control_values": [0xFF],
                    "tokens": [
                        {"kind": "single-byte-candidate", "value": 0x26},
                        {"kind": "single-byte-candidate", "value": 0xC0},
                        {"kind": "pair", "lead": 0x92, "trail": 0x34},
                        {"kind": "alt-glyph", "lead": 0xE1, "value": 0x8D},
                        {"kind": "control-candidate", "value": 0xFF},
                    ],
                }
            ]
        )
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["unique_pointers"], 1)
        self.assertEqual(report["single_byte"]["mapped_total"], 1)
        self.assertEqual(report["single_byte"]["unresolved_total"], 1)
        self.assertEqual(
            report["single_byte"]["unresolved_by_group_variant"],
            [
                {
                    "group": 1,
                    "variant": 2,
                    "records": 1,
                    "records_with_unresolved": 1,
                    "unresolved_total": 1,
                    "unresolved_units": {"0xC0": 1},
                }
            ],
        )
        self.assertEqual(report["pair"]["resolved_total"], 1)
        self.assertEqual(report["alternate_glyph"]["unique_slots"], 1)
        self.assertEqual(report["alternate_glyph"]["lead_counts"], {"0xE1": 1})
        self.assertEqual(report["alternate_glyph"]["used_indexes"]["0xE1"], [0x8D])
        self.assertEqual(report["control_candidate"]["used_values"], {"0xFF": 1})

    def test_report_contains_no_source_fields_or_text(self) -> None:
        report = MODULE.inventory(
            [
                {
                    "schema": MODULE.EXTRACTOR_SCHEMA,
                    "rom_sha256": MODULE.EXPECTED_SHA256,
                    "group": 0,
                    "variant": 0,
                    "pointer_cpu": "0x08002000",
                    "boundary": "max-span",
                    "truncated_pair": True,
                    "control_values": [],
                    "tokens": [{"kind": "alt-glyph-truncated", "lead": 0xE0}],
                    "raw_hex": "not emitted",
                }
            ]
        )
        encoded = __import__("json").dumps(report, ensure_ascii=False)
        self.assertNotIn("raw_hex", encoded)
        self.assertNotIn("not emitted", encoded)
        self.assertEqual(report["truncated_pair_records"], 1)

    def test_load_records_rejects_non_clean_schema(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            path.write_text(
                '{"schema":"wrong","rom_sha256":"%s","tokens":[]}\n' % MODULE.EXPECTED_SHA256,
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                MODULE.load_records(path)


if __name__ == "__main__":
    unittest.main()
