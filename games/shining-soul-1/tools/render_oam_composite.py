#!/usr/bin/env python3
"""Read-only recon: composite OBJ (sprite) VRAM tiles into a single
screen-sized image using the *actual* OAM attribute table (position,
shape/size, tile index, h/v flip, palette bank) rather than a naive
sequential tile grid.

This exists because a plain tile-grid dump of OBJ VRAM (see
render_vram_tiles.py --grid) scrambles any text/UI rendered via sprites -
each on-screen glyph is usually made of several tiles placed according to
OAM, not laid out contiguously in VRAM in reading order. The prior
session's README documents hitting exactly this trap when first decoding
the title screen's "PUSH START" text; this script is the fix that made a
correct composite possible for that screen and, in session 3, for the
mode-select screen ("シングルプレイモード" / "マルチプレイモード").

Usage:
    python3 render_oam_composite.py vram.bin palette.bin oam.bin --out out.ppm

Inputs are raw dumps as read live via gdbstub_client.py, e.g.:
    vram = c.read_mem(0x06000000, 0x18000)
    palette = c.read_mem(0x05000000, 0x400)
    oam = c.read_mem(0x07000000, 0x400)

Assumptions (GBA standard, OBJ 1D mapping only - the only mapping mode
seen so far in this game; if DISPCNT bit 6 is 0 this script's tile-index
math for multi-tile sprites will be wrong and needs the 2D-mapping
formula instead):
  - OBJ tile characters start at VRAM 0x10000 (charblock 4), 4bpp, 32
    bytes/tile - override with --obj-base / --bpp if a game uses 8bpp
    sprites.
  - "Active" sprite filter is a heuristic (y < 160 and OBJ mode != 2/
    "disabled affine"), matching what worked for this game's title and
    menu screens. A game with sprites parked off-screen via y >= 160 by
    design, or that actually uses y=160..255 (wrapping) on-screen, will
    need a different filter - inspect the raw OAM dump if the composite
    looks wrong or empty.
"""
import argparse
import struct

DIMS = {
    (0, 0): (1, 1), (0, 1): (2, 2), (0, 2): (4, 4), (0, 3): (8, 8),
    (1, 0): (2, 1), (1, 1): (4, 1), (1, 2): (4, 2), (1, 3): (8, 4),
    (2, 0): (1, 2), (2, 1): (1, 4), (2, 2): (2, 4), (2, 3): (4, 8),
}


def bgr15_to_rgb(v):
    r = (v & 0x1F) * 255 // 31
    g = ((v >> 5) & 0x1F) * 255 // 31
    b = ((v >> 10) & 0x1F) * 255 // 31
    return r, g, b


def decode_tile_4bpp(data, off):
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
    return [list(data[off + row * 8: off + row * 8 + 8]) for row in range(8)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vram")
    ap.add_argument("palette")
    ap.add_argument("oam")
    ap.add_argument("--obj-base", type=lambda x: int(x, 0), default=0x10000)
    ap.add_argument("--bpp", type=int, choices=[4, 8], default=4)
    ap.add_argument("--width", type=int, default=240)
    ap.add_argument("--height", type=int, default=160)
    ap.add_argument("--max-y", type=int, default=160,
                     help="active-sprite heuristic: only composite entries with y < this")
    ap.add_argument("--out", required=True)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    vram = open(args.vram, "rb").read()
    palraw = open(args.palette, "rb").read()
    oam = open(args.oam, "rb").read()

    pal_vals = struct.unpack_from("<256H", palraw, 0)
    pal = [bgr15_to_rgb(v) for v in pal_vals]

    tile_bytes = 32 if args.bpp == 4 else 64
    decode = decode_tile_4bpp if args.bpp == 4 else decode_tile_8bpp

    canvas = [[(0, 0, 0) for _ in range(args.width)] for _ in range(args.height)]

    n_composited = 0
    for i in range(128):
        a0, a1, a2, _pad = struct.unpack_from("<HHHH", oam, i * 8)
        y = a0 & 0xFF
        shape = (a0 >> 14) & 3
        obj_mode = (a0 >> 8) & 3  # 2 = affine-disabled (sprite off)
        size = (a1 >> 14) & 3
        x = a1 & 0x1FF
        if x >= 256:
            x -= 512
        hflip = bool(a1 & 0x1000)
        vflip = bool(a1 & 0x2000)
        tile = a2 & 0x3FF
        palbank = (a2 >> 12) & 0xF

        if not (y < args.max_y and obj_mode != 2):
            continue

        tw, th = DIMS.get((shape, size), (1, 1))
        if args.verbose:
            print(f"sprite {i}: xy=({x},{y}) shape={shape} size={size} "
                  f"-> {tw}x{th} tiles, tile#{tile} palbank={palbank}")
        n_composited += 1

        for ty in range(th):
            for tx in range(tw):
                # OBJ 1D mapping: tiles for one sprite are contiguous,
                # row-major.
                src_tx, src_ty = (tw - 1 - tx if hflip else tx,
                                   th - 1 - ty if vflip else ty)
                tnum = tile + src_ty * tw + src_tx
                off = args.obj_base + tnum * tile_bytes
                if off + tile_bytes > len(vram):
                    continue
                px = decode(vram, off)
                for py in range(8):
                    for pxi in range(8):
                        sx = 7 - pxi if hflip else pxi
                        sy = 7 - py if vflip else py
                        idx = px[sy][sx]
                        if idx == 0:
                            continue
                        cx = x + tx * 8 + pxi
                        cy = y + ty * 8 + py
                        if 0 <= cx < args.width and 0 <= cy < args.height:
                            pal_idx = (palbank * 16 + idx) if args.bpp == 4 else idx
                            canvas[cy][cx] = pal[pal_idx % 256]

    with open(args.out, "wb") as f:
        f.write(f"P6\n{args.width} {args.height}\n255\n".encode())
        for row in canvas:
            for r, g, b in row:
                f.write(bytes([r, g, b]))
    print(f"wrote {args.out}: {args.width}x{args.height}, "
          f"{n_composited} sprites composited")


if __name__ == "__main__":
    main()
