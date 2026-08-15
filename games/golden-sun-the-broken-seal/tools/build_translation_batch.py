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
    codes = []
    out = []
    i = 0
    while i < len(raw_text):
        m = CONTROL_RE.match(raw_text, i)
        if m:
            code = m.group(1).lower()
            codes.append(f"00{code}")
            if code == "03":
                out.append("\n")
            i = m.end()
            continue
        out.append(raw_text[i])
        i += 1
    return "".join(out), codes


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
            candidates = reference_index.get(stripped)

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
