#!/usr/bin/env python3
"""Read-only recon (session 10): extract/render any of the OBJ-sentence
kanji glyph tables this session confirmed, generalizing session 7's
extract_obj_kana_fonttable.py (which only knew about the category-0 kana
table) to the three newly-found kanji pools.

Background: session 8 decoded the OBJ sentence string format as a
NUL-terminated array of 16-bit codes, each splitting into
    category          = (code >> 8) & 0xF
    glyph_entry_index  = (code & 0xFF) - 1
Category 0 (kana) was known to index the session-7 master table at
ROM 0x46abe4 with an extra -1 offset (char_idx = glyph_entry_index - 1).
Categories 2/3 were known to be "some kind of kanji", base unresolved;
categories 1, 4-15 were not even confirmed to be glyph pools at all
(session 9 only observed that the codes exist in real data).

Session 10 confirmed THREE kanji tables, all using the exact same
`base + glyph_entry_index * 0x80` formula as the category-0 table (no
extra -1 offset - that offset is specific to category 0's own encoding
convention), each verified with 2 independent, exactly-fitting data
points (zero free parameters once stride 0x80 is fixed):

    category 1: base 0x474584   (剣=idx7, 士=idx8 - the job-select
                                  screen's "剣士" label, both glyphs
                                  independently found via live VRAM
                                  capture + exact ROM byte search, then
                                  their string code looked up via a
                                  breakpoint on the string-walk function
                                  0x0800e8bc)
    category 2: base 0x47dfa4   (職=idx137 - session 5/6's known address;
                                  色=idx138 - session 10 found the same
                                  way as 剣/士 above)
    category 3: base 0x4879c4   (業=idx234, 選=idx12 - both session 5/6
                                  known addresses, formula simply not
                                  computed until this session)

See research/obj-sentence-kanji-categories.md for the full derivation,
validation (6 real corpus sentences rendered and confirmed to read as
grammatical Japanese), and remaining open categories (4, 6-15 still
unsolved; category 5 seen too rarely in the corpus to say anything).

Usage:
    python3 extract_kanji_fonttable.py <rom> --category 1 --count 128 \
        --out-png cat1.png --palette <dump>/04_after_file1_a.pal.bin --palbank 15

    python3 extract_kanji_fonttable.py <rom> --base 0x47dfa4 --count 160 \
        --out-png cat2.png --palette ... --palbank 15

Read-only: only opens the ROM file for reading (plus an optional palette
dump file, also read-only).
"""
import argparse
import struct
from PIL import Image, ImageDraw

GLYPH_STRIDE = 0x80  # 128 bytes = 4 * 32-byte 4bpp tiles = one 16x16px glyph

# category -> confirmed table base (session 10; category 0 kept for
# reference even though this script is mainly for the kanji categories).
CATEGORY_BASES = {
    0: 0x46abe4,   # kana master table (session 7); NOTE extra -1 offset
                   # applies to category 0's glyph_entry_index -> char_idx,
                   # NOT reproduced here - this script indexes tables
                   # directly by glyph_entry_index for categories 1/2/3.
    1: 0x474584,   # session 10: 剣=idx7, 士=idx8
    2: 0x47dfa4,   # session 10: 職=idx137, 色=idx138
    3: 0x4879c4,   # session 10: 業=idx234, 選=idx12
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


def decode_glyph_2x2(data, off):
    """128 bytes -> 16x16 pixel index grid, OBJ 1D-mapping tile order
    (tile+0 top-left, tile+1 top-right, tile+2 bottom-left, tile+3
    bottom-right), same layout as extract_obj_kana_fonttable.py /
    render_oam_composite.py use for shape=0,size=1 sprites."""
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
    ap.add_argument("--category", type=int, choices=sorted(CATEGORY_BASES),
                     help="use this category's confirmed base (see CATEGORY_BASES)")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=None,
                     help="explicit ROM base offset (overrides --category)")
    ap.add_argument("--count", type=int, default=128,
                     help="how many glyph slots to extract")
    ap.add_argument("--out-bin", default=None)
    ap.add_argument("--out-png", default=None)
    ap.add_argument("--palette", default=None)
    ap.add_argument("--palbank", type=int, default=15)
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    if args.base is not None:
        base = args.base
    elif args.category is not None:
        base = CATEGORY_BASES[args.category]
    else:
        ap.error("must give either --category or --base")

    rom = open(args.rom, "rb").read()
    chunk = rom[base: base + args.count * GLYPH_STRIDE]

    if args.out_bin:
        with open(args.out_bin, "wb") as f:
            f.write(chunk)
        print(f"wrote {args.out_bin}: {len(chunk)} bytes ({args.count} glyphs)")

    nonzero = [i for i in range(len(chunk) // GLYPH_STRIDE)
               if any(chunk[i * GLYPH_STRIDE:(i + 1) * GLYPH_STRIDE])]
    print(f"base=0x{base:x}  non-zero glyph slots: {len(nonzero)} of {args.count}, "
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
        big = img.resize((img.size[0] * scale, img.size[1] * scale), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        for i in range(n):
            gx, gy = (i % cols) * 16, (i // cols) * 16
            draw.text((gx * scale, gy * scale), str(i), fill=(255, 0, 255))
        big.save(args.out_png)
        print(f"wrote {args.out_png}: {big.size}")


if __name__ == "__main__":
    main()
