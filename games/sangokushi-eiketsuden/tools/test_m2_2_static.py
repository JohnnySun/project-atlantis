#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ M2.2 source-safe helpers."""

from __future__ import annotations

import pathlib
import sys
import unittest


TOOL_DIR = pathlib.Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))
from test_table_b_static import synthetic_table_rom  # noqa: E402
from verify_table_b_roundtrip import verify_table_b  # noqa: E402


class M22StaticTest(unittest.TestCase):
    def test_roundtrip_verifier_covers_all_records_without_source_output(self) -> None:
        report = verify_table_b(synthetic_table_rom())
        self.assertEqual(report["entry_count"], 44)
        self.assertEqual(report["byte_identical_count"], 44)
        self.assertEqual(report["hash_identical_count"], 44)
        self.assertEqual(report["control_invariant_count"], 44)
        self.assertEqual(report["payload_length_counts"], {"2": 22, "4": 22})
        self.assertEqual(report["format_counts"], {"%u": 22})
        self.assertEqual(report["opaque_control_byte_counts"], {"0x1B": 22})
        for entry in report["entries"]:
            self.assertNotIn("text", entry)
            self.assertNotIn("raw_bytes", entry)


if __name__ == "__main__":
    unittest.main()
