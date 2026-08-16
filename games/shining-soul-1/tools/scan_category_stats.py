#!/usr/bin/env python3
"""Read-only static ROM scan (session 11): tally how often each string-code
`category` value (session 8's (code>>8)&0xF glyph-pool selector) actually
occurs in real text, across a wider ROM range than session 10's ad hoc
corpus, and record every occurrence of a chosen set of rare categories
(address + entry offset + surrounding rendered context) so they can be
prioritized/inspected without re-scanning.

Session 10 solved categories 0/1/2/3 (covering 99.6% of a 9,645-code
sample taken only from the two known regions, 0x499000-0x500000 and
0x460000-0x470000) and explicitly left category 4 (19 occurrences, one
unverified data point) and 6-15 (1-3 occurrences each) unsolved. This
tool reuses extract_string_pool.walk_pool() (the same session-9 pool
walker every other tool here uses) over one or more ROM ranges, decodes
every code in every well-formed pool entry found, and reports:
  - overall category frequency (to see if a wider scan changes session
    10's 0.4%-of-corpus estimate for the rare categories)
  - every occurrence of --target-categories, with ROM address, entry
    offset, position within the entry, and the rendered sentence context
    (unresolved categories shown as [c#:N] via render_string_glyphs-style
    decoding), so a human can pick the most promising ones to chase with
    a live mGBA capture.

This is purely additive to scan_string_pools.py - it does not change pool
detection, only adds category tallying/filtering on top of the same
entries that tool would find.

Usage:
    python3 scan_category_stats.py <rom.gba> \
        [--ranges 0x499000-0x500000,0x460000-0x470000] \
        [--target-categories 4,6,7,8,9,10,11,12,13,14,15] \
        [--min-chain 3]

Read-only: only opens the ROM file for reading.
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_string_pool import walk_pool, MAX_MARKER  # noqa: E402
from scan_sentence_strings import render_code, hiragana_ratio  # noqa: E402


def read_u16(data, off):
    return data[off] | (data[off + 1] << 8)


def looks_like_header_start(data, pos, n):
    if pos + 2 > n:
        return False
    m = read_u16(data, pos)
    if 1 <= m <= MAX_MARKER:
        return True
    if pos + 10 <= n and read_u16(data, pos + 4) == 0 and read_u16(data, pos + 6) == 0:
        return 1 <= read_u16(data, pos + 8) <= MAX_MARKER
    return False


def scan_range(data, start, end, min_chain, max_entries_per_pool=500, max_gap=64):
    """Same chained-pool walk as scan_string_pools.py; returns list of
    (pool_start, entries, pool_end)."""
    pools = []
    pos = start
    covered_until = -1
    while pos + 2 <= end:
        if pos <= covered_until or not looks_like_header_start(data, pos, end):
            pos += 2
            continue
        entries, pool_end = walk_pool(data, pos, max_entries_per_pool, max_gap)
        if len(entries) >= min_chain:
            pools.append((pos, entries, pool_end))
            covered_until = pool_end
            pos = pool_end
        else:
            pos += 2
    return pools


def parse_ranges(spec, rom_len):
    out = []
    for part in spec.split(","):
        a, b = part.split("-")
        out.append((int(a, 0), min(int(b, 0), rom_len)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--ranges", default="0x499000-0x500000,0x460000-0x470000",
                     help="comma list of start-end hex ranges to scan")
    ap.add_argument("--min-chain", type=int, default=3)
    ap.add_argument("--target-categories", default="4,5,6,7,8,9,10,11,12,13,14,15",
                     help="comma list of category values to report every occurrence of")
    ap.add_argument("--context", type=int, default=1,
                     help="how many entries of surrounding pool context to print per hit")
    ap.add_argument("--readability-filter", action="store_true",
                     help="apply session 10's per-line real-text filter before tallying "
                          "(avg codes/line proxy via per-line length>=3, hiragana_ratio>=0.6, "
                          ">=3 category-0 codes) - without this flag, counts include session 9's "
                          "known false-positive periodic/arithmetic-progression runs (e.g. "
                          "0x4aed1e/0x4c77xx/0x4c84xx/0x4c90xx), which inflate rare-category "
                          "counts; see research note for the specific false-positive addresses")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        data = f.read()

    ranges = parse_ranges(args.ranges, len(data))
    targets = set(int(x, 0) for x in args.target_categories.split(","))

    cat_counter = Counter()
    total_codes = 0
    hits = []  # (addr_of_entry, category, index_in_entry, rendered_line, code)
    rejected_lines = 0

    for start, end in ranges:
        pools = scan_range(data, start, end, args.min_chain)
        for pool_start, entries, pool_end in pools:
            for off, entry_id, marker, lines, entry_end in entries:
                for line in lines:
                    if args.readability_filter:
                        cat0_codes = [c for c in line if (c >> 8) & 0xF == 0]
                        hr = hiragana_ratio(line)
                        if len(line) < 3 or len(cat0_codes) < 3 or hr < 0.6:
                            rejected_lines += 1
                            continue
                    rendered = "".join(render_code(c) for c in line)
                    for i, code in enumerate(line):
                        cat = (code >> 8) & 0xF
                        idx = (code & 0xFF) - 1
                        cat_counter[cat] += 1
                        total_codes += 1
                        if cat in targets:
                            hits.append((off, cat, idx, code, rendered))
    if args.readability_filter:
        print(f"# readability filter rejected {rejected_lines} line(s)")

    print(f"# scan_category_stats.py  rom={args.rom}")
    print(f"# ranges={ranges}  min_chain={args.min_chain}")
    print(f"# total codes tallied: {total_codes}\n")

    print("category frequency (all categories seen):")
    for cat, n in sorted(cat_counter.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / total_codes if total_codes else 0.0
        print(f"  category {cat:2d}: {n:6d}  ({pct:5.2f}%)")

    print(f"\noccurrences of target categories {sorted(targets)}: {len(hits)} total\n")
    by_cat = {}
    for off, cat, idx, code, rendered in hits:
        by_cat.setdefault(cat, []).append((off, idx, code, rendered))
    for cat in sorted(by_cat):
        occ = by_cat[cat]
        distinct_idx = sorted(set(i for _, i, _, _ in occ))
        print(f"category {cat}: {len(occ)} occurrence(s), "
              f"{len(distinct_idx)} distinct index/indices {distinct_idx}")
        for off, idx, code, rendered in occ:
            print(f"    entry@0x{off:06x}  code=0x{code:04x}  idx={idx:4d}  "
                  f"context: {rendered}")
        print()


if __name__ == "__main__":
    main()
