#!/usr/bin/env python3
"""Read-only recon: scan a ROM for runs of bytes that decode as plausible
Shift-JIS (JIS X 0208 kanji/kana range + ASCII), to see whether game text
might be stored as plain(ish) Shift-JIS rather than a custom codepage.

This is a coarse heuristic only: it flags byte runs where every 1- or
2-byte unit is *structurally valid* Shift-JIS (falls in the lead/trail
byte ranges and decodes without error via Python's 'shift_jis' codec).
Structural validity is necessary but not sufficient - random binary data
can accidentally satisfy it for short runs, so only runs above a length
threshold (default 8 decoded characters) are reported, and results still
need eyeballing / cross-checking against actual glyph rendering.

Usage:
  python3 scan_sjis_runs.py <rom.gba> [--min-chars 8]
"""
import sys
import argparse


def is_sjis_lead(b):
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)


def is_sjis_trail(b):
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)


def is_halfwidth_kana(b):
    return 0xA1 <= b <= 0xDF


def scan(data, min_chars=8):
    runs = []
    i = 0
    n = len(data)
    cur_start = None
    cur_len = 0

    def flush():
        nonlocal cur_start, cur_len
        if cur_start is not None and cur_len >= min_chars:
            end = cur_start_byte_end
            try:
                text = data[cur_start:end].decode("shift_jis", errors="strict")
            except UnicodeDecodeError:
                text = data[cur_start:end].decode("shift_jis", errors="replace")
            runs.append((cur_start, end, cur_len, text))
        cur_start = None
        cur_len = 0

    cur_start_byte_end = 0
    while i < n:
        b = data[i]
        if is_sjis_lead(b) and i + 1 < n and is_sjis_trail(data[i + 1]):
            if cur_start is None:
                cur_start = i
                cur_len = 0
            cur_len += 1
            i += 2
            cur_start_byte_end = i
            continue
        if is_halfwidth_kana(b) or (0x20 <= b <= 0x7E):
            if cur_start is None:
                cur_start = i
                cur_len = 0
            cur_len += 1
            i += 1
            cur_start_byte_end = i
            continue
        flush()
        i += 1
    flush()
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--min-chars", type=int, default=8)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    data = open(args.rom, "rb").read()
    runs = scan(data, args.min_chars)
    runs.sort(key=lambda r: -r[2])
    print(f"{len(runs)} runs >= {args.min_chars} decoded chars\n")
    for start, end, length, text in runs[: args.limit]:
        preview = text.replace("\n", "\\n")[:80]
        print(f"0x{start:06x}-0x{end:06x} ({length} chars): {preview!r}")


if __name__ == "__main__":
    main()
