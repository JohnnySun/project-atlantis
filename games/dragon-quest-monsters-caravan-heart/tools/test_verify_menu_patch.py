import unittest

import verify_menu_patch as module


class VerifyMenuPatchTest(unittest.TestCase):
    def test_target_encoding_reextracts_to_zh_tw_text(self) -> None:
        encoded = module.encode_target(module.TARGET_TEXT)
        self.assertEqual(module.decode_target(encoded), module.TARGET_TEXT)

    def test_allowed_ranges_cover_menu_and_each_allocated_tile(self) -> None:
        ranges = module.allowed_ranges()
        self.assertEqual(len(ranges), 1 + len(module.GLYPH_SLOTS))
        self.assertEqual(ranges[0], (module.MENU_FILE_OFFSET, module.MENU_FILE_OFFSET + module.MENU_SPAN_LENGTH))

    def test_terminator_is_part_of_fixed_span(self) -> None:
        encoded = module.encode_target(module.TARGET_TEXT)
        self.assertEqual(encoded[-2:], module.TERMINATOR)
        self.assertEqual(len(encoded), module.MENU_SPAN_LENGTH)


if __name__ == "__main__":
    unittest.main()
