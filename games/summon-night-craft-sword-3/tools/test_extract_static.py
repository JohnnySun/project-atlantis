#!/usr/bin/env python3
"""Tests for the bounded B3CJ static extractor."""

from __future__ import annotations

import importlib.util
import pathlib
import struct
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("extract_static.py")
SPEC = importlib.util.spec_from_file_location("extract_static", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load extract_static.py")
EXTRACT_STATIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTRACT_STATIC)


def make_literal_lz77(decoded: bytes) -> bytes:
    if len(decoded) > 0xFFFFFF:
        raise ValueError("test payload too large")
    result = bytearray(b"\x10" + len(decoded).to_bytes(3, "little"))
    for start in range(0, len(decoded), 8):
        chunk = decoded[start : start + 8]
        result.append(0)
        result.extend(chunk)
    return bytes(result)


class ExtractStaticTest(unittest.TestCase):
    def test_lz77_uses_gba_msb_first_flags(self) -> None:
        decoded = b"PSI3" + bytes(12) + b"hello"
        compressed = make_literal_lz77(decoded)
        output, consumed = EXTRACT_STATIC.decode_lz77(compressed, 0)
        self.assertEqual(output, decoded)
        self.assertEqual(consumed, len(compressed))

    def test_text_record_marker_terminator_and_shift_jis(self) -> None:
        source = "ポータル"
        decoded = b"PSI3" + bytes(12)
        decoded += b"\x08\x03" + source.encode("shift_jis") + b"\x00\x00"
        records = list(EXTRACT_STATIC.parse_text_records(decoded, resource_id=12))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decompressed_offset"], 0x10)
        self.assertEqual(records[0]["source_text"], source)
        self.assertEqual(records[0]["raw_length"], len(source.encode("shift_jis")))
        self.assertEqual(records[0]["control_tokens"], ["0x0308", "0x0000"])

    def test_resource_pointer_uses_sixteen_byte_units(self) -> None:
        data = bytearray(0x180)
        table_offset = 0x100
        # For resource 0, csm3 reads table[2] and table[3].
        struct.pack_into("<II", data, table_offset + 8, 2, 7)
        resolved = EXTRACT_STATIC.resolve_script_resource(
            bytes(data), resource_id=0, table_file_offset=table_offset, table_size=0x20
        )
        self.assertEqual(resolved["relative_units"], 2)
        self.assertEqual(resolved["span_units"], 7)
        self.assertEqual(resolved["payload_file_offset"], table_offset + 2 * 16)

    def test_bounded_record_limit(self) -> None:
        source = "はい".encode("shift_jis")
        decoded = b"PSI3" + bytes(12)
        decoded += (b"\x08\x03" + source + b"\x00\x00") * 3
        records = list(EXTRACT_STATIC.parse_text_records(decoded, resource_id=1))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["decompressed_offset"], 0x10)


if __name__ == "__main__":
    unittest.main()
