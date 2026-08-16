#!/usr/bin/env python3
"""Tests for the all-payload B3CJ semantic no-op rebuild."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("rebuild_full_container.py")
SPEC = importlib.util.spec_from_file_location("rebuild_full_container", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load rebuild_full_container.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class RebuildFullContainerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()
        if cls.available:
            cls.rom_data = ROM_PATH.read_bytes()

    def require_rom(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM is not available")

    def test_all_nonzero_payloads_rebuild_and_preserve_aliases(self) -> None:
        self.require_rom()
        rebuilt, summary = AUDIT.rebuild(self.rom_data)
        self.assertEqual(len(rebuilt), len(self.rom_data))
        self.assertTrue(summary["static_only"])
        self.assertEqual(summary["translation_targets_added"], 0)
        self.assertEqual(summary["directory"]["resource_count"], 79)
        self.assertEqual(summary["directory"]["nonzero_resource_count"], 68)
        self.assertEqual(summary["directory"]["unique_positive_payload_groups"], 68)
        self.assertEqual(summary["directory"]["zero_span_resource_ids"], [2, 3, 4, 5, 9, 10, 26, 27, 28, 29, 30])
        self.assertTrue(summary["directory"]["byte_identical"])
        self.assertEqual(summary["payload_groups"]["rewritten_count"], 68)
        self.assertEqual(summary["records"]["logical_before"], 361)
        self.assertEqual(summary["records"]["logical_after"], 361)
        self.assertEqual(summary["records"]["unique_positive_payload_records"], 235)
        self.assertTrue(summary["roundtrip"]["byte_identical"])
        self.assertEqual(summary["roundtrip"]["resources"], 79)
        self.assertEqual(summary["roundtrip"]["records"], 361)
        self.assertEqual(summary["roundtrip"]["source_reencode_records"], 361)
        self.assertTrue(summary["byte_level"]["directory_byte_identical"])
        self.assertFalse(summary["byte_level"]["changed_outside_positive_payload_spans"])
        self.assertNotEqual(summary["rebuilt_rom"]["sha256"], summary["clean_rom"]["sha256"])

    def test_capacity_overrun_is_fail_closed(self) -> None:
        self.require_rom()
        original = AUDIT.LZ_ENCODER.lz77_compress

        def too_large(decoded: bytes) -> bytes:
            return bytes(len(decoded) + 0x10000)

        AUDIT.LZ_ENCODER.lz77_compress = too_large
        try:
            with self.assertRaisesRegex(ValueError, "compressed output exceeds span"):
                AUDIT.rebuild(self.rom_data)
        finally:
            AUDIT.LZ_ENCODER.lz77_compress = original

    def test_clean_identity_is_required(self) -> None:
        self.require_rom()
        altered = bytearray(self.rom_data)
        altered[0x1000] ^= 0x01
        with self.assertRaisesRegex(ValueError, "clean B3CJ SHA-256 mismatch"):
            AUDIT.rebuild(bytes(altered))

    def test_pointer_group_rejects_alias_span_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive alias span mismatch"):
            AUDIT._group_entries(
                [
                    {"resource_id": 1, "payload_file_offset": 0x100, "span_units": 2, "span_bytes": 32},
                    {"resource_id": 2, "payload_file_offset": 0x100, "span_units": 3, "span_bytes": 48},
                ]
            )


if __name__ == "__main__":
    unittest.main()
