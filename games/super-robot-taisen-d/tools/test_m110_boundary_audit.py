#!/usr/bin/env python3
"""Pure tests for the source-safe M1.10 boundary audit."""

from __future__ import annotations

import unittest

from m110_boundary_audit import BoundaryAuditError, audit_record, build_report


class M110BoundaryAuditTest(unittest.TestCase):
    def test_audit_record_reports_nul_and_does_not_emit_source_text(self) -> None:
        rom = bytearray(64)
        rom[8:10] = bytes.fromhex("8260")
        rom[10] = 0
        metadata = audit_record(bytes(rom), {"offset": 8, "text": "Ａ"})
        self.assertEqual(metadata["terminator"], "NUL")
        self.assertEqual(metadata["payload_length"], 2)
        self.assertTrue(metadata["byte_identity_no_op"])
        self.assertNotIn("text", metadata)

    def test_source_mismatch_fails_closed(self) -> None:
        rom = bytearray(64)
        rom[8:10] = bytes.fromhex("8260")
        rom[10] = 0
        with self.assertRaisesRegex(BoundaryAuditError, "differs from ROM"):
            audit_record(bytes(rom), {"offset": 8, "text": "Ｂ"})

    def test_opaque_record_is_byte_preserved_but_contract_rejected(self) -> None:
        rom = bytearray(64)
        rom[8:10] = b"AB"
        rom[10] = 0
        metadata = audit_record(bytes(rom), {"offset": 8, "text": "AB"})
        self.assertEqual(metadata["status"], "opaque_or_unaligned")
        self.assertTrue(metadata["byte_identity_no_op"])
        self.assertFalse(metadata["contract_eligible"])

    def test_report_rejects_overlapping_records(self) -> None:
        rom = bytearray(128)
        rom[8:10] = bytes.fromhex("8260")
        rom[10] = 0
        rom[10:12] = bytes.fromhex("8261")
        rom[12] = 0
        with self.assertRaisesRegex(BoundaryAuditError, "source table differs"):
            build_report(
                bytes(rom),
                [{"offset": 8, "text": "Ａ"}, {"offset": 10, "text": "Ａ"}],
                source_start=8,
                source_end=32,
                center=8,
                cohort_size=2,
            )


if __name__ == "__main__":
    unittest.main()
