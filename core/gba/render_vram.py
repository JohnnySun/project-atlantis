#!/usr/bin/env python3
"""Render standard GBA BG tilemaps, raw tile grids, or Mode 3 framebuffers.

Inputs are raw VRAM and palette dumps captured from a running emulator.  All
offsets are relative to the start of VRAM/palette RAM, not GBA bus addresses.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path
from typing import Callable


Rgb = tuple[int, int, int]


def bgr15_to_rgb(value: int) -> Rgb:
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
    )


def load_palette(data: bytes, count: int = 256) -> list[Rgb]:
    if len(data) < count * 2:
        raise ValueError(f"palette needs {count * 2} bytes, got {len(data)}")
    values = struct.unpack_from(f"<{count}H", data)
    return [bgr15_to_rgb(value) for value in values]


def decode_tile_4bpp(data: bytes, offset: int) -> list[list[int]]:
    if offset < 0 or offset + 32 > len(data):
        raise ValueError(f"4bpp tile offset outside VRAM: 0x{offset:x}")
    pixels = []
    for row in range(8):
        output_row = []
        for byte in data[offset + row * 4:offset + row * 4 + 4]:
            output_row.extend((byte & 0xF, byte >> 4))
        pixels.append(output_row)
    return pixels


def decode_tile_8bpp(data: bytes, offset: int) -> list[list[int]]:
    if offset < 0 or offset + 64 > len(data):
        raise ValueError(f"8bpp tile offset outside VRAM: 0x{offset:x}")
    return [list(data[offset + row * 8:offset + row * 8 + 8]) for row in range(8)]


def write_ppm(path: Path, width: int, height: int, pixels: list[list[Rgb]]) -> None:
    if len(pixels) != height or any(len(row) != width for row in pixels):
        raise ValueError("pixel dimensions do not match output dimensions")
    with path.open("wb") as output:
        output.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        for row in pixels:
            output.write(bytes(channel for pixel in row for channel in pixel))


def render_tile_grid(
    vram: bytes,
    palette: list[Rgb],
    *,
    charbase: int = 0,
    bpp: int = 4,
    palette_bank: int = 0,
    columns: int = 32,
) -> list[list[Rgb]]:
    tile_bytes = 32 if bpp == 4 else 64
    decode: Callable[[bytes, int], list[list[int]]] = (
        decode_tile_4bpp if bpp == 4 else decode_tile_8bpp
    )
    tile_count = max(0, len(vram) - charbase) // tile_bytes
    rows = (tile_count + columns - 1) // columns
    canvas = [[(32, 32, 32) for _ in range(columns * 8)] for _ in range(rows * 8)]
    for tile_index in range(tile_count):
        tile = decode(vram, charbase + tile_index * tile_bytes)
        base_x = (tile_index % columns) * 8
        base_y = (tile_index // columns) * 8
        for y in range(8):
            for x in range(8):
                index = tile[y][x]
                palette_index = palette_bank * 16 + index if bpp == 4 else index
                canvas[base_y + y][base_x + x] = palette[palette_index % len(palette)]
    return canvas


def render_bg_tilemap(
    vram: bytes,
    palette: list[Rgb],
    *,
    charbase: int,
    screenbase: int,
    bpp: int = 4,
    map_width: int = 32,
    map_height: int = 32,
) -> list[list[Rgb]]:
    entry_count = map_width * map_height
    if screenbase < 0 or screenbase + entry_count * 2 > len(vram):
        raise ValueError("tilemap is outside VRAM dump")
    entries = struct.unpack_from(f"<{entry_count}H", vram, screenbase)
    tile_bytes = 32 if bpp == 4 else 64
    decode = decode_tile_4bpp if bpp == 4 else decode_tile_8bpp
    canvas = [[(0, 0, 0) for _ in range(map_width * 8)] for _ in range(map_height * 8)]
    for tile_y in range(map_height):
        for tile_x in range(map_width):
            entry = entries[tile_y * map_width + tile_x]
            tile_number = entry & 0x3FF
            horizontal_flip = bool(entry & 0x400)
            vertical_flip = bool(entry & 0x800)
            palette_bank = (entry >> 12) & 0xF
            offset = charbase + tile_number * tile_bytes
            if offset + tile_bytes > len(vram):
                continue
            tile = decode(vram, offset)
            for y in range(8):
                for x in range(8):
                    source_x = 7 - x if horizontal_flip else x
                    source_y = 7 - y if vertical_flip else y
                    index = tile[source_y][source_x]
                    palette_index = palette_bank * 16 + index if bpp == 4 else index
                    canvas[tile_y * 8 + y][tile_x * 8 + x] = palette[
                        palette_index % len(palette)
                    ]
    return canvas


def render_mode3(vram: bytes, width: int = 240, height: int = 160) -> list[list[Rgb]]:
    needed = width * height * 2
    if len(vram) < needed:
        raise ValueError(f"Mode 3 framebuffer needs {needed} bytes, got {len(vram)}")
    values = struct.unpack_from(f"<{width * height}H", vram)
    return [
        [bgr15_to_rgb(values[y * width + x]) for x in range(width)]
        for y in range(height)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vram", type=Path)
    parser.add_argument("palette", type=Path, nargs="?")
    parser.add_argument("--mode", choices=("tilemap", "grid", "mode3"), default="tilemap")
    parser.add_argument("--charbase", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--screenbase", type=lambda value: int(value, 0))
    parser.add_argument("--bpp", type=int, choices=(4, 8), default=4)
    parser.add_argument("--palette-bank", type=int, default=0)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--map-width", type=int, default=32)
    parser.add_argument("--map-height", type=int, default=32)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    vram = args.vram.read_bytes()
    if args.mode == "mode3":
        pixels = render_mode3(vram)
    else:
        if args.palette is None:
            parser.error("palette is required for tilemap/grid modes")
        palette = load_palette(args.palette.read_bytes())
        if args.mode == "grid":
            pixels = render_tile_grid(
                vram,
                palette,
                charbase=args.charbase,
                bpp=args.bpp,
                palette_bank=args.palette_bank,
                columns=args.columns,
            )
        else:
            if args.screenbase is None:
                parser.error("--screenbase is required for tilemap mode")
            pixels = render_bg_tilemap(
                vram,
                palette,
                charbase=args.charbase,
                screenbase=args.screenbase,
                bpp=args.bpp,
                map_width=args.map_width,
                map_height=args.map_height,
            )
    write_ppm(args.out, len(pixels[0]), len(pixels), pixels)
    print(f"wrote {args.out}: {len(pixels[0])}x{len(pixels)}")


if __name__ == "__main__":
    main()
