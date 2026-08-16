import unittest

import build_bounded_batches as module
import patch_menu
import patch_message_batch_2
import patch_message_batch_3
import verify_menu_patch
import verify_message_batch_2
import verify_message_batch_3


class BoundedBatchBuildTest(unittest.TestCase):
    def test_merge_keeps_disjoint_batch_changes(self) -> None:
        clean = bytes(8)
        menu = bytearray(clean)
        message = bytearray(clean)
        menu[1] = 0x11
        message[6] = 0x66
        self.assertEqual(module.merge(clean, bytes(menu), bytes(message)), bytes((0, 0x11, 0, 0, 0, 0, 0x66, 0)))

    def test_merge_rejects_conflicting_changes(self) -> None:
        clean = bytes(2)
        with self.assertRaises(ValueError):
            module.merge(clean, bytes((0x11, 0)), bytes((0x22, 0)))

    def test_merge_keeps_third_disjoint_batch_change(self) -> None:
        clean = bytes(9)
        menu = bytearray(clean)
        message = bytearray(clean)
        message_3 = bytearray(clean)
        menu[1] = 0x11
        message[6] = 0x66
        message_3[8] = 0x88
        self.assertEqual(
            module.merge(clean, bytes(menu), bytes(message), bytes(message_3)),
            bytes((0, 0x11, 0, 0, 0, 0, 0x66, 0, 0x88)),
        )

    def test_ranges_are_disjoint(self) -> None:
        ranges = verify_menu_patch.allowed_ranges() + verify_message_batch_2.allowed_ranges() + verify_message_batch_3.allowed_ranges()
        for index, (start, end) in enumerate(ranges):
            for other_start, other_end in ranges[index + 1:]:
                self.assertTrue(end <= other_start or other_end <= start)


if __name__ == "__main__":
    unittest.main()
