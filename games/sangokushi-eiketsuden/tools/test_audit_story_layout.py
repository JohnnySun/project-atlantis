#!/usr/bin/env python3
"""ROM-independent tests for the bounded story layout gate."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("audit_story_layout.py")
SPEC = importlib.util.spec_from_file_location("audit_story_layout", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load audit_story_layout.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class StoryLayoutAuditTest(unittest.TestCase):
    def test_line_metrics_counts_trailing_and_internal_lines(self) -> None:
        self.assertEqual(AUDIT._line_metrics("甲\n乙\n"), [1, 1, 0])

    def test_control_signature_keeps_lf_only(self) -> None:
        self.assertEqual(AUDIT._control_signature(b"A\nB\0"), [10, 0])


if __name__ == "__main__":
    unittest.main()
