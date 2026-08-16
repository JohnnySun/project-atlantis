#!/usr/bin/env python3
"""Pure tests for the metadata-only A9PJ M2A record probe."""

from __future__ import annotations

import unittest

from m20_text_record_probe import (
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_INDEX_MAX,
    FONT_RECORD_STRIDE,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    code_unit_class,
    font_record_file_offset,
    font_record_table_end_file_offset,
    parser_evidence,
    read_halfword_stream,
    record_metadata,
    stable_candidate_id,
)


class M20TextRecordProbeTests(unittest.TestCase):
    def test_record_formula_and_full_table_bounds(self) -> None:
        self.assertEqual(font_record_file_offset(0), FONT_RECORD_FILE_BASE)
        self.assertEqual(
            font_record_file_offset(0x005E),
            FONT_RECORD_FILE_BASE + 0x005E * FONT_RECORD_STRIDE,
        )
        self.assertEqual(
            font_record_table_end_file_offset(),
            FONT_RECORD_FILE_BASE + (FONT_RECORD_INDEX_MAX + 1) * FONT_RECORD_STRIDE,
        )

    def test_record_metadata_keeps_geometry_not_rows(self) -> None:
        data = bytearray(font_record_table_end_file_offset() + 4)
        offset = font_record_file_offset(0x005E)
        data[offset:offset + 2] = (0x8001).to_bytes(2, "little")
        data[offset + 2:offset + 4] = (0x0004).to_bytes(2, "little")
        metadata = record_metadata(bytes(data), 0x005E)
        self.assertEqual(metadata["record_length"], 0x18)
        self.assertEqual(metadata["record_halfword_count"], 12)
        self.assertEqual(metadata["nonzero_halfword_count"], 2)
        self.assertEqual(metadata["nonzero_row_range"], [0, 1])
        self.assertNotIn("rows", metadata)
        self.assertNotIn("record_bytes", metadata)

    def test_code_unit_classes_are_separate(self) -> None:
        self.assertEqual(code_unit_class(NULL_CODE_UNIT), "terminator")
        self.assertEqual(code_unit_class(LINE_ADVANCE_CODE_UNIT), "control-candidate")
        self.assertEqual(code_unit_class(0x005E), "font-record-index")

    def test_stream_profile_records_control_and_terminator_without_units(self) -> None:
        data = bytearray(16)
        data[0:2] = (0x005E).to_bytes(2, "little")
        data[2:4] = LINE_ADVANCE_CODE_UNIT.to_bytes(2, "little")
        data[4:6] = (0x0066).to_bytes(2, "little")
        data[6:8] = NULL_CODE_UNIT.to_bytes(2, "little")
        profile = read_halfword_stream(bytes(data), 0, max_units=8)
        self.assertTrue(profile["terminated_by_0000"])
        self.assertEqual(profile["unit_count_including_terminator"], 4)
        self.assertEqual(profile["control_candidate_count"], 1)
        self.assertEqual(profile["font_record_index_count"], 2)
        self.assertNotIn("code_units", profile)
        self.assertNotIn("text", profile)

    def test_candidate_id_is_stable_and_content_free(self) -> None:
        first = stable_candidate_id(0x20, 0x1F0000, 8)
        second = stable_candidate_id(0x20, 0x1F0000, 8)
        changed = stable_candidate_id(0x24, 0x1F0000, 8)
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first), 24)

    def test_parser_evidence_keeps_mapping_unconfirmed(self) -> None:
        evidence = parser_evidence()
        self.assertEqual(evidence["codepage"]["primary_stream_width_bits"], 16)
        self.assertEqual(evidence["codepage"]["status"], "index-width-confirmed-mapping-unconfirmed")
        self.assertEqual(evidence["codepage"]["primary_stream_renderer_bl_pc"], "0x080063C2")
        self.assertFalse(evidence["control_code"]["runtime_sequence_confirmed"])
        self.assertEqual(evidence["glyph_identity"]["confirmed_count"], 2)
        self.assertEqual(evidence["glyph_identity"]["confirmed_code_units"], ["0x005E", "0x0066"])
        self.assertFalse(evidence["codepage"]["general_stream_mapping_confirmed"])


if __name__ == "__main__":
    unittest.main()
