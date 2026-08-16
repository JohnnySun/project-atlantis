#!/usr/bin/env python3
"""Tests for the bounded control-only format-template probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import format_template_probe  # noqa: E402


class FormatTemplateProbeTests(unittest.TestCase):
    def test_control_template_reports_tokens_without_source(self):
        result = format_template_probe.parse_control_template(b"%k\x00", 0)
        self.assertEqual(result["control_tokens"], ["%k"])
        self.assertEqual(result["raw_length_without_nul"], 2)
        self.assertNotIn("text", result)
        self.assertNotIn("raw", result)

    def test_control_template_rejects_plain_text(self):
        with self.assertRaises(ValueError):
            format_template_probe.parse_control_template(b"abc\x00", 0)

    def test_reviewed_addresses_remain_separate_from_strict_record(self):
        self.assertEqual(format_template_probe.TEMPLATE_OFFSET, 0x1474C0)
        self.assertEqual(format_template_probe.FORMAT_CALLER, 0x08001640)
        self.assertEqual(format_template_probe.PARSER_ENTRY, 0x080025CC)


if __name__ == "__main__":
    unittest.main()
