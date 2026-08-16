#!/usr/bin/env python3
"""Tests for the bounded B3CJ handler runtime probe."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("runtime_m5_handler_probe.py")
SPEC = importlib.util.spec_from_file_location("runtime_m5_handler_probe", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {TOOL_PATH}")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class RuntimeM5HandlerProbeTest(unittest.TestCase):
    def test_function_labels_are_fail_closed(self) -> None:
        self.assertEqual(PROBE.classify_breakpoint(PROBE.HANDLER), "sub_0800D81C")
        self.assertEqual(PROBE.classify_breakpoint(PROBE.TEXT_WINDOW), "sub_0800B730")
        self.assertEqual(PROBE.classify_breakpoint(PROBE.RETURN_SENTINEL), "return-sentinel")
        self.assertTrue(PROBE.classify_breakpoint(0x08001234).startswith("unknown:"))

    def test_register_receipt_does_not_include_unselected_state(self) -> None:
        receipt = PROBE.register_receipt({
            "r0": 1, "r1": 2, "r2": 3, "r3": 4, "sp": 5,
            "lr": 6, "pc": 7, "cpsr": 8, "r4": 9,
        })
        self.assertEqual(receipt["pc"], "0x00000007")
        self.assertNotIn("r4", receipt)
        self.assertNotIn("source_text", receipt)

    def test_runtime_contract_is_target_scoped(self) -> None:
        self.assertEqual(PROBE.TARGET_ID, "b3cj:t2:024:0x0064")
        self.assertEqual(PROBE.DEFAULT_MAX_STOPS, 10)
        self.assertEqual(PROBE.STATE_POINTER_LIMITS, (0x03000000, 0x03008000))


if __name__ == "__main__":
    unittest.main()
