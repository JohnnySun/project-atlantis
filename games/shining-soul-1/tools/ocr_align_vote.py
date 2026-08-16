#!/usr/bin/env python3
"""Read-only recon (session 13): the alignment/voting half of the
render+OCR+corpus-wide-statistical-alignment pattern documented in
.agents/skills/gba-localization/SKILL.md "Two separate problems" section,
ported from the reference implementation
games/golden-sun-the-lost-age/tools/infer_ja_codepage.rb (read but not
modified - Golden Sun workspaces are out of scope for this game).

Differences from the reference, all forced by how this game's glyph
system differs from Golden Sun's single-byte codepage (see module
docstrings in decode_strings.py / scan_sentence_strings.py for the
background this assumes):
  - The reference's "unit" is a single byte value indexing one flat
    codepage. Here each source position is a (category, glyph_entry_index)
    pair - votes are keyed on that pair, not a single scalar, because the
    same glyph_entry_index means a different glyph in each of the five
    category pools.
  - "Known" identity lookup reuses decode_strings.decode_glyph() as-is
    (both its confirmed AND provisional tiers count as "known" for
    alignment-anchor purposes - more known anchors improve alignment
    quality regardless of which tier supplied them), not a fresh lookup
    table.
  - The substitution-cost "is this a plausible candidate" bonus is
    generalized from the reference's CJK-ideograph-only check to also
    accept kana ranges for category-0 positions (advisor guidance,
    session 13: cheap to also try recovering unmapped category-0 slots,
    e.g. the small-kana 71-78 gap, via the same mechanism) - kanji
    categories (1/2/3/4) still only ever accept CJK ideographs as
    candidates, exactly like the reference.

Algorithm (unchanged from the reference): per corpus line, build a
"source" sequence of (pos_key, known_char_or_None) from its glyph codes
(known_char run through NFKD decomposition, same as the OCR target text -
this is load-bearing for voiced/semi-voiced kana, which canonically
decompose to base+combining-mark; skipping this on either side silently
breaks every dakuten/handakuten alignment). Run a Levenshtein-style edit
distance / alignment against the NFKD-decomposed OCR reading, with
substitution cost 0 for an exact match, 0.15 for "unknown position landed
on a plausible candidate character for that category", 0.8 for "unknown
position landed on something implausible", 1.5 for "known position
disagrees with a different known character" (a real misalignment, not a
vote). Reject the whole line if quality = edit_cost / max(len(source),
len(target)) exceeds a threshold (this is the noise filter - see
ocr_prepare_corpus.py's docstring for why the corpus itself is NOT
pre-filtered for "looks like real text"). Backtrack accepted lines'
alignments and accumulate one vote per (pos_key, candidate_char) pair.

Usage:
    python3 ocr_align_vote.py <rom> --corpus corpus_lines.tsv \
        --ocr ocr_results.tsv --quality-threshold 0.40 \
        --out-votes votes.tsv [--verbose-rejects]

Read-only: only opens the ROM file for reading.
"""
import argparse
import os
import sys
import unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decode_strings import decode_glyph  # noqa: E402
from scan_sentence_strings import decode_code  # noqa: E402


def cjk(ch):
    cp = ord(ch)
    return (0x3400 <= cp <= 0x9FFF) or (0xF900 <= cp <= 0xFAFF)


def kana(ch):
    cp = ord(ch)
    return (0x3041 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF)


def plausible_candidate(category, ch):
    if ch.isspace():
        return False
    if category == 0:
        return kana(ch)
    return cjk(ch)


def normalized_chars(text):
    return [c for c in unicodedata.normalize("NFKD", text) if not c.isspace()]


def build_source(codes):
    """List of (pos_key, known_char_or_None) with known chars NFKD-expanded
    to possibly multiple entries sharing the same pos_key (mirrors the
    reference's `known.map {|char| [unit, char]}` - handles a known glyph
    that canonically decomposes, e.g. any voiced-kana entry in GOJUON)."""
    source = []
    for code in codes:
        category, glyph_entry_index, char_idx = decode_code(code)
        char, _tier = decode_glyph(category, glyph_entry_index, char_idx)
        pos_key = (category, glyph_entry_index)
        if char is not None:
            for c in normalized_chars(char):
                source.append((pos_key, c))
        else:
            source.append((pos_key, None))
    return source


