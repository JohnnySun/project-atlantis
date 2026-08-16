#!/usr/bin/env python3
"""Unit tests for the bounded A5TJ M1.6 queue probe."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m16_queue_probe as probe  # noqa: E402


class M16QueueProbeTests(unittest.TestCase):
    def test_fixed_dma_decode_keeps_literal_pool_and_transfer_units(self) -> None:
        rom = bytearray(0x300)
        entry = 0x08000100
        offset = entry - probe.ROM_BASE
        for index, instruction in enumerate(probe.FIXED_DMA_INSTRUCTIONS):
            struct.pack_into("<H", rom, offset + index * 2, instruction)
        struct.pack_into(
            "<4I",
            rom,
            offset + 0x14,
            0x040000D4,
            0x02001000,
            0x06013000,
            0x84000700,
        )

        result = probe.decode_fixed_dma(bytes(rom), entry)

        self.assertTrue(result["instruction_pattern_valid"])
        self.assertEqual(result["source_store_pc"], "0x08000104")
        decoded = result["decoded"]
        self.assertEqual(decoded["source"]["value"], "0x02001000")
        self.assertEqual(decoded["destination"]["value"], "0x06013000")
        self.assertEqual(decoded["control"]["value"], "0x84000700")
        self.assertEqual(decoded["transfer_units"], 0x700)

    def test_queue_entry_metadata_is_hash_and_fields_only(self) -> None:
        entry = bytearray(0x24)
        struct.pack_into("<HHH", entry, 0x00, 1, 2, 0xFFFF)
        struct.pack_into("<I", entry, 0x10, 3)
        struct.pack_into("<I", entry, 0x14, 0x08509CF8)
        struct.pack_into("<I", entry, 0x20, 0x10241224)

        result = probe.queue_entry_metadata(bytes(entry), 0x02009068)

        self.assertEqual(result["address"], "0x02009068")
        self.assertEqual(result["length"], 0x24)
        self.assertEqual(result["state"], "0x00000001")
        self.assertEqual(result["source"]["rom_offset"], "0x00509cf8")
        self.assertNotIn("bytes", result)

    def test_dma_watch_value_comes_from_store_register(self) -> None:
        rom = bytearray(0x200)
        # Stop PC follows STR r0, [r1, #8]; this is the DMA3 CNT store form.
        struct.pack_into("<H", rom, 0x100, 0x6088)
        decoded = probe.thumb_store_info(bytes(rom), 0x08000102)

        self.assertEqual(decoded["form"], "str_word_imm")
        self.assertEqual(decoded["register"], 0)
        self.assertEqual(decoded["base_register"], 1)
        self.assertEqual(decoded["offset"], 8)

    def test_runtime_summary_discards_event_payloads(self) -> None:
        report = {
            "stopped_reason": "event-or-wall-limit",
            "keyinput_read_hits": 3,
            "start_sent": True,
            "watchpoint_counts": {"staging_buffer": 0},
            "queue_sources": [{"address": "0x08509cf8", "count": 1}],
            "events": [
                {"kind": "breakpoint", "site": "queue_producer"},
                {"kind": "watchpoint", "site": "staging_buffer"},
                {"kind": "breakpoint", "site": "obj_dma_0baecc"},
            ],
        }

        result = probe.runtime_summary(report)

        self.assertEqual(result["event_count"], 3)
        self.assertEqual(result["obj_dma_hits"], 1)
        self.assertEqual(result["staging_write_hits"], 1)
        self.assertEqual(result["queue_source_count"], 1)
        self.assertNotIn("events", result)

    def test_queue_contract_exposes_no_unconfirmed_head_tail_address(self) -> None:
        result = probe.queue_contract()

        self.assertEqual(result["entry_base"], "0x02009004")
        self.assertEqual(result["entry_stride"], "0x00000064")
        self.assertIn("no separate head/tail", result["head_tail_finding"])


if __name__ == "__main__":
    unittest.main()
