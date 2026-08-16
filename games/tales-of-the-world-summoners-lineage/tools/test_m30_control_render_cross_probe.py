import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m30_control_render_cross_probe import control_receipt  # noqa: E402


class M30ControlRenderCrossProbeTests(unittest.TestCase):
    def test_parser_and_render_layout_confirm_line_advance_only(self) -> None:
        data = b"\x5e\x00\x70\xff\x66\x00\x00\x00"
        result = control_receipt(data, 0, image_sha256="image", image_dimensions=(640, 96))
        self.assertEqual(result["control"]["occurrence_count_before_terminator"], 1)
        self.assertEqual(result["control"]["rendered_line_count_expected"], 2)
        self.assertTrue(result["gate"]["control_semantics_confirmed"])
        self.assertFalse(result["gate"]["variable_name_item_controls_confirmed"])
        self.assertFalse(result["gate"]["eligible_for_ledger"])
        self.assertFalse(result["source_text_emitted"])

    def test_without_render_stays_candidate(self) -> None:
        data = b"\x70\xff\x00\x00"
        result = control_receipt(data, 0)
        self.assertEqual(result["control"]["semantic_status"], "line-advance-candidate")
        self.assertFalse(result["gate"]["control_semantics_confirmed"])


if __name__ == "__main__":
    unittest.main()
