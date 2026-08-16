from __future__ import annotations

import unittest

from m17_layout import Token, Tokenization
from m116_layout_safe_contract import evaluate_tokenization


class M116LayoutSafeContractTest(unittest.TestCase):
    def test_accepts_only_narrow_within_observed_cap(self) -> None:
        tokens = tuple(
            Token(kind="glyph", raw=b"\x83\xe8", raw_offset=0, glyph_class="narrow", layout_width=8, glyph_stride=12)
            for _ in range(8)
        )
        decision = evaluate_tokenization(Tokenization(payload=b"".join(token.raw for token in tokens), tokens=tokens))
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["reason"], "single_line_narrow")

    def test_rejects_wide_and_over_cap(self) -> None:
        wide = Token(kind="glyph", raw=b"\x88\x40", raw_offset=0, glyph_class="wide", layout_width=12, glyph_stride=26)
        self.assertEqual(evaluate_tokenization(Tokenization(payload=wide.raw, tokens=(wide,)))["reason"], "glyph_only_wide")
        narrow_tokens = tuple(
            Token(kind="glyph", raw=b"\x83\xe8", raw_offset=index * 2, glyph_class="narrow", layout_width=8, glyph_stride=12)
            for index in range(9)
        )
        decision = evaluate_tokenization(Tokenization(payload=b"".join(token.raw for token in narrow_tokens), tokens=narrow_tokens))
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["reason"], "width_over_observed_cap")

    def test_rejects_opaque_token_without_naming_its_semantics(self) -> None:
        opaque = Token(kind="opaque_unit", raw=b"AB", raw_offset=0, reason="not_a_verified_double_byte_glyph")
        decision = evaluate_tokenization(Tokenization(payload=opaque.raw, tokens=(opaque,)))
        self.assertFalse(decision["accepted"])
        self.assertEqual(decision["reason"], "opaque_or_unaligned")


if __name__ == "__main__":
    unittest.main()
