#!/usr/bin/env python3
"""Small synthetic tests for the bounded A6SJ pointer/caller classifier."""

from __future__ import annotations

import struct
import unittest

from classify_pointer_callers import (
    ROM_BASE,
    arm_literal_candidates,
    pointer_runs,
    thumb_literal_candidates,
)


class PointerCallerClassifierTest(unittest.TestCase):
    def test_thumb_literal_resolves_target(self) -> None:
        data = bytearray(0x80)
        # ldr r1, [pc, #0x10] at file 0x10 -> aligned PC 0x14 + 0x10 = 0x24.
        struct.pack_into("<H", data, 0x10, 0x4904)
        struct.pack_into("<I", data, 0x24, ROM_BASE + 0x76000)
        hits = thumb_literal_candidates(bytes(data), 0, len(data), 0x76000, 0x76100)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["literal_offset"], 0x24)
        self.assertEqual(hits[0]["target_offset"], 0x76000)

    def test_arm_literal_resolves_subtractive_target(self) -> None:
        data = bytearray(0x100)
        # ldr r0, [pc, #-4], ARM encoding 0xe51f0004 at file 0x20 -> 0x24.
        struct.pack_into("<I", data, 0x20, 0xE51F0004)
        struct.pack_into("<I", data, 0x24, ROM_BASE + 0x76010)
        hits = arm_literal_candidates(bytes(data), 0, len(data), 0x76000, 0x76100)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["literal_offset"], 0x24)
        self.assertEqual(hits[0]["target_offset"], 0x76010)

    def test_pointer_run_membership_is_bounded(self) -> None:
        data = bytearray(0x40)
        for index, value in enumerate((0x76000, 0x76008, 0x76010, 0x76018)):
            struct.pack_into("<I", data, 0x10 + index * 4, ROM_BASE + value)
        refs, runs = pointer_runs(bytes(data), 0x76000, 0x76100, 4)
        self.assertEqual(len(refs), 4)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["start"], 0x10)
        self.assertEqual(runs[0]["words"], 4)


if __name__ == "__main__":
    unittest.main()
