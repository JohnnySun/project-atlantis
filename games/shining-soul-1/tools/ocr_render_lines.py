#!/usr/bin/env python3
"""Read-only recon (session 13): render OBJ-sentence corpus lines to
grayscale PNGs for OCR, extending render_string_glyphs.py's single-address
renderer into a batch tool that renders EVERY populated glyph slot in
categories 0-4 (not just the ones with a confirmed Unicode identity) --
this is the whole point of this session's task: the pixel data for the
~500 kanji entries already exists (session 10/11 solved the addressing
formula), we just don't know which Unicode character most of them are.

Deliberately does NOT depend on a palette dump / a running mgba instance
(advisor guidance, session 13): color is irrelevant to OCR. Any nonzero
4bpp pixel index is rendered as black ink on a white background --
Vision's recognizer does better on dark-on-light text than the game's
actual in-game palette (which is often light-on-dark), confirmed by this
session's calibration pass (see research note / README session-13
section).

Usage:
    python3 ocr_render_lines.py <rom> --addr 0x499b1a --out /tmp/x.png
    python3 ocr_render_lines.py <rom> --lines-file lines.tsv --out-dir /tmp/ocr_renders
        (lines.tsv: string_id \t hex_addr \t space-separated hex codes)

Read-only: only opens the ROM file for reading.
"""
import argparse
import os
import sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_string_glyphs import TABLES, GLYPH_STRIDE, decode_glyph_2x2, glyph_addr, read_codes  # noqa: E402

# Render geometry knobs, exposed as CLI flags so the calibration pass can
# sweep them without editing code (advisor guidance: settle these BEFORE
# mass-rendering ~2000 images).
DEFAULT_SCALE = 6
DEFAULT_PAD = 4

# Session 13 calibration (9 human-verified ground-truth sentences, see
# games/shining-soul-1/work/ocr/calib*/ + README session-13 section):
# swept scale in {4,5,6,7,8} x {normal, inverted} x {NEAREST, LANCZOS}
# resampling against known text via normalized edit distance. LANCZOS
# (smooth resample of the native 1x binary render, not a blocky NEAREST
# upscale of an already-large image) beat NEAREST by a wide margin in
# every configuration tried (best NEAREST ~0.26 avg ratio, best LANCZOS
# ~0.20); normal black-ink-on-white beat inverted white-on-black on
# average, though not by much and not for every sentence. scale 5/6/7
# were statistically indistinguishable (0.21-0.24); 6 was picked as the
# midpoint. This is NOT a claim that OCR is reliable at this ratio (0.2-
# 0.4 normalized edit distance is still a lot of character-level noise) -
# it is only the best of the configurations tried, which is why the
# alignment/voting step (ocr_align_vote.py) treats every OCR read as
# noisy evidence to be corroborated across many independent lines, never
# as ground truth for a single line.


def render_codes(rom, codes, scale=DEFAULT_SCALE, pad=DEFAULT_PAD, invert=False):
    n = len(codes)
    img = Image.new("L", (n * 16 + 2 * pad, 16 + 2 * pad), 255)
    px = img.load()
    for i, code in enumerate(codes):
        addr, cat, idx = glyph_addr(code)
        if addr is None or addr + GLYPH_STRIDE > len(rom):
            continue
        grid = decode_glyph_2x2(rom, addr)
        for y in range(16):
            for x in range(16):
                if grid[y][x] != 0:
                    px[pad + i * 16 + x, pad + y] = 0
    if invert:
        img = Image.eval(img, lambda v: 255 - v)
    # LANCZOS-resample the native-resolution (1x) render rather than
    # nearest-upscale a pre-enlarged image - see calibration note above.
    img = img.resize((img.size[0] * scale, img.size[1] * scale), Image.LANCZOS)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--addr", default=None, help="single hex ROM offset of a NUL-terminated code array")
    ap.add_argument("--out", default=None, help="output PNG path (single --addr mode)")
    ap.add_argument("--lines-file", default=None,
                     help="TSV: string_id\\taddr_hex\\tspace-separated-hex-codes, one per line")
    ap.add_argument("--out-dir", default=None, help="output dir (batch mode)")
    ap.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    ap.add_argument("--pad", type=int, default=DEFAULT_PAD)
    ap.add_argument("--invert", action="store_true", help="white ink on black instead of black on white")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()

    if args.addr:
        addr = int(args.addr, 0)
        codes = read_codes(rom, addr)
        img = render_codes(rom, codes, args.scale, args.pad, args.invert)
        img.save(args.out)
        print(f"wrote {args.out}  ({len(codes)} codes)")
        return

    if args.lines_file:
        os.makedirs(args.out_dir, exist_ok=True)
        n = 0
        with open(args.lines_file) as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                string_id, _addr_hex, codes_hex = line.split("\t")
                codes = [int(x, 16) for x in codes_hex.split()]
                if not codes:
                    continue
                img = render_codes(rom, codes, args.scale, args.pad, args.invert)
                safe_id = string_id.replace(":", "_").replace("/", "_")
                out_path = os.path.join(args.out_dir, f"{safe_id}.png")
                img.save(out_path)
                n += 1
        print(f"wrote {n} images to {args.out_dir}")
        return

    ap.error("must give either --addr/--out or --lines-file/--out-dir")


if __name__ == "__main__":
    main()
