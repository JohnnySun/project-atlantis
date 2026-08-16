#!/usr/bin/env python3
"""Read-only decoder (session 12, extended session 13): walk the two known
OBJ-sentence string pools (dialogue/prompt pool, monster/enemy-name pool -
see README.md sessions 9-11) and decode every NUL-terminated 16-bit code
array into the project's *local source table* format
(`docs/TRANSLATION-LEDGER.md` / `.agents/skills/gba-localization/SKILL.md`
"Recover source text locally"):

    {"string_id": ..., "locale": "ja", "text": "...", "provenance": "..."}

one JSON object per line, written to `research/shining-soul-1-decoded.jsonl`.

This is the first tool in this game's workspace that turns the fully-solved
code->(category, glyph_entry_index) format (session 8,
research/obj-sentence-string-format.md) into actual Unicode text rather
than a pixel render or a `[c#:N]` debug placeholder - it is the bridge
between "text system reverse-engineered" (sessions 1-11) and "translatable
source table" (this session, ROADMAP milestone 1's last checkbox).

## Two very different kinds of "known" glyph, kept explicitly distinct

Per the task that produced this tool: knowing a glyph's ROM pixel-table
address is NOT the same as knowing what Unicode character it is. This
decoder tracks THREE tiers per glyph, and only tier 1/2 ever produce real
characters - everything else becomes a literal `{unmapped_glyph:C:I}"`
placeholder (never a silent guess, never a dropped character):

1. **confirmed** - multiple independent, zero-free-parameter-fit data
   points (addresses, string-code cross-references, or both). This is:
   - category 0 (kana), char_idx 0-70: the standard gojuon hiragana table,
     GOJUON in scan_sentence_strings.py, confirmed with 7 independent
     address points (session 7/8).
   - 12 specific kanji identities confirmed one-at-a-time across sessions
     7/8/10/11 by cross-referencing a known on-screen word/sentence against
     its live string code (see KANJI_MAP below for the exact provenance of
     each). These are NOT a solved kanji codepage - they are 12 isolated
     points inside four large, still-otherwise-unmapped kanji tables
     (categories 1-4, each already known to span 100+ populated entries -
     see research/obj-sentence-kanji-categories.md and
     obj-sentence-category4-and-dispatch-table.md). Every other
     category-1/2/3/4 code renders as a placeholder, even though a real,
     located pixel glyph exists for it (base+index*0x80) - this is exactly
     the distinction the task called out: pixel location != Unicode
     identity.
2. **provisional** - a single real-sentence data point (or a documented,
   ordered-layout hypothesis with no independent address cross-check).
   Used for real text (not placeholdered) because refusing to decode
   virtually all katakana content - which is what most monster/item names
   in this game consist of - would make the string pool's most
   translation-ready content undecodable for no good reason, and because
   the hypothesis has real corroborating evidence (see each constant's
   docstring below). Every string that uses any provisional-tier glyph is
   flagged in its `provenance` field so a translator/reviewer knows to
   treat it with correspondingly less certainty than a category-0
   gojuon-only string - this is the "preserve the distinction" mechanism
   the task asked for, applied per-record rather than by dropping the
   content. **Session 13 added a second, larger source of provisional
   entries**: KANJI_MAP_OCR_PROVISIONAL, 23 kanji identities (18 category
   1, 4 category 3, plus 1 manual contextual-override entry) found by
   rendering ~200 real corpus sentences, running Apple Vision OCR on
   them, and statistically aligning/voting per the
   render+OCR+corpus-wide-alignment pattern in
   `.agents/skills/gba-localization/SKILL.md` - see that dict's own
   docstring for the full methodology (which started from a 27-candidate
   vote-accepted set before a second, semantic-context rejection round
   removed 4 systematic misreads - see the dict's own comments),
   acceptance bar, and explicitly rejected false-positive candidates.
   These are evidentially weaker than
   an address cross-reference (KANJI_MAP) but stronger than a single
   unverified layout guess, corroborated across multiple independent real
   sentences and eyeballed against the actual ROM pixels before
   inclusion - they stay in this tier, never "confirmed", per this
   project's standing "OCR output is candidate evidence, not ground
   truth" rule.
3. **unmapped** - no recorded identity at all (includes all of categories
   5-15, confirmed in session 11 to not even have a glyph pool attached in
   this ROM revision; all non-KANJI_MAP/non-KANJI_MAP_OCR_PROVISIONAL
   indices in categories 1-4; and any category-0 char_idx outside the
   confirmed/provisional ranges above). Renders as
   `{unmapped_glyph:<category>:<glyph_entry_index>}`.

Reuses (does not reimplement) the pool-walking and code-decoding logic
sessions 8-11 already wrote and validated:
  - extract_string_pool.walk_pool() / MAX_MARKER
  - scan_string_pools.looks_like_header_start() (chained-pool discovery)
  - scan_sentence_strings.decode_code() / GOJUON / KATAKANA /
    KATAKANA_BASE / SMALL_KANA_79

Scope: this session deliberately does NOT re-run a full-ROM 0x000000-
0x660000 chain scan. Session 9 already did that (see
research/obj-sentence-string-pool.md "沒有找到指標表" / summary point 4)
and found the two ranges scanned here account for essentially all of the
real content; the remaining ~208 pools/504 entries found elsewhere were
sample-checked and judged almost entirely false positives (internal
gojuon/katakana completeness-check debug tables, periodic graphics data).
Re-spending this session's budget re-confirming that would crowd out the
actual deliverable. If a future session wants to broaden coverage, rerun
scan_string_pools.py across the full range first and manually vet any new
pool before pointing this tool at it - do not just widen POOLS blindly.

Usage:
    python3 decode_strings.py <rom.gba> [--out ../research/shining-soul-1-decoded.jsonl]
        [--min-chain 3]

Read-only: only opens the ROM file for reading.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_string_pool import walk_pool, MAX_MARKER  # noqa: E402
from scan_string_pools import looks_like_header_start  # noqa: E402
from scan_sentence_strings import (  # noqa: E402
    decode_code, GOJUON, KATAKANA, KATAKANA_BASE, SMALL_KANA_79,
)

# Session 12 (this session), provisional tier, single-source evidence:
# code 0x00f9 appears TWICE in the confirmed real dialogue-pool sentence at
# ROM 0x499e18 ("ゲームを終了するとセーブされます", see
# research/obj-sentence-category4-and-dispatch-table.md "資料點 1"), in
# exactly the two positions a human reader would expect "ー" (chōonpu/long
# vowel mark): ゲ[0x00f9]ム and セ[0x00f9]ブ = ゲーム/セーブ, and that
# session's independently rendered pixel image was human-verified to show
# exactly those two words. decode_code(0x00f9) -> category=0,
# glyph_entry_index=248, char_idx=247. Two independent occurrences inside
# one human-verified real string is the same evidential shape as the
# katakana hypothesis below (an ordered/contextual inference, not an
# address cross-check), so it is kept in the same "provisional" tier
# rather than promoted to "confirmed" or left unmapped.
CHOONPU_CHAR_IDX = 247
CHOONPU_CHAR = "ー"

KANJI_MAP = {
    # (category, glyph_entry_index) -> confirmed Unicode identity.
    # category 1, base 0x474584 (research/obj-sentence-kanji-categories.md):
    (1, 7): "剣",   # "剣士" job-select label, sprite-position + string-code
    (1, 8): "士",   # cross-reference (session 10)
    # category 2, base 0x47dfa4:
    (2, 137): "職",  # "職業を選んでください" job-select sentence (session 8)
    (2, 138): "色",  # "色を選んでください" color-select sentence (session 10)
    # category 3, base 0x4879c4:
    (3, 234): "業",  # same job-select sentence as 職 (session 8)
    (3, 12): "選",   # "...選んでください" shared suffix, both sentences (session 8)
    # category 4, base 0x4913e4 (research/obj-sentence-category4-and-dispatch-table.md,
    # all four identified via corpus-validation renders read against real
    # dialogue-pool sentences, session 11):
    (4, 16): "了",  # "ゲームを終了する..." (0x499e1a)
    (4, 18): "失",  # "共に失われていく..." (0x49e42c)
    (4, 19): "別",  # "東西に別れた..." (0x49cd60)
    (4, 28): "妨",  # "...動きを妨害してきます" (0x49d594)
    (4, 29): "害",  # same sentence, "妨害" two-character compound
    (4, 30): "難",  # "...仕掛ける事が難しくなります" (0x49da64)
}

# Session 13, provisional tier, corpus-wide OCR statistical alignment
# (games/shining-soul-1/tools/ocr_render_lines.py -> ocr_align_vote.py ->
# ocr_contact_sheet.py; method follows .agents/skills/gba-localization/
# SKILL.md "render-whole-string + OCR + corpus-wide statistical alignment",
# ported from games/golden-sun-the-lost-age/tools/infer_ja_codepage.rb -
# see that file's docstring comparison in ocr_align_vote.py for what
# differs). 267 real corpus lines (>=1 category-1/2/3/4 code, >=2
# already-confirmed gojuon anchors) were rendered to grayscale PNGs and
# OCR'd with Apple Vision (ja-JP, .accurate), then each OCR reading was
# aligned against its glyph-code sequence with an edit-distance algorithm
# that treats already-known glyphs (gojuon + this file's own KANJI_MAP) as
# anchors and lets unknown (category, glyph_entry_index) positions float
# to whichever OCR character lines up there; only alignments with
# normalized edit-distance quality <=0.32 were kept (200/267 lines), and
# only (category, glyph_entry_index) positions with >=4 accepted votes AND
# a dominant candidate holding >=75% of those votes were considered at
# all - deliberately stricter than the reference implementation's 0.6
# ratio bar, because a first eyeball pass at 0.6 surfaced real false
# positives (see "explicitly rejected" note below) that a straight vote
# count did not catch on its own; every accepted entry below was ALSO
# individually eyeballed against a Hiragino-Sans-GB rendering of the
# claimed character next to the actual ROM glyph pixels
# (ocr_contact_sheet.py output) before being added here - this is
# candidate evidence corroborated across many independent real sentences,
# not an individually address-verified identity like KANJI_MAP above, so
# it stays in "provisional" per this project's standing OCR rule ("OCR
# output is candidate evidence, not ground truth" - never promote it to
# "confirmed" no matter how unanimous the vote).
#
# Explicitly rejected during the eyeball pass despite meeting a looser
# vote bar (recorded so a future session does not re-propose them without
# new evidence): category 0 (kana) candidates were dropped entirely this
# round - two different category-0 positions (glyph_entry_index 166 and
# 234) both voted near-unanimously for "ー" (chōonpu) but their actual ROM
# glyph pixels do NOT look like a horizontal dash (they look like short
# hook/tick shapes, nothing like the existing confirmed idx-247 "ー"
# glyph) - Vision appears to default to "ー" as a generic guess for
# strokes it cannot otherwise classify, which would make any bare vote
# count for it structurally unreliable regardless of tally. Two katakana
# candidates (cat0 idx156 "イ", idx249 "ツ") were similarly rejected on
# shape-mismatch grounds. (1, 184) "口" hit 3/3=100% but its ROM glyph is
# a near-empty single dot, obviously not a box-shaped 口 - a reminder that
# 100% agreement on a tiny vote count is not the same as a real signal.
#
# A second, more consequential rejection round happened AFTER the shape
# eyeball pass: re-decoding ~90 real corpus sentences with the initial
# 27-entry table (advisor guidance, session 13 - "re-decode 10-20 newly-
# clean sentences and read them for fluency") turned up FOUR category-3
# entries that had cleared both the vote-count/ratio bar and the shape
# eyeball, yet made every sentence they appeared in read as broken
# Japanese once put in context - a systematic OCR misread each vote count
# alone could not catch (advisor's warning: "OCR misreading X as Y twenty
# times produces twenty consistent wrong votes"). All four were removed
# from this dict entirely (not replaced with a guessed correct answer,
# per this project's standing rule against inventing identities):
#   - (3, 19) "加" (4 votes, 75%): every real occurrence is "...を加すため
#     に" / "...加したのですか" - "加す"/"加した" are not real verb forms
#     (加える conjugates to 加えた/加えて, never 加した). Plausible actual
#     readings include 課す/化す/貸す, none confirmed.
#   - (3, 26) "油" (6 votes, 100%): every real occurrence places it
#     immediately after a noun/pronoun and before a particle - "ボク油の
#     手で", "あなた油だけです", "士油が" - the exact distribution
#     expected of a PLURAL/GROUP SUFFIX (something like 達/たち), not the
#     noun 油 ("oil"), which cannot grammatically sit in that slot at all.
#   - (3, 56) "飲" (4 votes, 100%): occurrences include "...に大ダメージ"
#     (someone/something takes big damage) and "...の防御力が下がる"
#     (something's defense drops) - 飲 ("drink") cannot take damage or
#     have a defense stat; the real character is far more likely a noun
#     like 敵/魔物/族 (enemy/monster/race).
#   - (3, 216) "背" (3 votes, 75%): its one clean context is "[X]物がい
#     っぱいです" ("[X]-mono is full") - a bag/inventory-full message.
#     背物 is not a Japanese word; 荷物 ("luggage/cargo") fits perfectly
#     and was in fact OCR's own SECOND-place candidate at this position
#     (1/4 votes) - the correct reading was very likely sitting right
#     there in the vote tally, just not the plurality winner.
# None of these four are re-proposed with the "more likely" alternative
# substituted in - that would just be trading one unverified guess for
# another. They are simply unmapped again pending independent evidence
# (an address cross-reference, or a corpus-wide OCR pass with a different
# rendering/threshold that produces a cleaner vote). This whole episode is
# the strongest argument in this session for advisor guidance step 7:
# vote tallies validate agreement, not correctness, and only reading the
# decoded output back in context - not the raw vote numbers - caught it.
KANJI_MAP_OCR_PROVISIONAL = {
    # category 1, base 0x474584:
    (1, 6): "神", (1, 19): "光", (1, 25): "力", (1, 27): "気", (1, 31): "物",
    (1, 35): "具", (1, 43): "来", (1, 52): "手", (1, 55): "何", (1, 62): "大",
    (1, 117): "上", (1, 124): "下", (1, 133): "防", (1, 135): "本", (1, 137): "見",
    (1, 222): "中", (1, 226): "地", (1, 235): "界",
    # category 3, base 0x4879c4:
    (3, 40): "入", (3, 100): "立", (3, 133): "陸", (3, 146): "出",
    # Not an OCR vote winner - a manual contextual override found while
    # spot-checking the (1, 133) "防" entry above. OCR's plurality vote
    # for (1, 134) was "骨" (6/9 = 67%, below this round's 75% acceptance
    # bar, so it was never a candidate on vote grounds alone). But
    # rendering the real corpus sentence at ROM 0x49a0b8 with (1,133)=防
    # already substituted reads "[0:0]防[1:134]力が上がる" - i.e. "防
    # <?> 力が上がる", and 防御力 ("defense power") is a completely
    # standard RPG stat-increase message, immediately after a
    # newly-confirmed 防. 骨 ("bone") does not fit that sentence at all.
    # This is the same evidential shape session 7-11 used for several
    # KANJI_MAP entries (single real-sentence semantic fit), so it stays
    # provisional rather than unmapped, but it is flagged distinctly from
    # the systematic-vote entries above because it directly overrides
    # what OCR actually voted for - a future session should look for a
    # second independent sentence containing (1, 134) before trusting
    # this further.
    (1, 134): "御",
}

# Known real string pools this session decodes. Ranges match sessions 9-11
# (dialogue/prompt pool, monster/enemy-name pool) - see README.md "第九輪
# 偵察" and module docstring above for why the rest of the ROM is skipped.
# monster-names is capped at 0x46abe4 rather than the full 0x470000 session 9
# used, because 0x46abe4 is the session-7-confirmed START of the OBJ master
# glyph PIXEL table - scanning into it (as an unbounded 0x460000-0x470000
# chain scan does) picks up raw pixel bytes that coincidentally satisfy the
# pool-header byte pattern, producing garbage single-character "entries"
# (observed directly this session: dozens of `\nあ`/`ぐぷ`-shaped entries
# at addresses like 0x46ad0c, 0x46b244, ... - all past session 9's own
# documented "怪物名稱表往 0x462000 之後品質明顯下降" warning, and all
# inside or past the glyph table's known start).
POOLS = [
    ("dialogue-pool", 0x499000, 0x500000),
    ("monster-names", 0x460000, 0x46abe4),
]

# Per-line noise filter, applied before an entry is emitted. This is the
# same shape of filter sessions 9-11 used to separate real dialogue from
# structural false positives (periodic gojuon/katakana enumeration "debug"
# tables, numeric/parameter tables that happen to satisfy the pool-header
# byte grammar - see research/obj-sentence-string-pool.md "假陽性樣本" and
# scan_category_stats.py's --readability-filter), generalized to credit
# every glyph this decoder actually knows (gojuon + provisional-tier kana)
# rather than only pure hiragana (scan_sentence_strings.hiragana_ratio()
# undercounts katakana-heavy real text, e.g. monster names - session 11
# "篩選器的已知限制"). An entry is kept only if EVERY line in it passes,
# so a multi-line entry can't mix one real line with one noise line.
MIN_LINE_CODES = 3
MIN_CAT0_CODES = 1
MIN_KNOWN_CAT0_RATIO = 0.6


def line_passes_filter(codes):
    if len(codes) == 0:
        # An empty NUL-terminated line (terminator immediately after the
        # marker/previous terminator) is a normal structural spacer inside
        # real multi-line entries (session 9 observed this directly - see
        # extract_string_pool.py's marker="line count" docstring), not
        # noise. Rejecting the whole entry over a blank line would throw
        # away real dialogue that happens to have a blank line for
        # pacing/paragraph breaks - only non-empty lines are judged below.
        return True
    if len(codes) < MIN_LINE_CODES:
        return False
    cat0 = [c for c in codes if (c >> 8) & 0xF == 0]
    if len(cat0) < MIN_CAT0_CODES:
        return False
    known = 0
    for c in cat0:
        _cat, _idx, char_idx = decode_code(c)
        if 0 <= char_idx <= 70 or char_idx in (79, CHOONPU_CHAR_IDX) or (
            KATAKANA_BASE <= char_idx < KATAKANA_BASE + len(KATAKANA)
        ):
            known += 1
    return (known / len(cat0)) >= MIN_KNOWN_CAT0_RATIO


def decode_glyph(category, glyph_entry_index, char_idx):
    """Return (char_or_None, tier). tier is "confirmed", "provisional", or
    None (meaning: no known identity, caller must placeholder it)."""
    if category == 0:
        if 0 <= char_idx <= 70:
            return GOJUON[char_idx], "confirmed"
        if char_idx == 79:
            return SMALL_KANA_79, "provisional"
        if char_idx == CHOONPU_CHAR_IDX:
            return CHOONPU_CHAR, "provisional"
        if KATAKANA_BASE <= char_idx < KATAKANA_BASE + len(KATAKANA):
            return KATAKANA[char_idx - KATAKANA_BASE], "provisional"
        return None, None
    char = KANJI_MAP.get((category, glyph_entry_index))
    if char is not None:
        return char, "confirmed"
    char = KANJI_MAP_OCR_PROVISIONAL.get((category, glyph_entry_index))
    if char is not None:
        return char, "provisional"
    return None, None


def render_line(codes):
    """Decode one NUL-terminated 16-bit code array (already stripped of its
    terminator by the caller). Returns (text, tiers_used, placeholders,
    anomalies)."""
    out = []
    placeholders = []
    anomalies = []
    tiers_used = set()
    for code in codes:
        extra_bits = code >> 12  # category only ever consumes bits 8-11
        category, glyph_entry_index, char_idx = decode_code(code)
        if extra_bits:
            # Never observed in the confirmed corpus so far, but do not
            # silently mask it away if it shows up - flag it as its own
            # kind of unmapped placeholder and count it separately so a
            # reviewer can tell "no known identity" apart from "this code
            # doesn't even fit the known bit layout".
            ph = f"unmapped_glyph:{category}:{glyph_entry_index}"
            out.append("{" + ph + "}")
            placeholders.append(ph)
            anomalies.append(f"0x{code:04x} has nonzero bits above the category nibble")
            continue
        char, tier = decode_glyph(category, glyph_entry_index, char_idx)
        if char is None:
            ph = f"unmapped_glyph:{category}:{glyph_entry_index}"
            out.append("{" + ph + "}")
            placeholders.append(ph)
        else:
            out.append(char)
            tiers_used.add(tier)
    return "".join(out), tiers_used, placeholders, anomalies


def find_pools(data, start, end, min_chain, max_gap=64, max_entries_per_pool=500):
    """Chained pool discovery, same algorithm as scan_string_pools.main()
    factored out into a reusable function (that script only exposes it
    inline in __main__)."""
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


def entry_to_record(pool_name, off, entry_id, marker, lines):
    """One walk_pool() entry (a header + `marker` NUL-terminated lines) ->
    one source-table record. Lines are joined with \\n (Golden Sun
    precedent: one record per in-game message, not one record per line).
    Per-line ROM start offsets are recomputed arithmetically from the
    already-known code lengths (walk_pool doesn't expose them, and
    re-parsing the file a second time to get them isn't necessary - each
    line's length in bytes is 2*(len(codes)+1), including its own
    terminator, with no gap before the next line in a multi-line entry -
    see extract_string_pool.py's _read_lines docstring)."""
    line_start = off + (10 if entry_id is not None else 2)  # skip id+type+00+00+marker, or just marker
    line_texts = []
    line_offsets = []
    tiers_used = set()
    placeholders = []
    anomalies = []
    for codes in lines:
        line_offsets.append(line_start)
        text, line_tiers, line_placeholders, line_anomalies = render_line(codes)
        line_texts.append(text)
        tiers_used |= line_tiers
        placeholders.extend(line_placeholders)
        anomalies.extend(line_anomalies)
        line_start += 2 * (len(codes) + 1)

    text = "\n".join(line_texts)
    string_id = f"{pool_name}:0x{off:06x}"

    prov_parts = [
        f"{pool_name} pool entry, ROM header offset 0x{off:06x}",
        f"marker={marker} ({len(lines)} line(s))",
    ]
    if entry_id is not None:
        prov_parts.append(f"id-prefixed header, id={entry_id}")
    prov_parts.append(
        "line start offset(s): " + ", ".join(f"0x{o:06x}" for o in line_offsets)
    )
    prov_parts.append(
        "decoded via games/shining-soul-1/tools/decode_strings.py (session 12) "
        "using the category=(code>>8)&0xF / glyph_entry_index=(code&0xFF)-1 format "
        "confirmed in research/obj-sentence-string-format.md"
    )
    if "provisional" in tiers_used:
        prov_parts.append(
            "CONTAINS PROVISIONAL-TIER GLYPH(S) (katakana/chōonpu/small-tsu, an "
            "ordered-layout hypothesis or single real-sentence data point; OR a "
            "session-13 KANJI_MAP_OCR_PROVISIONAL kanji identity, corpus-wide OCR "
            "voting evidence eyeballed against the ROM glyph but not individually "
            "address-verified - see decode_strings.py module docstring tier 2). "
            "Lower confidence than a gojuon/confirmed-kanji-only string; OCR output "
            "is candidate evidence, not ground truth, and must never be treated as "
            "more certain than that."
        )
    if placeholders:
        prov_parts.append(
            f"{len(placeholders)} unmapped glyph(s), no known Unicode identity: "
            + ", ".join(placeholders)
        )
    if anomalies:
        prov_parts.append("anomalies: " + "; ".join(anomalies))

    record = {
        "string_id": string_id,
        "locale": "ja",
        "text": text,
        "provenance": " | ".join(prov_parts),
    }
    meta = {
        "has_placeholder": bool(placeholders),
        "uses_provisional": "provisional" in tiers_used,
        "confirmed_only": bool(tiers_used) and tiers_used == {"confirmed"} and not placeholders,
        "n_placeholders": len(placeholders),
        "n_anomalies": len(anomalies),
    }
    return record, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument(
        "--out",
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "research",
            "shining-soul-1-decoded.jsonl",
        ),
    )
    ap.add_argument("--min-chain", type=int, default=3)
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        data = f.read()

    all_records = []
    n_clean_confirmed = 0
    n_clean_provisional = 0
    n_has_placeholder = 0
    n_rejected_noise = 0
    total_codes = 0
    total_placeholders = 0
    total_anomalies = 0

    print(f"# decode_strings.py  rom={args.rom}  min_chain={args.min_chain}")
    for pool_name, start, end in POOLS:
        pools = find_pools(data, start, end, args.min_chain)
        n_entries = sum(len(entries) for _, entries, _ in pools)
        print(f"# pool region '{pool_name}' 0x{start:06x}-0x{end:06x}: "
              f"{len(pools)} sub-pool(s), {n_entries} entries (pre-noise-filter)")
        for pool_start, entries, pool_end in pools:
            for off, entry_id, marker, lines, _entry_end in entries:
                if not all(line_passes_filter(codes) for codes in lines):
                    n_rejected_noise += 1
                    continue
                record, meta = entry_to_record(pool_name, off, entry_id, marker, lines)
                all_records.append(record)
                total_codes += sum(len(c) for c in lines)
                total_placeholders += meta["n_placeholders"]
                total_anomalies += meta["n_anomalies"]
                if meta["has_placeholder"]:
                    n_has_placeholder += 1
                elif meta["uses_provisional"]:
                    n_clean_provisional += 1
                else:
                    n_clean_confirmed += 1

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    total = len(all_records)
    print(f"\n# {n_rejected_noise} entries rejected by the per-line noise filter "
          f"(structural false positives - periodic kana tables, param/graphics data "
          f"that happens to satisfy the pool header grammar; see module docstring)")
    print(f"# wrote {total} records to {out_path}")
    print(f"# {total_codes} total glyph codes decoded across all records "
          f"({total_placeholders} unmapped placeholders, {total_anomalies} anomalies)")
    print("#")
    print(f"# clean, confirmed-tier-only glyphs (zero placeholders):     "
          f"{n_clean_confirmed:5d}  ({n_clean_confirmed / total:.1%})" if total else "# (no records)")
    print(f"# clean, but uses >=1 provisional-tier glyph (zero placeholders): "
          f"{n_clean_provisional:5d}  ({n_clean_provisional / total:.1%})")
    print(f"# has >=1 unmapped-glyph placeholder:                        "
          f"{n_has_placeholder:5d}  ({n_has_placeholder / total:.1%})")


if __name__ == "__main__":
    main()
