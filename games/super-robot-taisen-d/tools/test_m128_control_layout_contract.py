from __future__ import annotations

import json
import unittest
from pathlib import Path

from m128_control_layout_contract import ControlLayoutReject, build_report


ROOT = Path(__file__).resolve().parents[1]


class M128ControlLayoutContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m123 = json.loads(
            (ROOT / "research/m123-control-semantic-boundary.json").read_text(encoding="utf-8")
        )
        self.m126 = json.loads(
            (ROOT / "research/m126-full-encoder-ledger-audit.json").read_text(encoding="utf-8")
        )

    def test_proven_bytes_and_unproven_semantics_are_separate(self) -> None:
        report = build_report(self.m123, self.m126)
        self.assertEqual(report["proven_boundaries"]["glyph_unit"]["code_unit_bytes"], 2)
        self.assertEqual(report["semantic_status"]["newline"]["dedicated_consumer_byte_compare_count"], 0)
        self.assertFalse(report["gate"]["newline_semantics_proven"])
        self.assertFalse(report["gate"]["speaker_semantics_proven"])
        self.assertFalse(report["gate"]["branch_semantics_proven"])
        self.assertFalse(report["gate"]["engine_width_limit_proven"])
        self.assertEqual(report["corpus_boundary"]["record_count"], 2325)
        self.assertEqual(report["corpus_boundary"]["target_encoder_admissible_count"], 12)

    def test_semantic_label_or_source_text_drift_fails_closed(self) -> None:
        bad_m123 = json.loads(json.dumps(self.m123))
        bad_m123["proven_control_flow"]["mode_routing_field"]["semantic_name"] = "speaker"
        with self.assertRaisesRegex(ControlLayoutReject, "mode_semantic_name_mismatch"):
            build_report(bad_m123, self.m126)
        bad_m126 = json.loads(json.dumps(self.m126))
        bad_m126["source_corpus"]["text"] = "forbidden"
        with self.assertRaisesRegex(ControlLayoutReject, "source_or_target_text_key"):
            build_report(self.m123, bad_m126)


if __name__ == "__main__":
    unittest.main()
