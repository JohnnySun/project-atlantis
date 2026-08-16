import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m29_ui_row_cross_probe import (  # noqa: E402
    EXPECTED_CALLER,
    EXPECTED_STREAM,
    cross_check,
)


def screen_summary() -> dict[str, object]:
    return {
        "rom": {"sha256": "wrong"},
        "starts": [
            {
                "screen": {
                    "gate_confirmed": True,
                    "dispcnt": "0x1B40",
                    "bgcnt": ["0x0001", "0x0106"],
                    "bg0_screenblock_sha256": "bg0",
                    "bg1_screenblock_sha256": "bg1",
                    "keyboard_layout": {"position_match_count": 8, "selected_positions": [1] * 8},
                }
            }
        ],
    }


class M29UiRowCrossProbeTests(unittest.TestCase):
    def test_correlated_row_still_keeps_ledger_closed(self) -> None:
        rows = [
            {
                "string_id": "synthetic",
                "caller_bus_address": EXPECTED_CALLER,
                "stream_file_offset": EXPECTED_STREAM,
                "source_text_sha256": "hash",
                "mapping_status_counts": {"provisional": 1},
                "unresolved_code_units": [],
                "control_candidates": [],
                "complete_codepage": True,
            }
        ]
        result = cross_check(rows, screen_summary())
        self.assertEqual(result["candidate_match_count"], 1)
        self.assertEqual(result["classification"]["scene_role_candidate"], "ui-name-entry")
        self.assertFalse(result["classification"]["reader_breakpoint_hit"])
        self.assertFalse(result["classification"]["eligible_for_ledger"])
        self.assertFalse(result["source_text_emitted"])

    def test_missing_row_is_not_classified(self) -> None:
        result = cross_check([], screen_summary())
        self.assertEqual(result["classification"]["scene_role_candidate"], "unknown")
        self.assertEqual(result["classification"]["runtime_context_proof"], "missing")


if __name__ == "__main__":
    unittest.main()
