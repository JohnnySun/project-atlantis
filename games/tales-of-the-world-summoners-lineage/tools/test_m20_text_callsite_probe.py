#!/usr/bin/env python3
"""Pure tests for the bounded static text-callsite index."""

from __future__ import annotations

import unittest
import struct

from m20_text_callsite_probe import (
    argument_provenance,
    caller_candidate,
    thumb_bl_target,
)


class M20TextCallsiteProbeTests(unittest.TestCase):
    def test_thumb_bl_decoder(self) -> None:
        data = bytearray(8)
        # BL at file offset 0 targeting bus address 0x08000010.
        target_offset = 0x10
        pc = 0x08000000
        displacement = target_offset - 4
        encoded = displacement & 0x7FFFFF
        first = 0xF000 | ((encoded >> 12) & 0x7FF)
        second = 0xF800 | ((encoded >> 1) & 0x7FF)
        data[0:4] = struct.pack("<HH", first, second)
        self.assertEqual(thumb_bl_target(bytes(data) + bytes(0x20), 0), pc + 4 + displacement)

    def test_literal_argument_provenance_has_no_instruction_bytes(self) -> None:
        data = bytearray(0x40)
        # ldr r2,[pc,#0] at offset 0; literal is at aligned PC+4.
        data[0:2] = struct.pack("<H", 0x4A00)
        data[4:8] = struct.pack("<I", 0x08000020)
        provenance = argument_provenance(bytes(data), 8, window=8)
        self.assertEqual(provenance["simple_register_values"]["r2"], "0x08000020")
        self.assertNotIn("instruction_bytes", provenance)

    def test_caller_candidate_keeps_stream_unclassified(self) -> None:
        data = bytearray(0x80)
        data[0:2] = struct.pack("<H", 0x4A00)
        data[4:8] = struct.pack("<I", 0x08000020)
        data[0x20:0x24] = (0x005E).to_bytes(2, "little") + (0).to_bytes(2, "little")
        candidate = caller_candidate(bytes(data), 8, max_units=8)
        self.assertEqual(candidate["role"], "unclassified-rom-pointer-stream-candidate")
        self.assertTrue(candidate["stream"]["terminated_by_0000"])
        self.assertEqual(candidate["runtime_context"], "none")
        self.assertFalse(candidate["source_text_emitted"])


if __name__ == "__main__":
    unittest.main()
