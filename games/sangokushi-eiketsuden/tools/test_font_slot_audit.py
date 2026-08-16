#!/usr/bin/env python3
"""ROM-independent tests for bounded custom glyph slot auditing."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("font_slot_audit.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_font_slot_audit", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load font_slot_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FontSlotAuditTest(unittest.TestCase):
    def test_shift_jis_pair_filter_is_bounded(self) -> None:
        self.assertTrue(AUDIT._is_shift_jis_pair(0x9594))
        self.assertTrue(AUDIT._is_shift_jis_pair(0xE353))
        self.assertFalse(AUDIT._is_shift_jis_pair(0xA140))

    def test_codepoint_parser_deduplicates_and_normalizes(self) -> None:
        self.assertEqual(AUDIT._parse_codepoints("u+7d93,9a57,U+7D93"), [0x7D93, 0x9A57])

    def test_audit_marks_candidates_unapproved(self) -> None:
        class FakeFormat:
            @staticmethod
            def read_codepage(_rom: bytes) -> list[int]:
                return [0x8140, 0x8141, 0x9594]

            @staticmethod
            def glyph_receipt(_rom: bytes, index: int, *, selector: int) -> dict[str, object]:
                return {"cache_sha256": f"cache-{index}", "source_planes": [{"sha256": f"plane-{index}"}, {"sha256": f"plane2-{index}"}]}

        original = AUDIT.font_glyph_format
        AUDIT.font_glyph_format = FakeFormat
        try:
            report = AUDIT.audit_slots(
                b"rom",
                {"source_record_count": 1, "undecodable_source_record_count": 0, "used_double_byte_code_unit_count": 1, "used_double_byte_code_units": [0x8140]},
                [0x7D93],
                candidate_limit=1,
            )
        finally:
            AUDIT.font_glyph_format = original
        self.assertEqual(report["candidate_count"], 1)
        self.assertTrue(report["requested_codepoints"][0]["candidate_slots_are_unapproved"])


if __name__ == "__main__":
    unittest.main()
