#!/usr/bin/env python3
"""Session 15 proof-of-concept: WRITE two new Chinese glyphs into the ROM's
category-4 OBJ-sentence font table and redirect one real, reachable string
(the job-select screen's "職業を選んでください" sentence, ROM 0x499b1a,
session 8's ground-truth string, re-confirmed every session since) to
render "道具" (the already-translated zh-TW target for "アイテム" in
translations/ui-strings-first-batch.jsonl) using those new glyphs instead.

This is the FIRST tool in this game's toolset that writes to the ROM file
itself - everything in tools/ before this session was read-only recon
(the only prior state-mutating tool, navigate_and_dump.py's key injection,
only ever wrote emulator registers/memory, never the ROM file).

Why category 4, index 40/41: session 11 found and this session independently
re-confirmed (see README "第十五輪偵察") that category 4's pixel table
(base 0x4913e4, same base+index*0x80 stride as the other four tables) is
essentially empty past index 39 - real corpus usage tops out around index
30, and this session's own zero-byte scan of all five tables' addressable
range (index 0-254, the max reachable via the code format's 8-bit
glyph_entry_index field) found ONLY ONE usable free run of any real size
across all five tables: category 4 indices 40-254 (215 slots), all-zero in
the base ROM. Every other table (categories 0/1/2/3) is >99% full across
its addressable range - this is the ONE place new glyphs can be inserted
without displacing anything that already exists. See "what a scalable
design needs" in the README for why this is a proof-of-concept insertion
point, not a scalable one (215 slots is nowhere near enough for a real
translation's full Chinese character set).

Glyph source: GNU Unifont (vendor/fonts/unifont/unifont-17.0.05.hex.gz),
the same font family already vendored into this repo for other games'
Chinese-glyph insertion work (core/fonts/extract-unifont-subset.rb).
Unifont's "wide" (16x16, 1bpp) glyph format for CJK codepoints is an exact
pixel-dimension match for this game's own glyph slot (128 bytes = 4 *
32-byte 4bpp 8x8 tiles = one 16x16px glyph, confirmed session 7-11,
extract_kanji_fonttable.py's decode_glyph_2x2()) - no scaling needed, only
a 1bpp->4bpp palette-index remap.

Palette-index choice: this session's own live capture (04_after_file1_a
in a fresh navigate_to_char_create.py dump) plus a frequency count over
the four already-decoded kanji tables found this game's own glyphs use a
two-tone style - palette index 2 (dark navy, ~58% of nonzero pixels,
almost always on outline/edge pixels) and index 1 (white, ~42%, almost
always interior-only pixels), with indices 12/13 (grays) appearing much
less often (likely a separate shading pass this POC does not attempt to
reproduce). Unifont's glyphs at this resolution are ~1px-wide strokes, so
the edge-detection heuristic below (a filled pixel with any 4-connected
background neighbor = "edge" = index 2, else "interior" = index 1) ends up
using almost entirely index 2 for both characters - close enough to the
game's own outline color to be legible, not a claim of matching its exact
shading algorithm.

Read-only up to the point of writing the output file: only ever opens the
base ROM for reading; the output path is always under roms/build/ (see
.gitignore's **/roms/ pattern - confirmed covered via `git check-ignore`).

Usage:
    python3 build_cn_glyph_poc.py \
        games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba \
        games/shining-soul-1/roms/build/ss1-cn-glyph-poc.gba
"""
import argparse
import gzip
import struct
import sys

CAT4_BASE = 0x4913e4
GLYPH_STRIDE = 0x80
TARGET_STRING_ADDR = 0x499b1a  # "職業を選んでください" - session 8 ground truth
# Space available before the next real string pool header (0x499b3c, the
# marker for "色を選んでください") - verified this session by reading raw
# ROM bytes: 22-byte original string + 12 bytes of trailing zero-fill.
TARGET_STRING_BUDGET = 34

# (codepoint, glyph slot index within category 4)
GLYPHS = [
    (0x9053, 41),  # 道
    (0x5177, 40),  # 具
]

UNIFONT_PATH = "vendor/fonts/unifont/unifont-17.0.05.hex.gz"


def load_unifont_glyph(codepoint, path=UNIFONT_PATH):
    target = "%04X" % codepoint
    with gzip.open(path, "rt", encoding="ascii") as f:
        for line in f:
            cp_hex, bitmap = line.strip().split(":", 1)
            if cp_hex.upper() == target:
                return bitmap
    raise KeyError("U+%04X not found in %s" % (codepoint, path))


def hex_to_bits(hexstr, width=16, height=16):
    nbytes = len(hexstr) // 2
    bytes_per_row = nbytes // height
    if bytes_per_row * height * 2 != len(hexstr):
        raise ValueError("unexpected unifont bitmap length %d (not a 16x16 wide glyph?)" % len(hexstr))
    rows = []
    for r in range(height):
        row_hex = hexstr[r * bytes_per_row * 2:(r + 1) * bytes_per_row * 2]
        val = int(row_hex, 16)
        bits = [(val >> (bytes_per_row * 8 - 1 - b)) & 1 for b in range(width)]
        rows.append(bits)
    return rows


