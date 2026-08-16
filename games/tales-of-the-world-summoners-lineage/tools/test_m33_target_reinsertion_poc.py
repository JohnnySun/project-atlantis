#!/usr/bin/env python3
"""Pure tests for the bounded M33 target relocation POC."""

from __future__ import annotations

import struct
import unittest

from m20_keyboard_codepage_probe import latin_row2_expected_values
from m33_target_reinsertion_poc import (
    CALLER_POINTER_FILE_OFFSET,
    EXPECTED_OLD_POINTER,
    build_target,
    verify_target,
)


class M33TargetReinsertionTests(unittest.TestCase):
    def fake_rom(self) -> bytes:
        data = bytearray(0x800000)
        struct.pack_into("<I", data, CALLER_POINTER_FILE_OFFSET, EXPECTED_OLD_POINTER)
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


if __name__ == "__main__":
    unittest.main()
