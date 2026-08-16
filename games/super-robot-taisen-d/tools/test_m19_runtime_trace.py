from __future__ import annotations

import unittest

from m19_runtime_trace import (
    CACHE_LENGTH,
    CONSUMER,
    NARROW_GLYPH_LENGTH,
    PATCHED_ROM_SHA256,
    STACK_LENGTH,
    classify_trace_events,
    gdb_pc_argument,
)


class M19RuntimeTraceTest(unittest.TestCase):
    def test_trace_contract_is_bounded_and_metadata_only(self) -> None:
        self.assertEqual(NARROW_GLYPH_LENGTH, 12)
        self.assertEqual(STACK_LENGTH, 0x100)
        self.assertEqual(CACHE_LENGTH, 0x1000)
        self.assertEqual(len(PATCHED_ROM_SHA256), 64)

    def test_controlled_entry_uses_consumer_prefetch_adjustment(self) -> None:
        self.assertEqual(gdb_pc_argument(CONSUMER, "thumb"), CONSUMER - 2)

    def test_unmatched_natural_consumer_never_counts_as_requested_render(self) -> None:
        result = classify_trace_events(
            [
                {
                    "kind": "codepage_lookup",
                    "source_pointer": "0x02018368",
                    "code_unit": "0x628D",
                },
                {"kind": "glyph_complete"},
                {"kind": "tile_writer", "writer": {}},
            ],
            expected_source_pointer="0x08080858",
            expected_unit_count=2,
        )
        self.assertFalse(result["consumer_argument_match"])
        self.assertFalse(result["complete_observed"])
        self.assertEqual(result["unit_loop_status"], "natural_or_unmatched_consumer")


if __name__ == "__main__":
    unittest.main()
