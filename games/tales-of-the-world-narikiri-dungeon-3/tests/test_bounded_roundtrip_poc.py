#!/usr/bin/env python3
"""Tests for the B3TJ equal-length static round-trip POC boundary."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from extract_strings import ParsedString  # noqa: E402
from bounded_roundtrip_poc import (  # noqa: E402
    PocReject,
    control_signature,
    patch_equal_length_record,
)


class BoundedRoundtripPocTests(unittest.TestCase):
    def setUp(self):
        self.rom = b"\0\0\x82\xA0\x82\xA2\0\0"
        self.record = ParsedString(
            region="text-pool",
            start=2,
            end=6,
            raw_length=4,
            units=2,
            double_byte_units=2,
            halfwidth_units=0,
            ascii_units=0,
            newline_units=0,
            control_units=0,
            text="仮仮",
        )

    def test_equal_length_patch_preserves_terminator_and_control_shape(self):
        replacement = b"\xA1\xA2\xA3\xA4"
        patched = patch_equal_length_record(self.rom, self.record, replacement)
        self.assertEqual(patched[2:6], replacement)
        self.assertEqual(patched[6], 0)
        self.assertEqual(control_signature(self.rom[2:6]), ())
        self.assertEqual(control_signature(replacement), ())

    def test_length_nul_ff_and_control_changes_fail_closed(self):
        with self.assertRaisesRegex(PocReject, "length"):
            patch_equal_length_record(self.rom, self.record, b"\xA1\xA2")
        with self.assertRaisesRegex(PocReject, "interior NUL"):
            patch_equal_length_record(self.rom, self.record, b"\xA1\0\xA3\xA4")
        with self.assertRaisesRegex(PocReject, "0xFF"):
            patch_equal_length_record(self.rom, self.record, b"\xA1\xFF\xA3\xA4")

        controlled_rom = b"\0\0\x82\xA0\x01\x82\xA2\0"
        controlled = ParsedString(
            **{**self.record.__dict__, "raw_length": 5, "end": 7}
        )
        with self.assertRaisesRegex(PocReject, "control"):
            patch_equal_length_record(
                controlled_rom, controlled, b"\xA1\xA2\xA3\xA4\xA5"
            )


if __name__ == "__main__":
    unittest.main()
