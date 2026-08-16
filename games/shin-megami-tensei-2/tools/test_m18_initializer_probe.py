#!/usr/bin/env python3
"""Tests for the bounded A5TJ M1.8 initializer probe."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m18_initializer_probe as probe  # noqa: E402


class M18InitializerProbeTests(unittest.TestCase):
    def test_thumb_store_decode_exposes_source_and_width(self) -> None:
        rom = bytearray(0x100)
        address = probe.ROM_BASE + 0x20
        struct.pack_into("<H", rom, address - probe.ROM_BASE, 0x6008)
        result = probe._decode_thumb_store(bytes(rom), address)
        self.assertEqual(result["form"], "str_word_imm")
        self.assertEqual(result["source_register"], 0)
        self.assertEqual(result["base_register"], 1)
        self.assertEqual(result["width"], 4)

    def test_literal_store_candidate_requires_loaded_base_register(self) -> None:
        rom = bytearray(0x200)
        literal_address = probe.ROM_BASE + 0x100
        instruction_address = probe.ROM_BASE + 0x20
        struct.pack_into("<H", rom, instruction_address - probe.ROM_BASE, 0x4800)
        struct.pack_into("<I", rom, literal_address - probe.ROM_BASE, probe.SELECTOR_TABLE_GLOBAL)
        # LDR r0,[pc,#0x3c] -> aligned PC base 0x08000024, literal 0x08000114;
        # use an exact helper-produced instruction instead of relying on this
        # synthetic offset for the candidate assertion.
        struct.pack_into("<H", rom, instruction_address - probe.ROM_BASE, 0x4837)
        struct.pack_into("<H", rom, instruction_address + 2 - probe.ROM_BASE, 0x6000)
        refs = probe._literal_refs_to(bytes(rom), probe.SELECTOR_TABLE_GLOBAL)
        self.assertEqual(len(refs), 1)
        candidates = probe._initializer_candidates(bytes(rom), refs)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["store"]["base_register"], 0)

    def test_key_driver_has_idle_hold_gap_and_no_table_write(self) -> None:
        driver = probe._NaturalKeyDriver(["a", "start"], idle_reads=2, hold_reads=1, gap_reads=1)
        values = [driver.next_value() for _ in range(7)]
        self.assertEqual(values[0][0], probe.KEY_VALUES["none"])
        self.assertEqual(values[2][0], probe.KEY_VALUES["a"])
        self.assertEqual(values[3][0], probe.KEY_VALUES["none"])
        self.assertEqual(driver.sent, ["a", "start"])
        self.assertEqual(driver.completed, ["a", "start"])

    def test_runtime_summary_has_no_events_or_raw_payload(self) -> None:
        report = {
            "path_id": "boot-start",
            "natural": True,
            "synthetic": False,
            "stopped_reason": "stop-or-wall-limit",
            "stop_count": 8,
            "keyinput_read_hits": 4,
            "keys_requested": ["a"],
            "completed_transitions": ["a"],
            "initializer": {"table_base": {"address": "0x08012340"}},
            "breakpoint_counts": {"selector_entry": 1, "queue_producer": 1},
            "watchpoint_counts": {"selector_table_pointer_global": 1},
            "install_failures": [],
            "events": [
                {"site": "selector_entry", "target_descriptor_selected": True},
                {"site": "queue_producer", "source": {"address": "0x081869c8"}},
                {"site": "indirect_trampoline", "target": {"address": "0x080baef0"}},
            ],
        }
        summary = probe.runtime_summary(report)
        self.assertEqual(summary["natural_selector_hits"], 1)
        self.assertEqual(summary["target_descriptor_hits"], 1)
        self.assertEqual(summary["producer_source_counts"]["0x081869c8"], 1)
        self.assertNotIn("events", summary)


if __name__ == "__main__":
    unittest.main()
