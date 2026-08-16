#!/usr/bin/env python3
"""Offline tests for the bounded M1.8 A1AC probe."""

import unittest
from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import m18_a1ac_probe  # noqa: E402


class M18A1ACProbeTests(unittest.TestCase):
    def test_fixed_edge_and_return_addresses_are_narrow(self):
        self.assertEqual(m18_a1ac_probe.STATE4_A050, 0x0800A050)
        self.assertEqual(m18_a1ac_probe.A1AC_CALLSITE, 0x0800A3E6)
        self.assertEqual(m18_a1ac_probe.EDGE_CHECK, 0x0800A174)
        self.assertEqual(m18_a1ac_probe.EDGE_TRUE_PATH, 0x0800A180)
        self.assertEqual(m18_a1ac_probe.POST_SLOT_STORE, 0x0800A18C)
        self.assertEqual(m18_a1ac_probe.A2C0_ENTRY, 0x0800A2C0)
        self.assertEqual(m18_a1ac_probe.STATE_RETURN, 0x08005E12)

    def test_active_low_pulse_and_release_values(self):
        self.assertEqual(m18_a1ac_probe.START_KEY, 0x03F7)
        self.assertEqual(m18_a1ac_probe.A_KEY, 0x03FE)
        self.assertEqual(m18_a1ac_probe.NO_KEY, 0x03FF)

    def test_ram_pointer_guard_does_not_promote_rom_or_io(self):
        self.assertTrue(m18_a1ac_probe.is_ram_pointer(0x02001000))
        self.assertTrue(m18_a1ac_probe.is_ram_pointer(0x030033F8))
        self.assertFalse(m18_a1ac_probe.is_ram_pointer(0x08146EE0))
        self.assertFalse(m18_a1ac_probe.is_ram_pointer(0x04000130))

    def test_step_status_is_bounded_without_runtime_client(self):
        self.assertEqual(m18_a1ac_probe.format_pointer(0x0800A1AC), "0x0800A1AC")
        self.assertEqual(m18_a1ac_probe.format_pointer(0x030033F8), "0x030033F8")


if __name__ == "__main__":
    unittest.main()
