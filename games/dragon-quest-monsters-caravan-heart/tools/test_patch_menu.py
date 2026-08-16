import importlib.util
import pathlib
import unittest


PATH = pathlib.Path(__file__).with_name("patch_menu.py")
SPEC = importlib.util.spec_from_file_location("dqmch_patch_menu", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PatchMenuTest(unittest.TestCase):
    def test_authored_tiles_are_gba_4bpp_and_nonempty(self) -> None:
        tiles = MODULE.validate_bitmaps()
        self.assertEqual(set(tiles), set(MODULE.GLYPH_SLOTS))
        self.assertTrue(all(len(tile) == 32 and any(tile) for tile in tiles.values()))

    def test_target_fits_fixed_menu_span_and_preserves_ff(self) -> None:
        encoded = MODULE.encode_target(MODULE.TARGET_TEXT)
        self.assertEqual(len(encoded), MODULE.MENU_SPAN_LENGTH)
        self.assertEqual(encoded[-2:], b"\xff\xff")
        self.assertNotIn(0xDF, encoded[:-2])

    def test_target_only_uses_allocated_glyphs_and_spaces(self) -> None:
        encoded = MODULE.encode_target(MODULE.TARGET_TEXT)[:-2]
        index = 0
        while index < len(encoded):
            value = encoded[index]
            if value == MODULE.SPACE_CODE:
                index += 1
            else:
                self.assertEqual(value, MODULE.ALT_LEAD)
                self.assertIn(encoded[index + 1], MODULE.GLYPH_SLOTS.values())
                index += 2


if __name__ == "__main__":
    unittest.main()
