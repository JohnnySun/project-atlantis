#!/usr/bin/env python3
"""Read-only static ROM scan (session 9): enumerate NUL-terminated 16-bit
character-code arrays using the exact string format session 8 decoded
(see research/obj-sentence-string-format.md), as a *structural signature*
rather than tracing each string live via the debugger.

Format recap (session 8, confirmed on two independently-found strings,
"職業を選んでください" at ROM 0x499b1a and "色を選んでください" at
0x499b3e):
  - a string is a halfword-aligned array of 16-bit little-endian codes,
    terminated by 0x0000.
  - for each non-zero code:
        category          = (code >> 8) & 0xF   (glyph-pool selector)
        glyph_entry_index = (code & 0xFF) - 1    (index within that pool)
  - category 0 codes additionally decode to a further offset
    char_idx = glyph_entry_index - 1, which indexes the session-7 master
    glyph table (ROM 0x46abe4 + char_idx*0x80); char_idx 0-70 is the
    standard gojuon hiragana order (confirmed identical ordering used by
    the session-5 BG name-entry font table), so this script can render a
    human-readable hiragana substring for any category-0 code with
    char_idx in 0-70, which is the main tool for telling real strings
    from accidental noise.
  - category 2/3 codes are known to be kanji from a still-unsolved pool
    (session 8); this script records their raw (category, glyph_entry_index)
    pair but cannot render them.

This is a STRUCTURAL signature scan, not a semantic one - it will find
false positives (graphics/audio/code bytes that happen to satisfy the
byte-pattern constraints), the same way session 1's Shift-JIS structural
scan did. Do not trust raw candidate counts; always sample-check decoded
output by eye (see --sample / the companion research note).

Usage:
    python3 scan_sentence_strings.py <rom.gba> [--categories 0,2,3]
        [--min-codes 3] [--max-glyph-index 300] [--end 0x660000]
        [--sample 30] [--sort hiragana-ratio|length]

Read-only: only opens the ROM file for reading.
"""
import argparse
import sys

GOJUON = [
    "あ", "い", "う", "え", "お", "か", "き", "く", "け", "こ",
    "さ", "し", "す", "せ", "そ", "た", "ち", "つ", "て", "と",
    "な", "に", "ぬ", "ね", "の", "は", "ひ", "ふ", "へ", "ほ",
    "ま", "み", "む", "め", "も", "や", "ゆ", "よ", "ら", "り",
    "る", "れ", "ろ", "わ", "を", "ん", "が", "ぎ", "ぐ", "げ",
    "ご", "ざ", "じ", "ず", "ぜ", "ぞ", "だ", "ぢ", "づ", "で",
    "ど", "ば", "び", "ぶ", "べ", "ぼ", "ぱ", "ぴ", "ぷ", "ぺ",
    "ぽ",
]  # index 0-70, confirmed gojuon order (session 7/8 cross-check, 7 pts)

# Session 9, UNCONFIRMED (single supporting data point, see
# research/obj-sentence-string-pool.md "katakana range"): master glyph
# table layout description (session 7, obj-sentence-glyph-loader.md
# "index ~80 起：片假名，同樣順序") says katakana repeats the same
# gojuon order starting at char_idx 80. Applied here as a working
# hypothesis to make candidate output more readable during manual
# review, NOT as a confirmed codepage entry - treat any katakana in
# scan output as a plausibility aid, not ground truth.
KATAKANA = [
    "ア", "イ", "ウ", "エ", "オ", "カ", "キ", "ク", "ケ", "コ",
    "サ", "シ", "ス", "セ", "ソ", "タ", "チ", "ツ", "テ", "ト",
    "ナ", "ニ", "ヌ", "ネ", "ノ", "ハ", "ヒ", "フ", "ヘ", "ホ",
    "マ", "ミ", "ム", "メ", "モ", "ヤ", "ユ", "ヨ", "ラ", "リ",
    "ル", "レ", "ロ", "ワ", "ヲ", "ン", "ガ", "ギ", "グ", "ゲ",
    "ゴ", "ザ", "ジ", "ズ", "ゼ", "ゾ", "ダ", "ヂ", "ヅ", "デ",
    "ド", "バ", "ビ", "ブ", "ベ", "ボ", "パ", "ピ", "プ", "ペ",
    "ポ",
]  # would occupy char_idx 80-150 under this hypothesis
KATAKANA_BASE = 80

# Session 9, single unconfirmed data point: char_idx 79 (last slot of the
# session-7-described "small kana 71-79" block) decoded as "っ" (small
# tsu) inside a plausible real word ("さっき"). Not enough evidence for
# the other 8 slots (71-78) to guess an order, so only this one index is
# filled in; see research note.
SMALL_KANA_79 = "っ"


