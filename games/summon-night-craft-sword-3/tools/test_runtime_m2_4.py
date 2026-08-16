#!/usr/bin/env python3
"""Tests for the B3CJ M2.4 runtime diagnostic and static fallback evidence."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("runtime_m2_4.py")
SPEC = importlib.util.spec_from_file_location("runtime_m2_4", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load runtime_m2_4.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)

GAME_ROOT = TOOL_PATH.parents[1]
ROM_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
POC_PATH = GAME_ROOT / "work" / "m2.3-poc.gba"


class RuntimeM24Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = ROM_PATH.is_file() and POC_PATH.is_file()
        if cls.available:
            cls.rom_data = ROM_PATH.read_bytes()

    def require_local_inputs(self) -> None:
        if not self.available:
            self.skipTest("local ignored B3CJ ROM and M2.3 POC are not available")

    def test_static_writer_contracts_are_fixed_by_local_rom_hashes(self) -> None:
        self.require_local_inputs()
        report = RUNTIME.static_writer_evidence(self.rom_data)
        self.assertEqual(report["evidence_level"], "confirmed-static")
        self.assertEqual(len(report["writer_function_checks"]), 4)
        self.assertEqual(
            [(path["caller"], path["glyph_writer"], path["per_glyph_stride"]) for path in report["writer_paths"]],
            [
                ("sub_080036F8", "sub_08002CB4", "0x80"),
                ("sub_0800379C", "sub_080031E8", "0x40"),
            ],
        )
        self.assertIn("live VRAM/OAM destination is not proven", report["boundary"])

    def test_static_poc_reports_changed_and_adjacent_untouched_cells(self) -> None:
        self.require_local_inputs()
        report = RUNTIME.static_poc_evidence(POC_PATH)
        entries = report["changed_and_adjacent"]
        self.assertEqual([entry["label"] for entry in entries], ["untouched_adjacent", "changed_de", "changed_ni"])
        self.assertEqual(entries[0]["expected_glyph_id"], "0x844")
        self.assertEqual(entries[0]["lookup_status"], "not_assigned")
        self.assertEqual([entry["lookup_glyph_id"] for entry in entries[1:]], ["0x845", "0x846"])
        self.assertEqual([entry["lookup_status"] for entry in entries[1:]], ["mapped", "mapped"])
        self.assertEqual([len(entry["rows"]) for entry in entries], [12, 12, 12])
        self.assertEqual([len(entry["rows"][0]) for entry in entries], [12, 12, 12])

    def test_handshake_configuration_is_single_connection_with_retry(self) -> None:
        result = RUNTIME.handshake(24764, timeout=0.1, packet_delay=0.08, retry_delay=0.25)
        self.assertTrue(result["single_connection"])
        self.assertEqual(result["ack_and_retry_provider"], "core/gba/gdbstub_client.py")
        self.assertEqual(result["packet_delay_seconds"], 0.08)
        self.assertEqual(result["retry_delay_seconds"], 0.25)


if __name__ == "__main__":
    unittest.main()
