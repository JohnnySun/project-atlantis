#!/usr/bin/env python3
"""Pure tests for M1.7 token and addressing boundaries."""

from __future__ import annotations

import unittest

from m17_layout import (
    M17Error,
    NARROW_STRIDE,
    WIDE_STRIDE,
    code_unit_slot,
    codepage_offset,
    encode_tokens,
    record_summary,
    select_cohort,
    sha256,
    static_consumer_report,
    tokenize_payload,
)


class M17LayoutTest(unittest.TestCase):
    def test_verified_glyph_classes_and_noop_bytes(self) -> None:
        payload = bytes.fromhex("88da93ae8b4397cd81ab")
        tokenization = tokenize_payload(payload)
        self.assertTrue(tokenization.supported)
        self.assertEqual(tokenization.glyph_count, 5)
        self.assertEqual(tokenization.line_width, 56)
        self.assertEqual(encode_tokens(tokenization), payload + b"\x00")
        self.assertEqual(tokenization.tokens[0].glyph_class, "wide")

    def test_opaque_ascii_and_unaligned_tail_are_not_named(self) -> None:
        ascii_tokens = tokenize_payload(b"DEFAULT")
        self.assertFalse(ascii_tokens.supported)
        self.assertEqual(ascii_tokens.tokens[0].kind, "opaque_ascii_or_format")
        tail_tokens = tokenize_payload(bytes.fromhex("8148ff"))
        self.assertFalse(tail_tokens.supported)
        self.assertEqual(tail_tokens.tokens[-1].kind, "opaque_unaligned_tail")

    def test_static_codepage_offsets_match_m16_runtime_points(self) -> None:
        self.assertEqual(codepage_offset(0x8983, "narrow"), 0x1500)
        self.assertEqual(codepage_offset(0xDA88, "wide"), 0x5BEA)
        self.assertEqual(code_unit_slot(0x8983, "narrow", 0x1980), 0x1500 // NARROW_STRIDE)
        self.assertEqual(code_unit_slot(0xDA88, "wide", 0x2E8A8), 0x5BEA // WIDE_STRIDE)

    def test_record_summary_reports_source_safe_noop(self) -> None:
        rom = bytearray(0x120)
        rom[0x100:0x102] = bytes.fromhex("8140")
        rom[0x102] = 0
        summary = record_summary(bytes(rom), {"offset": 0x100, "text": "　"})
        self.assertTrue(summary["no_op_byte_identical"])
        self.assertEqual(summary["encoded_record_sha256"], sha256(bytes.fromhex("814000")))
        self.assertEqual(summary["terminator_kind"], "NUL")

    def test_consumer_has_no_verified_single_byte_glyph_path(self) -> None:
        report = static_consumer_report(bytes(0x9000))
        branch = report["glyph_class_branch"]
        self.assertEqual(branch["verified_glyph_unit_bytes"], 2)
        self.assertFalse(branch["single_byte_glyph_path"])

    def test_cohort_is_bounded_and_centered(self) -> None:
        rows = [{"offset": value} for value in range(0x100, 0x180, 4)]
        cohort = select_cohort(rows, 0x140, 16)
        self.assertEqual(len(cohort), 16)
        self.assertIn(0x140, [int(row["offset"]) for row in cohort])
        with self.assertRaises(M17Error):
            select_cohort(rows, 0x140, 8)


if __name__ == "__main__":
    unittest.main()
