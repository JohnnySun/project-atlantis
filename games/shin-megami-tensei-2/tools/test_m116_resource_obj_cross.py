#!/usr/bin/env python3
"""Tests for bounded M1.16 resource-to-OBJ matching."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m116_resource_obj_cross as probe  # noqa: E402


class M116ResourceObjCrossTests(unittest.TestCase):
    def test_aligned_offsets_are_bounded_to_requested_alignment(self) -> None:
        payload = b"x" * 32 + b"abc" + b"x" * 29 + b"abc" + b"x" * 29
        self.assertEqual(probe._aligned_offsets(payload, b"abc"), [32, 64])
        self.assertEqual(probe._aligned_offsets(payload, b"abc", alignment=2), [32, 64])

    def test_transform_match_report_contains_no_bytes(self) -> None:
        report = probe.analyze(
            bytes(0x100),
            bytes(0x18000),
            bytes(0x400),
            max_y=160,
            obj_base=0x10000,
            mapping="1d",
        )
        self.assertFalse(report["scope"]["full_rom_glyph_scan"])
        self.assertFalse(report["scope"]["raw_payload_emitted"])
        self.assertNotIn("raw_bytes", str(report))
        self.assertNotIn("decoded_text", str(report))


if __name__ == "__main__":
    unittest.main()
