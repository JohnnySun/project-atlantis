from __future__ import annotations

import unittest

from m19_runtime_trace import (
    CACHE_LENGTH,
    NARROW_GLYPH_LENGTH,
    PATCHED_ROM_SHA256,
    STACK_LENGTH,
)


class M19RuntimeTraceTest(unittest.TestCase):
    def test_trace_contract_is_bounded_and_metadata_only(self) -> None:
        self.assertEqual(NARROW_GLYPH_LENGTH, 12)
        self.assertEqual(STACK_LENGTH, 0x100)
        self.assertEqual(CACHE_LENGTH, 0x1000)
        self.assertEqual(len(PATCHED_ROM_SHA256), 64)


if __name__ == "__main__":
    unittest.main()
