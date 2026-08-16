#!/usr/bin/env python3
"""Tests for M1.24 source-safe caller/corpus coverage reconciliation."""

from __future__ import annotations

import glob
import json
from pathlib import Path
import tempfile
import unittest

from m124_corpus_caller_coverage import (
    CoverageReconcileReject,
    build_report,
    read_ledger_ids,
)


ROOT = Path(__file__).resolve().parents[1]


class M124CorpusCallerCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        load = lambda name: json.loads((ROOT / "research" / name).read_text(encoding="utf-8"))
        self.coverage = load("m117-corpus-coverage.json")
        self.pointer = json.loads((ROOT / "work/pointer-caller-report.json").read_text(encoding="utf-8"))
        self.callsite = load("m120-semantic-caller-inventory.json")
        self.m119 = load("m119-caller-reroute.json")
        self.m122 = load("m122-runtime-receipt.json")
        self.full_corpus = load("m4-full-corpus-gate.json")
        self.ledger_ids = read_ledger_ids([Path(path) for path in glob.glob(str(ROOT / "translations/*.jsonl"))])

    def test_reconciliation_keeps_exact_pointer_and_ledger_counts(self) -> None:
        report = build_report(
            (ROOT / "roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes(),
            self.coverage,
            self.pointer,
            self.callsite,
            self.m119,
            self.m122,
            self.full_corpus,
            self.ledger_ids,
        )
        self.assertEqual(report["full_corpus"]["exact_pointer_candidate_count"], 609)
        self.assertEqual(report["full_corpus"]["exact_pointer_record_count"], 370)
        self.assertEqual(report["full_corpus"]["caller_cohort_count"], 123)
        self.assertEqual(report["consumer_callsite_inventory"]["candidate_count"], 5)
        self.assertEqual(report["translated_ledger_overlap"]["ledger_record_count"], 12)
        self.assertTrue(report["translated_ledger_overlap"]["all_ledger_records_have_exact_pointer_candidate"])
        self.assertFalse(report["gate"]["natural_caller_coverage_proven"])
        self.assertFalse(report["gate"]["semantic_scene_labels_proven"])
        self.assertEqual(report["runtime_coverage"]["m122_transport"]["result"], "transport_negative")

    def test_source_text_in_any_reused_report_is_rejected(self) -> None:
        bad = dict(self.coverage)
        bad["text"] = "forbidden"
        with self.assertRaisesRegex(CoverageReconcileReject, "source_text_key"):
            build_report(
                (ROOT / "roms/base/Super_Robot_Taisen_D_JP_A6SJ.gba").read_bytes(),
                bad,
                self.pointer,
                self.callsite,
                self.m119,
                self.m122,
                self.full_corpus,
                self.ledger_ids,
            )

    def test_ledger_source_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source-forbidden.jsonl"
            path.write_text('{"string_id": 1, "source": "forbidden"}\n', encoding="utf-8")
            with self.assertRaisesRegex(CoverageReconcileReject, "ledger_source_or_shape"):
                read_ledger_ids([path])


if __name__ == "__main__":
    unittest.main()
