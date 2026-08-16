#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ M2.1 static helpers."""

from __future__ import annotations

import pathlib
import struct
import sys
import unittest


TOOL_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))
from table_b_common import (  # noqa: E402
    ROM_BASE,
    TABLE_B_OFFSET,
    TABLE_B_NEXT_STRUCT_OFFSET,
    TABLE_C_OFFSET,
    analyze_consumer_chain,
    disassemble_thumb_span,
    extract_records,
    parse_table_b_boundary,
    record_structure,
    thumb_literal_target,
)


def synthetic_table_rom() -> bytes:
    data = bytearray(TABLE_C_OFFSET + 0x100)
    record_a = 0x1000
    record_b = 0x1010
    data[record_a:record_a + 5] = b"A%u\n\0"
    data[record_b:record_b + 4] = b"B\x1b\0"
    for index in range(44):
        target = record_a if index % 2 == 0 else record_b
        struct.pack_into("<I", data, TABLE_B_OFFSET + index * 4, ROM_BASE + target)
    # The zero word and the non-pointer gap represent the adjacent structure.
    struct.pack_into("<I", data, TABLE_B_NEXT_STRUCT_OFFSET, 0)
    return bytes(data)


class TableBStaticTest(unittest.TestCase):
    def test_thumb_literal_and_valid_instruction_span(self) -> None:
        self.assertEqual(thumb_literal_target(0x0262F8, 0x4A15), 0x08026350)
        code = bytes.fromhex("00b500bd")  # push {lr}; pop {r0}; bx r0 is not needed here
        self.assertEqual(len(disassemble_thumb_span(code, 0, len(code))), 2)

    def test_boundary_stops_at_zero_after_44_pointers(self) -> None:
        report = parse_table_b_boundary(synthetic_table_rom())
        self.assertEqual(report["entry_count"], 44)
        self.assertEqual(report["pointer_run_end_exclusive"], "0x0D20AC")
        self.assertEqual(report["first_non_pointer_word"], "0x00000000")
        self.assertEqual(report["following_structure_end"], "0x0D20D8")
        self.assertEqual(report["boundary_status"], "confirmed-static")

    def test_record_structure_keeps_unknown_control_opaque(self) -> None:
        structure = record_structure(b"A%u\n\x1b")
        self.assertEqual(structure["line_feed_count"], 1)
        self.assertEqual(structure["format_counts"], {"%u": 1})
        self.assertEqual(structure["opaque_control_byte_counts"], {"0x1B": 1})
        self.assertIn("text", structure)

    def test_extractor_shape_contains_source_only_in_local_record(self) -> None:
        records = extract_records(synthetic_table_rom())
        self.assertEqual(len(records), 44)
        self.assertEqual(records[0]["string_id"], "b3ej:table-b:000")
        self.assertEqual(records[0]["locale"], "ja-JP")
        self.assertIn("text", records[0])
        self.assertNotIn("raw_bytes", records[0])
        self.assertEqual(records[0]["provenance"]["status"], "confirmed-static")


if __name__ == "__main__":
    unittest.main()
