from __future__ import annotations

import unittest

from m113_full_encoder_contract import (
    EXPECTED_FONT_LICENSE_SHA256,
    EXPECTED_FONT_SOURCE_SHA256,
    EXPECTED_ROM_SHA256,
    EncoderReject,
    encode_text,
    read_narrow_map_from_report,
)


class M113FullEncoderContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.narrow = {ord("沒"): {"code_unit": 0xE883, "slot": 543}}
        self.wide = {
            ord("移"): {
                "code_unit": 0xDA88,
                "slot": 905,
                "runtime_status": "runtime_confirmed_bounded",
            },
            ord("一"): {
                "code_unit": 0xEA88,
                "slot": 921,
                "runtime_status": "static_source_context_only",
            },
        }

    def test_narrow_and_runtime_confirmed_wide_encode(self) -> None:
        encoded, modes = encode_text("沒移", self.narrow, self.wide)
        self.assertEqual(encoded, bytes.fromhex("83e888da"))
        self.assertEqual(modes, {"narrow": 1, "wide_runtime_confirmed": 1})

    def test_static_only_wide_identity_fails_closed(self) -> None:
        with self.assertRaisesRegex(EncoderReject, "wide_static_only_identity"):
            encode_text("一", self.narrow, self.wide)

    def test_missing_and_control_inputs_fail_closed(self) -> None:
        with self.assertRaisesRegex(EncoderReject, "missing_glyph"):
            encode_text("未", self.narrow, self.wide)
        with self.assertRaisesRegex(EncoderReject, "opaque_or_control"):
            encode_text("\n", self.narrow, self.wide)

    def test_font_and_rom_hash_mismatch_fail_closed(self) -> None:
        report = {
            "rom": {"source_sha256": EXPECTED_ROM_SHA256},
            "font": {
                "source_sha256": EXPECTED_FONT_SOURCE_SHA256,
                "license_sha256": EXPECTED_FONT_LICENSE_SHA256,
            },
            "allocator": {"font_hash_match": True},
            "allocations": [
                {
                    "codepoint": "U+6C92",
                    "code_unit_little_endian": "0xE883",
                    "slot": 543,
                }
            ],
        }
        bad_font = {**report, "font": {**report["font"], "source_sha256": "0" * 64}}
        with self.assertRaisesRegex(EncoderReject, "font_hash_mismatch"):
            read_narrow_map_from_report(bad_font)
        bad_rom = {**report, "rom": {"source_sha256": "0" * 64}}
        with self.assertRaisesRegex(EncoderReject, "rom_hash_mismatch"):
            read_narrow_map_from_report(bad_rom)

    def test_narrow_code_unit_collision_fails_closed(self) -> None:
        report = {
            "rom": {"source_sha256": EXPECTED_ROM_SHA256},
            "font": {
                "source_sha256": EXPECTED_FONT_SOURCE_SHA256,
                "license_sha256": EXPECTED_FONT_LICENSE_SHA256,
            },
            "allocator": {"font_hash_match": True},
            "allocations": [
                {
                    "codepoint": "U+6C92",
                    "code_unit_little_endian": "0xE883",
                    "slot": 543,
                },
                {
                    "codepoint": "U+6709",
                    "code_unit_little_endian": "0xE883",
                    "slot": 542,
                },
            ],
        }
        with self.assertRaisesRegex(EncoderReject, "narrow_codepoint_or_slot_collision"):
            read_narrow_map_from_report(report)


if __name__ == "__main__":
    unittest.main()
