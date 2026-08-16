#!/usr/bin/env python3
"""ROM-independent tests for the bounded B3EJ Table-B patcher."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("patch_table_b.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_patch_table_b", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load patch_table_b.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


class PatchTableBTest(unittest.TestCase):
    def test_entry_parser_is_strict_and_bounded(self) -> None:
        self.assertEqual(PATCH.parse_table_b_entry("b3ej:table-b:000"), 0)
        self.assertEqual(PATCH.parse_table_b_entry("b3ej:table-b:043"), 43)
        with self.assertRaises(ValueError):
            PATCH.parse_table_b_entry("b3ej:table-b:044")
        with self.assertRaises(ValueError):
            PATCH.parse_table_b_entry("b3ej:table-a:000")

    def test_fixed_slot_replacement_preserves_original_span(self) -> None:
        replacement = PATCH.fixed_slot_replacement(b"abcdef", b"xy")
        self.assertEqual(replacement, b"xy\0\0\0\0\0")
        self.assertEqual(len(replacement), 7)
        with self.assertRaises(ValueError):
            PATCH.fixed_slot_replacement(b"abc", b"abcd")


if __name__ == "__main__":
    unittest.main()
