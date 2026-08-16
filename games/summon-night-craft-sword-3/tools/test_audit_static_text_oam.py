#!/usr/bin/env python3
"""Tests for the B3CJ static text-object -> OAM audit."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("audit_static_text_oam.py")
SPEC = importlib.util.spec_from_file_location("audit_static_text_oam", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_static_text_oam.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

ROM_PATH = TOOL_PATH.parents[1] / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class StaticTextOamTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()

    def require_rom(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM is not available")

    def test_text_object_chain_is_locally_hash_guarded(self) -> None:
        self.require_rom()
        report = AUDIT.audit_rom(ROM_PATH)
        self.assertEqual(report["evidence_level"], "confirmed-static-text-object-to-oam-buffer-and-oam-dma")
        self.assertEqual(len(report["function_checks"]), 2)
        self.assertEqual(len(report["literal_checks"]), 5)
        chain = report["text_object_chain"]
        self.assertEqual(chain["object_descriptor_stride"], "0x28 bytes per glyph in the local sub_0800B730 loop")
        self.assertEqual(chain["serializer_output"], "gOamBuffer at 0x030038b0")
        self.assertEqual(chain["hardware_copy"], "sub_08001BC0 -> DmaCopyBufferToOam.local_sub_080092CC -> 0x07000000")

    def test_tilemap_and_live_oam_remain_fail_closed(self) -> None:
        self.require_rom()
        report = AUDIT.audit_rom(ROM_PATH)
        self.assertEqual(report["base_audit"]["tilemap"]["destination"], "unknown")
        self.assertFalse(report["runtime"]["live_oam_read"])
        self.assertFalse(report["runtime"]["tilemap_proven"])

    def test_function_drift_fails_closed(self) -> None:
        self.require_rom()
        data = bytearray(ROM_PATH.read_bytes())
        data[0x901C] ^= 0x01
        with self.assertRaises(ValueError):
            AUDIT._function_checks(bytes(data))

    def test_literal_drift_fails_closed(self) -> None:
        self.require_rom()
        data = bytearray(ROM_PATH.read_bytes())
        data[0x90F4 : 0x90F8] = (0x030038B4).to_bytes(4, "little")
        with self.assertRaises(ValueError):
            AUDIT._literal_checks(bytes(data))


if __name__ == "__main__":
    unittest.main()
