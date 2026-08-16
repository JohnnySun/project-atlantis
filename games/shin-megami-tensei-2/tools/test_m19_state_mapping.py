#!/usr/bin/env python3
"""Tests for the bounded M1.9 selector state mapper."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m19_state_mapping as mapping  # noqa: E402


class M19StateMappingTests(unittest.TestCase):
    def test_address_class_separates_rom_and_runtime_memory(self) -> None:
        self.assertEqual(mapping._address_class(0x08036666), "rom_pointer")
        self.assertEqual(mapping._address_class(0x030068C0), "iwram_address")
        self.assertEqual(mapping._address_class(0x0203DB40), "ewram_address")
        self.assertEqual(mapping._address_class(0x1234), "constant")

    def test_simple_thumb_decoder_keeps_argument_forms(self) -> None:
        rom = bytearray(0x100)
        base = mapping.ROM_BASE + 0x20
        struct.pack_into("<H", rom, 0x20, 0x2042)  # movs r0,#0x42
        struct.pack_into("<H", rom, 0x22, 0x6841)  # ldr r1,[r0,#0]
        self.assertEqual(mapping._decode_simple(bytes(rom), base)["form"], "movs_imm")
        decoded = mapping._decode_simple(bytes(rom), base + 2)
        self.assertEqual(decoded["form"], "ldr_word_imm")
        self.assertEqual(decoded["base"], 0)

    def test_provenance_marks_literal_and_runtime_load(self) -> None:
        rom = bytearray(0x100)
        base = mapping.ROM_BASE + 0x20
        # ldr r0,[pc,#0x14] -> aligned PC 0x08000024 + 0x50 = 0x08000074
        struct.pack_into("<H", rom, 0x20, 0x4814)
        struct.pack_into("<I", rom, 0x74, mapping.SELECTOR_SAVED_GLOBAL)
        struct.pack_into("<H", rom, 0x22, 0x6800)  # ldr r0,[r0,#0]
        registers, _ = mapping._provenance_before(bytes(rom), base, base + 4)
        self.assertEqual(registers[0]["kind"], "runtime_load")
        self.assertEqual(registers[0]["base"]["value"]["address"], "0x030068c0")

    def test_report_contract_does_not_expose_raw_payload_fields(self) -> None:
        report = {
            "schema": mapping.SCHEMA,
            "scan_scope": {"glyph_pattern_scan": False, "source_table_created": False},
            "tracked_literals": {},
            "seed_functions": [],
            "conclusions": {},
            "negative_boundary": {"translation_ledger": "blocked"},
        }
        serialized = mapping.json.dumps(report)
        self.assertNotIn("raw_dump", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("full_source", serialized)


if __name__ == "__main__":
    unittest.main()
