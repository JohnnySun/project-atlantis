#!/usr/bin/env python3
"""Read-only full-ROM structural scan (session 9), pool-chain variant.

scan_sentence_strings.py's raw "any NUL-terminated run of plausible
codes" signature is very noisy at full-ROM scale (found ~5800 candidates
over 0x000000-0x660000, dominated by periodic/arithmetic-progression
graphics or table data that coincidentally satisfies the byte-level
constraints - see research note for samples).

This script uses a much higher-precision structural signature found this
session by manually inspecting the two session-8-known strings' ROM
neighborhood (0x499b1a/0x499b3e): real strings are NOT isolated - they
sit back-to-back in a *pool*, each preceded by a small header (a 1..8
"line count" marker, sometimes with an extra id+type+00+00 prefix - see
extract_string_pool.py) and followed by zero padding up to the next
entry's header. This script tries every halfword-aligned offset as a
potential pool start and keeps it only if it produces a CHAIN of at
least --min-chain consecutive well-formed entries - accidental byte
patterns essentially never chain multiple times in a row the way a real,
deliberately laid out table does, so this cuts the false-positive rate
far below the single-run scan.

Usage:
    python3 scan_string_pools.py <rom.gba> [--min-chain 3] [--end 0x660000]

Read-only: only opens the ROM file for reading.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_string_pool import walk_pool, render_entry, MAX_MARKER  # noqa: E402


def read_u16(data, off):
    return data[off] | (data[off + 1] << 8)


def looks_like_header_start(data, pos, n):
    """Cheap pre-check before paying for a full walk_pool() call."""
    if pos + 2 > n:
        return False
    m = read_u16(data, pos)
    if 1 <= m <= MAX_MARKER:
        return True
    if pos + 10 <= n and read_u16(data, pos + 4) == 0 and read_u16(data, pos + 6) == 0:
        return 1 <= read_u16(data, pos + 8) <= MAX_MARKER
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--start", default="0x0")
    ap.add_argument("--end", default="0x660000")
    ap.add_argument("--min-chain", type=int, default=3,
                     help="minimum consecutive well-formed entries to report a pool")
    ap.add_argument("--max-entries-per-pool", type=int, default=500)
    ap.add_argument("--max-gap", type=int, default=64)
    ap.add_argument("--sample-lines", type=int, default=3,
                     help="how many entries of each found pool to print")
    args = ap.parse_args()

    start = int(args.start, 0)
    end = int(args.end, 0)
    with open(args.rom, "rb") as f:
        data = f.read()
    end = min(end, len(data))

    pools = []
    pos = start
    covered_until = -1
    while pos + 2 <= end:
        if pos <= covered_until or not looks_like_header_start(data, pos, end):
            pos += 2
            continue
        entries, pool_end = walk_pool(data, pos, args.max_entries_per_pool, args.max_gap)
        if len(entries) >= args.min_chain:
            pools.append((pos, entries, pool_end))
            covered_until = pool_end
            pos = pool_end
        else:
            pos += 2

    print(f"# scan_string_pools.py  rom={args.rom}  range=0x{start:06x}-0x{end:06x}  "
          f"min_chain={args.min_chain}")
    print(f"# {len(pools)} pool(s) found, {sum(len(e) for _, e, _ in pools)} total entries\n")

    for pool_start, entries, pool_end in pools:
        print(f"pool @ 0x{pool_start:06x}-0x{pool_end:06x}  "
              f"({len(entries)} entries, {pool_end - pool_start} bytes)")
        for off, entry_id, marker, lines, _end in entries[: args.sample_lines]:
            rendered = " / ".join(render_entry(c) for c in lines)
            id_str = f"id={entry_id} " if entry_id is not None else ""
            print(f"    0x{off:06x}  {id_str}marker={marker}  {rendered}")
        if len(entries) > args.sample_lines:
            print(f"    ... ({len(entries) - args.sample_lines} more)")
        print()


if __name__ == "__main__":
    main()
