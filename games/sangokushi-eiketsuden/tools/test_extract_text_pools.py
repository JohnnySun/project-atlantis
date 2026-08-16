#!/usr/bin/env python3
"""ROM-independent tests for the source-safe B3EJ pool decoder."""

from __future__ import annotations

import importlib.util
import pathlib
import struct
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("extract_text_pools.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_extract_text_pools", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load extract_text_pools.py")
EXTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACT)


def synthetic_pool_rom() -> bytes:
    data = bytearray(0x500)
    data[0xAC:0xB0] = b"B3EJ"
    table_offset = 0x100
    text_offsets = (0x200, 0x208)
    for index, target in enumerate(text_offsets):
        struct.pack_into("<I", data, table_offset + index * 4, 0x08000000 + target)
    data[0x200:0x208] = "一部".encode("shift_jis") + b"\0"
    data[0x208:0x20D] = b"A\nB\0"
    return bytes(data)


class ExtractTextPoolsTest(unittest.TestCase):
    def test_decoder_keeps_source_only_in_local_record_and_reports_metadata(self) -> None:
        records = EXTRACT.decode_pool(synthetic_pool_rom(), "synthetic", 0x100, 2)
        self.assertEqual(records[0]["text"], "一部")
        metadata = EXTRACT.pool_metadata(records, "synthetic", 0x100)
        self.assertEqual(metadata["entry_count"], 2)
        self.assertEqual(metadata["unique_target_count"], 2)
        self.assertEqual(metadata["records_with_line_feed"], 1)
        self.assertNotIn("text", metadata)

    def test_decoder_version_and_source_hash_are_present(self) -> None:
        records = EXTRACT.decode_pool(synthetic_pool_rom(), "synthetic", 0x100, 2)
        self.assertEqual(records[0]["provenance"]["decoder_version"], EXTRACT.DECODER_VERSION)
        self.assertEqual(len(records[0]["provenance"]["source_hash"]), 64)
        self.assertEqual(len(records[0]["provenance"]["source_text_hash"]), 64)
        self.assertNotIn("raw_bytes", records[0]["provenance"])


if __name__ == "__main__":
    unittest.main()
