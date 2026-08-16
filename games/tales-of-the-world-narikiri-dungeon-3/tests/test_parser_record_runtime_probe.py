#!/usr/bin/env python3
"""Offline tests for the bounded parser/caller runtime probe."""

import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import parser_record_runtime_probe  # noqa: E402
import state7_readiness_probe  # noqa: E402


class ParserRecordRuntimeProbeTests(unittest.TestCase):
    def test_parser_callsite_is_limited_to_reviewed_direct_callers(self):
        self.assertEqual(
            parser_record_runtime_probe.parser_callsite_from_lr(0x08001651),
            0x0800164C,
        )
        self.assertEqual(
            parser_record_runtime_probe.parser_callsite_from_lr(0x08001D97),
            0x08001D92,
        )
        self.assertIsNone(
            parser_record_runtime_probe.parser_callsite_from_lr(0x08009999)
        )

    def test_state_handler_entries_are_fixed_and_one_shot_candidates(self):
        self.assertEqual(
            parser_record_runtime_probe.STATE_HANDLER_ENTRIES,
            {
                "state7": 0x080A85D8,
                "state7_epilogue": 0x080A8644,
                "state3": 0x080A4E64,
            },
        )
        self.assertEqual(parser_record_runtime_probe.STATE_NEXT, 0x02000000)
        self.assertEqual(parser_record_runtime_probe.STATE_HANDLER_RETURN_ENTRIES, {})
        self.assertEqual(parser_record_runtime_probe.STATE7_CANDIDATE_ENTRIES, {})

    def test_state7_readiness_probe_keeps_fixed_resource_field_boundary(self):
        self.assertEqual(state7_readiness_probe.STATE7_ENTRY, 0x080A85D8)
        self.assertEqual(state7_readiness_probe.A82AC_ENTRY, 0x080A82AC)
        self.assertEqual(state7_readiness_probe.A82AC_RETURN, 0x080A8508)
        self.assertEqual(state7_readiness_probe.RESOURCE_STATUS_OFFSET, 0x28)
        self.assertEqual(
            state7_readiness_probe.parser_probe.STATE7_CANDIDATE_ENTRIES,
            {},
        )

    def test_parser_input_requires_exact_strict_record_start(self):
        records = {
            0x146EE0: {
                "string_id": "sjis:0x146EE0",
                "file_offset": "0x146EE0",
                "gba_address": "0x08146EE0",
                "region": "text-pool",
                "raw_length": 4,
            }
        }
        row = parser_record_runtime_probe.classify_parser_pointer(
            0x08146EE0, records, role="r1"
        )
        self.assertEqual(row["status"], "strict-record-start")
        self.assertEqual(row["role"], "r1")
        self.assertEqual(
            parser_record_runtime_probe.classify_parser_pointer(
                0x08146EE1, records, role="r1"
            )["status"],
            "strict-window-nonstrict-offset",
        )

    def test_parser_arguments_keep_ram_and_nontext_provisional(self):
        records = {}
        self.assertEqual(
            parser_record_runtime_probe.classify_parser_pointer(
                0x03001588, records, role="r0"
            )["status"],
            "ram-pointer",
        )
        self.assertEqual(
            parser_record_runtime_probe.classify_parser_pointer(
                0x08001234, records, role="r1"
            )["status"],
            "rom-pointer-outside-strict-record-start",
        )
        self.assertEqual(
            parser_record_runtime_probe.classify_parser_pointer(
                0x04000130, records, role="r1"
            )["status"],
            "non-pointer",
        )

    def test_classification_is_metadata_only(self):
        row = parser_record_runtime_probe.classify_parser_pointer(
            0x08146EE0,
            {
                0x146EE0: {
                    "string_id": "sjis:0x146EE0",
                    "file_offset": "0x146EE0",
                    "gba_address": "0x08146EE0",
                    "region": "text-pool",
                    "raw_length": 4,
                }
            },
            role="r1",
        )
        self.assertNotIn("bytes", row)
        self.assertNotIn("raw", row)


if __name__ == "__main__":
    unittest.main()
