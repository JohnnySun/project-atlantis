#!/usr/bin/env python3
"""Read-only recon (session 7): extract and render the THIRD, independent
glyph table this session located - an OBJ (sprite) hiragana table used to
render full sentences (e.g. job-select's "職業を選んでください"), as
opposed to the two already-confirmed BG tile tables (0x1398e8, 0x1316e8)
or the OBJ title-screen katakana/Latin table (0x62AA44-0x62B8E4).

Session 6 found, by exact byte-search of live OBJ VRAM against the ROM,
that 7 of the hiragana in that sentence landed in ROM 0x46A000-0x46E000
with some address deltas that were multiples of 128 bytes, but did not
solve the addressing formula. This session found it algebraically: each
glyph is a 2x2 OBJ-tile block (128 bytes = 4 * 32-byte 4bpp tiles,
matching the on-screen 16x16px glyph size), and the table is a flat
array indexed by standard gojuon order (same character ordering as the
name-entry screen's hiragana keyboard, session 5), starting at ROM file
offset 0x46abe4 (index 0 = "あ"), stride 0x80 bytes/glyph:

    glyph_rom_offset(kana_index) = 0x46abe4 + kana_index * 0x80

All 7 of session 6's observed addresses fit this exactly with zero
free parameters once the base is fixed (を=44, ん=45, だ=56, で=59,
く=7, さ=10, い=1 - see games/shining-soul-1/research/
name-entry-hiragana-codepage.md for the standard-order index table).
This script extracts N glyphs from that base and renders them as a
grid for visual confirmation - if the grid reads as the gojuon sequence
in order, the table (and by extension this addressing formula, i.e. a
real character-code -> glyph-address mapping rather than a per-screen
bespoke blit) is confirmed statically, no emulator needed.

Usage:
    python3 extract_obj_kana_fonttable.py <rom> --out-png kana.png \
        --palette /tmp/ss1_trace1/04_after_file1_a.pal.bin --palbank 15
"""
import argparse
import struct
from PIL import Image, ImageDraw

GLYPH_STRIDE = 0x80  # 128 bytes = 4 tiles = one 16x16px glyph
DEFAULT_BASE = 0x46abe4

# Standard gojuon ordering used by the name-entry keyboard (session 5) -
# for annotating the rendered grid only, not needed for extraction itself.
GOJUON = list("あいうえおかきくけこさしすせそたちつてとなにぬねの"
              "はひふへほまみむめもやゆよらりるれろわをん"
              "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ")


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


def decode_glyph_2x2(data, off):
    """128 bytes -> 16x16 pixel index grid, OBJ 1D-mapping tile order
    (tile+0 top-left, tile+1 top-right, tile+2 bottom-left, tile+3
    bottom-right - same layout render_oam_composite.py uses for
    shape=0,size=1 sprites)."""
    tiles = [decode_tile_4bpp(data, off + i * 32) for i in range(4)]
    grid = [[0] * 16 for _ in range(16)]
    for ty in range(2):
        for tx in range(2):
            t = tiles[ty * 2 + tx]
            for y in range(8):
                for x in range(8):
                    grid[ty * 8 + y][tx * 8 + x] = t[y][x]
    return grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=DEFAULT_BASE)
    ap.add_argument("--count", type=int, default=90,
                     help="how many glyph slots to extract (71 known + margin to see the boundary)")
    ap.add_argument("--out-bin", default=None)
    ap.add_argument("--out-png", default=None)
    ap.add_argument("--palette", default=None)
    ap.add_argument("--palbank", type=int, default=15)
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    chunk = rom[args.base: args.base + args.count * GLYPH_STRIDE]

    if args.out_bin:
        with open(args.out_bin, "wb") as f:
            f.write(chunk)
        print(f"wrote {args.out_bin}: {len(chunk)} bytes ({args.count} glyphs)")

    nonzero = [i for i in range(len(chunk) // GLYPH_STRIDE)
               if any(chunk[i*GLYPH_STRIDE:(i+1)*GLYPH_STRIDE])]
    print(f"non-zero glyph slots: {len(nonzero)} of {args.count}, "
          f"max index: {max(nonzero) if nonzero else -1}")

    if args.out_png:
        if args.palette:
            pal_vals = struct.unpack_from("<256H", open(args.palette, "rb").read(), 0)
            pal_full = [bgr15_to_rgb(v) for v in pal_vals]
            pal = pal_full[args.palbank * 16:(args.palbank + 1) * 16]
        else:
            pal = [(i * 17, i * 17, i * 17) for i in range(16)]

        cols = args.cols
        n = args.count
        rows = (n + cols - 1) // cols
        img = Image.new("RGB", (cols * 16, rows * 16), (0, 0, 0))
        px_out = img.load()
        for i in range(n):
            off = i * GLYPH_STRIDE
            if off + GLYPH_STRIDE > len(chunk):
                break
            grid = decode_glyph_2x2(chunk, off)
            gx, gy = (i % cols) * 16, (i // cols) * 16
            for y in range(16):
                for x in range(16):
                    idx = grid[y][x]
                    if idx == 0:
                        continue
                    px_out[gx + x, gy + y] = pal[idx % len(pal)]

        scale = args.scale
        big = img.resize((img.size[0]*scale, img.size[1]*scale), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        for i in range(n):
            gx, gy = (i % cols) * 16, (i // cols) * 16
            label = str(i)
            if i < len(GOJUON):
                label += f":{GOJUON[i]}"
            draw.text((gx*scale, gy*scale), label, fill=(255, 0, 255))
        big.save(args.out_png)
        print(f"wrote {args.out_png}: {big.size}")


if __name__ == "__main__":
    main()
