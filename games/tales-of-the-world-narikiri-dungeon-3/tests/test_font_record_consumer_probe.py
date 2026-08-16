#!/usr/bin/env python3
"""Tests for the bounded B3TJ source-pointer-shaped font edge."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import font_record_consumer_probe  # noqa: E402


class FontRecordConsumerProbeTests(unittest.TestCase):
    def test_asset_address_formula_is_guarded(self):
        self.assertEqual(
            font_record_consumer_probe.font_asset_address(0x120), 0x080E00C4
        )
        with self.assertRaises(ValueError):
            font_record_consumer_probe.font_asset_address(-1)
        with self.assertRaises(ValueError):
            font_record_consumer_probe.font_asset_address(0x100000)

    def test_fixed_direct_callsite_contract(self):
        self.assertEqual(font_record_consumer_probe.FONT_LOADER_CALLSITE, 0x15C26)
        self.assertEqual(font_record_consumer_probe.FONT_BUILDER_CALLSITE, 0xCD170)
        self.assertEqual(len(font_record_consumer_probe.OBJECT_TEXT_BUILDER_CALLS), 5)
        self.assertEqual(
            font_record_consumer_probe.OBJECT_TEXT_BUILDER_CALLER_INPUTS,
            (
                (0xD5218, 0xD5212, "[sp+0x00]", 0x9800),
                (0xD5224, 0xD521E, "[sp+0x04]", 0x9801),
                (0xD5234, 0xD522E, "[sp+0x08]", 0x9802),
                (0xD5240, 0xD523A, "[sp+0x0C]", 0x9803),
                (0xD6C86, 0xD6C80, "[r7+4+scaled-index]", 0x6800),
            ),
        )
        self.assertEqual(font_record_consumer_probe.FONT_ASSET_STRIDE, 0x20)

    def test_static_contract_constants_are_bounded(self):
        self.assertEqual(
            font_record_consumer_probe.FONT_LOOKUP_BASE, 0x03001464
        )
        self.assertEqual(
            font_record_consumer_probe.FONT_LOOKUP_AUX_BASE, 0x03001462
        )
        self.assertFalse(hasattr(font_record_consumer_probe, "VRAM_ADDRESS"))


if __name__ == "__main__":
    unittest.main()
