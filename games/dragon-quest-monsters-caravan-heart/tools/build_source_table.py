#!/usr/bin/env python3
"""Build a local, conservative Japanese source table for clean A9HJ.

The input JSONL is the ignored byte/token extraction produced by
``extract_text.py``.  This stage deliberately does not pretend that every
glyph in the 256-entry table has a Unicode identity: the confirmed ASCII,
hiragana, and katakana atlas regions are rendered as text, valid kana
diacritic pairs are rendered as text, and all other glyph units become
explicit ``{Uxx}``/``{Uxxxx}`` placeholders.  The proven E0/E1 one-byte
alternate-glyph consumer is represented as ``{G`` + two-digit lead +
two-digit index + ``}`` (for example ``{GE08D}``)
identities are independently cross-checked.  Bytes in the parser's control
range become canonical ``{HH}`` markers.

The output is a local source table for ``restore_translations.rb`` only.  It
contains source text and must stay under the ignored ``research/*-decoded``
path (or outside the repository).  Rows with placeholders, an unproven
terminator, or an unclassified pointer pool are never eligible for a ledger;
the eligibility decision is printed as an aggregate receipt, not hidden in a
translation record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib
from pathlib import Path
from typing import Iterable


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
CONTROL_MIN = 0xDF
DECODER_VERSION = "dqmch-source-table-20260816.v4-provisional"


def validate_rom(data: bytes) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")


def direct_map() -> dict[int, str]:
    """Return only the glyph identities supported by the clean atlas order."""

    result: dict[int, str] = {}
    for index, character in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        result[index] = character
    result.update(dict(enumerate("WXYZ", start=0x20)))

    hiragana = "あぁいぃうぅえぇおぉかきくけこさしすせそたちつってとなにぬねのはひふへほまみむめもやゃゆゅよょらりるれろわ"
    # The clean atlas places the small katakana vowels beside their large
    # vowels, and places small ッ after ツ.  The table starts at 0x5B; this
    # is cross-checked by rendered さそりアーマー and マタンゴ records,
    # not borrowed from a standard Shift-JIS table.
    katakana = "アァイィウゥエェオォカキクケコサシスセソタチツッテトナニヌネノハヒフヘホマミムメモヤャユュヨョラリルレロワ"
    if len(hiragana) != 53 or len(katakana) != 53:
        raise AssertionError("kana atlas map must contain 53 hiragana and 53 confirmed katakana entries")
    result.update(dict(enumerate(hiragana, start=0x24)))
    # These identities are supported by clean script-name/context records:
    # 0x59 occurs in ちからをためる and いきをすいこむ, while 0x5A
    # occurs in しんりゅう.
    result[0x59] = "を"
    result[0x5A] = "ん"
    result.update(dict(enumerate(katakana, start=0x5B)))
    # 0x90/0x91 are the direct ヲ/ン entries used by the kana test strings and
    # by names such as マタンゴ.  The independent Japanese character-code
    # table at arcenserv.info also lists 0x90=ヲ and 0x91=ン; it is used here
    # only as codepage corroboration, never as a translation source.
    result[0x90] = "ヲ"
    result[0x91] = "ン"
    # These punctuation entries are promoted only after repeated clean script
    # context: 0x94 closes ordinary dialogue sentences, 0x9B/0x9C close
    # question/exclamation sentences, and 0xA0/0xA2 occur in the clean title
    # as the middle dot and wave dash respectively.
    result[0x94] = "。"
    result[0x9B] = "？"
    result[0x9C] = "！"
    result[0xA0] = "・"
    # Clean names and the atlas identify this long-vowel mark.  It is a
    # direct glyph mapping, not a control-code convention.
    result[0xA1] = "ー"
    result[0xA2] = "～"
    # This clean atlas entry is all background nibbles and is used as a
    # visible separator in the stable menu.
    result[0xBF] = " "
    return result


DAKUTEN_PAIRS = {
    **dict(zip("かきくけこ", "がぎぐげご")),
    **dict(zip("さしすせそ", "ざじずぜぞ")),
    **dict(zip("たちつてと", "だぢづでど")),
    **dict(zip("はひふへほ", "ばびぶべぼ")),
    "う": "ゔ",
    **dict(zip("カキクケコ", "ガギグゲゴ")),
    **dict(zip("サシスセソ", "ザジズゼゾ")),
    **dict(zip("タチツテト", "ダヂヅデド")),
    **dict(zip("ハヒフヘホ", "バビブベボ")),
    "ウ": "ヴ",
}
HANDAKUTEN_PAIRS = dict(zip("はひふへほ", "ぱぴぷぺぽ"))
HANDAKUTEN_PAIRS.update(dict(zip("ハヒフヘホ", "パピプペポ")))


def pair_text(lead: int, trail: int, mapping: dict[int, str]) -> tuple[str, bool]:
    base = mapping.get(trail)
    if lead == 0x92 and base in DAKUTEN_PAIRS:
        return DAKUTEN_PAIRS[base], True
    if lead == 0x93 and base in HANDAKUTEN_PAIRS:
        return HANDAKUTEN_PAIRS[base], True
    return f"{{U{lead:02X}{trail:02X}}}", False


def token_text(tokens: Iterable[dict[str, object]], mapping: dict[int, str]) -> tuple[str, dict[str, int]]:
    parts: list[str] = []
    stats = {"mapped": 0, "unresolved": 0, "controls": 0, "pairs": 0, "alt_glyphs": 0}
    for token in tokens:
        kind = token["kind"]
        if kind == "single-byte-candidate":
            value = int(token["value"])
            if value >= CONTROL_MIN:
                parts.append(f"{{{value:02X}}}")
                stats["controls"] += 1
            elif value in mapping:
                parts.append(mapping[value])
                stats["mapped"] += 1
            else:
                parts.append(f"{{U{value:02X}}}")
                stats["unresolved"] += 1
        elif kind == "pair":
            text, resolved = pair_text(int(token["lead"]), int(token["trail"]), mapping)
            parts.append(text)
            stats["pairs"] += 1
            if resolved:
                stats["mapped"] += 1
            else:
                stats["unresolved"] += 1
        elif kind == "pair-truncated":
            parts.append(f"{{U{int(token['lead']):02X}}}")
            stats["unresolved"] += 1
        elif kind == "alt-glyph":
            parts.append(f"{{G{int(token['lead']):02X}{int(token['value']):02X}}}")
            stats["alt_glyphs"] += 1
            stats["unresolved"] += 1
        elif kind == "alt-glyph-truncated":
            parts.append(f"{{G{int(token['lead']):02X}}}")
            stats["alt_glyphs"] += 1
            stats["unresolved"] += 1
        elif kind == "control-candidate":
            value = int(token["value"])
            parts.append(f"{{{value:02X}}}")
            stats["controls"] += 1
        else:
            raise ValueError(f"unknown token kind: {kind!r}")
    return "".join(parts), stats


def source_record(record: dict[str, object], mapping: dict[int, str]) -> tuple[dict[str, object], dict[str, int | bool]]:
    text, stats = token_text(record["tokens"], mapping)  # type: ignore[arg-type]
    terminated = 0xFF in [int(value) for value in record["control_values"]]
    eligible = terminated and stats["unresolved"] == 0 and False
    string_id = (
        f"dqmch:a9hj:g{int(record['group']):02d}:"
        f"v{int(record['variant']):02d}:m{int(record['message_index']):04d}"
    )
    provenance = "; ".join(
        (
            f"rom_sha256={EXPECTED_SHA256}",
            f"pointer_cpu={record['pointer_cpu']}",
            f"pointer_file={record['pointer_file']}",
            f"span_end_file={record['span_end_file']}",
            f"boundary={record['boundary']}",
            f"decoder={DECODER_VERSION}",
            "runtime_context=false",
            "ledger_eligible=false",
        )
    )
    result = {
        "string_id": string_id,
        "locale": "ja-JP",
        "text": text,
        "provenance": provenance,
    }
    receipt = {
        "terminated": terminated,
        "eligible": eligible,
        **stats,
    }
    return result, receipt


def load_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("decoded", type=Path, help="ignored output from extract_text.py")
    parser.add_argument("--out", type=Path, required=True, help="ignored local source table")
    args = parser.parse_args()
    try:
        validate_rom(args.rom.read_bytes())
        records = load_records(args.decoded)
        mapping = direct_map()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        totals = {"rows": 0, "terminated": 0, "eligible": 0, "mapped": 0, "unresolved": 0, "controls": 0, "pairs": 0, "alt_glyphs": 0}
        with args.out.open("w", encoding="utf-8") as output:
            for record in records:
                row, receipt = source_record(record, mapping)
                output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                totals["rows"] += 1
                for key in ("terminated", "eligible", "mapped", "unresolved", "controls", "pairs", "alt_glyphs"):
                    totals[key] += int(receipt[key])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"build_source_table: {error}", file=sys.stderr)
        return 2

    print("decoder", DECODER_VERSION)
    print("rom-sha256", EXPECTED_SHA256)
    print("summary", totals)
    print("output", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
