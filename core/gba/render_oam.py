#!/usr/bin/env python3
"""Composite standard GBA OBJ sprites from VRAM, palette RAM, and OAM dumps.

Both 1D and 2D OBJ tile mapping are supported for non-affine sprites.  Affine
sprites are skipped deliberately because their matrix transform needs a
different renderer; use --verbose to see skipped entries.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from render_vram import Rgb, bgr15_to_rgb, decode_tile_4bpp, decode_tile_8bpp, write_ppm


DIMENSIONS = {
    (0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8),
    (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4),
    (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8),
}


def load_obj_palette(data: bytes, offset: int = 0x200) -> list[Rgb]:
    if offset + 0x200 > len(data):
        raise ValueError(
            f"OBJ palette range 0x{offset:x}-0x{offset + 0x200:x} "
            f"outside {len(data)}-byte dump"
        )
    return [
        bgr15_to_rgb(value)
        for value in struct.unpack_from("<256H", data, offset)
    ]


def composite_oam(
    vram: bytes,
    palette: list[Rgb],
    oam: bytes,
    *,
    obj_base: int = 0x10000,
    mapping_1d: bool = True,
    width: int = 240,
    height: int = 160,
    verbose: bool = False,
) -> tuple[list[list[Rgb]], int]:
    if len(oam) < 0x400:
        raise ValueError(f"OAM dump needs 1024 bytes, got {len(oam)}")
    canvas = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]
    composited = 0

    # Draw back-to-front: larger OBJ priority first, then larger OAM index.
    # Lower priority values and lower OAM indices therefore land on top.
    indices = sorted(
        range(128),
        key=lambda item: ((struct.unpack_from("<H", oam, item * 8 + 4)[0] >> 10) & 3, item),
        reverse=True,
    )
    for index in indices:
        attr0, attr1, attr2, _affine = struct.unpack_from("<HHHH", oam, index * 8)
        y = attr0 & 0xFF
        if y >= 160:
            y -= 256
        affine = bool(attr0 & 0x0100)
        disabled = not affine and bool(attr0 & 0x0200)
        object_mode = (attr0 >> 10) & 0x3
        color_8bpp = bool(attr0 & 0x2000)
        shape = (attr0 >> 14) & 0x3
        size = (attr1 >> 14) & 0x3
        x = attr1 & 0x1FF
        if x >= 256:
            x -= 512

        if disabled or object_mode == 3 or (shape, size) not in DIMENSIONS:
            continue
        if affine:
            if verbose:
                print(f"sprite {index}: skipped affine OBJ")
            continue

        horizontal_flip = bool(attr1 & 0x1000)
        vertical_flip = bool(attr1 & 0x2000)
        tile_number = attr2 & 0x3FF
        palette_bank = (attr2 >> 12) & 0xF
        tile_width, tile_height = DIMENSIONS[(shape, size)]
        index_scale = 2 if color_8bpp else 1
        if color_8bpp:
            tile_number &= ~1
        decode = decode_tile_8bpp if color_8bpp else decode_tile_4bpp
        tile_bytes = 64 if color_8bpp else 32

        if verbose:
            mode = "1D" if mapping_1d else "2D"
            bpp = 8 if color_8bpp else 4
            print(
                f"sprite {index}: xy=({x},{y}) {tile_width}x{tile_height} tiles "
                f"tile={tile_number} bpp={bpp} mapping={mode} pal={palette_bank}"
            )
        sprite_drawn = False

        for tile_y in range(tile_height):
            for tile_x in range(tile_width):
                source_tile_x = tile_width - 1 - tile_x if horizontal_flip else tile_x
                source_tile_y = tile_height - 1 - tile_y if vertical_flip else tile_y
                if mapping_1d:
                    tile_offset_units = (
                        source_tile_y * tile_width + source_tile_x
                    ) * index_scale
                else:
                    tile_offset_units = source_tile_y * 32 + source_tile_x * index_scale
                offset = obj_base + (tile_number + tile_offset_units) * 32
                if offset + tile_bytes > len(vram):
                    continue
                tile = decode(vram, offset)
                for pixel_y in range(8):
                    for pixel_x in range(8):
                        palette_index = tile[pixel_y][pixel_x]
                        if palette_index == 0:
                            continue
                        if not color_8bpp:
                            palette_index += palette_bank * 16
                        destination_x = x + tile_x * 8 + pixel_x
                        destination_y = y + tile_y * 8 + pixel_y
                        if 0 <= destination_x < width and 0 <= destination_y < height:
                            canvas[destination_y][destination_x] = palette[
                                palette_index % len(palette)
                            ]
                            sprite_drawn = True
        if sprite_drawn:
            composited += 1
    return canvas, composited


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vram", type=Path)
    parser.add_argument("palette", type=Path)
    parser.add_argument("oam", type=Path)
    parser.add_argument("--obj-base", type=lambda value: int(value, 0), default=0x10000)
    parser.add_argument(
        "--palette-offset",
        type=lambda value: int(value, 0),
        default=0x200,
        help="0x200 for a full 1 KiB palette dump; 0 for an OBJ-only dump",
    )
    parser.add_argument("--mapping", choices=("1d", "2d"), default="1d")
    parser.add_argument("--width", type=int, default=240)
    parser.add_argument("--height", type=int, default=160)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    pixels, count = composite_oam(
        args.vram.read_bytes(),
        load_obj_palette(args.palette.read_bytes(), args.palette_offset),
        args.oam.read_bytes(),
        obj_base=args.obj_base,
        mapping_1d=args.mapping == "1d",
        width=args.width,
        height=args.height,
        verbose=args.verbose,
    )
    write_ppm(args.out, args.width, args.height, pixels)
    print(f"wrote {args.out}: {args.width}x{args.height}, {count} sprites")


if __name__ == "__main__":
    main()
