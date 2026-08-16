#!/usr/bin/env python3
"""Offline tests for B3TJ runtime-probe helpers; no emulator is started."""

import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import runtime_probe  # noqa: E402


class RuntimeProbeTests(unittest.TestCase):
    def test_file_offset_maps_only_the_target_rom_window(self):
        self.assertEqual(
            runtime_probe.file_offset_for_gba(0x08001234, 0x100000), 0x1234
        )
        self.assertIsNone(runtime_probe.file_offset_for_gba(0x087FFFFF, 0x100000))

    def test_compression_header_reports_tag_and_declared_size(self):
        rom = bytes((0x30, 0x00, 0x02, 0x00))
        self.assertEqual(
            runtime_probe.compression_header(rom, 0),
            {"tag": 0x30, "name": "RLE", "declared_output_size": 0x200},
        )

    def test_unknown_header_is_not_promoted_to_a_codec(self):
        self.assertEqual(
            runtime_probe.compression_header(b"\x99\x01\x00\x00", 0),
            {"tag": 0x99, "name": "unknown"},
        )


if __name__ == "__main__":
    unittest.main()
