import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m26_punctuation_probe import PUNCTUATION_CANDIDATES, probe  # noqa: E402


class M26PunctuationProbeTests(unittest.TestCase):
    def test_fixed_punctuation_candidates_are_explicit(self) -> None:
        self.assertEqual(
            set(PUNCTUATION_CANDIDATES),
            {0x0006, 0x0008, 0x0009, 0x000A, 0x000C, 0x000D},
        )
        self.assertEqual(PUNCTUATION_CANDIDATES[0x0008]["layout_label"], "question-mark")

    def test_short_rom_does_not_open_any_gate(self) -> None:
        result = probe(b"\0" * 0x200)
        self.assertFalse(result["gate"]["confirmed_identity_count_added"])
        self.assertFalse(result["gate"]["control_semantics_confirmed"])
        self.assertFalse(result["gate"]["eligible_for_ledger"])
        self.assertNotIn("text", result)


if __name__ == "__main__":
    unittest.main()
