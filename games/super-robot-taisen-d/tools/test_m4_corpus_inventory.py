import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m17_layout import tokenize_payload
from m4_corpus_inventory import InventoryError, classify_partition, hash_ints, inventory


def pair(low: int, high: int) -> bytes:
    return bytes((low, high))


class M4CorpusInventoryTests(unittest.TestCase):
    def test_structural_partition_is_fail_closed(self) -> None:
        self.assertEqual(classify_partition(tokenize_payload(pair(0x83, 0x40))), "glyph_only_narrow")
        self.assertEqual(classify_partition(tokenize_payload(pair(0x88, 0x40))), "glyph_only_wide")
        self.assertEqual(
            classify_partition(tokenize_payload(pair(0x83, 0x40) + pair(0x88, 0x40))),
            "glyph_only_mixed",
        )
        self.assertEqual(classify_partition(tokenize_payload(b"AB")), "opaque_or_unaligned")

    def test_inventory_requires_exact_clean_rom_and_corpus(self) -> None:
        with self.assertRaises(InventoryError):
            inventory(b"not a rom", [])

    def test_source_safe_digest_is_deterministic(self) -> None:
        self.assertEqual(
            hash_ints([1, 2, 3]),
            "8a6ae15122001229edb8866f56e342af12ae8187203c3e3b33931743e7c0c48d",
        )


if __name__ == "__main__":
    unittest.main()
