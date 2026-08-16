#!/usr/bin/env python3
"""ROM-independent tests for the custom-glyph verifier boundary."""

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


VERIFY = load("verify_custom_glyph_patch")


class VerifyCustomGlyphPatchTest(unittest.TestCase):
    def test_changed_offsets_allow_only_reviewed_spans(self) -> None:
        self.assertTrue(VERIFY._changed_offsets_inside(b"abcdef", b"abXdef", [(2, 3)]))
        self.assertTrue(VERIFY._changed_offsets_inside(b"abcdef", b"abcdeX", [(2, 3), (5, 6)]))
        self.assertFalse(VERIFY._changed_offsets_inside(b"abcdef", b"Xbcdef", [(2, 3)]))

    def test_changed_offsets_allow_disjoint_record_and_glyph_spans(self) -> None:
        self.assertTrue(VERIFY._changed_offsets_inside(b"0123456789", b"0A234567B9", [(1, 2), (8, 9)]))
        self.assertFalse(VERIFY._changed_offsets_inside(b"0123456789", b"0A234C67B9", [(1, 2), (8, 9)]))


if __name__ == "__main__":
    unittest.main()
