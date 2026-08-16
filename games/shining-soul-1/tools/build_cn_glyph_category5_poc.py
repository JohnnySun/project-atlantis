#!/usr/bin/env python3
"""Session 16 proof-of-concept: wire up a BRAND NEW glyph category (5),
previously hard-NULL in the IWRAM dispatch table (session 11), by
patching a single ROM registry pointer plus adding a new header+struct+
pixel-table block in confirmed free ROM space (0x660000+) - NOT by
touching any of the five existing categories' data or any executable
code. This builds directly on session 15's category-4-slot-filling POC
but removes its ~215-slot ceiling: the mechanism proven here scales to
as many new categories as fit in the header's offset table (categories
5-15 are all still unused, and the count field itself is unbounded in
principle - see games/shining-soul-1/README.md "第十六輪偵察").

Background (full derivation in README "第十六輪偵察"): the runtime IWRAM
dispatch table at 0x030065f0 (session 11) that string-rendering code
queries for "category -> glyph-pool-struct pointer" is populated at boot
by a small loop at ROM file offset 0xeb40-0xeb64:

    r5 = get_category_count(type=8)          ; bl 0x08002c10
    for i in 0..r5:
        r0 = lookup_resource(type=8, index=i) ; bl 0x08002a04
        dispatch_table[i] = r0                ; stm r7!, {r0}

Both callees are part of a generic, engine-wide multi-level "resource
registry" (24 possible types, each with its own header) - NOT anything
font-specific. Tracing both functions down to their leaf logic (see
README for the full disassembly) shows type 8's own header is a plain
DATA structure, not code:

    header_base = 0x0846932c (ROM)
    header_base[0]        = count (currently 5, i.e. categories 0-4)
    header_base[4 + i*4]  = relative offset; struct_addr(i) = header_base + that offset

Both get_category_count(8) and lookup_resource(8, i) reach this SAME
header via the SAME registry entry: a literal-pool constant L1 =
0x080fa4e8 (identical in both functions, confirmed live) plus a
per-type offset read from *(L1 + 8 + type*4) = *(0x080fa510). That one
word currently holds (0x0846932c - L1) = 0x0036ee44. A static ROM-wide
search found NO other literal reference to either 0x0846932c or
0x080fa510 anywhere else in the ROM - this registry entry is the ONLY
path to type 8's header.

This means: rather than touching type 8's existing header (whose
offset-table slot immediately after the 5th entry is NOT free space -
it's the very first word of category 0's own struct, confirmed by
static read: all 5 known structs' first word is exactly 0x1820, which
is also the struct-to-pixel-table offset session 11 already found by a
different method), we can build a COMPLETE NEW replacement header
(count=6, six offset-table entries: five pointing at the unmoved
existing category structs, one pointing at a new category-5 struct we
build from scratch) in free ROM space, and repoint the SINGLE registry
word at 0x080fa510 to it. Every one of the 8 MiB ROM's other bytes -
including all five existing categories' pixel data - is untouched.

New category-5 struct format mimics the one universal fact confirmed
about the existing five structs (their first word is always 0x1820,
the already-known struct-to-pixel-table-base offset from session 11) -
this session cannot fully prove whether that offset is a hardcoded
constant in the *consuming* code or is read live from the struct's own
first field, so the new struct copies the same convention rather than
guessing which hypothesis is correct.

Glyph source/palette convention: same as session 15's
build_cn_glyph_poc.py (GNU Unifont 16x16 wide glyphs, 1:1 pixel match
to this game's glyph slot format, 2-tone edge-detection shading).

Read-only up to the point of writing the output file.

Usage:
    python3 build_cn_glyph_category5_poc.py \
        games/shining-soul-1/roms/base/Shining_Soul_JP_AHUJ8P.gba \
        games/shining-soul-1/roms/build/ss1-cat5-poc.gba
"""
import argparse
import gzip
import struct
import sys

ROM_BASE = 0x08000000

# --- confirmed-by-recon constants (session 16) ---
REGISTRY_ENTRY_ADDR = 0x080fa510   # *(L1 + 8 + type*4), type=8 (font/glyph-category resource kind)
REGISTRY_ENTRY_EXPECTED = 0x0036ee44  # current value: header_base(0x0846932c) - L1(0x080fa4e8)
REGISTRY_L1 = 0x080fa4e8
OLD_HEADER_BASE = 0x0846932c
OLD_HEADER_EXPECTED_BYTES = None  # filled in main() after computing

EXISTING_CATEGORY_STRUCTS = [0x08469344, 0x08472d64, 0x0847c784, 0x084861a4, 0x0848fbc4]
STRUCT_FIRST_WORD = 0x1820  # confirmed identical across all 5 existing structs

