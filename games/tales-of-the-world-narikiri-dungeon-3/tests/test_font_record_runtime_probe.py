#!/usr/bin/env python3
"""Offline tests for the bounded source-shaped font-loader runtime probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import font_record_runtime_probe  # noqa: E402


class FontRecordRuntimeProbeTests(unittest.TestCase):
    def test_source_pointer_classification_requires_exact_record_start(self):
        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 12,
            }
        }
        hit = font_record_runtime_probe.classify_source_pointer(0x08146EE0, records)
        self.assertEqual(hit["status"], "strict-record-start")
        self.assertEqual(hit["record"]["string_id"], "sjis:0x146EE0")
        interior = font_record_runtime_probe.classify_source_pointer(
            0x08146EE1, records
        )
        self.assertEqual(interior["status"], "strict-window-nonstrict-offset")

    def test_asset_pointer_classification_is_metadata_only(self):
        row = font_record_runtime_probe.classify_asset_pointer(0x080E00C4)
        self.assertEqual(row["status"], "asset-slot-address-shaped")
        self.assertEqual(row["index"], "0x00000120")
        self.assertNotIn("bytes", row)
        self.assertNotIn("raw", row)

    def test_bounded_fake_pipeline_confirms_source_and_asset_reads(self):
        class FakeClient:
            def __init__(self):
                self.stops = [
                    (
                        "rwatch:08146ee0;",
                        {"pc": 0x080021B6, "lr": 0x08015C2B, "r1": 0x08146EE0},
                    ),
                    (
                        "T05thread:1;",
                        {
                            "pc": 0x080021DA,
                            "lr": 0x08015C2B,
                            "r1": 0x08146EE0,
                            "r8": 0x080E00C4,
                        },
                    ),
                    (
                        "rwatch:080e00c4;",
                        {
                            "pc": 0x08002200,
                            "lr": 0x08015C2B,
                            "r1": 0x08146EE0,
                            "r8": 0x080E00C4,
                        },
                    ),
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

            def write_register(self, register_number, value):
                self.points.append(("register-write", register_number, value))
                if register_number == 1:
                    self.registers["r1"] = value

            def remove_watchpoint(self, address, kind, watch_type):
                self.points.append(("watch-", address, kind, watch_type))

            def remove_breakpoint(self, address, kind):
                self.points.append(("break-", address, kind))

        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 12,
            }
        }
        client = FakeClient()
        result = font_record_runtime_probe.trace_loader_hit(
            client,
            "T05thread:1;",
            {
                "pc": font_record_runtime_probe.FONT_LOADER_ENTRY,
                "lr": 0x08015C2B,
                "r1": 0x08146EE0,
            },
            records,
            desired_key=font_record_runtime_probe.NO_KEY,
            stage_timeout=1.0,
            max_stage_stops=4,
        )
        self.assertEqual(
            result["source_read_status"],
            "confirmed-runtime-strict-record-source-read",
        )
        self.assertEqual(
            result["asset_read_status"],
            "confirmed-runtime-asset-read-candidate",
        )
        self.assertEqual(result["pipeline_status"], "source-and-asset-read-observed")
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)

    def test_injected_source_is_explicitly_not_natural_flow_proof(self):
        class FakeClient:
            def __init__(self):
                self.registers = {
                    "pc": font_record_runtime_probe.FONT_LOADER_ENTRY,
                    "lr": 0x08015C2B,
                    "r1": 0x02001000,
                }
                self.stops = [
                    (
                        "rwatch:08146ee0;",
                        {"pc": 0x080021B6, "lr": 0x08015C2B, "r1": 0x08146EE0},
                    ),
                    (
                        "T05thread:1;",
                        {
                            "pc": 0x080021DA,
                            "lr": 0x08015C2B,
                            "r1": 0x08146EE0,
                            "r8": 0x080E00C4,
                        },
                    ),
                    (
                        "rwatch:080e00c4;",
                        {
                            "pc": 0x08002200,
                            "lr": 0x08015C2B,
                            "r1": 0x08146EE0,
                            "r8": 0x080E00C4,
                        },
                    ),
                ]

            def write_register(self, register_number, value):
                self.registers[f"r{register_number}"] = value

            def read_registers(self):
                return self.registers

            def set_watchpoint(self, *_args, **_kwargs):
                pass

            def set_breakpoint(self, *_args, **_kwargs):
                pass

            def continue_until_stop(self, _timeout):
                stop, registers = self.stops.pop(0)
                self.registers = registers
                return stop

            def remove_watchpoint(self, *_args, **_kwargs):
                pass

            def remove_breakpoint(self, *_args, **_kwargs):
                pass

        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 12,
            }
        }
        result = font_record_runtime_probe.trace_loader_hit(
            FakeClient(),
            "T05thread:1;",
            {
                "pc": font_record_runtime_probe.FONT_LOADER_ENTRY,
                "lr": 0x08015C2B,
                "r1": 0x02001000,
            },
            records,
            desired_key=font_record_runtime_probe.NO_KEY,
            stage_timeout=1.0,
            max_stage_stops=4,
            injected_source_address=0x08146EE0,
        )
        self.assertEqual(
            result["source_read_status"],
            "confirmed-runtime-injected-strict-record-source-read",
        )
        self.assertEqual(
            result["source_injection"]["provenance"],
            "runtime-argument-injected",
        )
        self.assertNotEqual(
            result["source_injection"]["provenance"], "natural-game-flow"
        )
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)


if __name__ == "__main__":
    unittest.main()
