#!/usr/bin/env python3
"""Build a draft translation JSONL batch for a contiguous string-ID range,
reusing golden-sun-the-lost-age's already-drafted zh-Hans/zh-TW text
wherever the (control-code-stripped) Japanese source is byte-identical --
both games share large blocks of system/UI text -- and leaving a
placeholder for any ID with no exact source match, since those need a
translator to fill --zh-hans/--zh-tw by hand.

usage: build_translation_batch.py \
  --decoded-jsonl FILE --id-start N --id-end N \
  --reference-translations-glob 'GLOB' \
  --game NAME --revision REV --output FILE
"""
import argparse
import glob
import json
import re

CONTROL_RE = re.compile(r"\{([0-9A-Fa-f]{2})\}")


def strip_controls(raw_text):
    """core/golden-sun/japanese_codepage.rb decodes control unit 0x03 as a
    literal "\n" character, not a "{03}" bracket marker (unlike every other
    control unit < 0x20) -- so newlines must be counted as an implicit 0003
    in the returned control-code sequence, in their actual source position,
    or the declared control_codes list silently drops them."""
    codes = []
    out = []
    i = 0
    while i < len(raw_text):
        if raw_text[i] == "\n":
            codes.append("0003")
            out.append("\n")
            i += 1
            continue
        m = CONTROL_RE.match(raw_text, i)
        if m:
            code = m.group(1).lower()
            codes.append(f"00{code}")
            i = m.end()
            continue
        out.append(raw_text[i])
        i += 1
    return "".join(out), codes


def prefix_and_suffix_codes(raw_text):
    """Split raw_text's control-code sequence (0003 included) into
    (prefix, internal_non_0003, suffix) around its first/last display
    character, mirroring build_zh_tw_trial.rb's implicit-control path:
    prefix/suffix (with any embedded 0003 dropped, same as the Ruby
    `.reject { |unit| unit == 0x03 }`) are what a reused target with no
    explicit {HH} markers of its own automatically inherits."""
    events = []
    i = 0
    while i < len(raw_text):
        if raw_text[i] == "\n":
            events.append(("code", "0003"))
            i += 1
            continue
        m = CONTROL_RE.match(raw_text, i)
        if m:
            events.append(("code", f"00{m.group(1).lower()}"))
            i = m.end()
            continue
        events.append(("display", None))
        i += 1
    first_display = next((idx for idx, (kind, _) in enumerate(events) if kind == "display"), None)
    if first_display is None:
        return None, None, None
    last_display = max(idx for idx, (kind, _) in enumerate(events) if kind == "display")
    prefix = [code for kind, code in events[:first_display] if kind == "code" and code != "0003"]
    internal = [code for kind, code in events[first_display : last_display + 1] if kind == "code" and code != "0003"]
    suffix = [code for kind, code in events[last_display + 1 :] if kind == "code" and code != "0003"]
    return prefix, internal, suffix


def implicit_reuse_matches(raw_text, codes, candidate_target):
    """Replicate build_zh_tw_trial.rb's implicit-control acceptance check in
    Python: candidate_target has no explicit {HH} marker of its own, so it
    can only be reused if source has no internal (non-0003) control code, and
    prefix-codes + candidate's own newline-derived 0003s + suffix-codes
    reproduces this game's actual full control sequence exactly."""
    prefix, internal, suffix = prefix_and_suffix_codes(raw_text)
    if prefix is None or internal:
        return False
    reconstructed = prefix + target_control_codes(candidate_target) + suffix
    return reconstructed == codes


def target_control_codes(target_text):
    """Extract the ordered {HH}/implicit-0003 control-code sequence a reused
    target string declares, using the same convention strip_controls() applies
    to Japanese source text -- so it can be checked against this game's own
    actual control-code sequence for the id being reused into."""
    codes = []
    i = 0
    while i < len(target_text):
        if target_text[i] == "\n":
            codes.append("0003")
            i += 1
            continue
        m = CONTROL_RE.match(target_text, i)
        if m:
            codes.append(f"00{m.group(1).lower()}")
            i = m.end()
            continue
        i += 1
    return codes


def load_reference_index(pattern):
    index = {}
    for path in glob.glob(pattern):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                index.setdefault(rec["source"]["text"], []).append(rec)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoded-jsonl", required=True, help="output of core/golden-sun/decode-text-ids.rb")
    parser.add_argument("--id-start", required=True, type=int)
    parser.add_argument("--id-end", required=True, type=int, help="inclusive")
    parser.add_argument("--reference-translations-glob", required=True)
    parser.add_argument("--game", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--author", default="JohnnySun")
    parser.add_argument("--model", default="Claude Sonnet 5")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    reference_index = load_reference_index(args.reference_translations_glob)

    decoded = {}
    with open(args.decoded_jsonl, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            decoded[d["id"]] = d["text"]

    matched, unmatched = 0, 0
    with open(args.output, "w", encoding="utf-8") as out:
        for sid in range(args.id_start, args.id_end + 1):
            raw = decoded.get(sid)
            if raw is None:
                continue
            stripped, codes = strip_controls(raw)
            if stripped == "?" and not codes:
                # Bare "?" with no control codes at all is this corpus's
                # established debug/unused-slot placeholder pattern (see
                # README "?"/"???" exclusion convention) -- never translate it.
                continue
            candidates = reference_index.get(stripped) or []
            usable = None
            for candidate in candidates:
                candidate_target = candidate["targets"]["zh-TW"]["text"]
                if CONTROL_RE.search(candidate_target):
                    # explicit_controls? path (core/golden-sun/localized_text.rb):
                    # the target alone must fully reproduce this game's actual
                    # control-code sequence -- no automatic prefix/suffix.
                    if target_control_codes(candidate_target) == codes:
                        usable = candidate
                        break
                elif implicit_reuse_matches(raw, codes, candidate_target):
                    usable = candidate
                    break
            candidates = [usable] if usable else []

            record = {
                "game": args.game,
                "revision": args.revision,
                "string_id": sid,
                "source": {
                    "locale": "ja",
                    "text": stripped,
                    "provenance": args.provenance + (
                        " Control markers are declared separately." if codes else ""
                    ),
                },
                "context": {
                    "scene": "TODO",
                    "max_lines": stripped.count("\n") + 1,
                    "control_codes": codes,
                },
                "terms": [],
                "status": "ai_draft",
            }

            if candidates:
                m = candidates[0]
                record["targets"] = {
                    "zh-Hans": {"text": m["targets"]["zh-Hans"]["text"], "author": args.author, "model": args.model},
                    "zh-TW": {"text": m["targets"]["zh-TW"]["text"], "author": args.author, "model": args.model},
                }
                record["context"]["scene"] = m["context"].get("scene", "TODO")
                record["review_notes"] = (
                    f"沿用 {m['game']} id {m['string_id']} 的相同日文原句譯文；待遊戲內寬度與控制碼 QA。"
                )
                matched += 1
            else:
                record["targets"] = {
                    "zh-Hans": {"text": "TODO", "author": args.author, "model": args.model},
                    "zh-TW": {"text": "TODO", "author": args.author, "model": args.model},
                }
                record["review_notes"] = "參考語料庫無完全相同原句，需要人工新譯。"
                unmatched += 1

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"wrote {matched + unmatched} records ({matched} reused, {unmatched} need fresh translation) to {args.output}")


if __name__ == "__main__":
    main()
