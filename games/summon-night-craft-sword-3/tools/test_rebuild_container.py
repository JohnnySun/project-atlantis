#!/usr/bin/env python3
"""Tests for the bounded B3CJ semantic container rebuild verifier."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("rebuild_container.py")
SPEC = importlib.util.spec_from_file_location("rebuild_container", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load rebuild_container.py")
REBUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REBUILD)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class RebuildContainerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()
        if cls.available:
            cls.rom_data = ROM_PATH.read_bytes()

    def require_rom(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM is not available")

    def test_all_reviewed_resources_rebuild_semantically_and_stay_in_spans(self) -> None:
        self.require_rom()
        rebuilt, summary = REBUILD.rebuild(self.rom_data)
        self.assertEqual(len(rebuilt), len(self.rom_data))
        self.assertTrue(summary["static_only"])
        self.assertEqual(summary["translation_targets_added"], 0)
        self.assertEqual(summary["resources"]["resource_count"], 13)
        self.assertEqual(summary["resources"]["payload_group_count"], 11)
        self.assertEqual(summary["records"]["before"], 361)
        self.assertEqual(summary["records"]["after"], 361)
        self.assertTrue(summary["records"]["identity_byte_identical"])
        self.assertEqual(len(summary["records"]["stable_identity_sha256"]), 64)
        self.assertTrue(summary["roundtrip"]["psi3_stream_byte_identical"])
        self.assertEqual(summary["roundtrip"]["source_reencode_records"], 361)
        self.assertFalse(summary["byte_level"]["changed_outside_payload_spans"])
        self.assertTrue(summary["byte_level"]["directory_byte_identical"])
        self.assertTrue(all(group["capacity_ok"] for group in summary["resources"]["groups"]))
        self.assertNotEqual(summary["rebuilt_rom"]["sha256"], summary["clean_rom"]["sha256"])

    def test_compressed_capacity_is_fail_closed(self) -> None:
        self.require_rom()
        original = REBUILD.LZ_ENCODER.lz77_compress

        def too_large(decoded: bytes) -> bytes:
            return bytes(len(decoded) + 0x10000)

        REBUILD.LZ_ENCODER.lz77_compress = too_large
        try:
            with self.assertRaisesRegex(ValueError, "compressed output exceeds span"):
                REBUILD.rebuild(self.rom_data)
        finally:
            REBUILD.LZ_ENCODER.lz77_compress = original

    def test_clean_identity_is_required(self) -> None:
        self.require_rom()
        altered = bytearray(self.rom_data)
        altered[0x1000] ^= 0x01
        with self.assertRaisesRegex(ValueError, "clean B3CJ SHA-256 mismatch"):
            REBUILD.rebuild(bytes(altered))


if __name__ == "__main__":
    unittest.main()
