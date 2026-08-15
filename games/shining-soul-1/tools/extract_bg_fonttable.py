#!/usr/bin/env python3
"""Read-only recon: extract and render the BG glyph/font table this
session (4) located in the ROM, for visual inspection and for computing
which ROM bytes back a given VRAM BG tile-index.

Session 4 finding (see README "第四輪偵察"): the save-file-select
screen's BG2 (screenbase 0xf000, stat labels) and BG3 (screenbase
0xf800, FILE slots) both use charbase 0x0, and ALL 1024 possible 4bpp
BG tile-numbers (the full 10-bit range a tilemap entry can address) are
bulk-copied byte-for-byte from ROM file offset 0x1398e8 into VRAM
0x06000000 - confirmed by an exhaustive per-tile comparison between a
live VRAM capture and this ROM range (see navigate_and_dump.py for how
to capture 03_save_select.vram.bin). Only tiles 0-227 in that table
contain non-zero (visibly drawn) glyph data; 228-1023 are zero padding
in this ROM copy. Because the tilemap's tile-number field indexes
straight into this table, the tile-index itself already functions as
the "character code" for BG-rendered text - there is no separate
indirect lookup layer to find on this path.

This table is a SEPARATE, differently-located font asset from the
earlier-confirmed OBJ font (ROM 0x62AA44-0x62B8E4, used by the title/
mode-select screen's sprite-rendered text) - do not conflate the two.

Usage:
    python3 extract_bg_fonttable.py <rom> --out-bin table.bin \
        --out-png table_annotated.png [--base 0x1398e8] [--count 1024]

Verify the base offset is still correct for a given capture (it's a
concrete ROM address, not derived at runtime) with --verify-against
<vram.bin>, which does the same exhaustive per-tile comparison this
session used to confirm the range and reports the first mismatching
tile index (should be exactly 1024 for the save-select screen's
current build - anything else means the assumption needs rechecking).
"""
import argparse
import struct
from PIL import Image, ImageDraw


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--base", type=lambda x: int(x, 0), default=0x1398e8)
    ap.add_argument("--count", type=int, default=1024)
    ap.add_argument("--out-bin", default=None)
    ap.add_argument("--out-png", default=None)
    ap.add_argument("--palette", default=None,
                     help="raw 512-byte palette dump (256 x 15-bit BGR); "
                          "if omitted, a synthetic grayscale ramp is used "
                          "(shapes still legible, colors are meaningless)")
    ap.add_argument("--cols", type=int, default=16)
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--verify-against", default=None,
                     help="a captured VRAM dump (e.g. 03_save_select.vram.bin) "
                          "to compare byte-for-byte against this ROM range")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    chunk = rom[args.base: args.base + args.count * 32]

    if args.out_bin:
        with open(args.out_bin, "wb") as f:
            f.write(chunk)
        print(f"wrote {args.out_bin}: {len(chunk)} bytes ({args.count} tiles)")

    nonzero = [i for i in range(len(chunk) // 32) if any(chunk[i*32:(i+1)*32])]
    print(f"non-zero (visibly drawn) tiles: {len(nonzero)}, "
          f"max index: {max(nonzero) if nonzero else -1}")

    if args.verify_against:
        vram = open(args.verify_against, "rb").read()
        n = min(len(vram) // 32, args.count)
        mismatch = None
        for i in range(n):
            if vram[i*32:(i+1)*32] != chunk[i*32:(i+1)*32]:
                mismatch = i
                break
        print(f"verify-against {args.verify_against}: first mismatching tile "
              f"= {mismatch} (checked {n} tiles; None means full match)")

    if args.out_png:
        if args.palette:
            pal_vals = struct.unpack_from("<256H", open(args.palette, "rb").read(), 0)
            pal = [bgr15_to_rgb(v) for v in pal_vals]
        else:
            pal = []
            for bank in range(16):
                for idx in range(16):
                    g = idx * 17
                    pal.append((g, g, g))

        cols = args.cols
        n_tiles = args.count
        rows = (n_tiles + cols - 1) // cols
        img = Image.new("RGB", (cols * 8, rows * 8), (0, 0, 0))
        px_out = img.load()
        for i in range(n_tiles):
            off = i * 32
            if off + 32 > len(chunk):
                break
            tpx = decode_tile_4bpp(chunk, off)
            tx, ty = i % cols, i // cols
            for y in range(8):
                for x in range(8):
                    idx = tpx[y][x]
                    if idx == 0:
                        continue
                    px_out[tx*8+x, ty*8+y] = pal[idx % len(pal)]

        scale = args.scale
        big = img.resize((img.size[0]*scale, img.size[1]*scale), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        for i in range(n_tiles):
            tx, ty = i % cols, i // cols
            draw.text((tx*8*scale, ty*8*scale), str(i), fill=(255, 0, 255))
        big.save(args.out_png)
        print(f"wrote {args.out_png}: {big.size}")


if __name__ == "__main__":
    main()
