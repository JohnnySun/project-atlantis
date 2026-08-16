#!/usr/bin/env python3
"""Offline tests for the bounded B3TJ consumer probe."""

import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import consumer_probe  # noqa: E402


class ConsumerProbeTests(unittest.TestCase):
    def test_active_low_key_values(self):
        self.assertEqual(consumer_probe.key_value("none"), 0x03FF)
        self.assertEqual(consumer_probe.key_value("start"), 0x03F7)
        self.assertEqual(consumer_probe.key_value("a"), 0x03FE)

    def test_sequence_parser(self):
        self.assertEqual(
            consumer_probe.parse_sequence("start:2,none:3,a:1"),
            [("start", 2), ("none", 3), ("a", 1)],
        )
        with self.assertRaises(ValueError):
            consumer_probe.parse_sequence("bad:1")

    def test_render_parameters_follow_gba_register_bits(self):
        params = consumer_probe.render_parameters(0x1260, 0xD001)
        self.assertEqual(params["bg1_charbase"], 0)
        self.assertEqual(params["bg1_screenbase"], 0x8000)
        self.assertEqual(params["bg1_bpp"], 4)
        self.assertEqual(params["obj_mapping"], "1d")

    def test_exact_tile_match_requires_nonzero_32_byte_tile(self):
        rom = b"\x00" * 16 + bytes(range(32)) + b"\x00" * 16
        vram = b"\x00" * 32 + bytes(range(32))
        rows = consumer_probe.exact_tile_matches(rom, vram)
        self.assertEqual(rows[0]["vram_offset"], "0x00020")
        self.assertEqual(rows[0]["rom_offsets"], ["0x000010"])

    def test_resolver_pointer_is_filtered_to_strict_window_record(self):
        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 12,
            }
        }
        result = consumer_probe.classify_resolved_pointer(
            0x08146EE0, records
        )
        self.assertEqual(result["status"], "confirmed-window-record")
        self.assertEqual(result["window"], "text-pool")
        self.assertEqual(result["record"]["string_id"], "sjis:0x146EE0")

    def test_resolver_pointer_does_not_promote_non_boundary_or_outside_value(self):
        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 12,
            }
        }
        non_boundary = consumer_probe.classify_resolved_pointer(
            0x08146EE1, records
        )
        self.assertEqual(
            non_boundary["status"], "confirmed-window-nonstrict-offset"
        )
        self.assertEqual(
            consumer_probe.classify_resolved_pointer(0, records)["status"],
            "null-result",
        )

    def test_destination_candidates_only_report_gba_ram(self):
        registers = {
            "r0": 0x02001000,
            "r1": 0x08146EE0,
            "r2": 0x03007000,
            "r3": 0x06000000,
            "sp": 0x03007DC4,
        }
        self.assertEqual(
            consumer_probe.destination_candidates(registers),
            {
                "r0": "0x02001000",
                "r2": "0x03007000",
                "sp": "0x03007DC4",
            },
        )


if __name__ == "__main__":
    unittest.main()