def bits_to_shaded_grid(bits):
    """16x16 bool grid -> 16x16 palette-index grid (0=transparent, 2=edge,
    1=interior), see module docstring for the palette-index rationale."""
    h, w = len(bits), len(bits[0])
    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not bits[y][x]:
                continue
            edge = any(
                ny < 0 or ny >= h or nx < 0 or nx >= w or not bits[ny][nx]
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
            )
            grid[y][x] = 2 if edge else 1
    return grid


def grid_to_glyph_bytes(grid):
    """16x16 palette-index grid -> 128 bytes: 4 tiles (TL,TR,BL,BR order,
    matching extract_kanji_fonttable.py's decode_glyph_2x2), each an 8x8
    4bpp tile (row = 4 bytes, low nibble = left pixel of each byte-pair)."""
    def tile_bytes(gy0, gx0):
        out = bytearray(32)
        for row in range(8):
            for b in range(4):
                lo = grid[gy0 + row][gx0 + b * 2]
                hi = grid[gy0 + row][gx0 + b * 2 + 1]
                out[row * 4 + b] = (lo & 0xF) | ((hi & 0xF) << 4)
        return bytes(out)
    return tile_bytes(0, 0) + tile_bytes(0, 8) + tile_bytes(8, 0) + tile_bytes(8, 8)


def codepoint_to_glyph_bytes(codepoint):
    bitmap = load_unifont_glyph(codepoint)
    bits = hex_to_bits(bitmap)
    grid = bits_to_shaded_grid(bits)
    return grid_to_glyph_bytes(grid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("output")
    args = ap.parse_args()

    rom = bytearray(open(args.rom, "rb").read())

    print("Verifying target glyph slots (category 4, idx 40/41) are blank in the base ROM...")
    for codepoint, idx in GLYPHS:
        off = CAT4_BASE + idx * GLYPH_STRIDE
        chunk = rom[off:off + GLYPH_STRIDE]
        if any(chunk):
            sys.exit("ABORT: category 4 idx %d (off 0x%x) is NOT blank - refusing to overwrite "
                      "real data. Re-check games/shining-soul-1/README.md's free-slot scan." % (idx, off))
    print("  confirmed blank, OK.")

    print("Verifying target string at 0x%x still matches session 8's known "
          "'職業を選んでください' codes (drift guard)..." % TARGET_STRING_ADDR)
    expected_codes = [0x28a, 0x3eb, 0x2e, 0x30d, 0x2f, 0x3d, 0x9, 0x3a, 0xc, 0x3, 0x0]
    actual_codes = list(struct.unpack_from("<11H", rom, TARGET_STRING_ADDR))
    if actual_codes != expected_codes:
        sys.exit("ABORT: string at 0x%x does not match expected codes (got %r, want %r) - "
                  "ROM revision mismatch or research drift, refusing to patch."
                  % (TARGET_STRING_ADDR, actual_codes, expected_codes))
    print("  confirmed match, OK.")

    print("Writing new glyphs (source: GNU Unifont 17.0.05)...")
    for codepoint, idx in GLYPHS:
        off = CAT4_BASE + idx * GLYPH_STRIDE
        glyph_bytes = codepoint_to_glyph_bytes(codepoint)
        assert len(glyph_bytes) == GLYPH_STRIDE
        rom[off:off + GLYPH_STRIDE] = glyph_bytes
        print("  U+%04X -> category 4 idx %d (ROM 0x%x-0x%x)" % (codepoint, idx, off, off + GLYPH_STRIDE))

    print("Redirecting string at 0x%x to render \"道具\" using the new glyphs..." % TARGET_STRING_ADDR)
    # code = (category << 8) | (glyph_entry_index + 1); order = 道 then 具.
    new_codes = [0x0400 | (41 + 1), 0x0400 | (40 + 1), 0x0000]
    new_bytes = struct.pack("<3H", *new_codes)
    if len(new_bytes) > TARGET_STRING_BUDGET:
        sys.exit("ABORT: new string (%d bytes) exceeds verified available budget (%d bytes)"
                  % (len(new_bytes), TARGET_STRING_BUDGET))
    padded = new_bytes + b"\x00" * (TARGET_STRING_BUDGET - len(new_bytes))
    rom[TARGET_STRING_ADDR:TARGET_STRING_ADDR + TARGET_STRING_BUDGET] = padded
    print("  wrote codes %s + zero-fill to budget (%d bytes total, next pool header at 0x499b3c untouched)"
          % ([hex(c) for c in new_codes], TARGET_STRING_BUDGET))

    with open(args.output, "wb") as f:
        f.write(rom)
    print("wrote %s (%d bytes)" % (args.output, len(rom)))


if __name__ == "__main__":
    main()
