#!/usr/bin/env python3
"""Session 20: the general encoder - turn a set of ledger work batches into a
patched ROM. This is what session 15's and session 16/20's proofs of concept
were building towards: instead of hand-placing two glyphs and rewriting one
known string, take every translated record in `work/*.jsonl`, collect the
distinct characters, allocate them across brand-new glyph categories, insert
the pixel data, and rewrite each string's 16-bit code array in place.

Pipeline (each step's evidence is cited to the session that established it):

  1. Parse work batches. Each record's `string_id` is `<pool>:<hex offset>`,
     where the offset is the entry's marker/header position in the ROM
     (session 9's string-pool structure, session 12's decoder).
  2. For each record, walk the pool at that offset to recover the entry's
     line layout and, from the NEXT entry's header position, the exact byte
     budget available for rewriting (session 15 confirmed that zero-filling
     the remainder of that span leaves the following entry intact).
  3. Collect distinct characters across all target texts, allocate them to
     categories 5..15 at 255 slots each.
  4. Build a replacement type-8 resource header in confirmed-free ROM space,
     with one new struct per new category (each a verbatim copy of an
     existing category's 6,176-byte prologue - session 20) plus its pixel
     table, and repoint the single registry word at 0x080fa510.
  5. Rewrite each record's code array; refuse (and report) any record that
     does not fit its budget rather than overrunning into the next entry.

Slot arithmetic: the code format is `category=(code>>8)&0xF`,
`glyph_entry_index=(code&0xFF)-1` (session 8), so the low byte ranges 0x01
to 0xFF and a category addresses indices 0..254 - **255 usable slots**, not
256. (The struct prologue declares a 256-slot / 0x8000-byte pixel span; the
256th slot exists in storage but cannot be named by any code, because a low
byte of 0x00 is the string terminator.) Categories 5-15 are unused in this
JP ROM (session 11), so the ceiling is 11 x 255 = 2,805 glyphs.

Glyph metadata: a new category's per-glyph metadata is copied wholesale from
category 0, i.e. kana metadata applied to Chinese glyphs. Session 20 probed
this directly - the same glyph placed at indices 0, 127 and 254 rendered with
byte-identical sprite tiles, identical sprite geometry and a uniform 13px
advance, which is also exactly the advance the original Japanese text uses.
So the metadata is index-insensitive across the whole addressable range and
slots may be allocated freely. (What the metadata words actually *encode* is
still not decoded; this is an empirical bound, not a derivation.)

Writes only the output file; never modifies the base ROM.

Usage:
    python3 build_translation_rom.py \
        --rom games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba \
        --out games/shining-soul-1/roms/build/ss1-zh-tw.gba \
        --locale zh-TW \
        --batch 'games/shining-soul-1/work/*.jsonl'
"""
import argparse
import glob
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_cn_glyph_category5_poc import (  # noqa: E402
    EXISTING_CATEGORY_STRUCTS, GLYPH_STRIDE, GLYPH_SLOTS_PER_CATEGORY,
    NEW_HEADER, REGISTRY_ENTRY_ADDR, REGISTRY_ENTRY_EXPECTED, REGISTRY_L1,
    ROM_BASE, STRUCT_FIRST_WORD, STRUCT_PROLOGUE_LEN, bits_to_shaded_grid,
    grid_to_glyph_bytes, hex_to_bits, load_unifont_glyph, pad_to_cell, u32,
)
from extract_string_pool import walk_pool  # noqa: E402

FIRST_NEW_CATEGORY = 5
LAST_CATEGORY = 15
SLOTS_PER_CATEGORY = 255          # indices 0..254; see module docstring
STRUCT_TOTAL = STRUCT_PROLOGUE_LEN + GLYPH_SLOTS_PER_CATEGORY * GLYPH_STRIDE
TERMINATOR = b"\x00\x00"


DEFAULT_INK_WIDTH = 13


def off(addr):
    return addr - ROM_BASE