# Session 20 correction: the struct is NOT just its first word. Everything from
# +0 to +0x1820 is a real 6,176-byte prologue (2,494 non-zero bytes: word[0] =
# 0x1820 = offset to the pixel table, word[1] = 0x9820 = its end, i.e. a 0x8000
# byte / 256-slot span, followed by a table of 3-word per-glyph metadata
# entries). All five existing categories' prologues are BYTE-IDENTICAL (verified
# by sha256), so a new category copies one verbatim. Session 16 wrote only
# word[0] and left the other 6,172 bytes as 0xFF padding; the ROM it produced
# booted and rendered every OTHER screen correctly, but the one screen that
# actually draws a category-5 code came up with its entire OBJ layer blank
# (character sprite and "剣士" label wiped too, 128 garbage OAM entries) -
# reproduced identically on two independent clean-boot runs, against a base-ROM
# control that rendered that screen correctly at the same step. See SESSION-LOG
# "第二十輪".
STRUCT_PROLOGUE_LEN = 0x1820
GLYPH_SLOTS_PER_CATEGORY = 0x8000 // 0x80  # 256, declared by prologue word[1]

# --- new layout, all inside the confirmed 0xFF-padded free region ---
NEW_HEADER = 0x08660000
NEW_STRUCT5 = NEW_HEADER + 0x40
NEW_PIXEL5 = NEW_STRUCT5 + STRUCT_FIRST_WORD
GLYPH_STRIDE = 0x80
# header + full prologue + the whole 256-slot pixel span the prologue declares
NEW_BLOCK_LEN = 0x40 + STRUCT_PROLOGUE_LEN + GLYPH_SLOTS_PER_CATEGORY * GLYPH_STRIDE

TARGET_STRING_ADDR = 0x499b1a  # "職業を選んでください" - session 8 ground truth, reused by session 15
TARGET_STRING_BUDGET = 34

