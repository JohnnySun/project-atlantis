import importlib.util
import pathlib
import unittest


_PATH = pathlib.Path(__file__).with_name("render_script_record.py")
_SPEC = importlib.util.spec_from_file_location("render_script_record", _PATH)
assert _SPEC and _SPEC.loader
MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MODULE)


class RenderScriptRecordTest(unittest.TestCase):
    def test_gba_4bpp_uses_low_nibble_at_even_x(self) -> None:
        tile = bytes([0x21]) + bytes(31)
        image = MODULE.tile_image(tile, scale=1)
        self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(image.getpixel((1, 0)), (255, 255, 255))

    def test_alt_glyph_control_consumes_one_parameter(self) -> None:
        rom = bytes(range(256)) * (0x800000 // 256)
        record = {
            "tokens": [
                {"kind": "control-candidate", "value": 0xE0},
                {"kind": "single-byte-candidate", "value": 0x8D},
                {"kind": "control-candidate", "value": 0xFF},
            ]
        }
        image, controls = MODULE.render_record(rom, record, scale=1, skip_controls=True)
        self.assertEqual((image.width, image.height), (9, 8))
        self.assertEqual(controls, 1)

    def test_e1_selects_the_second_alternate_glyph_bank(self) -> None:
        rom = bytearray(0x800000)
        first = MODULE.ALT_GLYPH_TABLE_FILE + 3 * MODULE.GLYPH_STRIDE
        second = first + MODULE.ALT_GLYPH_BANK_BIAS
        rom[first] = 0x11
        rom[second] = 0x22
        self.assertEqual(MODULE.alt_table_tile(bytes(rom), 3, 0xE0)[0], 0x11)
        self.assertEqual(MODULE.alt_table_tile(bytes(rom), 3, 0xE1)[0], 0x22)

    def test_missing_alt_parameter_stays_a_control_marker(self) -> None:
        rom = bytes(range(256)) * (0x800000 // 256)
        record = {"tokens": [{"kind": "control-candidate", "value": 0xE1}]}
        image, controls = MODULE.render_record(rom, record, scale=1, skip_controls=False)
        self.assertEqual((image.width, image.height), (9, 8))
        self.assertEqual(controls, 1)


if __name__ == "__main__":
    unittest.main()
