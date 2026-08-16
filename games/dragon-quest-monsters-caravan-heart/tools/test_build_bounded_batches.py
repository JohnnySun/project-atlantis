import unittest

import build_bounded_batches as module
import patch_menu
import patch_message_batch_2
import patch_message_batch_3
import patch_message_batch_4
import patch_message_batch_5
import verify_menu_patch
import verify_message_batch_2
import verify_message_batch_3
import verify_message_batch_4
import verify_message_batch_5


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

    def test_merge_keeps_fourth_disjoint_batch_change(self) -> None:
        clean = bytes(10)
        menu = bytearray(clean)
        message = bytearray(clean)
        message_3 = bytearray(clean)
        message_4 = bytearray(clean)
        menu[1] = 0x11
        message[6] = 0x66
        message_3[8] = 0x88
        message_4[9] = 0x99
        self.assertEqual(
            module.merge(clean, bytes(menu), bytes(message), bytes(message_3), bytes(message_4)),
            bytes((0, 0x11, 0, 0, 0, 0, 0x66, 0, 0x88, 0x99)),
        )

    def test_merge_keeps_fifth_disjoint_batch_change(self) -> None:
        clean = bytes(11)
        menu = bytearray(clean)
        message = bytearray(clean)
        message_3 = bytearray(clean)
        message_4 = bytearray(clean)
        message_5 = bytearray(clean)
        menu[1] = 0x11
        message[6] = 0x66
        message_3[8] = 0x88
        message_4[9] = 0x99
        message_5[10] = 0xAA
        self.assertEqual(
            module.merge(clean, bytes(menu), bytes(message), bytes(message_3), bytes(message_4), bytes(message_5)),
            bytes((0, 0x11, 0, 0, 0, 0, 0x66, 0, 0x88, 0x99, 0xAA)),
        )

    def test_message_ranges_are_disjoint(self) -> None:
        # Batch 5 intentionally reuses six exact authored glyph slots.  The
        # fixed message spans themselves must remain disjoint; merge() still
        # rejects conflicting overlapping font bytes.
        ranges = [
            verify_menu_patch.allowed_ranges()[0],
            verify_message_batch_2.allowed_ranges()[0],
            verify_message_batch_3.allowed_ranges()[0],
            verify_message_batch_4.allowed_ranges()[0],
            verify_message_batch_5.allowed_ranges()[0],
        ]
        for index, (start, end) in enumerate(ranges):
            for other_start, other_end in ranges[index + 1:]:
                self.assertTrue(end <= other_start or other_end <= start)


if __name__ == "__main__":
    unittest.main()
