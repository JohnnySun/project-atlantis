import unittest

import patch_message_batch_2 as patch
import verify_message_batch_2 as verify


class MessageBatch2Test(unittest.TestCase):
    def test_target_round_trip_preserves_dynamic_tail(self) -> None:
        encoded = patch.encode_target(patch.TARGET_TEXT)
        self.assertEqual(len(encoded), patch.MESSAGE_SPAN_LENGTH)
        self.assertEqual(encoded[-len(patch.PRESERVED_TAIL):], patch.PRESERVED_TAIL)
        self.assertEqual(verify.decode_target(encoded), patch.TARGET_TEXT)

    def test_authored_tiles_are_nonempty(self) -> None:
        tiles = patch.validate_bitmaps()
        self.assertEqual(set(tiles), set(patch.GLYPH_SLOTS))
        self.assertTrue(all(any(tile) for tile in tiles.values()))

    def test_allowed_ranges_include_each_tile(self) -> None:
        ranges = verify.allowed_ranges()
        self.assertEqual(len(ranges), 1 + len(patch.GLYPH_SLOTS))
        self.assertEqual(ranges[0], (patch.MESSAGE_FILE_OFFSET, patch.MESSAGE_FILE_OFFSET + patch.MESSAGE_SPAN_LENGTH))


if __name__ == "__main__":
    unittest.main()
