import unittest

import patch_message_batch_5 as module


class MessageBatch5Test(unittest.TestCase):
    def test_new_tiles_are_nonempty_and_disjoint(self) -> None:
        tiles = module.validate_bitmaps()
        self.assertEqual(len(tiles), 10)
        self.assertTrue(all(any(tile) for tile in tiles.values()))
        self.assertTrue(set(module.NEW_GLYPH_SLOTS.values()).isdisjoint(module.RESERVED_BATCH_SLOTS))

    def test_target_round_trip_preserves_fe_and_ff(self) -> None:
        from verify_message_batch_5 import decode_target

        encoded = module.encode_target(module.TARGET_TEXT)
        self.assertEqual(len(encoded), module.MESSAGE_SPAN_LENGTH)
        self.assertIn(module.PAGE_CONTROL, encoded)
        self.assertEqual(encoded[-1:], module.PRESERVED_TAIL)
        self.assertEqual(decode_target(encoded), module.TARGET_TEXT)

    def test_allowed_ranges_cover_message_and_each_tile(self) -> None:
        from verify_message_batch_5 import allowed_ranges

        ranges = allowed_ranges()
        self.assertEqual(len(ranges), 1 + len(module.GLYPH_SLOTS))
        self.assertEqual(
            ranges[0],
            (module.MESSAGE_FILE_OFFSET, module.MESSAGE_FILE_OFFSET + module.MESSAGE_SPAN_LENGTH),
        )


if __name__ == "__main__":
    unittest.main()
