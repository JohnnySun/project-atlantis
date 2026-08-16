import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m25_context_mapping_probe import (  # noqa: E402
    CONTEXT_PROVISIONAL,
    probe,
)


class M25ContextMappingProbeTests(unittest.TestCase):
    def test_candidate_tier_is_not_confirmed(self) -> None:
        self.assertEqual(set(CONTEXT_PROVISIONAL), {0x000C, 0x00A8})
        self.assertEqual(CONTEXT_PROVISIONAL[0x000C]["unicode_candidate"], "ー")
        self.assertEqual(CONTEXT_PROVISIONAL[0x00A8]["unicode_candidate"], "ッ")

    def test_short_rom_keeps_gate_closed(self) -> None:
        result = probe(b"\0" * 0x200)
        self.assertFalse(result["gate"]["runtime_scene_context_confirmed"])
        self.assertFalse(result["gate"]["eligible_for_ledger"])
        self.assertEqual(
            [item["identity_status"] for item in result["candidates"]],
            ["context-provisional", "context-provisional"],
        )
        self.assertNotIn("text", result)


if __name__ == "__main__":
    unittest.main()
