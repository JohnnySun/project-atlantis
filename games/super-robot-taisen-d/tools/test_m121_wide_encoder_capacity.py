#!/usr/bin/env python3
"""Unit tests for the source-safe M1.21 capacity boundary."""

from __future__ import annotations

import unittest

from m121_wide_encoder_capacity import (
    EXPECTED_NARROW_ALLOCATION_COUNT,
    EXPECTED_RUNTIME_WIDE_COUNT,
    EXPECTED_WIDE_IDENTITY_COUNT,
    RUNTIME_WIDE_CODEPOINT,
    RUNTIME_WIDE_CODE_UNIT,
    RUNTIME_WIDE_SLOT,
    _character_status,
    _record_category,
)


class M121WideEncoderCapacityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.narrow = {0x6C92: {"code_unit": 0xE883}}
        self.wide = {
            RUNTIME_WIDE_CODEPOINT: {
                "code_unit": RUNTIME_WIDE_CODE_UNIT,
                "slot": RUNTIME_WIDE_SLOT,
                "runtime_status": "runtime_confirmed_bounded",
            },
            0x4E00: {
                "code_unit": 0xEA88,
                "slot": 921,
                "runtime_status": "static_source_context_only",
            },
        }

    def test_identity_counts_are_explicitly_bounded(self) -> None:
        self.assertEqual(EXPECTED_NARROW_ALLOCATION_COUNT, 28)
        self.assertEqual(EXPECTED_WIDE_IDENTITY_COUNT, 743)
        self.assertEqual(EXPECTED_RUNTIME_WIDE_COUNT, 1)

    def test_narrow_and_runtime_wide_are_distinct_accepted_statuses(self) -> None:
        self.assertEqual(_character_status("沒", self.narrow, self.wide), "target_narrow_known")
        self.assertEqual(
            _character_status("移", self.narrow, self.wide),
            "target_wide_runtime_confirmed",
        )

    def test_static_wide_and_missing_remain_rejected(self) -> None:
        self.assertEqual(_character_status("一", self.narrow, self.wide), "target_wide_static_only")
        self.assertEqual(_character_status("\u3000", self.narrow, self.wide), "target_missing")
        self.assertEqual(
            _record_category("glyph_only_wide", {"target_wide_static_only"}),
            "reject_static_only_wide",
        )
        self.assertEqual(
            _record_category("glyph_only_narrow", {"target_missing"}),
            "reject_unmapped_target",
        )

    def test_runtime_wide_does_not_override_another_rejection(self) -> None:
        self.assertEqual(
            _record_category(
                "glyph_only_mixed",
                {
                    "target_narrow_known",
                    "target_wide_runtime_confirmed",
                    "target_wide_static_only",
                },
            ),
            "reject_static_only_wide",
        )
        self.assertEqual(
            _record_category(
                "glyph_only_narrow",
                {"target_narrow_known", "target_wide_runtime_confirmed"},
            ),
            "admissible_narrow_plus_runtime_wide",
        )

    def test_opaque_shape_is_never_named_as_a_glyph(self) -> None:
        self.assertEqual(
            _record_category("opaque_or_unaligned", {"target_narrow_known"}),
            "opaque_or_unaligned",
        )


if __name__ == "__main__":
    unittest.main()
