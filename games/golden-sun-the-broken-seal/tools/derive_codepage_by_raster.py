#!/usr/bin/env python3
"""Derive an extended-glyph Japanese codepage for one Golden Sun ROM by
matching font rasters against another game's already-verified codepage.

Both AGSJ01 (The Broken Seal) and AGFJ01 (The Lost Age) run the same GBA
engine and font renderer (24 bytes per extended glyph: 12 rows x u16, fixed
10px width). Each game assigns extended glyph IDs independently, in order of
first appearance in that game's own string table, so IDs are NOT comparable
across games -- but the font bitmap for a given character is byte-identical
in both ROMs. Matching rasters (not IDs) therefore recovers a correct,
per-game codepage without OCR.

Do not reuse another game's codepage.tsv directly by ID -- see
research/jp-codepage-derivation.md for a concrete case (glyph 0x102/0x103)
where identical structural coverage produced wrong characters.

usage: derive_codepage_by_raster.py \
  --target-rom ROM --target-font-base OFFSET --target-count N \
  --reference-rom ROM --reference-codepage TSV --reference-font-base OFFSET \
  --output TSV
"""
import argparse

GLYPH_BYTES = 24


def load_codepage(path):
    mapping = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            hexid, char, _status = line.rstrip("\n").split("\t")
            mapping[int(hexid, 16)] = char
    return mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-rom", required=True)
    parser.add_argument("--target-font-base", required=True, type=lambda v: int(v, 0),
                         help="offset of the target ROM's extended glyph raster table")
    parser.add_argument("--target-count", required=True, type=int,
                         help="number of extended glyph IDs to derive, starting at 0x100")
    parser.add_argument("--reference-rom", required=True)
    parser.add_argument("--reference-codepage", required=True)
    parser.add_argument("--reference-font-base", required=True, type=lambda v: int(v, 0))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.target_rom, "rb") as f:
        target = f.read()
    with open(args.reference_rom, "rb") as f:
        reference = f.read()

    reference_codepage = load_codepage(args.reference_codepage)
    raster_to_char = {}
    for gid, char in reference_codepage.items():
        if gid < 0x100:
            continue
        offset = args.reference_font_base + (gid - 0x100) * GLYPH_BYTES
        raster = reference[offset:offset + GLYPH_BYTES]
        if raster in raster_to_char and raster_to_char[raster] != char:
            raise SystemExit(f"raster collision: {char!r} vs {raster_to_char[raster]!r}")
        raster_to_char[raster] = char

    entries = []
    unmatched = []
    for gid in range(0x100, 0x100 + args.target_count):
        offset = args.target_font_base + (gid - 0x100) * GLYPH_BYTES
        raster = target[offset:offset + GLYPH_BYTES]
        char = raster_to_char.get(raster)
        if char is None:
            unmatched.append(gid)
        else:
            entries.append((gid, char))

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("id\tcharacter\tstatus\n")
        for gid, char in entries:
            f.write(f"{gid:04x}\t{char}\tprovisional\n")

    print(f"matched {len(entries)}/{args.target_count}; unmatched: "
          f"{[hex(g) for g in unmatched] if unmatched else 'none'}")


if __name__ == "__main__":
    main()
