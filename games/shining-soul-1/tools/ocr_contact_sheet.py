#!/usr/bin/env python3
"""Read-only recon (session 13): build a visual spot-check contact sheet
for OCR-derived candidate kanji identities before accepting any of them.

Advisor guidance (session 13): vote count alone does not protect against
a SYSTEMATIC OCR misread (Vision consistently reading one real kanji as a
different, similar-looking one would produce many internally-consistent
but wrong votes). The only real check is eyeballing the actual ROM pixel
glyph next to a normal font's rendering of the claimed candidate
character. This script does that: for each row of a votes.tsv file
(ocr_align_vote.py output) meeting a caller-supplied acceptance bar, draw
[ROM glyph pixels] [system-font glyph for the top candidate] [label] side
by side.

Uses Hiragino Sans GB (bundled with macOS) as the comparison font - it is
a Simplified Chinese font, not Japanese, but at 16x16-ish comparison
scale common Han characters are shape-identical across the two scripts;
this is only for a human/agent shape sanity check, not a claim that the
font is otherwise appropriate for this project.

Usage:
    python3 ocr_contact_sheet.py <rom> --votes votes.tsv --out sheet.png \
        [--min-votes 3] [--min-ratio 0.6]

Read-only: only opens the ROM file and system font file for reading.
"""
import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_string_glyphs import TABLES, GLYPH_STRIDE, decode_glyph_2x2  # noqa: E402

FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def glyph_bitmap(rom, category, idx):
    entry = TABLES.get(category)
    if entry is None:
        return None
    base, _extra = entry
    addr = base + idx * GLYPH_STRIDE
    if addr < 0 or addr + GLYPH_STRIDE > len(rom):
        return None
    return decode_glyph_2x2(rom, addr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--votes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-votes", type=int, default=3)
    ap.add_argument("--min-ratio", type=float, default=0.6)
    ap.add_argument("--scale", type=int, default=6)
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()

    rows = []
    with open(args.votes, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            parts = line.rstrip("\n").split("\t")
            category, idx, total, top_char, top_count = parts[0:5]
            category, idx, total, top_count = int(category), int(idx), int(total), int(top_count)
            if total < args.min_votes:
                continue
            ratio = top_count / total
            if ratio < args.min_ratio:
                continue
            rows.append((category, idx, total, top_char, top_count, ratio))

    rows.sort(key=lambda r: (-r[4], r[0], r[1]))

    font = ImageFont.truetype(FONT_PATH, 15)
    scale = args.scale
    cell_w, cell_h = 16 * scale + 220, 16 * scale + 8
    img = Image.new("RGB", (cell_w, cell_h * len(rows) + 10), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for i, (category, idx, total, top_char, top_count, ratio) in enumerate(rows):
        y0 = i * cell_h
        grid = glyph_bitmap(rom, category, idx)
        if grid is not None:
            for py in range(16):
                for px in range(16):
                    if grid[py][px] != 0:
                        draw.rectangle(
                            [px * scale, y0 + py * scale,
                             px * scale + scale - 1, y0 + py * scale + scale - 1],
                            fill=(0, 0, 0),
                        )
        fx = 16 * scale + 10
        draw.text((fx, y0), top_char, font=font, fill=(180, 0, 0))
        draw.text((fx + 40, y0 + 2),
                   f"cat{category} idx{idx}  {top_char}  {top_count}/{total}={ratio:.0%}",
                   fill=(0, 0, 0))
        draw.line([(0, y0 + cell_h), (cell_w, y0 + cell_h)], fill=(200, 200, 200))

    img.save(args.out)
    print(f"wrote {args.out}: {len(rows)} rows")


if __name__ == "__main__":
    main()
