#!/usr/bin/env python3
"""Offline tests for pointer classification helpers."""

import struct
import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import classify_pointers  # noqa: E402
from extract_strings import ParsedString  # noqa: E402


class ClassifyPointersTests(unittest.TestCase):
    def test_absolute_reference_is_found_at_any_alignment(self):
        data = bytearray(0x100)
        target = 0x40
        data[0x13:0x17] = struct.pack("<I", classify_pointers.ROM_BASE + target)
        row = ParsedString("test", target, target + 3, 3, 2, 2, 0, 0, 0, 0, "かな")
        refs = classify_pointers.scan_references(bytes(data), [row])
        self.assertEqual(
            [(ref.kind, ref.location) for ref in refs[target] if ref.kind == "absolute32"],
            [("absolute32", 0x13)],
        )
        self.assertNotIn("relative24-exact", [ref.kind for ref in refs[target]])

    def test_relative_self_reference_is_marked_provisional(self):
        data = bytearray(0x100)
        target = 0x50
        location = 0x20
        struct.pack_into("<I", data, location, target - location)
        row = ParsedString("test", target, target + 3, 3, 2, 2, 0, 0, 0, 0, "かな")
        refs = classify_pointers.scan_references(bytes(data), [row])
        self.assertIn("relative32-self", [ref.kind for ref in refs[target]])

    def test_absolute_table_span_groups_adjacent_candidate_pointers(self):
        data = bytearray(0x100)
        rows = []
        for index, target in enumerate((0x40, 0x50, 0x60)):
            struct.pack_into("<I", data, 0x20 + index * 4, classify_pointers.ROM_BASE + target)
            rows.append(ParsedString("test", target, target + 3, 3, 2, 2, 0, 0, 0, 0, "かな"))
        table = classify_pointers.absolute_table_span(bytes(data), 0x24, {row.start: row for row in rows})
        self.assertEqual(table["start"], 0x20)
        self.assertEqual(table["end"], 0x2C)
        self.assertEqual(table["words"], 3)


if __name__ == "__main__":
    unittest.main()
