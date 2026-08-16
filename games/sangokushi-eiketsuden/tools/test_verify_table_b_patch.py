#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ patch verifier."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("verify_table_b_patch.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_verify_table_b_patch", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load verify_table_b_patch.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class VerifyTableBPatchTest(unittest.TestCase):
    def test_changed_offsets_must_be_inside_selected_spans(self) -> None:
        before = b"abcdefghij"
        after = b"abXdefghij"
        self.assertTrue(VERIFY.changed_offsets_within(before, after, [(2, 4)]))
        self.assertFalse(VERIFY.changed_offsets_within(before, after, [(0, 2)]))

    def test_empty_work_is_rejected_by_verifier_contract(self) -> None:
        with self.assertRaises(ValueError):
            VERIFY.verify_table_b(bytes(0x100), bytes(0x100), {})


if __name__ == "__main__":
    unittest.main()
