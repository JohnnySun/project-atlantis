#!/usr/bin/env python3
"""Tests for the static B3CJ resource relocation POC."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


GAME_ROOT = pathlib.Path(__file__).parents[1]
TOOL_PATH = GAME_ROOT / "tools" / "relocate_resource_poc.py"
SPEC = importlib.util.spec_from_file_location("relocate_resource_poc", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load relocate_resource_poc.py")
POC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POC)

ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"


class RelocateResourcePocTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file()
        cls.rom = ROM_PATH.read_bytes() if cls.available else b""

    def require_artifacts(self) -> None:
        if not self.available:
            self.skipTest("ignored B3CJ ROM unavailable")

    def test_resource_24_redirect_reextracts_all_records(self) -> None:
        self.require_artifacts()
        relocated, summary = POC.relocate(self.rom)
        self.assertEqual(len(relocated), len(self.rom))
        self.assertEqual(summary["resource_id"], 24)
        self.assertEqual(summary["records"]["before"], 361)
        self.assertEqual(summary["records"]["after"], 361)
        self.assertTrue(summary["records"]["byte_identity"])
        self.assertTrue(summary["destination"]["zero_filled"])
        self.assertEqual(summary["destination"]["aligned_pointer_references"], 0)

    def test_nonzero_destination_is_rejected(self) -> None:
        self.require_artifacts()
        with self.assertRaises(ValueError):
            POC.validate_destination(self.rom, 0x172611C, 0x570)


if __name__ == "__main__":
    unittest.main()
