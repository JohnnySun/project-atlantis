#!/usr/bin/env python3
"""Regression tests for the FE6 M1.27 font data-flow contract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
GAME_ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import analyze_m127_font_contract as contract  # noqa: E402


ROM_PATH = GAME_ROOT / "roms/base/AFEJ.gba"


@unittest.skipUnless(ROM_PATH.is_file(), "local reviewed AFEJ ROM is not installed")
class AfejM127FontContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = contract.build_report(ROM_PATH)

    def test_renderer_has_four_0x40_plane_calls(self) -> None:
        renderer = self.report["static"]["renderer"]
        self.assertEqual(renderer["plane_count"], 4)
        self.assertEqual(renderer["plane_offsets"], ["0x00000000", "0x00000040", "0x00000080", "0x000000c0"])
        self.assertEqual(renderer["plane_stride"], "0x00000040")
        self.assertEqual(len(renderer["plane_calls"]), 4)

    def test_kernel_is_packed_nibble_merge_and_writer_boundary(self) -> None:
        kernel = self.report["static"]["kernel"]
        self.assertEqual(kernel["entry"], "0x08099580")
        self.assertEqual(kernel["writer_instruction"], "0x080995a6: str r1, [r2]")
        self.assertEqual(kernel["nibble_mask_formula"], "0x0f << ((r2 & 0x07) * 4)")
        self.assertEqual(kernel["plane_merge_formula"], "dest = (dest & ~mask) | (source & mask)")
        self.assertTrue(kernel["packed_nibble_operation_confirmed"])
        self.assertFalse(kernel["semantic_name_assigned"])

    def test_address_literals_do_not_confirm_font_or_unicode_identity(self) -> None:
        model = self.report["static"]["composer"]["address_model"]
        self.assertEqual(model["source_base_literal"], "0x02000000")
        self.assertEqual(model["destination_base_literal"], "0x06010000")
        self.assertFalse(model["source_candidate_is_single_literal"])
        self.assertFalse(model["destination_candidate_is_single_literal"])
        self.assertFalse(self.report["status"]["font_identity_confirmed"])
        self.assertFalse(self.report["status"]["unicode_identity_confirmed"])

    def test_serialized_report_has_no_bitmap_or_source_payload(self) -> None:
        serialized = json.dumps(self.report, ensure_ascii=False)
        self.assertNotIn("bytes_hex", serialized)
        self.assertNotIn("bitmap_bytes", serialized)
        self.assertNotIn("source_bytes", serialized)
        self.assertNotIn("decoded_text", serialized)
        self.assertFalse(self.report["status"]["translation_ready"])

    def test_runtime_writer_negative_is_explicit(self) -> None:
        result = contract._runtime_summary({
            "runtime": {
                "renderer_entries": [
                    {"source_register_r0": "0x020020c0", "destination_register_r1": "0x06014000"}
                ],
                "writer_receipts": [],
            }
        })
        self.assertTrue(result["source_candidate_observed"])
        self.assertTrue(result["destination_candidate_observed"])
        self.assertEqual(result["writer_receipt_count"], 0)
        self.assertFalse(result["same_run_writer_pairing_confirmed"])


if __name__ == "__main__":
    unittest.main()
