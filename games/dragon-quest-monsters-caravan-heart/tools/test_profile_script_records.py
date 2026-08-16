#!/usr/bin/env python3
"""Tests for the aggregate-only script boundary profile."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


TOOL = Path(__file__).with_name("profile_script_records.py")
SPEC = importlib.util.spec_from_file_location("dqmch_profile_script_records", TOOL)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def record(tokens: list[dict[str, object]]) -> dict[str, object]:
    return {
        "rom_sha256": MODULE.EXPECTED_SHA256,
        "boundary": "next-pointer-in-table",
        "tokens": tokens,
    }


class ScriptProfileTest(unittest.TestCase):
    def test_first_ff_is_only_a_candidate_when_bytes_follow(self) -> None:
        report = MODULE.profile(
            [
                record(
                    [
                        {"kind": "single-byte-candidate", "value": 0x24, "offset": 0},
                        {"kind": "control-candidate", "value": 0xFF, "offset": 1},
                        {"kind": "pair", "lead": 0x92, "trail": 0x34, "offset": 2},
                    ]
                )
            ]
        )
        self.assertEqual(report["terminated_candidate"], 1)
        self.assertEqual(report["post_terminator_records"], 1)
        self.assertEqual(report["post_terminator_bytes"], 2)
        self.assertFalse(report["ff_is_boundary_proven"])

    def test_last_ff_and_missing_ff_are_distinguished(self) -> None:
        report = MODULE.profile(
            [
                record([{"kind": "control-candidate", "value": 0xFF, "offset": 0}]),
                record([{"kind": "single-byte-candidate", "value": 0x24, "offset": 0}]),
            ]
        )
        self.assertEqual(report["terminated_candidate"], 1)
        self.assertEqual(report["terminator_last_token"], 1)
        self.assertEqual(report["no_terminator_candidate"], 1)

    def test_wrong_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.validate_rom(b"not a ROM")


if __name__ == "__main__":
    unittest.main()
