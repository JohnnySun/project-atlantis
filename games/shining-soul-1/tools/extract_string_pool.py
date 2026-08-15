#!/usr/bin/env python3
"""Read-only static ROM extraction (session 9): walk a contiguous run of
session-8-format strings forward from a known-good anchor.

While sanity-checking scan_sentence_strings.py's raw output against the
two session-8-confirmed strings (0x499b1a "職業を選んでください",
0x499b3e "色を選んでください"), this session found that both are
preceded by a constant 16-bit marker value 0x0001 two bytes before the
string's own start, and that the bytes after each string's 0x0000
terminator are zero-padded up to the next entry's 0x0001 marker - i.e.
this ROM region is a tightly packed, *sequential* string pool/table:

    [u16 marker=0x0001] [u16 code]* [u16 0x0000 terminator] [zero padding]
    [u16 marker=0x0001] [u16 code]* [u16 0x0000 terminator] [zero padding]
    ...

The zero-padding length is NOT constant (varies per entry - looks like
leftover space rather than a fixed-size slot), so entries cannot be
enumerated by a fixed stride; this script walks them one at a time,
searching forward past each terminator for the next 0x0001 marker.

This IS the "pointer table" analog the task asked to look for: instead
of an array of ROM addresses pointing at scattered strings, the strings
are simply laid out back-to-back in one heap and can be enumerated by
sequential walk from any known start - no separate pointer array exists
(or was found) that points into this pool; see research/
obj-sentence-string-pool.md "pointer table search" section for the
explicit 4-byte-address search that came up empty.

Usage:
    python3 extract_string_pool.py <rom.gba> [--start 0x499a48]
        [--max-entries 2000] [--max-gap 64]

--max-gap bounds how far past a terminator we'll scan zero-padding
looking for the next 0x0001 marker before concluding the pool has ended.

Read-only: only opens the ROM file for reading.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_sentence_strings import decode_code, render_code, GOJUON  # noqa: E402

# Session 9 finding: the field immediately before each string is NOT a
# constant sentinel (an earlier draft of this tool assumed marker==1
# always, because both session-8-known strings happen to have marker=1).
# It varies (observed 1 and 2 so far) and behaves like a *line count*:
# marker=N means "read N consecutive NUL-terminated code arrays" before
# looking for padding/the next entry. This matches the observed data
# exactly (a marker=2 entry at ROM 0x499ca8 contains two back-to-back
# NUL-terminated runs with no padding between them, and decodes as two
# separate, independently plausible sentence fragments). Kept as a
# hypothesis - only cross-checked against a handful of entries, see
# research note.
MAX_MARKER = 8  # sanity bound; reject markers outside 1..MAX_MARKER as "not an entry"


def read_u16(data, off):
    return data[off] | (data[off + 1] << 8)


def _read_lines(data, j, n, marker, max_codes):
    """Read `marker` consecutive NUL-terminated halfword code arrays
    starting at file offset j. Returns (lines, end_offset, ok)."""
    lines = []
    ok = True
    for _line in range(marker):
        codes = []
        while True:
            if j + 2 > n:
                ok = False
                break
            code = read_u16(data, j)
            if code == 0:
                j += 2
                break
            codes.append(code)
            j += 2
            if len(codes) > max_codes:
                ok = False
                break
        if not ok:
            break
        lines.append(codes)
    return lines, j, ok


def walk_pool(data, start, max_entries=2000, max_gap=64, max_codes=200):
    """Walk forward from `start` as long as either of two observed entry
    headers holds. Returns (entries, end_offset). Each entry:
    (marker_offset, id_or_None, marker_value, [line codes, ...], entry_end).

    Two header shapes seen in the wild (session 9), both followed by the
    same marker+lines+terminator(s) body:
      plain:       [u16 marker(1..MAX_MARKER)]
      id-prefixed: [u16 id][u16 type][u16 0][u16 0][u16 marker(1..MAX_MARKER)]
    The plain shape covers ROM 0x499a48-0x49a7f0 (100 entries); the
    id-prefixed shape was found immediately after that (starting
    0x49a7f8) with a per-entry 8-byte header whose first halfword looks
    like a message/group ID (observed repeating twice per ID: 0x0009
    then 0x000a, ...) - read as "each ID has 2 variant lines", consistent
    with common RPG flavor-text randomization, but NOT independently
    confirmed (single region observed, see research note).
    """
    entries = []
    pos = start
    n = len(data)
    while len(entries) < max_entries and pos + 2 <= n:
        entry_id = None
        marker_pos = pos
        marker = read_u16(data, pos) if pos + 2 <= n else -1
        if not (1 <= marker <= MAX_MARKER):
            # try id-prefixed header
            if pos + 10 <= n and read_u16(data, pos + 4) == 0 and read_u16(data, pos + 6) == 0:
                cand_marker = read_u16(data, pos + 8)
                if 1 <= cand_marker <= MAX_MARKER:
                    entry_id = read_u16(data, pos)
                    marker_pos = pos + 8
                    marker = cand_marker
                else:
                    break
            else:
                break
        j = marker_pos + 2
        lines, j, ok = _read_lines(data, j, n, marker, max_codes)
        if not ok or not lines or not any(lines):
            break
        entries.append((pos, entry_id, marker, lines, j))
        # skip zero padding looking for the next entry's header
        k = j
        gap = 0
        while k + 2 <= n and read_u16(data, k) == 0 and gap < max_gap:
            k += 2
            gap += 2
        nxt = read_u16(data, k) if k + 2 <= n else -1
        if 1 <= nxt <= MAX_MARKER:
            pos = k
        elif (k + 10 <= n and read_u16(data, k + 4) == 0 and read_u16(data, k + 6) == 0
              and 1 <= read_u16(data, k + 8) <= MAX_MARKER):
            pos = k
        else:
            pos = k
            break
    return entries, pos


def render_entry(codes):
    return "".join(render_code(c) for c in codes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--start", default="0x499a48", help="hex/dec offset of first marker")
    ap.add_argument("--max-entries", type=int, default=2000)
    ap.add_argument("--max-gap", type=int, default=64)
    ap.add_argument("--show", type=int, default=40)
    ap.add_argument("--out", default=None, help="optional path to write full entry dump")
    args = ap.parse_args()

    start = int(args.start, 0)
    with open(args.rom, "rb") as f:
        data = f.read()

    entries, end = walk_pool(data, start, args.max_entries, args.max_gap)

    print(f"# extract_string_pool.py  rom={args.rom}  start=0x{start:06x}")
    print(f"# {len(entries)} entries found, pool ends near 0x{end:06x} "
          f"(span 0x{start:06x}-0x{end:06x} = {end - start} bytes)\n")

    out_lines = []
    for off, entry_id, marker, lines, entry_end in entries:
        rendered = " / ".join(render_entry(c) for c in lines)
        id_str = f"id={entry_id} " if entry_id is not None else ""
        line = f"0x{off:06x}  {id_str}marker={marker}  {rendered}"
        out_lines.append(line)

    for line in out_lines[: args.show]:
        print(line)
    if len(out_lines) > args.show:
        print(f"... ({len(out_lines) - args.show} more entries, use --show/--out for all)")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        print(f"\nwrote {len(out_lines)} entries to {args.out}")


if __name__ == "__main__":
    main()
