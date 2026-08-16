#!/usr/bin/env python3
"""Tests for the B3CJ M2.7 transport-only runtime QA guard."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("runtime_m2_7.py")
SPEC = importlib.util.spec_from_file_location("runtime_m2_7", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load runtime_m2_7.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.requests: list[str] = []
        self.closed = False
        self.__class__.instances.append(self)

    def connect(self) -> None:
        return None

    def request(self, payload: str) -> str:
        self.requests.append(payload)
        return "S02" if payload == "?" else "PacketSize=4000"

    def close(self) -> None:
        self.closed = True


class RuntimeM27Test(unittest.TestCase):
    def test_probe_uses_one_connection_and_readiness_first(self) -> None:
        original = RUNTIME.M26.GdbClient
        RUNTIME.M26.GdbClient = FakeClient
        FakeClient.instances.clear()
        try:
            result = RUNTIME.probe(26371, timeout=0.1)
        finally:
            RUNTIME.M26.GdbClient = original
        self.assertEqual(result["handshake"], "confirmed")
        self.assertTrue(result["single_connection"])
        self.assertEqual(FakeClient.instances[0].requests, ["qSupported:multiprocess+", "?"])
        self.assertTrue(FakeClient.instances[0].closed)

    def test_transport_block_does_not_create_consumer_or_vram_evidence(self) -> None:
        original = RUNTIME.M26.GdbClient

        class RefusedClient:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def connect(self) -> None:
                raise PermissionError(1, "Operation not permitted")

            def close(self) -> None:
                return None

        RUNTIME.M26.GdbClient = RefusedClient
        try:
            result = RUNTIME.probe(26371, timeout=0.1)
        finally:
            RUNTIME.M26.GdbClient = original
        self.assertEqual(result["handshake"], "blocked")
        self.assertFalse(result["connect"])
        self.assertIsNone(result["qSupported"])
        self.assertEqual(result["error"]["type"], "PermissionError")

    def test_report_boundary_names_changed_and_adjacent_slots(self) -> None:
        self.assertEqual(RUNTIME.TARGET_ID, "b3cj:t2:024:0x0064")
        self.assertEqual(RUNTIME.CHANGED_GLYPHS, ("0x847", "0x848", "0x849"))
        self.assertEqual(RUNTIME.ADJACENT_GLYPH, "0x846")


if __name__ == "__main__":
    unittest.main()
