#!/usr/bin/env python3
"""Tests for the fail-closed B3CJ M2.3 glyph/record POC encoder."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("encode_m2_3_poc.py")
SPEC = importlib.util.spec_from_file_location("encode_m2_3_poc", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load encode_m2_3_poc.py")
ENCODER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENCODER)

GAME_ROOT = TOOL_PATH.parents[1]
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
SOURCE_PATH = GAME_ROOT / "research" / "summon-night-craft-sword-3-decoded.jsonl"
MANIFEST_PATH = GAME_ROOT / "research" / "m2.3-glyph-manifest.json"
UNIFONT_PATH = TOOL_PATH.parents[3] / "vendor" / "fonts" / "unifont" / "unifont-17.0.05.hex.gz"


class EncodeM23PocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(path.is_file() for path in (ROM_PATH, SOURCE_PATH, MANIFEST_PATH, UNIFONT_PATH))
        if cls.available:
            cls.rom_data = ROM_PATH.read_bytes()
            cls.source_sha256 = ENCODER.sha256_file(SOURCE_PATH)
            cls.manifest_bytes = MANIFEST_PATH.read_bytes()
            cls.manifest = json.loads(cls.manifest_bytes.decode("utf-8"))

    def require_local_inputs(self) -> None:
        if not self.available:
            self.skipTest("local ignored B3CJ ROM/source/font inputs are not available")

    def test_actual_bounded_poc_is_byte_verified(self) -> None:
        self.require_local_inputs()
        patched, summary, render_cells = ENCODER.build_poc(
            self.rom_data,
            SOURCE_PATH,
            UNIFONT_PATH,
            self.manifest,
            ENCODER.sha256_bytes(self.manifest_bytes),
        )
        self.assertEqual(len(patched), len(self.rom_data))
        self.assertTrue(summary["static_only"])
        self.assertFalse(summary["runtime_qa"])
        self.assertEqual(len(summary["font"]["post_allocations"]), 2)
        self.assertEqual(
            [entry["glyph_id"] for entry in summary["font"]["post_allocations"]],
            [0x845, 0x846],
        )
        self.assertEqual(summary["font"]["untouched_adjacent_glyph_id"], 0x844)
        self.assertEqual(len(summary["records"]), 2)
        self.assertEqual([record["target_code_units"] for record in summary["records"]], [["ec48", "ec49"], ["ec49"]])
        self.assertEqual([record["post_stream_roundtrip"] for record in summary["records"]], ["byte_identical"] * 2)
        self.assertEqual(summary["byte_level"]["font_mapping_and_cell_roundtrip"], "byte_identical")
        self.assertEqual(summary["byte_level"]["record_and_psi3_stream_roundtrip"], "byte_identical")
        self.assertFalse(summary["byte_level"]["changed_outside_manifest_regions"])
        self.assertEqual([resource["new_compressed_size"] for resource in summary["resources"]], [485, 1652])
        self.assertEqual(len(render_cells), 3)

    def test_manifest_rejects_widened_or_duplicate_allocation(self) -> None:
        self.require_local_inputs()

        widened = copy.deepcopy(self.manifest)
        widened["font"]["allowed_slot_first"] = "0x844"
        with self.assertRaisesRegex(ValueError, "first allowed slot"):
            ENCODER.validate_manifest(widened)

        out_of_range = copy.deepcopy(self.manifest)
        out_of_range["allocations"][0]["glyph_id"] = "0x860"
        with self.assertRaisesRegex(ValueError, "outside 0x845..0x85f"):
            ENCODER.validate_manifest(out_of_range)

        duplicate_unit = copy.deepcopy(self.manifest)
        duplicate_unit["allocations"][1]["code_unit"] = "ec48"
        with self.assertRaisesRegex(ValueError, "duplicate allocation code unit"):
            ENCODER.validate_manifest(duplicate_unit)

        duplicate_slot = copy.deepcopy(self.manifest)
        duplicate_slot["allocations"][1]["glyph_id"] = "0x845"
        with self.assertRaisesRegex(ValueError, "duplicate allocation glyph"):
            ENCODER.validate_manifest(duplicate_slot)

        strict_collision = copy.deepcopy(self.manifest)
        strict_collision["allocations"][0]["code_unit"] = "eaa2"
        with self.assertRaisesRegex(ValueError, "collides with strict Shift-JIS"):
            ENCODER.validate_manifest(strict_collision)

    def test_manifest_and_source_hashes_are_required(self) -> None:
        self.require_local_inputs()

        wrong_rom_hash = copy.deepcopy(self.manifest)
        wrong_rom_hash["rom"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "ROM SHA-256"):
            ENCODER.validate_manifest(wrong_rom_hash)

        wrong_source_hash = copy.deepcopy(self.manifest)
        wrong_source_hash["rom"]["source_table_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source-table SHA-256"):
            ENCODER.validate_manifest(wrong_source_hash)

        wrong_record_hash = copy.deepcopy(self.manifest)
        wrong_record_hash["records"][0]["source_raw_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source raw hash mismatch"):
            ENCODER.build_poc(
                self.rom_data,
                SOURCE_PATH,
                UNIFONT_PATH,
                wrong_record_hash,
                ENCODER.sha256_bytes(self.manifest_bytes),
            )

    def test_resource_capacity_overrun_is_rejected(self) -> None:
        self.require_local_inputs()
        original_compressor = ENCODER.lz77_compress
        ENCODER.lz77_compress = lambda decoded: bytes(497)
        try:
            with self.assertRaisesRegex(ValueError, "exceeds span 496"):
                ENCODER.build_poc(
                    self.rom_data,
                    SOURCE_PATH,
                    UNIFONT_PATH,
                    self.manifest,
                    ENCODER.sha256_bytes(self.manifest_bytes),
                )
        finally:
            ENCODER.lz77_compress = original_compressor

    def test_existing_fallback_and_out_of_resource_are_not_mapped_targets(self) -> None:
        self.require_local_inputs()
        font = ENCODER.INSPECT_FONT.parse_font_resource(self.rom_data)
        fallback = ENCODER.INSPECT_FONT.lookup_code_unit(
            self.rom_data,
            bytes.fromhex("ec48"),
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        out_of_resource = ENCODER.INSPECT_FONT.lookup_code_unit(
            self.rom_data,
            bytes.fromhex("eaa2"),
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        self.assertEqual(fallback["status"], "fallback")
        self.assertEqual(fallback["table_value"], "0x0000")
        self.assertEqual(out_of_resource["status"], "out_of_resource")
        self.assertNotEqual(out_of_resource["status"], "mapped")


if __name__ == "__main__":
    unittest.main()
