#!/usr/bin/env python3
"""ROM-independent tests for the bounded B3CJ static scanner."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("scan_static.py")
SPEC = importlib.util.spec_from_file_location("scan_static", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load scan_static.py")
SCAN_STATIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCAN_STATIC)


class ScanStaticTest(unittest.TestCase):
    def test_lz77_decoder_accepts_literal_and_back_reference(self) -> None:
        # "ABCABCABC": three literals followed by a length-6, distance-3 copy.
        stream = bytes.fromhex("10 09 00 00 10 41 42 43 30 02")
        self.assertEqual(SCAN_STATIC.decode_lz77(stream, 0), (9, 10))

    def test_rle_decoder_accepts_run_and_literal_block(self) -> None:
        # "AAAABC": a four-byte run followed by two literal bytes.
        stream = bytes.fromhex("30 06 00 00 81 41 01 42 43")
        self.assertEqual(SCAN_STATIC.decode_rle(stream, 0), (6, 9))

    def test_sjis16_scan_keeps_endian_and_pointer_evidence(self) -> None:
        text = "あいうえおかきく"
        direct = text.encode("shift_jis")
        little = b"".join(direct[index:index + 2][::-1] for index in range(0, len(direct), 2))
        pointer = (0x08000010).to_bytes(4, "little")
        data = b"\0" * 0x10 + direct + b"\0" * 0x10 + little + pointer
        candidates = SCAN_STATIC.scan_sjis16_runs(data)
        self.assertTrue(any(item["endian"] == "big" for item in candidates))
        self.assertTrue(any(item["endian"] == "little" for item in candidates))
        self.assertTrue(all("pointer_ref_offsets" in item for item in candidates))


if __name__ == "__main__":
    unittest.main()
