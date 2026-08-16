from __future__ import annotations

import json
import unittest
from pathlib import Path

from m129_scene_wide_release_boundary import SceneWideBoundaryReject, build_report


ROOT = Path(__file__).resolve().parents[1]


class M129SceneWideReleaseBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.m124 = json.loads(
            (ROOT / "research/m124-corpus-caller-coverage.json").read_text(encoding="utf-8")
        )
        self.m121 = json.loads(
            (ROOT / "research/m121-wide-encoder-capacity.json").read_text(encoding="utf-8")
        )
        self.m128 = json.loads(
            (ROOT / "research/m128-control-layout-contract.json").read_text(encoding="utf-8")
        )

    def test_structural_coverage_and_scene_semantics_are_separate(self) -> None:
        report = build_report(self.m124, self.m121, self.m128)
        self.assertEqual(report["structural_caller_coverage"]["exact_pointer_candidate_count"], 609)
        self.assertEqual(report["structural_caller_coverage"]["exact_pointer_record_count"], 370)
        self.assertEqual(report["structural_caller_coverage"]["direct_consumer_callsite_count"], 5)
        self.assertEqual(report["scene_semantics"]["story"], "unconfirmed")
        self.assertEqual(report["scene_semantics"]["battle_dialogue"], "unconfirmed")
        self.assertFalse(report["release_boundary"]["scene_classification_complete"])

    def test_wide_strategy_is_existing_runtime_identity_only(self) -> None:
        report = build_report(self.m124, self.m121, self.m128)
        wide = report["wide_encoder_strategy"]
        self.assertEqual(wide["existing_identity_count"], 743)
        self.assertEqual(wide["runtime_confirmed_identity_count"], 1)
        self.assertEqual(wide["static_only_identity_count"], 742)
        self.assertEqual(wide["new_slot_capacity"], 0)
        self.assertEqual(wide["status"], "runtime_confirmed_existing_identity_only")

    def test_scene_label_or_text_leak_fails_closed(self) -> None:
        bad = json.loads(json.dumps(self.m124))
        bad["semantic_scene_partition"]["story"] = "story"
        with self.assertRaisesRegex(SceneWideBoundaryReject, "scene_semantic_label_inferred"):
            build_report(bad, self.m121, self.m128)
        bad_text = json.loads(json.dumps(self.m121))
        bad_text["source_corpus"]["text"] = "forbidden"
        with self.assertRaisesRegex(SceneWideBoundaryReject, "source_or_target_text_key"):
            build_report(self.m124, bad_text, self.m128)


if __name__ == "__main__":
    unittest.main()
