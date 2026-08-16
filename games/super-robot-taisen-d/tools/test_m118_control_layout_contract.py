from __future__ import annotations

import unittest

from m17_layout import Token
from m118_control_layout_contract import token_policy


class M118ControlLayoutContractTest(unittest.TestCase):
    def test_known_glyph_policy_is_structural(self) -> None:
        narrow = Token(kind="glyph", raw=b"\x83\xe8", raw_offset=0, glyph_class="narrow", layout_width=8, glyph_stride=12)
        wide = Token(kind="glyph", raw=b"\x88\x40", raw_offset=0, glyph_class="wide", layout_width=12, glyph_stride=26)
        self.assertEqual(token_policy(narrow), "glyph_narrow")
        self.assertEqual(token_policy(wide), "glyph_wide")

    def test_unknown_units_remain_opaque(self) -> None:
        token = Token(kind="opaque_unit", raw=b"AB", raw_offset=0, reason="not_a_verified_double_byte_glyph")
        self.assertEqual(token_policy(token), "opaque_unit")
        newline = Token(kind="opaque_newline_candidate", raw=b"\nA", raw_offset=0)
        self.assertEqual(token_policy(newline), "opaque_newline_candidate")


if __name__ == "__main__":
    unittest.main()
