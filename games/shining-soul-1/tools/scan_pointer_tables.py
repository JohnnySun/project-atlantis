#!/usr/bin/env python3
"""Read-only recon: look for GBA ROM-address pointer tables (arrays of
4-byte little-endian values in the 0x08000000-0x09FFFFFF cartridge
address space) as a candidate signal for a string/data table, the way
Golden Sun's string and Huffman-tree pointer tables look.

A run is reported if it has at least --min-run consecutive 4-byte-aligned
words that:
  - fall in the ROM address window (0x08000000 to 0x08000000+len(rom)-1
    for a 32MB-mapped image, adjusted for actual file size)
  - are non-decreasing (pointer tables are very often, but not always,
    sorted) OR just densely packed - both modes are reported separately

This is a coarse structural heuristic, not a confirmed pointer table -
false positives happen in code (literal pools) and graphics data that
coincidentally look like valid addresses.

Usage:
  python3 scan_pointer_tables.py <rom.gba> [--min-run 8]
"""
import argparse
import struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--min-run", type=int, default=8)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    data = open(args.rom, "rb").read()
    n = len(data)
    base = 0x08000000
    lo, hi = base, base + n - 1

    words = struct.unpack("<%dI" % (n // 4), data[: (n // 4) * 4])

    def in_range(w):
        return lo <= w <= hi

    runs = []
    i = 0
    L = len(words)
    while i < L:
        if in_range(words[i]):
            j = i
            increasing = True
            while j + 1 < L and in_range(words[j + 1]) and words[j + 1] >= words[j]:
                j += 1
            run_len = j - i + 1
            if run_len >= args.min_run:
                runs.append((i * 4, run_len, words[i], words[j]))
            i = j + 1
        else:
            i += 1

    runs.sort(key=lambda r: -r[1])
    print(f"{len(runs)} non-decreasing pointer-table candidates, "
          f"min run {args.min_run} words, window 0x{lo:08x}-0x{hi:08x}\n")
    for off, run_len, first, last in runs[: args.limit]:
        span = last - first
        print(f"  file_offset 0x{off:06x}  words={run_len:5d}  "
              f"first={first:#010x} last={last:#010x}  span=0x{span:x}")


if __name__ == "__main__":
    main()
