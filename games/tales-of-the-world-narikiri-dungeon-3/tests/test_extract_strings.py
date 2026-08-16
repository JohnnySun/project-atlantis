#!/usr/bin/env python3
"""Deterministic tests for the strict B3TJ local source-table extractor."""

import struct
import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import extract_strings  # noqa: E402


class ExtractStringsTests(unittest.TestCase):
    def test_parser_decodes_sjis_and_preserves_control_bytes(self):
        raw = "かなA".encode("shift_jis") + b"\n\x12\x00"
        row = extract_strings.parse_nul_string(raw, 0, len(raw), "text-pool")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.text, "かなA\n{12}")
        self.assertEqual(row.double_byte_units, 2)
        self.assertEqual(row.newline_units, 1)
        self.assertEqual(row.control_units, 1)

    def test_parser_rejects_invalid_bytes_and_unterminated_runs(self):
        invalid = b"\x82\x40\xff\x00"
        unterminated = "かな".encode("shift_jis")
        self.assertIsNone(
            extract_strings.parse_nul_string(invalid, 0, len(invalid), "text-pool")
        )
        self.assertIsNone(
            extract_strings.parse_nul_string(
                unterminated, 0, len(unterminated), "text-pool"
            )
        )

    def test_iterator_requires_nul_boundary(self):
        good = "かな".encode("shift_jis") + b"\x00"
        data = b"X" + good + b"Y" + good
        rows = list(
            extract_strings.iter_parsed_strings(
                data, (extract_strings.RangeSpec("test", 1, len(data)),)
            )
        )
        self.assertEqual([row.start for row in rows], [1, 6])
        self.assertNotIn(7, [row.start for row in rows])

    def test_pointer_counts_use_gba_absolute_addresses(self):
        text = "かな".encode("shift_jis") + b"\x00"
        data = bytearray(0x100)
        data[0x20 : 0x20 + len(text)] = text
        struct.pack_into("<I", data, 0x40, extract_strings.ROM_BASE + 0x20)
        counts = extract_strings.pointer_reference_counts(bytes(data), {0x20})
        self.assertEqual(counts[0x20], 1)


if __name__ == "__main__":
    unittest.main()
