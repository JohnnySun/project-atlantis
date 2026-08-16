#!/usr/bin/env python3
"""Pure fail-closed tests for the M1.7 no-op POC contract."""

from __future__ import annotations

import unittest

from m17_layout import sha256, tokenize_payload, token_summary
from m17_poc import PocContract, validate_candidate


def synthetic_resources() -> dict[str, dict[str, object]]:
    return {
        "narrow": {
            "resource_start": "0x08001000",
            "resource_size": 0x18,
            "stride": 12,
            "glyph_payload_bytes": 12,
            "conservative_new_slot_capacity": 0,
        },
        "wide": {
            "resource_start": "0x08002000",
            "resource_size": 0x34,
            "stride": 26,
            "glyph_payload_bytes": 24,
            "conservative_new_slot_capacity": 0,
        },
    }


def contract() -> tuple[PocContract, bytes, bytearray]:
    payload = bytes.fromhex("8140")
    tokenization = tokenize_payload(payload)
    signature = tuple(
        (row["kind"], row["glyph_class"], row["layout_width"])
        for row in tokenization.signature()
    )
    rom = bytearray(0x2400)
    rom[0x1000 : 0x1000 + 12] = bytes([1]) + bytes(11)
    result = PocContract(
        source_offset=0x100,
        source_hash=sha256(payload),
        source_length=len(payload),
        source_width=8,
        token_signature=signature,
        required_slots=(("narrow", 0),),
        max_width=8,
    )
    return result, payload, rom


class M17PocTest(unittest.TestCase):
    def test_noop_candidate_is_accepted(self) -> None:
        spec, payload, rom = contract()
        result = validate_candidate(spec, payload, bytes(rom), synthetic_resources(), declared_source_hash=spec.source_hash)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["reasons"], [])

    def test_source_hash_and_length_are_fail_closed(self) -> None:
        spec, payload, rom = contract()
        result = validate_candidate(
            spec,
            payload + bytes.fromhex("8140"),
            bytes(rom),
            synthetic_resources(),
            declared_source_hash="0" * 64,
        )
        self.assertIn("source_hash_mismatch", result["reasons"])
        self.assertIn("variable_length_rejected", result["reasons"])

    def test_opaque_control_and_width_mismatch_are_rejected(self) -> None:
        spec, _payload, rom = contract()
        opaque = validate_candidate(
            spec,
            b"AB",
            bytes(rom),
            synthetic_resources(),
            declared_source_hash=spec.source_hash,
        )
        self.assertIn("opaque_token_or_unaligned_record", opaque["reasons"])
        self.assertIn("control_token_or_glyph_class_mismatch", opaque["reasons"])
        wide = validate_candidate(
            spec,
            bytes.fromhex("8840"),
            bytes(rom),
            synthetic_resources(),
            declared_source_hash=spec.source_hash,
        )
        self.assertIn("line_width_rejected", wide["reasons"])

    def test_missing_glyph_and_capacity_are_rejected(self) -> None:
        spec, _payload, rom = contract()
        missing = validate_candidate(
            spec,
            bytes.fromhex("8141"),
            bytes(rom),
            synthetic_resources(),
            declared_source_hash=spec.source_hash,
        )
        self.assertIn("missing_glyph", missing["reasons"])
        self.assertIn("capacity_exceeded", missing["reasons"])

    def test_token_summary_exposes_counts_not_source(self) -> None:
        summary = token_summary(tokenize_payload(bytes.fromhex("81408141")))
        self.assertEqual(summary["glyph_count"], 2)
        self.assertNotIn("text", summary)


if __name__ == "__main__":
    unittest.main()
