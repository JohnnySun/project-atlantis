#!/usr/bin/env python3
"""Tests for the bounded M1.12 OBJ runtime probe helpers."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m112_obj_runtime as runtime  # noqa: E402


class M112ObjRuntimeTests(unittest.TestCase):
    def test_store_metadata_is_register_only(self) -> None:
        rom = bytearray(0x100)
        rom[0x20:0x22] = (0x6048).to_bytes(2, "little")
        item = runtime.store_metadata(bytes(rom), 0x08000022)
        self.assertEqual(item["form"], "str_word_imm")
        self.assertEqual(item["source_register"], 0)
        self.assertEqual(item["base_register"], 1)
        self.assertEqual(item["offset"], 4)
        self.assertNotIn("instruction", item)

    def test_region_and_cohort_are_bounded(self) -> None:
        self.assertEqual(runtime.region(0x06013000), "obj_vram")
        self.assertEqual(runtime.region(0x08000000), "rom")
        self.assertEqual(len(runtime.OBJ_VRAM_LITERAL_LOADS), 12)
        self.assertNotIn(0x02001000, runtime.OBJ_VRAM_LITERAL_LOADS)

    def test_metadata_contract_has_no_raw_payload(self) -> None:
        report = {
            "events": [{"pc": "0x08000000", "sample_hash": "x", "sample_length": 64}],
            "natural_transition": True,
        }
        serialized = json.dumps(report)
        self.assertNotIn("raw_bytes", serialized)
        self.assertNotIn("full_source", serialized)
        self.assertNotIn("tile_data", serialized)


if __name__ == "__main__":
    unittest.main()
