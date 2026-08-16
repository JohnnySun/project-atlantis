#!/usr/bin/env python3
"""Tests for the bounded B3TJ static font pipeline probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import font_pipeline_probe  # noqa: E402


class FontPipelineProbeTests(unittest.TestCase):
    def test_asset_stride_formula_is_fixed_and_bounded(self):
        self.assertEqual(font_pipeline_probe.FONT_ASSET_STRIDE, 0x20)
        self.assertEqual(
            font_pipeline_probe.font_asset_address(0x120), 0x080E00C4
        )
        with self.assertRaises(ValueError):
            font_pipeline_probe.font_asset_address(-1)

    def test_table_summary_is_metadata_only(self):
        data = bytes(range(32)) * 8
        result = font_pipeline_probe._table_summary(
            data, font_pipeline_probe.ROM_BASE, window=0x100
        )
        self.assertEqual(result["halfword_count"], 0x80)
        self.assertNotIn("bytes", result)
        self.assertNotIn("raw", result)

    def test_fixed_calls_and_transform_constants_are_not_runtime_claims(self):
        self.assertEqual(
            font_pipeline_probe.EXPECTED_CALLS[font_pipeline_probe.FONT_MAP_ENTRY],
            (0x1556, 0x15F8),
        )
        self.assertEqual(
            font_pipeline_probe.TRANSFORM_LOOKUP_TABLE, 0x03001464
        )
        self.assertEqual(
            font_pipeline_probe.CODEPOINT_LOOKUP_ENTRY, 0x08004D90
        )


if __name__ == "__main__":
    unittest.main()
