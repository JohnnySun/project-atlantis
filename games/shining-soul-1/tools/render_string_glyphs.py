#!/usr/bin/env python3
"""Read-only recon (session 10): render a full OBJ sentence (a
NUL-terminated 16-bit code array, per session 8's string format) as an
image, using every glyph table confirmed so far - the session-7 kana
master table (category 0) plus the three kanji pools session 10 found
(categories 1/2/3). Categories with no confirmed table (4-15) render as
a blank 16x16 cell so gaps are visually obvious rather than silently
wrong.

This is the tool session 10 used to sanity-check the newly-confirmed
kanji tables against real dialogue-pool corpus data (not just the two
already-known job-select/color-select sentences): pick an address from
scan_string_pools.py / extract_string_pool.py output and render it here
to see whether it reads as plausible Japanese. See
research/obj-sentence-kanji-categories.md "corpus validation" for the
sentences checked this way (e.g. 0x499b5e -> "名前を入力してください",
0x499aa2 -> "それは引き取れません", 0x499e1a -> "ゲームを...すると
セーブされます" with one still-unconfirmed category-4 gap).

Usage:
    python3 render_string_glyphs.py <rom> --addr 0x499b5e --out sent.png \
        --palette <dump-dir>/04_after_file1_a.pal.bin --palbank 15

Read-only: only opens the ROM file and an optional palette dump for
reading.
"""
import argparse
import struct
from PIL import Image

GLYPH_STRIDE = 0x80

# category -> (base, has_extra_offset). Category 0's glyph_entry_index
# needs an extra -1 to become the master table's char_idx (session 8
# finding); categories 1/2/3 index their tables directly by
# glyph_entry_index (session 10 finding, confirmed via exact-fit
# 2-point address checks - see extract_kanji_fonttable.py docstring).
TABLES = {
    0: (0x46abe4, True),
    1: (0x474584, False),
    2: (0x47dfa4, False),
    3: (0x4879c4, False),
    # session 11: base found via two independent zero-free-parameter methods -
    # (a) live IWRAM category-dispatch table (0x030065f0 + category*4) plus the
    #     same "+0x1820" struct-to-pixel-table offset validated on categories
    #     1/2/3, (b) live enqueue-source-pointer capture for two real corpus
    #     glyphs (idx 16 and 18), both exactly matching 0x4913e4 + idx*0x80.
    # See research/obj-sentence-category4-and-dispatch-table.md.
    4: (0x4913e4, False),
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
    tiles = [decode_tile_4bpp(data, off + i * 32) for i in range(4)]
    grid = [[0] * 16 for _ in range(16)]
    for ty in range(2):
        for tx in range(2):
            t = tiles[ty * 2 + tx]
            for y in range(8):
                for x in range(8):
                    grid[ty * 8 + y][tx * 8 + x] = t[y][x]
    return grid


def glyph_addr(code):
    category = (code >> 8) & 0xF
    glyph_entry_index = (code & 0xFF) - 1
    entry = TABLES.get(category)
    if entry is None:
        return None, category, glyph_entry_index
    base, extra_offset = entry
    idx = glyph_entry_index - 1 if extra_offset else glyph_entry_index
    return base + idx * GLYPH_STRIDE, category, idx


def read_codes(rom, addr):
    codes = []
    p = addr
    while True:
        c = rom[p] | (rom[p + 1] << 8)
        p += 2
        if c == 0:
            break
        codes.append(c)
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--addr", type=lambda x: int(x, 0), required=True,
                     help="ROM file offset of the NUL-terminated code array")
    ap.add_argument("--out", required=True)
    ap.add_argument("--palette", default=None)
    ap.add_argument("--palbank", type=int, default=15)
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    codes = read_codes(rom, args.addr)
    print("codes:", [hex(c) for c in codes])
    decoded = [((c >> 8) & 0xF, (c & 0xFF) - 1) for c in codes]
    print("decoded (category, glyph_entry_index):", decoded)
    unresolved = sorted(set(cat for cat, _ in decoded if cat not in TABLES))
    if unresolved:
        print(f"  (categories with no confirmed table, rendered blank: {unresolved})")

    if args.palette:
        pal_vals = struct.unpack_from("<256H", open(args.palette, "rb").read(), 0)
        pal_full = [bgr15_to_rgb(v) for v in pal_vals]
        pal = pal_full[args.palbank * 16:(args.palbank + 1) * 16]
    else:
        pal = [(i * 17, i * 17, i * 17) for i in range(16)]

    n = len(codes)
    img = Image.new("RGB", (n * 16, 16), (30, 0, 30))
    px_out = img.load()
    for i, code in enumerate(codes):
        addr, cat, idx = glyph_addr(code)
        if addr is None or addr + GLYPH_STRIDE > len(rom):
            continue
        grid = decode_glyph_2x2(rom, addr)
        for y in range(16):
            for x in range(16):
                v = grid[y][x]
                if v == 0:
                    continue
                px_out[i * 16 + x, y] = pal[v % len(pal)]
    img = img.resize((img.size[0] * 4, img.size[1] * 4), Image.NEAREST)
    img.save(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
