#!/usr/bin/env python3
"""Read-only recon: decode a raw VRAM dump (captured live via mGBA's GDB
stub, see gdbstub_client.py) into a viewable PPM image, using standard
GBA tile-mode conventions:
  - 4bpp tile = 8x8 px, 32 bytes, each byte = two 4-bit palette indices
    (low nibble = left pixel, high nibble = right pixel).
  - 8bpp tile = 8x8 px, 64 bytes, one byte per pixel.
  - BG palette: 256 entries (16 banks x 16 colors) at palette RAM
    0x000-0x1FF; each entry is 15-bit BGR packed little-endian in 2
    bytes (X BBBBB GGGGG RRRRR).
  - Screen (tilemap) entry (regular BG, 2 bytes): bits0-9 tile number,
    bit10 hflip, bit11 vflip, bits12-15 palette bank (4bpp only).

This is a generic renderer, not specific to any assumed text location -
it's meant for visually inspecting whatever is actually in VRAM at the
moment of capture, to distinguish font-glyph-shaped tiles (sparse,
outline-like, high tile-to-tile *variation* in a small used-color set)
from photographic/gradient graphics tiles.

Usage:
  python3 render_vram_tiles.py vram.bin pal.bin --charbase 0x0000 \
      --screenbase 0xe800 --bpp 4 --out /tmp/bg1.ppm

  python3 render_vram_tiles.py vram.bin pal.bin --charbase 0x0000 \
      --bpp 4 --grid --out /tmp/charblock0.ppm
      (--grid: dump the raw tile charblock as a grid, ignoring any tilemap)
"""
import argparse
import struct


def bgr15_to_rgb(v):
    r = (v & 0x1F) * 255 // 31
    g = ((v >> 5) & 0x1F) * 255 // 31
    b = ((v >> 10) & 0x1F) * 255 // 31
    return r, g, b


def load_palette(pal_bytes, count=256):
    vals = struct.unpack_from(f"<{count}H", pal_bytes, 0)
    return [bgr15_to_rgb(v) for v in vals]


def decode_tile_4bpp(data, off):
    """Return 8x8 list of palette indices (0-15) from 32 bytes."""
    px = []
    for row in range(8):
        rowpx = []
        for b in range(4):
            byte = data[off + row * 4 + b]
            rowpx.append(byte & 0xF)
            rowpx.append((byte >> 4) & 0xF)
        px.append(rowpx)
    return px


def decode_tile_8bpp(data, off):
    px = []
    for row in range(8):
        rowpx = list(data[off + row * 8: off + row * 8 + 8])
        px.append(rowpx)
    return px


def write_ppm(path, w, h, rgb_getter):
    with open(path, "wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode())
        for y in range(h):
            row = bytearray()
            for x in range(w):
                r, g, b = rgb_getter(x, y)
                row += bytes([r, g, b])
            f.write(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vram")
    ap.add_argument("palette")
    ap.add_argument("--charbase", type=lambda x: int(x, 0), default=0)
    ap.add_argument("--screenbase", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--bpp", type=int, choices=[4, 8], default=4)
    ap.add_argument("--palbank", type=int, default=0, help="palette bank for --grid mode (4bpp only)")
    ap.add_argument("--grid", action="store_true", help="render raw charblock as tile grid, ignore tilemap")
    ap.add_argument("--cols", type=int, default=32, help="columns for --grid mode")
    ap.add_argument("--map-w", type=int, default=32)
    ap.add_argument("--map-h", type=int, default=32)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    vram = open(args.vram, "rb").read()
    pal = load_palette(open(args.palette, "rb").read())

    tile_bytes = 32 if args.bpp == 4 else 64
    decode = decode_tile_4bpp if args.bpp == 4 else decode_tile_8bpp

    if args.grid:
        region = vram[args.charbase:]
        n_tiles = len(region) // tile_bytes
        cols = args.cols
        rows = (n_tiles + cols - 1) // cols
        w, h = cols * 8, rows * 8

        def rgb_getter(x, y):
            tx, ty = x // 8, y // 8
            tile_idx = ty * cols + tx
            if tile_idx >= n_tiles:
                return (32, 32, 32)
            px = decode(region, tile_idx * tile_bytes)
            idx = px[y % 8][x % 8]
            if idx == 0:
                return (0, 0, 0)
            pal_idx = (args.palbank * 16 + idx) if args.bpp == 4 else idx
            return pal[pal_idx % 256]

        write_ppm(args.out, w, h, rgb_getter)
        print(f"wrote {args.out}: {w}x{h} ({n_tiles} tiles, {rows} rows x {cols} cols)")
        return

    # tilemap mode
    sb = args.screenbase
    map_w, map_h = args.map_w, args.map_h
    entries = struct.unpack_from(f"<{map_w*map_h}H", vram, sb)
    w, h = map_w * 8, map_h * 8

    def rgb_getter(x, y):
        tx, ty = x // 8, y // 8
        entry = entries[ty * map_w + tx]
        tile_num = entry & 0x3FF
        hflip = bool(entry & 0x400)
        vflip = bool(entry & 0x800)
        palbank = (entry >> 12) & 0xF
        off = args.charbase + tile_num * tile_bytes
        if off + tile_bytes > len(vram):
            return (64, 0, 0)
        px = decode(vram, off)
        px_x, px_y = x % 8, y % 8
        if hflip:
            px_x = 7 - px_x
        if vflip:
            px_y = 7 - px_y
        idx = px[px_y][px_x]
        if idx == 0:
            return (0, 0, 0)
        pal_idx = (palbank * 16 + idx) if args.bpp == 4 else idx
        return pal[pal_idx % 256]

    write_ppm(args.out, w, h, rgb_getter)
    print(f"wrote {args.out}: {w}x{h} tilemap render")


if __name__ == "__main__":
    main()
