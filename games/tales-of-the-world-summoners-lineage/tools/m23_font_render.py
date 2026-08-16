#!/usr/bin/env python3
"""Private-safe static renderer for A9PJ 16x12 font records.

The text renderer consumes a 24-byte record at ``0x08089E00 + unit*0x18``.
This utility can render a bounded candidate stream to a caller-supplied PGM
for local OCR or visual review.  It prints only image dimensions and a hash;
the image and any OCR result must remain in an ignored/private directory.

It is a renderer, not a decoder: code units are intentionally not converted
to Unicode and ``0xFF70`` is only treated as a line-break layout candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m20_text_record_probe import (
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_STRIDE,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
)


RENDERER_VERSION = "m23-font-render-20260816.v1"
GLYPH_WIDTH = 16
GLYPH_HEIGHT = 12
DEFAULT_SCALE = 4
DEFAULT_SPACING = 2
DEFAULT_MAX_UNITS = 0x400


def glyph_rows(data: bytes, code_unit: int) -> tuple[int, ...]:
    """Read one record as 12 little-endian 16-bit rows."""

    if not 0 <= code_unit <= 0xFFFF:
        raise ValueError("code unit must fit unsigned 16-bit width")
    offset = FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE
    record = data[offset:offset + FONT_RECORD_STRIDE]
    if len(record) != FONT_RECORD_STRIDE:
        raise ValueError("font record is outside the supplied ROM")
    return tuple(
        int.from_bytes(record[index:index + 2], "little")
        for index in range(0, FONT_RECORD_STRIDE, 2)
    )


def stream_units(data: bytes, target: int, *, max_units: int) -> list[int]:
    if not 0 <= target < len(data):
        raise ValueError("stream target is outside the supplied ROM")
    if max_units <= 0:
        raise ValueError("max_units must be positive")
    units: list[int] = []
    position = target
    while len(units) < max_units and position + 2 <= len(data):
        unit = int.from_bytes(data[position:position + 2], "little")
        position += 2
        units.append(unit)
        if unit == NULL_CODE_UNIT:
            break
    return units


def render_unit_rows(
    data: bytes,
    units: list[int],
    *,
    scale: int = DEFAULT_SCALE,
    spacing: int = DEFAULT_SPACING,
    bit_order: str = "msb",
) -> tuple[int, int, bytes]:
    """Render units to an 8-bit grayscale PGM payload without source labels."""

    if scale <= 0 or spacing < 0:
        raise ValueError("scale must be positive and spacing non-negative")
    if bit_order not in {"msb", "lsb"}:
        raise ValueError("bit_order must be msb or lsb")

    lines: list[list[tuple[int, tuple[int, ...]]]] = [[]]
    for unit in units:
        if unit == NULL_CODE_UNIT:
            break
        if unit == LINE_ADVANCE_CODE_UNIT:
            lines.append([])
            continue
        pixels = glyph_rows(data, unit)
        # Store a glyph marker and rasterize after line widths are known.
        lines[-1].append((unit, pixels))

    # The first loop uses a line list of glyph records; expand each line into
    # pixels without exposing the units in the output format.
    expanded_lines: list[list[int]] = []
    for line in lines:
        glyphs = line
        if not glyphs:
            expanded_lines.append([0])
            continue
        line_width = len(glyphs) * GLYPH_WIDTH + max(0, len(glyphs) - 1) * spacing
        pixels = [0] * (line_width * GLYPH_HEIGHT)
        for glyph_index, (_, glyph) in enumerate(glyphs):
            x0 = glyph_index * (GLYPH_WIDTH + spacing)
            for y, value in enumerate(glyph):
                for x in range(GLYPH_WIDTH):
                    bit = (15 - x) if bit_order == "msb" else x
                    if value & (1 << bit):
                        pixels[y * line_width + x0 + x] = 255
        expanded_lines.append(pixels)

    width = max(len(line) // GLYPH_HEIGHT for line in expanded_lines)
    height = len(expanded_lines) * GLYPH_HEIGHT
    image = bytearray(width * height)
    for line_index, line in enumerate(expanded_lines):
        line_width = len(line) // GLYPH_HEIGHT
        for y in range(GLYPH_HEIGHT):
            start = (line_index * GLYPH_HEIGHT + y) * width
            image[start:start + line_width] = bytes(line[y * line_width:(y + 1) * line_width])
    if scale != 1:
        scaled = bytearray((width * scale) * (height * scale))
        scaled_width = width * scale
        for y in range(height):
            source = image[y * width:(y + 1) * width]
            expanded = b"".join(bytes([value]) * scale for value in source)
            for dy in range(scale):
                start = (y * scale + dy) * scaled_width
                scaled[start:start + scaled_width] = expanded
        width *= scale
        height *= scale
        image = scaled
    return width, height, bytes(image)


def write_pgm(path: Path, width: int, height: int, pixels: bytes) -> str:
    payload = f"P5\n{width} {height}\n255\n".encode("ascii") + pixels
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def render_stream(
    data: bytes,
    target: int,
    output: Path,
    *,
    max_units: int = DEFAULT_MAX_UNITS,
    scale: int = DEFAULT_SCALE,
    spacing: int = DEFAULT_SPACING,
    bit_order: str = "msb",
) -> dict[str, object]:
    units = stream_units(data, target, max_units=max_units)
    width, height, pixels = render_unit_rows(
        data,
        units,
        scale=scale,
        spacing=spacing,
        bit_order=bit_order,
    )
    image_sha256 = write_pgm(output, width, height, pixels)
    return {
        "renderer_version": RENDERER_VERSION,
        "target_file_offset": f"0x{target:X}",
        "unit_count_including_terminator": len(units),
        "terminated_by_0000": NULL_CODE_UNIT in units,
        "line_advance_candidates": units.count(LINE_ADVANCE_CODE_UNIT),
        "width": width,
        "height": height,
        "scale": scale,
        "spacing": spacing,
        "bit_order": bit_order,
        "image_sha256": image_sha256,
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("target", type=lambda value: int(value, 0), help="file offset of a candidate stream")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=DEFAULT_MAX_UNITS)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    parser.add_argument("--spacing", type=int, default=DEFAULT_SPACING)
    parser.add_argument("--bit-order", choices=("msb", "lsb"), default="msb")
    args = parser.parse_args()
    receipt = render_stream(
        args.rom.read_bytes(),
        args.target,
        args.output,
        max_units=args.max_units,
        scale=args.scale,
        spacing=args.spacing,
        bit_order=args.bit_order,
    )
    print(json.dumps({"output": str(args.output), **receipt}, sort_keys=True))


if __name__ == "__main__":
    main()
