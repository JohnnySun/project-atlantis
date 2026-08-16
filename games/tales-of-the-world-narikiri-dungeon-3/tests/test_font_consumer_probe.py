#!/usr/bin/env python3
"""Offline tests for the bounded B3TJ font consumer harness."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import font_consumer_probe  # noqa: E402


class FontConsumerProbeTests(unittest.TestCase):
    def test_asset_address_is_guarded_and_uses_static_stride(self):
        self.assertEqual(
            font_consumer_probe.font_asset_address(0x120), 0x080E00C4
        )
        with self.assertRaises(ValueError):
            font_consumer_probe.font_asset_address(-1)
        with self.assertRaises(ValueError):
            font_consumer_probe.font_asset_address(0x100000)

    def test_lr_maps_only_reviewed_font_map_callers(self):
        self.assertEqual(
            font_consumer_probe.callsite_from_lr(0x0800155B), 0x08001556
        )
        self.assertEqual(
            font_consumer_probe.callsite_from_lr(0x080015FD), 0x080015F8
        )
        self.assertIsNone(font_consumer_probe.callsite_from_lr(0x08009999))

    def test_metadata_row_has_no_memory_bytes(self):
        row = font_consumer_probe._stop_row(
            "T05thread:1;", "watch", 0x080E00C4,
            {"pc": 0x08001414, "lr": 0x0800155B, "r2": 0x120},
        )
        self.assertNotIn("bytes", row)
        self.assertNotIn("raw", row)
        self.assertEqual(row["stop_address"], "0x080E00C4")

    def test_bounded_fake_pipeline_keeps_only_stage_metadata(self):
        class FakeClient:
            def __init__(self):
                self.stops = [
                    ("T05thread:1;", {"pc": 0x080011A8, "lr": 0x0800155B, "r2": 0x120}),
                    ("rwatch:080e00c4;", {"pc": 0x080011D4, "lr": 0x0800155B, "r2": 0x120}),
                    ("watch:03000560;", {"pc": 0x080011F6, "lr": 0x0800155B, "r2": 0x120}),
                ]
                self.points = []

            def set_watchpoint(self, address, kind, watch_type):
                self.points.append(("watch+", address, kind, watch_type))

            def set_breakpoint(self, address, kind):
                self.points.append(("break+", address, kind))

            def continue_until_stop(self, _timeout):
                stop, registers = self.stops.pop(0)
                self.registers = registers
                return stop

            def read_registers(self):
                return self.registers

            def remove_watchpoint(self, address, kind, watch_type):
                self.points.append(("watch-", address, kind, watch_type))

            def remove_breakpoint(self, address, kind):
                self.points.append(("break-", address, kind))

        client = FakeClient()
        result = font_consumer_probe.trace_font_hit(
            client,
            "T05thread:1;",
            {"pc": font_consumer_probe.FONT_MAP_ENTRY, "lr": 0x0800155B, "r2": 0x120},
            rom_size=font_consumer_probe.EXPECTED_SIZE,
            stage_timeout=1.0,
            max_stage_stops=4,
        )
        self.assertEqual(result["pipeline_status"], "asset-read-and-scratch-write-observed")
        self.assertEqual(result["source_watch_status"], "confirmed-runtime-asset-read-candidate")
        self.assertEqual(result["scratch_status"], "confirmed-runtime-scratch-write-candidate")
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)


if __name__ == "__main__":
    unittest.main()
