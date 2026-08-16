#!/usr/bin/env python3
"""Tests for the common-tool B3CJ M5.5 runtime case manifest."""

from __future__ import annotations

import pathlib
import unittest

from core.gba.runtime_validation.manifest import load_manifest


CASE = pathlib.Path(__file__).parents[1] / "research" / "m5.5-runtime-session-case.json"


class M5RuntimeSessionCaseTest(unittest.TestCase):
    def test_manifest_is_strict_and_target_scoped(self) -> None:
        manifest = load_manifest(CASE)
        self.assertEqual(manifest["case_id"], "b3cj.m5.5.palette-queue")
        self.assertEqual(manifest["rom"]["sha256"], "acfb3587a8217bf4ea444daf25f32c0947998a9203ee874db5006d7b6b016db6")
        self.assertEqual(manifest["rom"]["game_code_hex"], "4233434a")
        self.assertEqual(manifest["runtime"]["actions"][0]["address"], "0x08006BA4")
        self.assertEqual(manifest["runtime"]["actions"][1]["regions"][1]["length"], 1024)

    def test_manifest_has_no_rom_path_or_source_payload(self) -> None:
        text = CASE.read_text(encoding="utf-8")
        self.assertNotIn("source_text", text)
        self.assertNotIn("roms/", text)
        self.assertNotIn("work/", text)


if __name__ == "__main__":
    unittest.main()