def decode_code(code):
    category = (code >> 8) & 0xF
    glyph_entry_index = (code & 0xFF) - 1
    char_idx = glyph_entry_index - 1
    return category, glyph_entry_index, char_idx


def render_code(code):
    category, glyph_entry_index, char_idx = decode_code(code)
    if category == 0:
        if 0 <= char_idx <= 70:
            return GOJUON[char_idx]
        if char_idx == 79:
            return SMALL_KANA_79
        if KATAKANA_BASE <= char_idx < KATAKANA_BASE + len(KATAKANA):
            return KATAKANA[char_idx - KATAKANA_BASE]
        return f"[g{glyph_entry_index}]"
    return f"[c{category}:{glyph_entry_index}]"


def is_plausible(code, allowed_categories, max_glyph_index):
    if code == 0:
        return False
    category, glyph_entry_index, _ = decode_code(code)
    if category not in allowed_categories:
        return False
    if glyph_entry_index < 0:
        return False
    if category == 0 and glyph_entry_index > max_glyph_index:
        return False
    return True


def scan(data, start, end, allowed_categories, min_codes, max_glyph_index,
         max_run=200):
    candidates = []
    i = start
    while i + 2 <= end:
        codes = []
        j = i
        ok = True
        while True:
            if j + 2 > end:
                ok = False
                break
            code = data[j] | (data[j + 1] << 8)
            if code == 0:
                break
            if not is_plausible(code, allowed_categories, max_glyph_index):
                ok = False
                break
            codes.append(code)
            j += 2
            if len(codes) > max_run:
                ok = False
                break
        if ok and len(codes) >= min_codes:
            candidates.append((i, codes))
            i = j + 2  # skip past the 0x0000 terminator
        else:
            i += 2
    return candidates


def hiragana_ratio(codes):
    cat0 = [c for c in codes if (c >> 8) & 0xF == 0]
    if not cat0:
        return 0.0
    hits = sum(1 for c in cat0 if 0 <= (c & 0xFF) - 2 <= 70)
    return hits / len(cat0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--categories", default="0,2,3",
                     help="comma list of allowed category nibbles (default: 0,2,3, "
                          "the only ones session 8 observed)")
    ap.add_argument("--min-codes", type=int, default=3)
    ap.add_argument("--max-glyph-index", type=int, default=300,
                     help="upper bound on glyph_entry_index for category-0 codes "
                          "(master glyph table confirmed to ~259 entries, session 7)")
    ap.add_argument("--start", default="0x0", help="hex/dec start offset")
    ap.add_argument("--end", default="0x660000",
                     help="hex/dec end offset (default: end of ROM's used range, "
                          "per session-1 entropy scan - rest is 0xFF padding)")
    ap.add_argument("--sample", type=int, default=30,
                     help="print this many top candidates by hiragana ratio then length")
    ap.add_argument("--sort", choices=["hiragana-ratio", "length"], default="hiragana-ratio")
    ap.add_argument("--dump-all", action="store_true",
                     help="print every candidate, not just --sample (for piping to a file)")
    args = ap.parse_args()

    allowed = set(int(x, 0) for x in args.categories.split(","))
    start = int(args.start, 0)
    end = int(args.end, 0)

    with open(args.rom, "rb") as f:
        data = f.read()
    end = min(end, len(data))

    candidates = scan(data, start, end, allowed, args.min_codes, args.max_glyph_index)

    print(f"# scan_sentence_strings.py  rom={args.rom}")
    print(f"# range=0x{start:06x}-0x{end:06x}  categories={sorted(allowed)}  "
          f"min_codes={args.min_codes}  max_glyph_index={args.max_glyph_index}")
    print(f"# {len(candidates)} raw candidates\n")

    scored = []
    for off, codes in candidates:
        hr = hiragana_ratio(codes)
        scored.append((hr, len(codes), off, codes))

    if args.sort == "hiragana-ratio":
        scored.sort(key=lambda t: (-t[0], -t[1]))
    else:
        scored.sort(key=lambda t: -t[1])

    n_show = len(scored) if args.dump_all else args.sample
    for hr, length, off, codes in scored[:n_show]:
        rendered = "".join(render_code(c) for c in codes)
        print(f"0x{off:06x}  len={length:3d}  hiragana_ratio={hr:.2f}  {rendered}")

    if not args.dump_all:
        print(f"\n(showing top {n_show} of {len(scored)}; use --dump-all to print everything)")


if __name__ == "__main__":
    main()
