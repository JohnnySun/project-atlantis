#!/usr/bin/env python3
"""Tests for the B3CJ static pointer/record/layout audit."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("audit_layout.py")
SPEC = importlib.util.spec_from_file_location("audit_layout", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_layout.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class AuditLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()

    def require_rom(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM is not available")

    def test_real_rom_pointer_and_record_contract(self) -> None:
        self.require_rom()
        report = AUDIT.audit_rom(ROM_PATH)
        self.assertEqual(report["evidence_level"], "confirmed-static-pointer-record-contract-with-unknown-layout-semantics")
        self.assertEqual(report["resources"], 13)
        self.assertEqual(report["records"], 361)
        pointer = report["pointer_contract"]
        self.assertEqual(pointer["pointer_scale_bytes"], 16)
        self.assertEqual(pointer["unique_payload_groups"], 11)
        self.assertEqual(pointer["zero_span_alias_resource_ids"], [9, 10])
        self.assertTrue(pointer["positive_span_intervals_non_overlapping"])
        text = report["text_contract"]
        self.assertEqual(text["marker"], "0x0308")
        self.assertEqual(text["terminator"], "0x0000")
        self.assertEqual(text["opaque_following_control_count"], 30)
        self.assertEqual(report["layout_contract"]["line_semantics"], "unknown_opaque_controls_remain_uninterpreted")

    def test_pointer_group_rejects_span_overrun(self) -> None:
        with self.assertRaises(ValueError):
            AUDIT._pointer_groups(
                [
                    {
                        "resource_id": 1,
                        "payload_file_offset": 0x100,
                        "span_bytes": 4,
                        "compressed_size": 8,
                    }
                ]
            )

    def test_shift_jis_code_unit_count_is_lossless(self) -> None:
        self.assertEqual(AUDIT._code_unit_count("賞品".encode("shift_jis")), 2)
        with self.assertRaises(UnicodeDecodeError):
            AUDIT._code_unit_count(b"\x82")


if __name__ == "__main__":
    unittest.main()
