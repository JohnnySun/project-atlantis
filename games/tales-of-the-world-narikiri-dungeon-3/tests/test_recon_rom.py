#!/usr/bin/env python3
"""Small deterministic tests for the first-pass read-only recon tool."""

import struct
import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import recon_rom  # noqa: E402


class ReconRomTests(unittest.TestCase):
    def test_gba_header_checksum_uses_negative_0x19_constant(self):
        data = bytearray(0xC0)
        data[0xA0:0xAC] = b"TOWNARIKIRI3"
        data[0xAC:0xB0] = b"B3TJ"
        data[0xB0:0xB2] = b"AF"
        data[0xB2] = 0x96
        data[0xBD] = recon_rom.gba_header_checksum(data)
        self.assertEqual(data[0xBD], 0x31)
        self.assertTrue(recon_rom.header_record(data)["header_complement_ok"])

    def test_sjis_run_scanner_counts_structure_without_decoding_text(self):
        data = b"\x00" + "かなABC".encode("shift_jis") + b"\x00"
        rows = recon_rom.scan_sjis_runs(data, min_units=3)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].units, 5)
        self.assertEqual(rows[0].double_byte_units, 2)
        self.assertEqual(rows[0].single_byte_units, 3)

    def test_pointer_run_normalizes_gba_addresses_to_file_offsets(self):
        data = bytearray(0x100)
        for index, target in enumerate((0x20, 0x24, 0x28, 0x2C)):
            struct.pack_into("<I", data, 0x40 + index * 4, recon_rom.ROM_BASE + target)
        rows = recon_rom.pointer_runs(bytes(data), min_run=4)
        self.assertEqual(rows[0]["table_offset"], 0x40)
        self.assertEqual(rows[0]["words"], 4)
        self.assertEqual(rows[0]["first_target"], 0x20)
        self.assertEqual(rows[0]["last_target"], 0x2C)

    def test_compression_candidates_are_only_structural_signals(self):
        data = bytearray(0x40)
        data[0:4] = bytes((0x10, 0x20, 0x00, 0x00))
        data[4:8] = bytes((0x24, 0x20, 0x00, 0x00))
        data[8:12] = bytes((0x30, 0x20, 0x00, 0x00))
        rows = recon_rom.compression_candidates(bytes(data), max_size=0x100)
        self.assertEqual(len(rows["LZ77"]), 1)
        self.assertEqual(len(rows["Huffman"]), 1)
        self.assertEqual(len(rows["RLE"]), 1)


if __name__ == "__main__":
    unittest.main()
