from __future__ import annotations

import unittest
from unittest.mock import patch

import m114_runtime_boundary as boundary


class M114RuntimeBoundaryTest(unittest.TestCase):
    def test_normalization_never_promotes_unmatched_consumer(self) -> None:
        rom = bytearray(0x900000)
        source_offset = 0x080858
        rom[source_offset : source_offset + 5] = bytes.fromhex("83e883e700")
        rom_hash = boundary.sha256(bytes(rom))
        trace = {
            "rom": {"sha256": rom_hash},
            "gdb": {"port": 2346, "single_connection": True, "fresh_process_required": True},
            "initializer": {"nonzero_base_guard": True, "slot_values": {"narrow": "0x0814F664", "wide": "0x08120DBC"}, "event_count": 3},
            "controlled_call": {
                "source_offset": source_offset,
                "events": [
                    {"kind": "codepage_lookup", "source_pointer": "0x02018368", "code_unit": "0x628D"},
                    {"kind": "tile_writer", "writer": {}},
                    {"kind": "glyph_complete"},
                ],
            },
        }
        with patch.object(boundary, "PATCHED_ROM_SHA256", rom_hash):
            report = boundary.build_report(trace, bytes(rom))
        self.assertFalse(report["requested_record"]["consumer_argument_match"])
        self.assertFalse(report["gate"]["requested_target_render_proven"])
        self.assertEqual(report["requested_record"]["unit_loop_status"], "natural_or_unmatched_consumer")


if __name__ == "__main__":
    unittest.main()
