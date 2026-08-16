#!/usr/bin/env python3
"""Unit tests for the bounded A5TJ M1.7 descriptor probe."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m17_descriptor_probe as probe  # noqa: E402


class M17DescriptorProbeTests(unittest.TestCase):
    def test_first_command_run_uses_callback_payload_contract(self) -> None:
        start = probe.ROM_BASE + 0x100
        end = start + 0x30
        rom = bytearray(end - probe.ROM_BASE)
        words = [
            0x0B,
            0x08000101,
            0x00000002,
            0x00,
            0x0A,
            0x08000201,
            probe.DESCRIPTOR_SENTINEL,
        ]
        for index, value in enumerate(words):
            struct.pack_into("<I", rom, start - probe.ROM_BASE + index * 4, value)
        result = probe._first_command_run(bytes(rom), start, end)
        self.assertEqual(result["status"], "sentinel_reached")
        self.assertEqual(result["command_count"], 3)
        self.assertEqual(result["commands"][0]["payload_words"], 2)
        self.assertEqual(result["commands"][2]["payload_words"], 1)
        self.assertEqual(result["commands"][0]["payload_function_pointer_count"], 1)

    def test_selector_data_ref_is_group_one_index_seven(self) -> None:
        self.assertEqual(
            (probe.SELECTOR_DATA_REF - probe.SELECTOR_GROUP1_TABLE) // 4,
            7,
        )

    def test_known_descriptor_targets_keep_thumb_entry_metadata(self) -> None:
        rom = bytearray(0x200)
        entry = probe.ROM_BASE + 0x80
        struct.pack_into("<H", rom, entry - probe.ROM_BASE, 0xB510)
        result = probe._known_thumb_target(bytes(rom), entry, 0x20, "test")
        self.assertEqual(result["entry_halfword"], "0xb510")
        self.assertTrue(result["thumb_pointer"]["address"].endswith("81"))
        self.assertTrue(result["arm7tdmi_thumb_entry"])

    def test_runtime_summary_separates_selector_and_indirect_targets(self) -> None:
        report = {
            "stopped_reason": "stop-or-wall-limit",
            "stop_count": 12,
            "keyinput_read_hits": 8,
            "keys_requested": ["a", "down"],
            "breakpoint_counts": {"selector_entry": 2},
            "watchpoint_counts": {"staging_buffer": 1},
            "install_failures": [],
            "events": [
                {"site": "selector_entry", "target_descriptor_selected": True},
                {"site": "selector_entry", "target_descriptor_selected": False},
                {"site": "indirect_trampoline", "target": {"address": "0x080baef0"}},
                {"site": "lz77_wrapper", "source": {"address": "0x081839f4"}},
            ],
        }
        result = probe.runtime_summary(report)
        self.assertEqual(result["selector_hit_count"], 2)
        self.assertEqual(result["target_descriptor_selected_count"], 1)
        self.assertEqual(result["indirect_target_counts"]["0x080baef0"], 1)
        self.assertEqual(result["distinct_source_addresses"], ["0x081839f4"])
        self.assertNotIn("events", result)

    def test_key_scheduler_has_idle_and_release_gap(self) -> None:
        scheduler = probe._KeyScheduler(["a"], idle_reads=2, hold_reads=1, gap_reads=1)
        values = [scheduler.value_for_next_read() for _ in range(5)]
        self.assertEqual(values[0:2], [probe.KEY_VALUES["none"]] * 2)
        self.assertEqual(values[2], probe.KEY_VALUES["a"])
        self.assertEqual(values[3], probe.KEY_VALUES["none"])
        self.assertEqual(values[4], probe.KEY_VALUES["none"])


if __name__ == "__main__":
    unittest.main()
