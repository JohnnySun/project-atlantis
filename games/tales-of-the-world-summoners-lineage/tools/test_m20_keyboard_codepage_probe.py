#!/usr/bin/env python3
"""Pure tests for the bounded keyboard code-unit table probe."""

from __future__ import annotations

import unittest

from m20_keyboard_codepage_probe import (
    KEYBOARD_ROW_STRIDE_ENTRIES,
    KNOWN_ROW0_LABELS,
    LATIN_ROW_LABELS,
    encode_bounded_target,
    latin_row2_expected_values,
    latin_row2_mapping,
    probe,
    read_row,
    row_entry_file_offset,
    target_encoder_metadata,
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

    def test_latin_row2_has_fixed_upper_and_lower_table_shape(self) -> None:
        table = 0x8884C + 2 * KEYBOARD_ROW_STRIDE_ENTRIES * 2
        data = bytearray(table + len(LATIN_ROW_LABELS) * 2)
        values = latin_row2_expected_values()
        for index, value in enumerate(values):
            data[table + index * 2:table + index * 2 + 2] = value.to_bytes(2, "little")
        self.assertEqual(latin_row2_mapping(bytes(data)), dict(zip(LATIN_ROW_LABELS, values)))

    def test_bounded_target_encoder_preserves_middle_dot_and_encodes_latin(self) -> None:
        table = 0x8884C + 2 * KEYBOARD_ROW_STRIDE_ENTRIES * 2
        data = bytearray(table + len(LATIN_ROW_LABELS) * 2)
        for index, value in enumerate(latin_row2_expected_values()):
            data[table + index * 2:table + index * 2 + 2] = value.to_bytes(2, "little")
        encoded = encode_bounded_target(bytes(data), "・Lester")
        self.assertEqual(
            [int.from_bytes(encoded[index:index + 2], "little") for index in range(0, len(encoded), 2)],
            [0x0006, 0x0040, 0x0033, 0x004F, 0x0051, 0x0033, 0x004D],
        )
        receipt = target_encoder_metadata(bytes(data), "・Lester")
        self.assertEqual(receipt["encoded_code_unit_count"], 7)
        self.assertFalse(receipt["general_codepage_confirmed"])
        self.assertFalse(receipt["cjk_encoder_confirmed"])

    def test_latin_probe_does_not_call_static_order_general_codepage(self) -> None:
        table = 0x8884C + 2 * KEYBOARD_ROW_STRIDE_ENTRIES * 2
        values = latin_row2_expected_values()
        data = bytearray(max(table + len(LATIN_ROW_LABELS) * 2, 0x89E00 + (max(values) + 1) * 0x18))
        for index, value in enumerate(values):
            data[table + index * 2:table + index * 2 + 2] = value.to_bytes(2, "little")
        for code_unit in set(values):
            offset = 0x89E00 + code_unit * 0x18
            data[offset:offset + 0x18] = bytes([code_unit & 0xFF]) * 0x18
        result = probe(bytes(data), row=2, count=52)
        self.assertEqual(result["codepage"]["status"], "bounded-static-latin-row2-only")
        self.assertFalse(result["codepage"]["general_stream_mapping_confirmed"])
        self.assertEqual(result["mappings"][0]["keyboard_label"], "A")
        self.assertEqual(result["mappings"][25]["keyboard_label"], "a")
        self.assertEqual(result["mappings"][50]["keyboard_label"], "Z")


if __name__ == "__main__":
    unittest.main()
