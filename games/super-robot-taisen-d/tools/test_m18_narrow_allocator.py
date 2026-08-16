#!/usr/bin/env python3
"""Pure tests for the M1.8 narrow allocator and bitmap renderer."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from m18_narrow_allocator import (
    AllocatorReject,
    FONT_SHA256,
    allocate_target,
    build_from_work,
    build_plan,
    code_unit_bytes,
    downsample_16x16_to_8x12,
    enumerate_narrow_code_units,
    _glyph_bytes_at,
    load_font_metadata,
    render_narrow_4bpp,
    validate_source_shape,
)


class M18NarrowAllocatorTest(unittest.TestCase):
    def test_formula_exposes_exact_544_slot_narrow_range(self) -> None:
        slot_to_units = enumerate_narrow_code_units(0x1980)
        self.assertEqual(len(slot_to_units), 544)
        self.assertEqual(code_unit_bytes(slot_to_units[0][0]), bytes.fromhex("8140"))
        self.assertEqual(code_unit_bytes(slot_to_units[543][0]), bytes.fromhex("83e8"))
        self.assertTrue(all(len(units) == 1 for units in slot_to_units.values()))

    def test_16x16_box_downsample_and_8x12_render(self) -> None:
        rows = tuple(0xFFFF for _ in range(16))
        glyph = downsample_16x16_to_8x12(rows)
        self.assertEqual(glyph, bytes([0xFF] * 12))
        packed = render_narrow_4bpp(bytes([0xC0] + [0] * 11))
        self.assertEqual(packed[0], 0x11)
        self.assertEqual(packed[1:4], bytes(3))

    def test_allocator_uses_only_narrow_free_slots(self) -> None:
        occupancy = {
            "free_blank_slots": [10, 11],
            "slot_to_units": {10: (0x5581,), 11: (0x5681,)},
        }
        rows = {0x6C92: tuple(0xFFFF for _ in range(16))}
        allocations = allocate_target("沒", 1, occupancy, rows)
        self.assertEqual(allocations[0].slot, 11)
        self.assertEqual(allocations[0].raw_code_unit, bytes.fromhex("8156"))

    def test_allocator_rejects_length_missing_capacity_and_collision(self) -> None:
        occupancy = {
            "free_blank_slots": [10],
            "slot_to_units": {10: (0x5581,)},
        }
        rows = {0x6C92: tuple(0xFFFF for _ in range(16))}
        with self.assertRaisesRegex(AllocatorReject, "variable_length"):
            allocate_target("沒有", 1, occupancy, rows)
        with self.assertRaisesRegex(AllocatorReject, "missing_glyph"):
            allocate_target("有", 1, occupancy, rows)
        collision = {"free_blank_slots": [10], "slot_to_units": {10: (0x5581, 0x5681)}}
        with self.assertRaisesRegex(AllocatorReject, "code_unit_slot_collision"):
            allocate_target("沒", 1, collision, rows)
        with self.assertRaisesRegex(AllocatorReject, "capacity_exceeded"):
            allocate_target("沒", 1, {"free_blank_slots": [], "slot_to_units": {}}, rows)

    def test_source_gate_rejects_wide_and_opaque_units(self) -> None:
        with self.assertRaisesRegex(AllocatorReject, "wide_glyph"):
            validate_source_shape(bytes.fromhex("8840"))
        with self.assertRaisesRegex(AllocatorReject, "opaque_or_control"):
            validate_source_shape(b"AB")
        with self.assertRaisesRegex(AllocatorReject, "opaque_or_control"):
            allocate_target(
                "\n",
                1,
                {"free_blank_slots": [10], "slot_to_units": {10: (0x5581,)}},
                {0x000A: tuple(0xFFFF for _ in range(16))},
            )
        with self.assertRaisesRegex(AllocatorReject, "wide_glyph"):
            allocate_target(
                "沒",
                1,
                {"free_blank_slots": [10], "slot_to_units": {10: (0x4088,)}},
                {0x6C92: tuple(0xFFFF for _ in range(16))},
            )

    def test_allocator_rejects_range_and_hash_mismatches(self) -> None:
        occupancy = {"resource_size": 0x1980}
        with self.assertRaisesRegex(AllocatorReject, "code_unit_out_of_range"):
            _glyph_bytes_at(b"", 0x8040, occupancy)
        with self.assertRaisesRegex(AllocatorReject, "rom_hash_mismatch"):
            build_plan(b"", [], 0, "沒", Path("font"), Path("license"))
        with patch("m18_narrow_allocator.file_sha256", return_value="0" * 64):
            with self.assertRaisesRegex(AllocatorReject, "font_hash_mismatch"):
                load_font_metadata(Path("font"), Path("license"))
        with patch("m18_narrow_allocator.file_sha256", side_effect=[FONT_SHA256, "0" * 64]):
            with self.assertRaisesRegex(AllocatorReject, "font_license_hash_mismatch"):
                load_font_metadata(Path("font"), Path("license"))

    def test_allocator_rejects_source_hash_mismatch_before_rom_access(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            ledger = root / "ledger.jsonl"
            working = root / "working.jsonl"
            source_table = root / "source.jsonl"
            row = {
                "string_id": 1,
                "source": {"text": "placeholder"},
                "targets": {"zh-TW": {"text": "target"}},
            }
            ledger.write_text(
                json.dumps({"string_id": 1, "source_hash": "0" * 64}) + "\n",
                encoding="utf-8",
            )
            working.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            source_table.write_text("\n", encoding="utf-8")
            args = SimpleNamespace(
                rom=root / "missing.gba",
                source_table=source_table,
                ledger=ledger,
                working=working,
                target_offset=1,
                font=Path("font"),
                license=Path("license"),
                locale="zh-TW",
                patched_rom=root / "patched.gba",
                report=root / "report.json",
                render_dir=None,
            )
            with self.assertRaisesRegex(AllocatorReject, "source_hash_mismatch"):
                build_from_work(args)


if __name__ == "__main__":
    unittest.main()
