from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m130_runtime_target import (  # noqa: E402
    DIRECT_THUMB_INITIALIZER_CALLER,
    _record_metadata,
    compare_reports,
)


class M130RuntimeTargetTest(unittest.TestCase):
    def test_record_metadata_is_source_safe(self) -> None:
        rom = bytearray(0x100)
        rom[0x20:0x24] = bytes.fromhex("83e883e7")
        rom[0x24] = 0
        row = _record_metadata(bytes(rom), 0x20, "target", "a" * 64)
        self.assertEqual(row["unit_count"], 2)
        self.assertEqual(row["line_width"], 16)
        self.assertEqual(row["terminator"], "NUL")
        self.assertNotIn("text", row)
        self.assertNotIn("raw", row)

    def test_direct_thumb_entry_is_an_architectural_address(self) -> None:
        self.assertEqual(DIRECT_THUMB_INITIALIZER_CALLER, 0x08014E84)

    def test_compare_keeps_screen_and_release_fail_closed(self) -> None:
        def unit(glyph: str, render: str) -> dict:
            return {"glyph": {"glyph": {"sha256": glyph}}, "render": {"pixel_nibble_sha256": render}}

        def report(label: str, target_payload: str, target_render: str) -> dict:
            target_units = [unit(target_render + "a", target_render + "b"), unit(target_render + "c", target_render + "d")]
            adjacent_units = [unit("same-a", "same-b"), unit("same-c", "same-d")]
            target = {
                "record": {"unit_count": 2},
                "units": target_units,
                "combined_unit_render_sha256": target_render,
                "layout": {"width": 16, "height": 12, "exact_per_unit": True},
                "termination": {"unit_count_observed": 2, "record_not_truncated": True, "nul_branch": {"observed": True}},
            }
            adjacent = {
                "units": adjacent_units,
                "layout": {"exact_per_unit": True},
            }
            return {
                "rom": {"sha256": label},
                "source_policy": {"target_payload_sha256": target_payload, "adjacent_payload_sha256": "adj"},
                "runtime": {"font_slots": {"narrow": "0x1", "wide": "0x2"}, "target": target, "adjacent": adjacent},
                "gate": {"font_base_nonzero": True},
            }

        result = compare_reports(report("base", "base", "base-render"), report("patched", "patched", "patched-render"))
        self.assertTrue(result["target"]["patched_record_not_truncated"])
        self.assertTrue(result["adjacent"]["runtime_untouched"])
        self.assertFalse(result["gate"]["release_ready"])
        self.assertTrue(result["gate"]["natural_screen_not_claimed"])


if __name__ == "__main__":
    unittest.main()