def condense(bits, target, cell=16):
    """Horizontally condense a glyph so its ink fits `target` columns.

    Measured on the base ROM (session 20): the game's own kanji in categories
    1/2/3 have a maximum ink width of exactly 13px across every sampled glyph,
    which is also exactly the sprite advance the engine uses. Unifont's CJK
    glyphs are 15px wide, so dropping them in unmodified makes every character
    overlap its neighbour by 2px - visible and confirmed in the first end-to-end
    render. Condensing to 13 restores the original spacing.

    LANCZOS + threshold rather than nearest-neighbour: session 13 established
    that nearest-neighbour resampling of this game's glyph bitmaps destroys
    thin strokes where LANCZOS preserves them.
    """
    from PIL import Image
    h, w = len(bits), len(bits[0])
    if target >= w:
        return bits
    im = Image.new("L", (w, h))
    im.putdata([255 * v for row in bits for v in row])
    data = list(im.resize((target, h), Image.LANCZOS).getdata())
    out = [[1 if data[y * target + x] >= 96 else 0 for x in range(target)] for y in range(h)]
    left = (cell - target) // 2
    return [[0] * left + row + [0] * (cell - target - left) for row in out]


def glyph_bytes(codepoint, ink_width):
    """Font bitmap -> the game's 128-byte 4bpp 2-tone glyph format.

    Condensing happens before shading so the outline is computed on the final
    shape rather than being squeezed along with it.
    """
    bits = pad_to_cell(hex_to_bits(load_unifont_glyph(codepoint)))
    if ink_width:
        bits = condense(bits, ink_width)
    return grid_to_glyph_bytes(bits_to_shaded_grid(bits))


def load_records(patterns, locale):
    """Read ledger work batches, keeping records that have text for `locale`."""
    out = []
    seen = set()
    for pattern in patterns:
        for path in sorted(glob.glob(pattern)):
            name = os.path.basename(path)
            # roundtrip/restored files are verification by-products, not batches
            if "roundtrip" in name or "restored" in name:
                continue
            for lineno, raw in enumerate(open(path, encoding="utf-8"), 1):
                raw = raw.strip()
                if not raw:
                    continue
                rec = json.loads(raw)
                text = rec.get("targets", {}).get(locale, {}).get("text", "")
                if not text:
                    continue
                sid = rec["string_id"]
                if sid in seen:
                    print(f"  note: {name}:{lineno} duplicate string_id {sid}, keeping first")
                    continue
                seen.add(sid)
                out.append({"string_id": sid, "text": text, "source": path})
    return out


def locate_entry(rom, string_id):
    """Resolve a `<pool>:<hex offset>` string_id to (line_start, budget, marker).

    budget is the number of bytes from the first line's start up to the NEXT
    entry's header - the span session 15 verified is safe to overwrite as long
    as the remainder is zero-filled.
    """
    marker_off = int(string_id.split(":")[1], 16)
    entries, _end = walk_pool(rom, marker_off, max_entries=2)
    if not entries:
        return None, None, None
    pos, entry_id, marker, lines, entry_end = entries[0]
    line_start = pos + (10 if entry_id is not None else 2)
    if len(entries) > 1:
        budget = entries[1][0] - line_start
    else:
        budget = entry_end - line_start          # conservative: no padding
    return line_start, budget, marker


