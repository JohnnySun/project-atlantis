import unittest

import patch_message_batch_8 as module
import verify_message_batch_8


class MessageBatch8Test(unittest.TestCase):
    def test_new_slots_are_mixed_bank_and_disjoint(self) -> None:
        self.assertEqual(module.NEW_GLYPH_SLOTS["方"], (0xE1, 0xFF))
        self.assertEqual(module.NEW_GLYPH_SLOTS["拒"], (0xE0, 0x22))
        self.assertEqual(module.NEW_GLYPH_SLOTS["絕"], (0xE0, 0xF7))
        self.assertEqual(len(set(module.GLYPH_SLOTS.values())), len(module.GLYPH_SLOTS))

    def test_targets_round_trip_with_preserved_tail(self) -> None:
        for spec in module.MESSAGE_SPECS:
            encoded = module.encode_target(str(spec["target"]), int(spec["data_length"]))
            self.assertEqual(len(encoded), int(spec["span_length"]))
            self.assertEqual(verify_message_batch_8.decode_target(encoded, spec), spec["target"])
            self.assertEqual(encoded[-1:], module.PRESERVED_TAIL)

    def test_encoder_uses_both_alt_leads(self) -> None:
        encoded = module.encode_target("對方拒絕對戰。", 15)
        self.assertIn(bytes((0xE0, 0x22)), encoded)
        self.assertIn(bytes((0xE1, 0xFF)), encoded)


if __name__ == "__main__":
    unittest.main()
