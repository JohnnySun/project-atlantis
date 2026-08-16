#!/usr/bin/env python3

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core.gba.runtime_validation.manifest import ManifestError, load_manifest  # noqa: E402
from core.gba.runtime_validation.result import Report  # noqa: E402
from core.gba.runtime_validation.runtime import _pixel_receipt, run_runtime  # noqa: E402
from core.gba.runtime_validation.static_checks import run_static  # noqa: E402


def fixture_rom():
    base = bytearray(0x240)
    base[0xAC:0xB0] = b"TEST"
    base[0x80:0x84] = (0x08000100).to_bytes(4, "little")
    base[0x100:0x108] = bytes([1, 2, 0xFE, 3, 0, 0xA5, 0xA5, 0xA5])
    candidate = bytearray(base)
    candidate[0x100:0x105] = bytes([4, 5, 0xFE, 6, 0])
    manifest = {
        "format_version": 1,
        "case_id": "fixture-static-pass",
        "rom": {
            "sha256": hashlib.sha256(base).hexdigest(),
            "size": len(base),
            "game_code_hex": b"TEST".hex(),
        },
        "static": {
            "change_policy": {"allowed_changed_ranges": [[0x100, 0x104]], "require_change": True},
            "regions": [
                {"id": "target", "offset": 0x100, "length": 5, "policy": "changed"},
                {"id": "adjacent", "offset": 0x105, "length": 3, "policy": "unchanged"},
            ],
            "pointers": [
                {"id": "target-pointer", "offset": 0x80, "target_ranges": [[0x08000100, 0x08000107]], "alignment": 4}
            ],
            "records": [
                {
                    "id": "target-record",
                    "offset": 0x100,
                    "allocated_length": 8,
                    "terminator": 0,
                    "allowed_values": [[1, 6]],
                    "control_values": [0xFE],
                    "preserve_controls": True,
                    "layout": {"default_width": 8, "max_width": 24, "max_lines": 1},
                }
            ],
        },
    }
    return bytes(base), bytes(candidate), manifest


class StaticValidationTest(unittest.TestCase):
    def run_fixture(self, mutate=None):
        base, candidate, manifest = fixture_rom()
        if mutate:
            candidate, manifest = mutate(bytearray(candidate), manifest)
            candidate = bytes(candidate)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "base.gba").write_bytes(base)
            (root / "candidate.gba").write_bytes(candidate)
            return run_static(manifest, root / "base.gba", root / "candidate.gba")

    def test_target_and_adjacent_pass(self):
        report = self.run_fixture()
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.evidence["regions"][1]["changed_bytes"], 0)

    def test_adjacent_pollution_and_outside_range_fail(self):
        def mutate(candidate, manifest):
            candidate[0x106] ^= 0xFF
            return candidate, manifest
        report = self.run_fixture(mutate)
        self.assertEqual(report.status, "fail")
        codes = {row["code"] for row in report.diagnostics if row["status"] == "fail"}
        self.assertIn("static.region.unchanged", codes)
        self.assertIn("static.relocation.allowed_ranges", codes)

    def test_pointer_range_fail(self):
        def mutate(candidate, manifest):
            candidate[0x80:0x84] = (0x02000000).to_bytes(4, "little")
            manifest["static"]["change_policy"]["allowed_changed_ranges"].append([0x80, 0x83])
            return candidate, manifest
        report = self.run_fixture(mutate)
        self.assertEqual(report.status, "fail")
        self.assertTrue(any(row["code"] == "static.pointer.range" and row["status"] == "fail" for row in report.diagnostics))

    def test_missing_terminator_fails(self):
        def mutate(candidate, manifest):
            candidate[0x104] = 4
            return candidate, manifest
        report = self.run_fixture(mutate)
        self.assertEqual(report.status, "fail")
        self.assertTrue(any(row["code"] == "static.record.terminator" for row in report.diagnostics))

    def test_unknown_glyph_width_fails_closed(self):
        def mutate(candidate, manifest):
            manifest["static"]["records"][0]["layout"].pop("default_width")
            manifest["static"]["records"][0]["layout"]["glyph_widths"] = {"4": 8}
            return candidate, manifest
        report = self.run_fixture(mutate)
        self.assertEqual(report.status, "unknown")
        self.assertEqual(report.exit_code, 2)


