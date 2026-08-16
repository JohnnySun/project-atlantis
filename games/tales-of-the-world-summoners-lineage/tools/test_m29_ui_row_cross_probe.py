import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m29_ui_row_cross_probe import (  # noqa: E402
    EXPECTED_CALLER,
    EXPECTED_STREAM,
    M32_STREAM_UNITS,
    crop_mask,
    cross_check,
    font_record_mask,
    image_component_mask,
    tilemap_receipt,
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

    def test_raster_receipt_promotes_only_the_matching_row(self) -> None:
        rows = [
            {
                "string_id": "m32-row",
                "caller_bus_address": EXPECTED_CALLER,
                "stream_file_offset": EXPECTED_STREAM,
                "source_text_sha256": "hash",
                "mapping_status_counts": {"provisional": 5},
                "unresolved_code_units": [],
                "control_candidates": [],
                "complete_codepage": True,
            }
        ]
        receipt = {
            "classification": {
                "runtime_context_proof": "known-screen-record-raster-and-tilemap-correlated",
                "glyph_identity_confirmed_by_this_probe": 5,
                "eligible_for_ledger": True,
            }
        }
        result = cross_check(rows, screen_summary(), raster_receipt=receipt)
        self.assertEqual(result["classification"]["glyph_identity_confirmed_by_this_probe"], 5)
        self.assertTrue(result["classification"]["eligible_for_ledger"])
        self.assertFalse(result["classification"]["raw_byte_copy_confirmed"])

    def test_missing_row_is_not_classified(self) -> None:
        result = cross_check([], screen_summary())
        self.assertEqual(result["classification"]["scene_role_candidate"], "unknown")
        self.assertEqual(result["classification"]["runtime_context_proof"], "missing")

    def test_record_and_screen_masks_use_same_msb_geometry(self) -> None:
        record = bytearray(24)
        record[4:6] = (0x0600).to_bytes(2, "little")
        expected = ((1, 1),)
        self.assertEqual(font_record_mask(bytes(record)), expected)
        image = [[(0, 0, 0) for _ in range(4)] for _ in range(4)]
        image[1][1] = (255, 255, 255)
        image[1][2] = (255, 255, 255)
        screen = image_component_mask(image, (1, 1, 3, 2))
        self.assertEqual(crop_mask(screen), expected)

    def test_tilemap_probe_is_bounded_and_fails_closed_on_blank_vram(self) -> None:
        receipt = tilemap_receipt(bytes(0x18000))
        self.assertEqual(len(receipt["rows"]), len(M32_STREAM_UNITS))
        self.assertFalse(receipt["expected_vram_sha256_match"])
        self.assertFalse(receipt["all_tilemap_and_tile_hashes_match"])


if __name__ == "__main__":
    unittest.main()
