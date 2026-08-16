#!/usr/bin/env python3
"""ROM-independent tests for the B3EJ M2.3 upstream-bound evidence."""

from __future__ import annotations

import importlib.util
import pathlib
import unittest


TOOL_PATH = pathlib.Path(__file__).with_name("m2_3_static.py")
SPEC = importlib.util.spec_from_file_location("sangokushi_m2_3_static", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load m2_3_static.py")
STATIC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATIC)


class M23StaticTest(unittest.TestCase):
    def test_bound_evidence_distinguishes_builder_relation_from_global_proof(self) -> None:
        evidence = STATIC.index_bound_evidence()
        self.assertEqual(evidence["table_b_entry_count"], 44)
        self.assertEqual(evidence["empty_path_count"], 44)
        self.assertEqual(
            evidence["static_status"],
            "builder_relation_confirmed; universal_index_lt_44_not-proven",
        )
        self.assertIn("runtime table", evidence["normal_path_count_source"])
        self.assertNotIn("text", evidence)
        self.assertNotIn("raw_bytes", evidence)

    def test_reviewed_spans_exclude_inline_data_gaps(self) -> None:
        self.assertEqual(STATIC.UPSTREAM_DATA_GAPS[0], (0x026546, 0x026554))
        self.assertEqual(STATIC.EVENT_BUILDER_DATA_GAP, (0x0192FC, 0x019308))
        self.assertEqual(STATIC.EVENT_BUILDER_EXIT_OBSERVATION, 0x019376)
        self.assertLess(STATIC.EVENT_BUILDER_RETURN_VALUE, STATIC.EVENT_BUILDER_EXIT_OBSERVATION)


if __name__ == "__main__":
    unittest.main()
