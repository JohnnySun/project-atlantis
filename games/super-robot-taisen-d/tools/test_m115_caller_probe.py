from __future__ import annotations

import unittest

from m115_caller_probe import CONSUMER, classify_entry


class M115CallerProbeTest(unittest.TestCase):
    def test_entry_metadata_preserves_caller_and_pointer_match(self) -> None:
        regs = {
            "pc": CONSUMER,
            "lr": 0x0800F49F,
            "r0": 0x08080858,
            "r1": 0,
            "r2": 0,
            "r3": 0,
            "r4": 0,
            "r5": 0,
            "sp": 0x0203FF00,
        }
        result = classify_entry(regs, target_pointer=0x08080858)
        self.assertEqual(result["caller_callsite"], "0x0800F49A")
        self.assertTrue(result["target_pointer_match"])
        self.assertEqual(result["source_pointer_region"], "rom")

    def test_ram_buffer_is_not_target(self) -> None:
        regs = {
            "pc": CONSUMER,
            "lr": 0x08008811,
            "r0": 0x02018368,
            "r1": 0,
            "r2": 0,
            "r3": 0,
            "r4": 0,
            "r5": 0,
            "sp": 0x03007E00,
        }
        result = classify_entry(regs, target_pointer=0x08080858)
        self.assertFalse(result["target_pointer_match"])
        self.assertEqual(result["source_pointer_region"], "ram_or_io")


if __name__ == "__main__":
    unittest.main()
