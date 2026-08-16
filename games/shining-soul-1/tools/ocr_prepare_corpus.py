#!/usr/bin/env python3
"""Read-only recon (session 13): enumerate every corpus LINE (not entry -
entries can be multi-line, per extract_string_pool.py) across the two
known-good pool ranges (dialogue pool, monster-names, same as
decode_strings.py POOLS), computing each line's own ROM start address the
same way decode_strings.entry_to_record() does, and write a TSV the OCR
pipeline (ocr_render_lines.py, ocr_align_vote.py) can consume.

Deliberately does NOT reuse decode_strings.line_passes_filter() (advisor
guidance, session 13): that filter requires >=60% of a line's category-0
codes to already be individually known, which is circular for this
task's purpose (we're trying to learn NEW identities, so a filter tuned
to "this line is already mostly readable" systematically discards lines
that are exactly where an unmapped kanji shows up next to few kana
anchors). Instead this script applies a much looser structural filter
(>=1 code in categories 1-4 - the whole point, since those are the
tables with populated-pixel-but-unknown-identity entries - and >=2
already-confirmed anchor codes for the alignment algorithm to lock onto)
and leaves noise rejection to the edit-distance quality gate in
ocr_align_vote.py, which is what the reference implementation
(games/golden-sun-the-lost-age/tools/infer_ja_codepage.rb) does too.

Also skips any line containing one of the 4 known "high-bit anomaly"
codes session 12 flagged (0x8000/0x4000 pattern, bits above the category
nibble set) - those are documented as not even fitting the known code
format, so a glyph render for them would be nonsense input to OCR.

Usage:
    python3 ocr_prepare_corpus.py <rom> --out corpus_lines.tsv
        [--min-chain 3] [--min-anchors 2]

Read-only: only opens the ROM file for reading.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode_strings import find_pools, POOLS  # noqa: E402
from scan_sentence_strings import decode_code, GOJUON  # noqa: E402


def is_confirmed_anchor(code):
    """A code this session can already render with certainty - used only
    to judge whether a line has enough anchors for the alignment
    algorithm to lock onto, not to decide what gets rendered (every
    in-range glyph is rendered regardless, see ocr_render_lines.py)."""
    category, glyph_entry_index, char_idx = decode_code(code)
    if category != 0:
        return False
    return 0 <= char_idx <= 70  # confirmed gojuon range (session 7/8)


def has_vote_target(codes):
    for code in codes:
        category, _idx, _char_idx = decode_code(code)
        if category in (1, 2, 3, 4):
            return True
    return False


def has_anomaly(code):
    return (code >> 12) != 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-chain", type=int, default=3)
    ap.add_argument("--min-anchors", type=int, default=2,
                     help="minimum confirmed-anchor codes (gojuon) required in a line")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        data = f.read()

    n_lines_total = 0
    n_kept = 0
    n_skip_no_target = 0
    n_skip_few_anchors = 0
    n_skip_anomaly = 0

    with open(args.out, "w", encoding="utf-8") as out:
        for pool_name, start, end in POOLS:
            pools = find_pools(data, start, end, args.min_chain)
            for pool_start, entries, pool_end in pools:
                for off, entry_id, marker, lines, _entry_end in entries:
                    line_start = off + (10 if entry_id is not None else 2)
                    for codes in lines:
                        n_lines_total += 1
                        line_len_bytes = 2 * (len(codes) + 1)
                        this_line_addr = line_start
                        line_start += line_len_bytes
                        if not codes:
                            continue
                        if any(has_anomaly(c) for c in codes):
                            n_skip_anomaly += 1
                            continue
                        if not has_vote_target(codes):
                            n_skip_no_target += 1
                            continue
                        n_anchors = sum(1 for c in codes if is_confirmed_anchor(c))
                        if n_anchors < args.min_anchors:
                            n_skip_few_anchors += 1
                            continue
                        string_id = f"{pool_name}:0x{off:06x}:{this_line_addr:06x}"
                        codes_hex = " ".join(f"{c:04x}" for c in codes)
                        out.write(f"{string_id}\t0x{this_line_addr:06x}\t{codes_hex}\n")
                        n_kept += 1

    print(f"# ocr_prepare_corpus.py  rom={args.rom}")
    print(f"# {n_lines_total} total lines walked across {[p[0] for p in POOLS]}")
    print(f"# kept {n_kept}")
    print(f"# skipped: {n_skip_no_target} (no cat1-4 code), "
          f"{n_skip_few_anchors} (<{args.min_anchors} confirmed anchors), "
          f"{n_skip_anomaly} (high-bit anomaly code)")
    print(f"# wrote {args.out}")


if __name__ == "__main__":
    main()
