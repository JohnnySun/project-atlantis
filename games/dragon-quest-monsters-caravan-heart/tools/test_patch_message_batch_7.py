import unittest

import patch_message_batch_7 as module


class MessageBatch7Test(unittest.TestCase):
    def test_new_tiles_are_nonempty_and_unique(self) -> None:
        tiles = module.validate_bitmaps()
        self.assertEqual(set(tiles), {"要", "嗎", "開", "始", "對", "戰"})
        self.assertTrue(all(any(tile) for tile in tiles.values()))
        self.assertEqual(len(module.NEW_GLYPH_SLOTS), 2)
        self.assertEqual(len(module.REUSED_GLYPH_SLOTS), 4)
        self.assertEqual(len(set(module.GLYPH_SLOTS.values())), 6)

    def test_target_round_trip_fits_and_preserves_ff(self) -> None:
        from verify_message_batch_7 import decode_target

        encoded = module.encode_target(module.TARGET_TEXT)
        self.assertEqual(len(encoded), module.MESSAGE_SPAN_LENGTH)
        self.assertEqual(encoded[-1:], module.PRESERVED_TAIL)
        self.assertEqual(decode_target(encoded), module.TARGET_TEXT)

    def test_allowed_ranges_cover_message_and_each_tile(self) -> None:
        from verify_message_batch_7 import allowed_ranges

        ranges = allowed_ranges()
        self.assertEqual(len(ranges), 1 + len(module.GLYPH_SLOTS))
        self.assertEqual(
            ranges[0],
            (module.MESSAGE_FILE_OFFSET, module.MESSAGE_FILE_OFFSET + module.MESSAGE_SPAN_LENGTH),
        )


if __name__ == "__main__":
    unittest.main()
