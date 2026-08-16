#!/usr/bin/env python3
"""ROM-independent tests for the bounded event-system pool patcher."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


def load(name: str):
    path = pathlib.Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PATCH = load("patch_fixed_pool")
VERIFY = load("verify_fixed_pool_patch")


class FixedPoolPatchTest(unittest.TestCase):
    def test_parser_is_pool_specific_and_bounded(self) -> None:
        self.assertEqual(PATCH.parse_pool_entry("b3ej:event-system:001", "event-system"), 1)
        self.assertEqual(PATCH.parse_pool_entry("b3ej:story-event:002", "story-event"), 2)
        with self.assertRaises(ValueError):
            PATCH.parse_pool_entry("b3ej:table-b:001", "event-system")
        with self.assertRaises(ValueError):
            PATCH.parse_pool_entry("b3ej:event-system:028", "event-system")
        with self.assertRaises(ValueError):
            PATCH.parse_pool_entry("b3ej:story-event:033", "story-event")

    def test_fixed_slot_replacement_keeps_span(self) -> None:
        original = b"ABCD"
        self.assertEqual(PATCH.fixed_slot_replacement(original, b"XY"), b"XY\0\0\0")
        with self.assertRaises(ValueError):
            PATCH.fixed_slot_replacement(original, b"12345")

    def test_changed_offsets_are_restricted_to_record_spans(self) -> None:
        self.assertTrue(VERIFY._changed_offsets_inside(b"abcdef", b"abXdef", [(2, 3)]))
        self.assertFalse(VERIFY._changed_offsets_inside(b"abcdef", b"Xbcdef", [(2, 3)]))

    def test_empty_work_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            VERIFY.verify_pool(bytes(16), bytes(16), {}, "event-system")

    def test_control_contract_is_preserved(self) -> None:
        PATCH._validate_record_controls(b"A\nB", b"X\nY")
        with self.assertRaises(ValueError):
            PATCH._validate_record_controls(b"A\nB", b"X\rY")

    def test_forbidden_custom_units_are_rejected(self) -> None:
        self.assertEqual(PATCH._code_units_from_encoded("蜀".encode("shift_jis")), [0xE586])
        self.assertEqual(PATCH._code_units_from_encoded(b"?"), [])


if __name__ == "__main__":
    unittest.main()
