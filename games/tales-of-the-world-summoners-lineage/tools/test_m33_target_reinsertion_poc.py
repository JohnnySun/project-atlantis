#!/usr/bin/env python3
"""Pure tests for the bounded M33 target relocation POC."""

from __future__ import annotations

import struct
import unittest

from m20_keyboard_codepage_probe import latin_row2_expected_values
from m33_target_reinsertion_poc import (
    CALLER_POINTER_FILE_OFFSET,
    EXPECTED_OLD_POINTER,
    M47_TARGET_TEXT,
    M47_TARGET_NEW_UNITS,
    PROFILES,
    build_target,
    m47_target_units,
    verify_target,
)


class M33TargetReinsertionTests(unittest.TestCase):
    def fake_rom(self, profile: str = "m32") -> bytes:
        data = bytearray(0x800000)
        selected = PROFILES[profile]
        struct.pack_into(
            "<I",
            data,
            int(selected["caller_pointer_file_offset"]),
            int(selected["expected_old_pointer"]),
        )
        table = 0x8884C + 2 * 65 * 2
        for index, value in enumerate(latin_row2_expected_values()):
            data[table + index * 2:table + index * 2 + 2] = value.to_bytes(2, "little")
        return bytes(data)

    def test_build_relocates_one_pointer_and_appends_terminated_target(self) -> None:
        clean = self.fake_rom()
        target, receipt = build_target(clean, "・Lester")
        self.assertEqual(len(target), len(clean) + 0x10)
        self.assertEqual(struct.unpack_from("<I", target, CALLER_POINTER_FILE_OFFSET)[0], 0x08800000)
        self.assertEqual(receipt["relocated_stream_file_offset"], "0x800000")
        verification = verify_target(clean, target, receipt)
        self.assertTrue(verification["terminator_confirmed"])
        self.assertTrue(verification["receipt_match"])
        self.assertTrue(verification["original_stream_unchanged"])
        self.assertEqual(verification["unresolved_unit_count"], 0)

    def test_rejects_unknown_target_character(self) -> None:
        with self.assertRaises(ValueError):
            build_target(self.fake_rom(), "・漢")

    def test_m34_profile_relocates_its_fixed_source_pointer(self) -> None:
        clean = self.fake_rom("m34")
        target, receipt = build_target(clean, "Fulein", profile="m34")
        self.assertEqual(len(target), len(clean) + 0x0E)
        pointer_offset = int(PROFILES["m34"]["caller_pointer_file_offset"])
        self.assertEqual(struct.unpack_from("<I", target, pointer_offset)[0], 0x08800000)
        self.assertEqual(receipt["profile"], "m34")
        verification = verify_target(clean, target, receipt)
        self.assertTrue(verification["terminator_confirmed"])
        self.assertTrue(verification["receipt_match"])
        self.assertTrue(verification["original_stream_unchanged"])
        self.assertEqual(verification["unresolved_unit_count"], 0)

    def test_m47_target_sequence_is_fixed_and_uses_blank_slot_assignments(self) -> None:
        units = m47_target_units(M47_TARGET_TEXT)
        self.assertEqual(len(units), len(M47_TARGET_TEXT) + 1)
        self.assertEqual(units[-1], 0)
        self.assertEqual(
            {unit for unit in units[:-1]} & set(M47_TARGET_NEW_UNITS.values()),
            set(M47_TARGET_NEW_UNITS.values()),
        )
        with self.assertRaises(ValueError):
            m47_target_units("請選擇其他文字。")


if __name__ == "__main__":
    unittest.main()
