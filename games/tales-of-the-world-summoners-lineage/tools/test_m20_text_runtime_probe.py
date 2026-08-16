#!/usr/bin/env python3
"""Pure tests for the bounded M20 runtime text probe."""

from __future__ import annotations

import unittest

from m20_text_runtime_probe import (
    memory_region,
    screen_gate_metadata,
    static_render_path,
    summarize_window,
)


class M20TextRuntimeProbeTests(unittest.TestCase):
    def test_window_summary_separates_terminator_and_control_candidate(self) -> None:
        data = b"".join(
            value.to_bytes(2, "little")
            for value in (0x005E, 0xFF70, 0x0066, 0x0000)
        ) + b"\xAA\x55"
        summary = summarize_window(data)
        self.assertTrue(summary["terminated_by_0000"])
        self.assertEqual(summary["control_candidate_count"], 1)
        self.assertEqual(summary["font_record_index_count"], 2)
        self.assertEqual(
            summary["static_render_path_counts"],
            {
                "font-record-consumer-080049a0": 2,
                "line-advance-ff70": 1,
                "terminator-0000": 1,
            },
        )
        self.assertNotIn("code_units", summary)
        self.assertNotIn("text", summary)

    def test_static_dispatch_model_keeps_nonzero_units_on_font_path(self) -> None:
        self.assertEqual(static_render_path(0x0000), "terminator-0000")
        self.assertEqual(static_render_path(0xFF70), "line-advance-ff70")
        self.assertEqual(static_render_path(0x0003), "font-record-consumer-080049a0")

    def test_static_dispatch_model_is_explicitly_not_runtime_evidence(self) -> None:
        summary = summarize_window((0x0003).to_bytes(2, "little"))
        model = summary["static_path_model"]
        self.assertFalse(model["runtime_observed"])
        self.assertEqual(model["record_stride"], "0x18")

    def test_window_summary_marks_cap_without_terminator(self) -> None:
        summary = summarize_window((0x005E).to_bytes(2, "little") * 4)
        self.assertFalse(summary["terminated_by_0000"])
        self.assertTrue(summary["capped_or_short"])
        self.assertEqual(summary["unit_count_including_terminator"], 4)

    def test_region_classification_is_not_a_source_claim(self) -> None:
        self.assertEqual(memory_region(0x08010000), "rom-bus")
        self.assertEqual(memory_region(0x02004014), "ewram")
        self.assertEqual(memory_region(0x03007EAC), "iwram")
        self.assertEqual(memory_region(0x06004020), "vram")
        self.assertEqual(memory_region(0x04000000), "other")

    def test_screen_gate_metadata_has_hashes_but_no_raw_maps(self) -> None:
        class FakeClient:
            def read_memory(self, address: int, length: int, chunk_size: int = 0x200) -> bytes:
                del chunk_size
                if address == 0x04000000:
                    return (0x1B40).to_bytes(2, "little")
                if address == 0x04000008:
                    return (0x0001).to_bytes(2, "little")
                if address == 0x0400000A:
                    return (0x0106).to_bytes(2, "little")
                if address == 0x0400000C:
                    return (0x028A).to_bytes(2, "little")
                if address == 0x0400000E:
                    return (0x030F).to_bytes(2, "little")
                if address == 0x06000000:
                    return b"\0" * 0x800
                if address == 0x06000800:
                    tilemap = bytearray(0x800)
                    for x, y, tile_id in (
                        (1, 7, 1), (2, 7, 2), (3, 7, 3), (4, 7, 4),
                        (5, 7, 5), (1, 8, 27), (2, 8, 28), (3, 8, 29),
                    ):
                        tilemap[2 * (y * 32 + x):2 * (y * 32 + x) + 2] = (0x1000 | tile_id).to_bytes(2, "little")
                    return bytes(tilemap)
                raise AssertionError((hex(address), length))

        metadata = screen_gate_metadata(FakeClient())
        self.assertTrue(metadata["keyboard_gate"])
        self.assertEqual(metadata["keyboard_position_match_count"], 8)
        self.assertNotIn("bg0", metadata)
        self.assertNotIn("bg1", metadata)


if __name__ == "__main__":
    unittest.main()
