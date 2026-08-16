#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ pointer-table summary helper."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("scan_text_pointers.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_scan_text_pointers", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load scan_text_pointers.py")
SCAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCAN)


class ScanTextPointersTest(unittest.TestCase):
    def test_parse_table_spec_accepts_hex(self) -> None:
        self.assertEqual(SCAN.parse_table_spec("0x20:4"), (0x20, 4))

    def test_summary_counts_rom_targets_without_emitting_bytes(self) -> None:
        data = bytearray(0x100)
        for index, target in enumerate((0x40, 0x44, 0x40, 0x80)):
            data[0x10 + index * 4 : 0x14 + index * 4] = (0x08000000 + target).to_bytes(4, "little")
        report = SCAN.summarize_table(bytes(data), 0x10, 4)
        self.assertEqual(report["rom_pointer_count"], 4)
        self.assertEqual(report["unique_target_count"], 3)
        self.assertEqual(report["target_file_offset_min"], "0x000040")
        self.assertEqual(report["target_file_offset_max"], "0x000080")
        self.assertFalse("text" in report)

    def test_summary_rejects_out_of_range_table(self) -> None:
        with self.assertRaises(ValueError):
            SCAN.summarize_table(bytes(8), 4, 2)


if __name__ == "__main__":
    unittest.main()