class ManifestTest(unittest.TestCase):
    def test_unknown_top_level_field_is_rejected(self):
        _, _, manifest = fixture_rom()
        manifest["surprise"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ManifestError):
                load_manifest(path)

    def test_unknown_nested_field_is_rejected(self):
        _, _, manifest = fixture_rom()
        manifest["static"]["records"][0]["surprise"] = True
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "unknown fields in static.records"):
                load_manifest(path)

    def test_runtime_action_requires_operation_fields(self):
        manifest = {
            "format_version": 1,
            "case_id": "missing-key-register",
            "rom": {"sha256": "0" * 64},
            "runtime": {"actions": [{"op": "keys", "keys": ["A"]}]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "destination_register"):
                load_manifest(path)

    def test_failure_precedes_unknown(self):
        report = Report("test")
        report.add("unknown", "x", "unknown")
        report.add("fail", "y", "fail")
        self.assertEqual(report.status, "fail")


class FakeGdbClient:
    def __init__(self, *args, **kwargs):
        self.connect_attempts = 1
        self.vram = bytearray(0x18000)
        self.palette = bytearray(0x400)
        self.oam = bytearray(0x400)
        self.registers = {name: 0 for name in [
            "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
            "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
        ]}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def request(self, payload):
        return "PacketSize=400" if payload.startswith("qSupported") else "S02"

    def read_registers(self):
        return dict(self.registers)

    def read_memory(self, address, length):
        if 0x06000000 <= address < 0x06018000:
            start = address - 0x06000000
            return bytes(self.vram[start:start + length])
        if 0x05000000 <= address < 0x05000400:
            start = address - 0x05000000
            return bytes(self.palette[start:start + length])
        if 0x07000000 <= address < 0x07000400:
            start = address - 0x07000000
            return bytes(self.oam[start:start + length])
        if address == 0x04000000:
            return (0x1040).to_bytes(length, "little")
        if address == 0x04000130:
            return (0x3FF).to_bytes(length, "little")
        return bytes(length)

    def set_watchpoint(self, *args, **kwargs):
        return None

    def remove_watchpoint(self, *args, **kwargs):
        return None

    def set_breakpoint(self, *args, **kwargs):
        return None

    def remove_breakpoint(self, *args, **kwargs):
        return None

    def continue_until_stop(self, timeout):
        return "T05rwatch:04000130;"

    def write_register(self, number, value):
        if value != 0x3FF:
            self.vram[0] = 1


class RuntimeValidationTest(unittest.TestCase):
    def test_render_clip_guard_is_machine_decidable(self):
        pixels = [[(0, 0, 0) for _ in range(5)] for _ in range(5)]
        pixels[2][2] = (255, 255, 255)
        row = {"clip_guard": {"x": 0, "y": 0, "width": 5, "height": 5, "background_rgb": [0, 0, 0]}}
        receipt = _pixel_receipt(pixels, row, "render")
        self.assertEqual(receipt["clip_guard"]["border_non_background_pixels"], 0)
        pixels[0][2] = (255, 255, 255)
        receipt = _pixel_receipt(pixels, row, "render")
        self.assertEqual(receipt["clip_guard"]["border_non_background_pixels"], 1)

    @patch("core.gba.runtime_validation.runtime.RetryingGdbClient", FakeGdbClient)
    def test_input_hook_and_runtime_hash_change(self):
        manifest = {
            "format_version": 1,
            "case_id": "fixture-runtime-pass",
            "rom": {"sha256": "0" * 64},
            "runtime": {
                "required_capabilities": ["gdb-remote", "watchpoint", "keyinput-consumer-hook"],
                "actions": [
                    {"op": "capture", "id": "before", "regions": [{"id": "vram", "address": "0x06000000", "length": 32}]},
                    {"op": "keys", "id": "press-a", "keys": ["A"], "destination_register": "r1", "hold_reads": 2, "release_reads": 1},
                    {"op": "capture", "id": "after", "regions": [{"id": "vram", "address": "0x06000000", "length": 32}]},
                ],
                "assertions": [
                    {"kind": "changed", "id": "input-state-change", "before": "before", "after": "after", "path": "regions.vram.sha256"}
                ],
            },
        }
        report = run_runtime(manifest, "127.0.0.1", 2345)
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.evidence["actions"][1]["result"]["method"], "keyinput-consumer-hook")

    @patch("core.gba.runtime_validation.runtime.RetryingGdbClient", FakeGdbClient)
    def test_breakpoint_register_region_receipt(self):
        manifest = {
            "format_version": 1,
            "case_id": "fixture-breakpoint-pass",
            "rom": {"sha256": "0" * 64},
            "runtime": {
                "actions": [{
                    "op": "breakpoint",
                    "id": "consumer",
                    "address": "0x08000100",
                    "register_regions": [{"id": "source", "register": "r0", "length": 16}],
                }]
            },
        }
        report = run_runtime(manifest, "127.0.0.1", 2345)
        self.assertEqual(report.status, "pass")
        self.assertEqual(report.evidence["actions"][0]["register_regions"][0]["length"], 16)


if __name__ == "__main__":
    unittest.main()
