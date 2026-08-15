#!/usr/bin/env python3
"""Read-only recon: count THUMB `swi #imm8` call sites in a GBA ROM by
scanning for the byte pattern [imm8, 0xDF] at every offset (not
instruction-aligned - see caveat below).

THUMB's swi instruction encodes as the halfword 0b11011111_iiiiiiii,
i.e. bytes [imm8, 0xDF] in little-endian order. A true call site only
exists at an even (halfword-aligned) offset that is actually decoded as
an instruction at runtime; this scanner does NOT disassemble or verify
alignment/reachability, so counts are an upper bound including false
positives from ARM code, literal pools, and data that coincidentally
contains the byte 0xDF. Treat this purely as a coarse signal for "does
this ROM's code call the BIOS (de)compression services at all" - it is
not evidence of *where* text specifically is compressed.

Usage:
  python3 scan_swi_calls.py <rom.gba> [--align2]
"""
import argparse
from collections import Counter

SWI_NAMES = {
    0x01: "RegisterRamReset", 0x02: "Halt", 0x03: "Stop", 0x04: "IntrWait",
    0x05: "VBlankIntrWait", 0x06: "Div", 0x07: "DivArm", 0x08: "Sqrt",
    0x09: "ArcTan", 0x0A: "ArcTan2", 0x0B: "CpuSet", 0x0C: "CpuFastSet",
    0x0D: "GetBiosChecksum", 0x0E: "BgAffineSet", 0x0F: "ObjAffineSet",
    0x10: "BitUnPack", 0x11: "LZ77UnCompWram", 0x12: "LZ77UnCompVram",
    0x13: "HuffUnComp", 0x14: "RLUnCompWram", 0x15: "RLUnCompVram",
    0x16: "Diff8bitUnFilterWram", 0x17: "Diff8bitUnFilterVram",
    0x18: "Diff16bitUnFilter", 0x19: "SoundBias", 0x1A: "SoundDriverInit",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--align2", action="store_true",
                     help="only count halfword-aligned offsets (reduces false positives)")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    data = open(args.rom, "rb").read()
    step = 2 if args.align2 else 1
    counts = Counter()
    locations = {}
    n = len(data)
    for off in range(0, n - 1, step):
        if data[off + 1] == 0xDF:
            imm = data[off]
            counts[imm] += 1
            locations.setdefault(imm, []).append(off)

    for imm in sorted(SWI_NAMES):
        name = SWI_NAMES[imm]
        locs = locations.get(imm, [])
        print(f"swi 0x{imm:02x} ({name}): {len(locs)} occurrences"
              + (f" (of {counts[imm]} raw)" if step == 1 else ""))
        if locs:
            print("   first:", ", ".join(hex(x) for x in locs[: args.show]))


if __name__ == "__main__":
    main()
