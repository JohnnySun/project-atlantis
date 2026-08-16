#!/usr/bin/env python3
"""Tests for the B3CJ M2.6 target/runtime QA guard."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("runtime_m2_6.py")
SPEC = importlib.util.spec_from_file_location("runtime_m2_6", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load runtime_m2_6.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)

GAME_ROOT = TOOL_PATH.parents[1]
BASE_PATH = GAME_ROOT / "roms" / "base" / "B3CJ-jp-from-zip.gba"
TARGET_PATH = GAME_ROOT / "work" / "m2.5-prize-ui-built.gba"
BPS_PATH = GAME_ROOT / "work" / "m2.5-prize-ui.bps"
APPLIED_PATH = GAME_ROOT / "work" / "m2.5-prize-ui-applied.gba"
SUMMARY_PATH = GAME_ROOT / "work" / "m2.5-prize-ui-summary.json"
PLAN_PATH = GAME_ROOT / "research" / "m2.5-batch-plan.json"


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.requests: list[str] = []
        self.closed = False
        self.connected = False
        self.__class__.instances.append(self)

    def connect(self) -> None:
        self.connected = True

    def request(self, payload: str) -> str:
        self.requests.append(payload)
        return "S02" if payload == "?" else "PacketSize=4000"

    def close(self) -> None:
        self.closed = True


class RuntimeM26Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.available = all(
            path.is_file()
            for path in (BASE_PATH, TARGET_PATH, BPS_PATH, APPLIED_PATH, SUMMARY_PATH, PLAN_PATH)
        )

    def require_local_inputs(self) -> None:
        if not self.available:
            self.skipTest("ignored M2.5 B3CJ runtime inputs are not available")

    def test_static_target_and_adjacent_proof_is_hash_guarded(self) -> None:
        self.require_local_inputs()
        report = RUNTIME.verify_static_target(
            BASE_PATH,
            TARGET_PATH,
            BPS_PATH,
            APPLIED_PATH,
            SUMMARY_PATH,
            PLAN_PATH,
        )
        self.assertEqual(report["evidence_level"], "confirmed-static-target")
        self.assertEqual(report["translated_string_ids"], ["b3cj:t2:024:0x0064"])
        self.assertEqual(
            [item["glyph_id"] for item in report["changed_glyphs"]],
            ["0x847", "0x848", "0x849"],
        )
        self.assertTrue(report["adjacent_untouched_glyph"]["byte_identical"])
        self.assertEqual(report["reextract"]["records_total"], 361)
        self.assertEqual(report["reextract"]["untouched_records"], 360)

    def test_handshake_uses_one_connection_and_readiness_first(self) -> None:
        original = RUNTIME.GdbClient
        RUNTIME.GdbClient = FakeClient
        FakeClient.instances.clear()
        try:
            result = RUNTIME.handshake(25126, timeout=0.1)
        finally:
            RUNTIME.GdbClient = original
        self.assertEqual(result["handshake"], "confirmed")
        self.assertTrue(result["single_connection"])
        self.assertTrue(result["connect"])
        self.assertEqual(FakeClient.instances[0].requests, ["qSupported:multiprocess+", "?"])
        self.assertTrue(FakeClient.instances[0].closed)

    def test_blocked_handshake_is_not_runtime_evidence(self) -> None:
        original = RUNTIME.GdbClient

        class RefusedClient:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def connect(self) -> None:
                raise ConnectionRefusedError(61, "Connection refused")

            def close(self) -> None:
                pass

        RUNTIME.GdbClient = RefusedClient
        try:
            result = RUNTIME.handshake(25126, timeout=0.1)
        finally:
            RUNTIME.GdbClient = original
        self.assertEqual(result["handshake"], "blocked")
        self.assertFalse(result["connect"])
        self.assertIsNone(result["qSupported"])
        self.assertEqual(result["error"]["type"], "ConnectionRefusedError")


if __name__ == "__main__":
    unittest.main()
