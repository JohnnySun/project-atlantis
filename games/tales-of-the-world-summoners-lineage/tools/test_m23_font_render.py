import sys
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from m23_font_render import (  # noqa: E402
    GLYPH_HEIGHT,
    GLYPH_WIDTH,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    render_unit_rows,
    stream_units,
)


class M23FontRenderTests(unittest.TestCase):
    def test_stream_stops_at_terminator(self) -> None:
        data = b"\x5e\x00\x70\xff\x00\x00\x66\x00"
        self.assertEqual(stream_units(data, 0, max_units=10), [0x005E, LINE_ADVANCE_CODE_UNIT, NULL_CODE_UNIT])

    def test_renderer_dimensions_and_bit_order(self) -> None:
        data = bytearray(0x89E00 + 0x18 * 0x5E + 0x18)
        offset = 0x89E00 + 0x18 * 0x5E
        data[offset:offset + 2] = (1 << 15).to_bytes(2, "little")
        width, height, pixels = render_unit_rows(
            bytes(data),
            [0x005E, NULL_CODE_UNIT],
            scale=1,
            spacing=0,
            bit_order="msb",
        )
        self.assertEqual((width, height), (GLYPH_WIDTH, GLYPH_HEIGHT))
        self.assertEqual(pixels[0], 255)
        self.assertEqual(sum(pixels), 255)

    def test_line_advance_creates_second_line(self) -> None:
        data = bytearray(0x89E00 + 0x18 * 0x5E + 0x18)
        offset = 0x89E00 + 0x18 * 0x5E
        data[offset:offset + 2] = (1 << 15).to_bytes(2, "little")
        width, height, _ = render_unit_rows(
            bytes(data),
            [0x005E, LINE_ADVANCE_CODE_UNIT, 0x005E, NULL_CODE_UNIT],
            scale=1,
            spacing=0,
        )
        self.assertEqual((width, height), (GLYPH_WIDTH, GLYPH_HEIGHT * 2))


if __name__ == "__main__":
    unittest.main()