def allocate(chars):
    """Assign each distinct character a (category, index) slot."""
    capacity = (LAST_CATEGORY - FIRST_NEW_CATEGORY + 1) * SLOTS_PER_CATEGORY
    if len(chars) > capacity:
        sys.exit(f"ABORT: {len(chars)} distinct characters exceed the {capacity}-glyph "
                 f"ceiling (categories {FIRST_NEW_CATEGORY}-{LAST_CATEGORY} x "
                 f"{SLOTS_PER_CATEGORY} slots).")
    mapping = {}
    for n, ch in enumerate(chars):
        mapping[ch] = (FIRST_NEW_CATEGORY + n // SLOTS_PER_CATEGORY, n % SLOTS_PER_CATEGORY)
    return mapping


def encode(text, mapping):
    return [(cat << 8) | (idx + 1) for cat, idx in (mapping[ch] for ch in text)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--locale", default="zh-TW")
    ap.add_argument("--batch", action="append", required=True,
                    help="glob for ledger work batches; repeatable")
    ap.add_argument("--ink-width", type=int, default=DEFAULT_INK_WIDTH,
                    help="condense glyph ink to this many columns (0 disables); "
                         "defaults to the 13px the game's own kanji use")
    ap.add_argument("--dry-run", action="store_true",
                    help="report allocation and fit without writing a ROM")
    args = ap.parse_args()

    rom = bytearray(open(args.rom, "rb").read())

    print("=== drift guards ===")
    reg = struct.unpack_from("<I", rom, off(REGISTRY_ENTRY_ADDR))[0]
    if reg != REGISTRY_ENTRY_EXPECTED:
        sys.exit(f"ABORT: registry entry at 0x{REGISTRY_ENTRY_ADDR:x} = 0x{reg:x}, expected "
                 f"0x{REGISTRY_ENTRY_EXPECTED:x} - research drift, refusing to patch.")
    prologues = [bytes(rom[off(a):off(a) + STRUCT_PROLOGUE_LEN]) for a in EXISTING_CATEGORY_STRUCTS]
    if any(p != prologues[0] for p in prologues):
        sys.exit("ABORT: existing category struct prologues are not byte-identical.")
    if struct.unpack_from("<I", prologues[0], 0)[0] != STRUCT_FIRST_WORD:
        sys.exit("ABORT: struct prologue word[0] is not the expected pixel-table offset.")
    print(f"  registry word and all {len(prologues)} struct prologues match expectations")

    print(f"\n=== batches ({args.locale}) ===")
    records = load_records(args.batch, args.locale)
    if not records:
        sys.exit("ABORT: no records with target text for this locale.")
    print(f"  {len(records)} translated records")

    # Resolve each record and check it fits before allocating anything.
    resolved, skipped = [], []
    for rec in records:
        line_start, budget, marker = locate_entry(rom, rec["string_id"])
        if line_start is None:
            skipped.append((rec, "could not walk the pool at this offset"))
            continue
        lines = rec["text"].split("\n")
        if len(lines) != marker:
            skipped.append((rec, f"translation has {len(lines)} line(s) but the entry's "
                                 f"marker declares {marker}"))
            continue
        need = sum(len(l) * 2 + 2 for l in lines)
        if need > budget:
            skipped.append((rec, f"needs {need} bytes, budget is {budget}"))
            continue
        rec.update(line_start=line_start, budget=budget, lines=lines, need=need)
        resolved.append(rec)
    print(f"  {len(resolved)} fit their budget, {len(skipped)} skipped")

    chars = sorted({ch for rec in resolved for ch in "".join(rec["lines"])})
    mapping = allocate(chars)
    n_cats = (len(chars) + SLOTS_PER_CATEGORY - 1) // SLOTS_PER_CATEGORY
    print(f"\n=== allocation ===")
    print(f"  {len(chars)} distinct characters -> categories "
          f"{FIRST_NEW_CATEGORY}..{FIRST_NEW_CATEGORY + n_cats - 1} "
          f"({SLOTS_PER_CATEGORY} slots each)")

    missing = []
    glyphs = {}
    for ch in chars:
        try:
            glyphs[ch] = glyph_bytes(ord(ch), args.ink_width)
        except KeyError:
            missing.append(ch)
    if missing:
        sys.exit(f"ABORT: no glyph in the font for: {''.join(missing)}")
    print(f"  all {len(glyphs)} glyphs sourced from the font"
          + (f", ink condensed to {args.ink_width}px" if args.ink_width else ""))

    new_structs = [NEW_HEADER + 0x40 + i * STRUCT_TOTAL for i in range(n_cats)]
    block_len = 0x40 + n_cats * STRUCT_TOTAL
    free = rom[off(NEW_HEADER):off(NEW_HEADER) + block_len]
    if any(b != 0xFF for b in free):
        sys.exit(f"ABORT: free-space region 0x{NEW_HEADER:x}+0x{block_len:x} is not all 0xFF.")
    print(f"  free space 0x{NEW_HEADER:x}-0x{NEW_HEADER + block_len:x} "
          f"(0x{block_len:x} bytes) confirmed all 0xFF")

    if args.dry_run:
        report(resolved, skipped, chars, mapping)
        return

    print("\n=== writing glyph tables ===")
    all_structs = EXISTING_CATEGORY_STRUCTS + new_structs
    header = struct.pack("<I", len(all_structs))
    for s in all_structs:
        header += struct.pack("<I", u32(s - NEW_HEADER))
    rom[off(NEW_HEADER):off(NEW_HEADER) + len(header)] = header
    print(f"  header @ 0x{NEW_HEADER:x}: count={len(all_structs)} "
          f"({len(EXISTING_CATEGORY_STRUCTS)} existing + {n_cats} new)")

    span = GLYPH_SLOTS_PER_CATEGORY * GLYPH_STRIDE
    for i, s in enumerate(new_structs):
        rom[off(s):off(s) + STRUCT_PROLOGUE_LEN] = prologues[0]
        pix = s + STRUCT_FIRST_WORD
        rom[off(pix):off(pix) + span] = b"\x00" * span
        print(f"  category {FIRST_NEW_CATEGORY + i}: struct @ 0x{s:x}, pixels @ 0x{pix:x}")

    for ch, (cat, idx) in mapping.items():
        pix = new_structs[cat - FIRST_NEW_CATEGORY] + STRUCT_FIRST_WORD + idx * GLYPH_STRIDE
        rom[off(pix):off(pix) + GLYPH_STRIDE] = glyphs[ch]
    print(f"  {len(mapping)} glyphs written")

    struct.pack_into("<I", rom, off(REGISTRY_ENTRY_ADDR), u32(NEW_HEADER - REGISTRY_L1))
    print(f"  registry word 0x{REGISTRY_ENTRY_ADDR:x} -> header @ 0x{NEW_HEADER:x}")

    print("\n=== rewriting strings ===")
    for rec in resolved:
        body = b""
        for line in rec["lines"]:
            body += struct.pack("<%dH" % len(line), *encode(line, mapping)) + TERMINATOR
        body += b"\x00" * (rec["budget"] - len(body))
        rom[rec["line_start"]:rec["line_start"] + rec["budget"]] = body
    print(f"  {len(resolved)} strings rewritten in place (remainder zero-filled)")

    with open(args.out, "wb") as f:
        f.write(rom)
    orig = open(args.rom, "rb").read()
    diff = sum(1 for a, b in zip(orig, rom) if a != b)
    print(f"\nwrote {args.out} ({len(rom)} bytes, {diff} differ from base)")
    report(resolved, skipped, chars, mapping)


def report(resolved, skipped, chars, mapping):
    print("\n=== report ===")
    for rec in resolved:
        print(f"  ok    {rec['string_id']}  {rec['need']}/{rec['budget']} bytes  "
              f"{rec['text'][:24]!r}")
    for rec, why in skipped:
        print(f"  SKIP  {rec['string_id']}  {why}")
    if skipped:
        print(f"\n  {len(skipped)} record(s) skipped - these are NOT in the output ROM.")
    cats = sorted({c for c, _ in mapping.values()})
    print(f"\n  {len(chars)} glyphs in categories {cats}; "
          f"headroom {(LAST_CATEGORY - FIRST_NEW_CATEGORY + 1) * SLOTS_PER_CATEGORY - len(chars)} "
          f"more glyphs")


if __name__ == "__main__":
    main()