GLYPHS = [
    (0x5B57, 0),  # 字 ("character/script")
    (0x578B, 1),  # 型 ("type/mold") - together "字型" = "font" (thematic, category-5-is-a-font pun)
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
    rows = []
    for r in range(height):
        row_hex = hexstr[r * bytes_per_row * 2:(r + 1) * bytes_per_row * 2]
        val = int(row_hex, 16)
        bits = [(val >> (bytes_per_row * 8 - 1 - b)) & 1 for b in range(width)]
        rows.append(bits)
    return rows


def bits_to_shaded_grid(bits):
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


def u32(v):
    return v & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("output")
    args = ap.parse_args()

    rom = bytearray(open(args.rom, "rb").read())

    def off(addr):
        return addr - ROM_BASE

    print("=== drift guards ===")
    reg_val = struct.unpack_from("<I", rom, off(REGISTRY_ENTRY_ADDR))[0]
    if reg_val != REGISTRY_ENTRY_EXPECTED:
        sys.exit(f"ABORT: registry entry at 0x{REGISTRY_ENTRY_ADDR:x} = 0x{reg_val:x}, "
                 f"expected 0x{REGISTRY_ENTRY_EXPECTED:x} - research drift, refusing to patch.")
    print(f"  registry entry 0x{REGISTRY_ENTRY_ADDR:x} = 0x{reg_val:x} (matches expected)")

    for cat, addr in enumerate(EXISTING_CATEGORY_STRUCTS):
        first_word = struct.unpack_from("<I", rom, off(addr))[0]
        if first_word != STRUCT_FIRST_WORD:
            sys.exit(f"ABORT: category {cat} struct's first word is 0x{first_word:x}, "
                     f"expected 0x{STRUCT_FIRST_WORD:x} - refusing to patch.")
    print(f"  all 5 existing category structs' first word = 0x{STRUCT_FIRST_WORD:x} (matches)")

    # Session 20: the whole prologue - not just word[0] - is what the renderer
    # consumes, so copying one verbatim is only sound if they really are all the
    # same. Check that here rather than trusting the earlier session's note.
    prologues = [bytes(rom[off(a):off(a) + STRUCT_PROLOGUE_LEN]) for a in EXISTING_CATEGORY_STRUCTS]
    if any(p != prologues[0] for p in prologues):
        sys.exit("ABORT: the 5 existing category struct prologues are NOT byte-identical - "
                 "copying one verbatim is unsound, refusing to patch.")
    print(f"  all 5 struct prologues ({STRUCT_PROLOGUE_LEN} bytes) are byte-identical")
    declared_end = struct.unpack_from("<I", prologues[0], 4)[0]
    declared_slots = (declared_end - STRUCT_FIRST_WORD) // GLYPH_STRIDE
    if declared_slots != GLYPH_SLOTS_PER_CATEGORY:
        sys.exit(f"ABORT: prologue declares {declared_slots} glyph slots, expected "
                 f"{GLYPH_SLOTS_PER_CATEGORY} - refusing to patch.")
    print(f"  prologue declares pixel span 0x{STRUCT_FIRST_WORD:x}-0x{declared_end:x} "
          f"= {declared_slots} glyph slots")

    free_check = rom[off(NEW_HEADER):off(NEW_HEADER) + NEW_BLOCK_LEN]
    if any(b != 0xFF for b in free_check):
        sys.exit(f"ABORT: target free-space region 0x{NEW_HEADER:x}+0x{NEW_BLOCK_LEN:x} is not "
                 f"all 0xFF - refusing to write over unknown content.")
    print(f"  free-space region 0x{NEW_HEADER:x}-0x{NEW_HEADER+NEW_BLOCK_LEN:x} "
          f"(0x{NEW_BLOCK_LEN:x} bytes) confirmed all 0xFF")

    expected_codes = [0x28a, 0x3eb, 0x2e, 0x30d, 0x2f, 0x3d, 0x9, 0x3a, 0xc, 0x3, 0x0]
    actual_codes = list(struct.unpack_from("<11H", rom, TARGET_STRING_ADDR))
    if actual_codes != expected_codes:
        sys.exit(f"ABORT: target string at 0x{TARGET_STRING_ADDR:x} does not match session 8's "
                 f"known codes - refusing to patch.")
    print(f"  target string at 0x{TARGET_STRING_ADDR:x} matches session 8 ground truth")

    print("\n=== writing new header + struct + pixel data (pure addition, free space only) ===")
    # New header: count=6, 6 offset-table entries (relative to NEW_HEADER)
    all_structs = EXISTING_CATEGORY_STRUCTS + [NEW_STRUCT5]
    header_bytes = struct.pack("<I", len(all_structs))
    for s in all_structs:
        header_bytes += struct.pack("<I", u32(s - NEW_HEADER))
    rom[off(NEW_HEADER):off(NEW_HEADER) + len(header_bytes)] = header_bytes
    print(f"  new header @ 0x{NEW_HEADER:x}: count={len(all_structs)}, "
          f"offset_table={[hex(u32(s - NEW_HEADER)) for s in all_structs]}")

    # New category-5 struct: copy an existing category's ENTIRE prologue verbatim
    # (session 20 - writing only word[0], as session 16 did, leaves the renderer
    # reading 0xFF garbage and blanks the whole OBJ layer of any screen that
    # draws a category-5 code).
    rom[off(NEW_STRUCT5):off(NEW_STRUCT5) + STRUCT_PROLOGUE_LEN] = prologues[0]
    # Zero the pixel span so unused slots are blank rather than 0xFF noise, matching
    # how the existing tables' unused slots read (session 15's all-zero slot scan).
    rom[off(NEW_PIXEL5):off(NEW_PIXEL5) + GLYPH_SLOTS_PER_CATEGORY * GLYPH_STRIDE] = \
        b"\x00" * (GLYPH_SLOTS_PER_CATEGORY * GLYPH_STRIDE)
    print(f"  new category-5 struct @ 0x{NEW_STRUCT5:x}: full {STRUCT_PROLOGUE_LEN}-byte "
          f"prologue copied from category 0 (pixel table -> 0x{NEW_PIXEL5:x}, "
          f"{GLYPH_SLOTS_PER_CATEGORY} slots, zero-filled)")

    print("\n=== writing new glyphs (source: GNU Unifont 17.0.05) into category 5 ===")
    for codepoint, idx in GLYPHS:
        glyph_addr = NEW_PIXEL5 + idx * GLYPH_STRIDE
        glyph_bytes = codepoint_to_glyph_bytes(codepoint)
        assert len(glyph_bytes) == GLYPH_STRIDE
        rom[off(glyph_addr):off(glyph_addr) + GLYPH_STRIDE] = glyph_bytes
        print(f"  U+{codepoint:04X} -> category 5 idx {idx} (ROM 0x{glyph_addr:x}-0x{glyph_addr+GLYPH_STRIDE:x})")

    print(f"\n=== patching the ONE existing registry word at 0x{REGISTRY_ENTRY_ADDR:x} ===")
    new_reg_val = u32(NEW_HEADER - REGISTRY_L1)
    struct.pack_into("<I", rom, off(REGISTRY_ENTRY_ADDR), new_reg_val)
    print(f"  0x{REGISTRY_ENTRY_EXPECTED:x} -> 0x{new_reg_val:x} "
          f"(now resolves to header @ 0x{REGISTRY_L1 + new_reg_val:x})")

    print(f"\n=== redirecting string at 0x{TARGET_STRING_ADDR:x} to render \"字型\" via category 5 ===")
    new_codes = [0x0500 | (0 + 1), 0x0500 | (1 + 1), 0x0000]
    new_bytes = struct.pack("<3H", *new_codes)
    if len(new_bytes) > TARGET_STRING_BUDGET:
        sys.exit("ABORT: new string exceeds verified available budget")
    padded = new_bytes + b"\x00" * (TARGET_STRING_BUDGET - len(new_bytes))
    rom[TARGET_STRING_ADDR:TARGET_STRING_ADDR + TARGET_STRING_BUDGET] = padded
    print(f"  wrote codes {[hex(c) for c in new_codes]} + zero-fill to budget")

    with open(args.output, "wb") as f:
        f.write(rom)

    total_diff = sum(1 for a, b in zip(open(args.rom, "rb").read(), rom) if a != b)
    print(f"\nwrote {args.output} ({len(rom)} bytes, {total_diff} bytes differ from base ROM)")


if __name__ == "__main__":
    main()
