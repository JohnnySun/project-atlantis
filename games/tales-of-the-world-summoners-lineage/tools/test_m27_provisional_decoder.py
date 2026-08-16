import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m27_provisional_decoder import (  # noqa: E402
    PROVISIONAL_OVERLAY,
    overlay_mapping,
    summary,
)


class M27ProvisionalDecoderTests(unittest.TestCase):
    def test_overlay_statuses_are_explicit(self) -> None:
        self.assertEqual(PROVISIONAL_OVERLAY[0x000C][1], "context-provisional-keyboard-punctuation")
        self.assertEqual(PROVISIONAL_OVERLAY[0x00A8][1], "context-provisional-small-kana")

    def test_short_rom_does_not_open_ledger_gate(self) -> None:
        result = summary(b"rom", [])
        self.assertFalse(result["runtime_context_confirmed"])
        self.assertFalse(result["eligible_for_ledger"])
        self.assertEqual(result["rows_emitted"], 0)

    def test_overlay_does_not_replace_existing_mapping(self) -> None:
        fake = b"\0" * 0x200
        mapping = overlay_mapping(fake)
        self.assertEqual(mapping[0x000C]["text"], "ー")
        self.assertEqual(mapping[0x00A8]["text"], "ッ")


if __name__ == "__main__":
    unittest.main()
