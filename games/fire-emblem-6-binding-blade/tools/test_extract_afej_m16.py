#!/usr/bin/env python3
"""Regression tests for the bounded AFEJ M1.6 extractor."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


GAME_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = GAME_ROOT / "tools/extract_afej_m16.py"
ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"
RECEIPT_PATH = GAME_ROOT / "work/afej-m16-runtime-receipt.json"

spec = importlib.util.spec_from_file_location("afej_m16_extractor", TOOL_PATH)
assert spec and spec.loader
extractor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = extractor
spec.loader.exec_module(extractor)


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM16ExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = extractor.load_rom(ROM_PATH)

    def test_static_table_boundary_and_inverse_tree(self) -> None:
        self.assertEqual(extractor.prove_table_end(self.rom), 3342)
        codebook = extractor.build_codebook(self.rom)
        self.assertEqual(len(codebook), 1642)

    def test_bounded_cohort_round_trips(self) -> None:
        records = extractor.extract(self.rom, start=3080, count=16)
        self.assertEqual(len(records), 16)
        self.assertEqual(records[0]["string_id"], "afej.ptr.3080")
        self.assertEqual(records[-1]["string_id"], "afej.ptr.3095")
        self.assertTrue(all(row["decode_encode_byte_identical"] for row in records))
        self.assertTrue(
            all(
                row["provenance"]["source_span_matches_next_entry"]
                for row in records
            )
        )
        self.assertEqual(
            sum(len(row["control_marker_offsets"]["0x01"]) for row in records),
            9,
        )
        self.assertEqual(
            sum(len(row["control_marker_offsets"]["0x00"]) for row in records),
            16,
        )

    def test_index_3087_matches_runtime_receipt_hash(self) -> None:
        rows = extractor.extract(self.rom, start=3087, count=1)
        self.assertEqual(
            rows[0]["output_hash"],
            extractor.RUNTIME_RECEIPT_BUFFER_SHA256,
        )
        self.assertEqual(rows[0]["source_length"], 39)
        self.assertEqual(rows[0]["payload_length"], 44)
        self.assertEqual(rows[0]["control_marker_offsets"]["0x01"], [8])
        self.assertEqual(rows[0]["control_marker_offsets"]["0x00"], [43])

        if RECEIPT_PATH.is_file():
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
            self.assertEqual(receipt["table_index"], 3087)
            self.assertEqual(receipt["buffer_sha256"], rows[0]["output_hash"])


if __name__ == "__main__":
    unittest.main()