def align(source, target, threshold):
    n, m = len(source), len(target)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = cost[i][j]
            if cur == INF:
                continue
            if i < n and cur + 1 < cost[i + 1][j]:
                cost[i + 1][j] = cur + 1
                back[i + 1][j] = (i, j, "delete")
            if j < m and cur + 1 < cost[i][j + 1]:
                cost[i][j + 1] = cur + 1
                back[i][j + 1] = (i, j, "insert")
            if i < n and j < m:
                pos_key, known = source[i]
                tgt = target[j]
                if known == tgt:
                    sub = 0.0
                elif known is None and plausible_candidate(pos_key[0], tgt):
                    sub = 0.15
                elif known is None:
                    sub = 0.8
                else:
                    sub = 1.5
                if cur + sub < cost[i + 1][j + 1]:
                    cost[i + 1][j + 1] = cur + sub
                    back[i + 1][j + 1] = (i, j, "substitute")
    quality = cost[n][m] / max(n, m, 1)
    if quality > threshold:
        return quality, None
    pairs = []
    i, j = n, m
    while i > 0 or j > 0:
        prev = back[i][j]
        if prev is None:
            break
        pi, pj, action = prev
        if action == "substitute":
            pairs.append((source[pi], target[pj]))
        i, j = pi, pj
    return quality, pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--corpus", required=True, help="ocr_prepare_corpus.py TSV output")
    ap.add_argument("--ocr", required=True, help="vision_ocr_bin TSV output (path\\ttext)")
    ap.add_argument("--quality-threshold", type=float, default=0.40)
    ap.add_argument("--out-votes", required=True)
    ap.add_argument("--verbose-rejects", action="store_true")
    args = ap.parse_args()

    ocr_by_id = {}
    with open(args.ocr, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            path, text = line.split("\t", 1)
            base = os.path.splitext(os.path.basename(path))[0]
            ocr_by_id[base] = text.replace("\\n", "")

    lines = []
    with open(args.corpus, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            string_id, addr_hex, codes_hex = line.split("\t")
            codes = [int(x, 16) for x in codes_hex.split()]
            safe_id = string_id.replace(":", "_").replace("/", "_")
            lines.append((string_id, safe_id, codes))

    votes = defaultdict(Counter)
    examples = defaultdict(list)
    n_total = 0
    n_no_ocr = 0
    n_accepted = 0
    n_rejected = 0
    qualities = []

    for string_id, safe_id, codes in lines:
        n_total += 1
        text = ocr_by_id.get(safe_id)
        if text is None:
            n_no_ocr += 1
            continue
        source = build_source(codes)
        target = normalized_chars(text)
        quality, pairs = align(source, target, args.quality_threshold)
        qualities.append(quality)
        if pairs is None:
            n_rejected += 1
            if args.verbose_rejects:
                print(f"REJECT q={quality:.2f} {string_id}  OCR={text!r}", file=sys.stderr)
            continue
        n_accepted += 1
        for (pos_key, known), tgt_char in pairs:
            if known is not None:
                continue
            if not plausible_candidate(pos_key[0], tgt_char):
                continue
            votes[pos_key][tgt_char] += 1
            if len(examples[pos_key]) < 5:
                examples[pos_key].append((string_id, text))

    qualities.sort()
    print(f"# {n_total} lines, {n_no_ocr} missing OCR output, "
          f"{n_accepted} accepted (quality<={args.quality_threshold}), {n_rejected} rejected")
    if qualities:
        mid = qualities[len(qualities) // 2]
        print(f"# quality distribution: min={qualities[0]:.2f} median={mid:.2f} "
              f"max={qualities[-1]:.2f}")
    print(f"# {len(votes)} distinct (category, glyph_entry_index) positions received >=1 vote")

    with open(args.out_votes, "w", encoding="utf-8") as out:
        out.write("category\tglyph_entry_index\ttotal_votes\ttop_char\ttop_count\t"
                   "second_char\tsecond_count\tall_candidates\texample_string_ids\n")
        for pos_key in sorted(votes):
            category, idx = pos_key
            counts = votes[pos_key].most_common()
            total = sum(c for _, c in counts)
            top_char, top_count = counts[0]
            second_char, second_count = (counts[1] if len(counts) > 1 else ("", 0))
            all_str = " ".join(f"{c}:{n}" for c, n in counts)
            ex_str = " ".join(sid for sid, _ in examples[pos_key])
            out.write(f"{category}\t{idx}\t{total}\t{top_char}\t{top_count}\t"
                      f"{second_char}\t{second_count}\t{all_str}\t{ex_str}\n")
    print(f"# wrote {args.out_votes}")


if __name__ == "__main__":
    main()
