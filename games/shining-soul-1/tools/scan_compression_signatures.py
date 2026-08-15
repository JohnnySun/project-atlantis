#!/usr/bin/env python3
"""Read-only recon: scan a GBA ROM for BIOS-style compression headers
(LZ77 0x10, Huffman 0x24, RLE 0x30) and report candidate locations.

This does NOT confirm a candidate is really compressed data - the GBA
BIOS decompression header format is just a 4-byte magic:
  byte0       = compression type nibble in high nibble (0x10/0x20/0x30/0x40)
                combined with a reserved low nibble (usually 0 for
                Nintendo's official routines, but not enforced by hardware)
  bytes1-3    = decompressed size (24-bit LE)

We treat any byte0 in {0x10, 0x24, 0x30} in a plausible position (word
aligned, decompressed size in a sane range) as a *candidate*, not a
confirmed compressed block. Cross-reference against ROM code that
actually calls SWI 0x11/0x12/0x13 (LZ77UnCompWram/Vram, HuffUnComp,
RLUnComp) before trusting any of these.

Usage:
  python3 scan_compression_signatures.py <rom.gba> [--min-size N] [--max-size N]
"""
import sys
import argparse
import struct


def scan(data, min_size=16, max_size=2 * 1024 * 1024, align=4):
    hits = {0x10: [], 0x24: [], 0x30: []}
    n = len(data)
    for off in range(0, n - 4, align):
        b0 = data[off]
        if b0 not in hits:
            continue
        size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
        if min_size <= size <= max_size:
            hits[b0].append((off, size))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--min-size", type=int, default=16)
    ap.add_argument("--max-size", type=int, default=2 * 1024 * 1024)
    ap.add_argument("--align", type=int, default=4)
    ap.add_argument("--limit", type=int, default=40, help="max hits to print per type")
    args = ap.parse_args()

    data = open(args.rom, "rb").read()
    hits = scan(data, args.min_size, args.max_size, args.align)

    names = {0x10: "LZ77", 0x24: "Huffman", 0x30: "RLE"}
    for tag, name in names.items():
        rows = hits[tag]
        print(f"=== {name} (0x{tag:02x}) candidates: {len(rows)} total, "
              f"word-aligned scan, size in [{args.min_size},{args.max_size}] ===")
        for off, size in rows[: args.limit]:
            print(f"  offset 0x{off:06x}  decompressed_size {size} (0x{size:x})")
        if len(rows) > args.limit:
            print(f"  ... {len(rows) - args.limit} more not shown")
        print()


if __name__ == "__main__":
    main()
