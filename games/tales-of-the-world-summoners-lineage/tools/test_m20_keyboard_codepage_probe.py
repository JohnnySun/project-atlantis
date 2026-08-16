#!/usr/bin/env python3
"""Pure tests for the bounded keyboard code-unit table probe."""

from __future__ import annotations

import unittest

from m20_keyboard_codepage_probe import (
    KEYBOARD_ROW_STRIDE_ENTRIES,
    KNOWN_ROW0_LABELS,
    probe,
    read_row,
    row_entry_file_offset,
)


class M20KeyboardCodepageProbeTests(unittest.TestCase):
    def test_row_formula_uses_65_entry_stride(self) -> None:
        self.assertEqual(row_entry_file_offset(0, 0), 0x8884C)
        self.assertEqual(row_entry_file_offset(1, 0), 0x8884C + 2 * KEYBOARD_ROW_STRIDE_ENTRIES)
        self.assertEqual(row_entry_file_offset(0, 4), 0x8884C + 8)

    def test_row_read_is_little_endian_and_bounded(self) -> None:
        data = bytearray(0x8884C + KEYBOARD_ROW_STRIDE_ENTRIES * 2)
        for index, value in enumerate((0x005E, 0x0062, 0x0066)):
            offset = 0x8884C + index * 2
            data[offset:offset + 2] = value.to_bytes(2, "little")
        self.assertEqual(read_row(bytes(data), 0, 3), [0x005E, 0x0062, 0x0066])

    def test_known_labels_are_not_general_stream_mapping(self) -> None:
        data = bytearray(0x89E00 + 0x1000)
        table = 0x8884C
        for index, value in enumerate((0x005E, 0x0062, 0x0066, 0x006B, 0x006F)):
            data[table + 2 * index:table + 2 * index + 2] = value.to_bytes(2, "little")
        for code_unit in (0x005E, 0x0062, 0x0066, 0x006B, 0x006F):
            offset = 0x89E00 + code_unit * 0x18
            data[offset:offset + 0x18] = bytes([code_unit & 0xFF]) * 0x18
        result = probe(bytes(data), row=0, count=5)
        self.assertEqual([item["keyboard_label"] for item in result["mappings"]], list(KNOWN_ROW0_LABELS))
        self.assertEqual(result["codepage"]["width_bits"], 16)
        self.assertFalse(result["codepage"]["general_stream_mapping_confirmed"])
        self.assertTrue(all(item["record"]["rows_emitted"] is False for item in result["mappings"]))


if __name__ == "__main__":
    unittest.main()
