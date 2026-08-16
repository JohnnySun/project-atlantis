#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import trace_m19_glyph_sink as tracer  # noqa: E402


ROM_PATH = Path(__file__).resolve().parents[1] / "roms" / "base" / "AFEJ.gba"


class AfejM119GlyphSinkStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = tracer._static_gate(ROM_PATH.read_bytes())

    def test_runtime_map_and_unicode_boundary_are_separate(self):
        mapping = self.report["two_byte_map"]
        self.assertEqual(mapping["lookup_entry"], "0x080992dc")
        self.assertEqual(mapping["map_base"], "0x08691644")
        self.assertTrue(mapping["runtime_lookup_confirmed"])
        self.assertFalse(mapping["unicode_identity_confirmed"])
        self.assertFalse(self.report["semantic_name_assigned"])

    def test_exact_glyph_field_and_composer_boundaries(self):
        field = self.report["glyph_field"]
        composer = self.report["composer"]
        self.assertIn("strh r0, [r4]", field["write_instruction"])
        self.assertEqual(field["field_offset"], "0x4a")
        self.assertIn("bl #0x80995b0", composer["call_instruction"])
        self.assertIn("str r1, [r2]", composer["writer_instruction"])
        self.assertEqual(composer["writer_after"], "0x080995a8: pop {r4}")

    def test_breakpoint_addresses_keep_mov_and_bl_distinct(self):
        self.assertNotEqual(tracer.COMPOSER_CALL, 0x08099460)
        self.assertEqual(tracer.COMPOSER_CALL, 0x08099462)
        self.assertEqual(tracer.RENDERER_WRITE, 0x080995A6)
        self.assertIn(tracer.RENDERER_KERNEL, tracer.BREAKPOINTS)

    def test_route_is_bounded_and_natural_only(self):
        self.assertEqual(tracer.parse_sequence("start,a"), ["start", "a"])
        self.assertNotIn(tracer.MAP_BASE, [tracer.BUFFER, tracer.KEYINPUT])


if __name__ == "__main__":
    unittest.main()
