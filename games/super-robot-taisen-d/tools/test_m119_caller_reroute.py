from __future__ import annotations

import unittest

from m119_caller_reroute import build_report


class M119CallerRerouteTest(unittest.TestCase):
    def test_natural_ram_buffer_hit_stays_fail_closed(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        rom = (root / "games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M18_static_poc.gba").read_bytes()
        probe = {
            "gdb": {"port": 2346, "single_connection": True, "fresh_process_required": True, "window_seconds": 3.0},
            "initializer": {"nonzero_base_guard": True, "slot_values": {"narrow": "0x0814F664", "wide": "0x08120DBC"}},
            "caller": {
                "status": "consumer_entry_observed",
                "consumer_pc": "0x08008724",
                "caller_callsite": "0x08066050",
                "lr": "0x08066055",
                "registers": {"r0": "0x02018368", "r7": "0x02018368"},
                "source_pointer": "0x02018368",
                "source_pointer_region": "ram_or_io",
                "target_pointer": "0x08080858",
                "target_pointer_match": False,
            },
        }
        report = build_report(rom, probe)
        self.assertTrue(report["gate"]["known_direct_callsite_static_match"])
        self.assertTrue(report["gate"]["argument_setup_verified"])
        self.assertTrue(report["gate"]["ram_buffer_consumer_observed"])
        self.assertFalse(report["gate"]["target_pointer_match"])
        self.assertFalse(report["gate"]["target_render_proven"])

    def test_unknown_callsite_does_not_promote_target(self) -> None:
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        rom = (root / "games/super-robot-taisen-d/work/Super_Robot_Taisen_D_A6SJ_M18_static_poc.gba").read_bytes()
        probe = {
            "gdb": {"port": 2346, "single_connection": True, "fresh_process_required": True},
            "initializer": {"nonzero_base_guard": True},
            "caller": {
                "status": "consumer_entry_observed",
                "consumer_pc": "0x08008724",
                "caller_callsite": "0x08065000",
                "lr": "0x08065005",
                "source_pointer": "0x02018000",
                "source_pointer_region": "ram_or_io",
                "target_pointer": "0x08080858",
                "target_pointer_match": False,
            },
        }
        report = build_report(rom, probe)
        self.assertFalse(report["gate"]["known_direct_callsite_static_match"])
        self.assertFalse(report["gate"]["target_render_proven"])


if __name__ == "__main__":
    unittest.main()
