#!/usr/bin/env python3
"""Verify the bounded title-menu reinsertion without retaining source text.

The verifier checks the clean A9HJ identity, decodes the patched fixed span,
checks every authored alternate-glyph tile, and proves that all other ROM
bytes are unchanged.  It is intentionally a bounded static re-extraction;
full-script extraction and runtime QA remain separate roadmap items.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from patch_menu import (
    ALT_GLYPH_BANK_BIAS,
    ALT_GLYPH_STRIDE,
    ALT_GLYPH_TABLE_FILE,
    MENU_DATA_LENGTH,
    MENU_FILE_OFFSET,
    MENU_SPAN_LENGTH,
    MENU_STRING_ID,
    TARGET_TEXT,
    TERMINATOR,
    GLYPH_BITMAPS,
    GLYPH_SLOTS,
    encode_target,
    tile_bytes,
    validate_rom,
)


def decode_target(encoded: bytes) -> str:
    if len(encoded) != MENU_SPAN_LENGTH or encoded[-2:] != TERMINATOR:
        raise ValueError("patched menu does not preserve the fixed FF terminator")
    text: list[str] = []
    cursor = 0
    while cursor < MENU_DATA_LENGTH:
        value = encoded[cursor]
        if value == 0xBF:
            text.append(" ")
            cursor += 1
            continue
        if value != 0xE1 or cursor + 1 >= MENU_DATA_LENGTH:
            raise ValueError(f"unexpected patched menu byte at {cursor}: 0x{value:02X}")
        slot = encoded[cursor + 1]
        characters = [character for character, index in GLYPH_SLOTS.items() if index == slot]
        if len(characters) != 1:
            raise ValueError(f"unexpected allocated E1 slot: 0x{slot:02X}")
        text.append(characters[0])
        cursor += 2
    return "".join(text).rstrip(" ")


def allowed_ranges() -> list[tuple[int, int]]:
    ranges = [(MENU_FILE_OFFSET, MENU_FILE_OFFSET + MENU_SPAN_LENGTH)]
    ranges.extend(
        (
            ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + index * ALT_GLYPH_STRIDE,
            ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + (index + 1) * ALT_GLYPH_STRIDE,
        )
        for index in GLYPH_SLOTS.values()
    )
    return ranges


def verify(clean: bytes, patched: bytes) -> dict[str, object]:
    validate_rom(clean)
    if len(patched) != len(clean):
        raise ValueError("patched ROM size differs from clean ROM")
    menu = patched[MENU_FILE_OFFSET:MENU_FILE_OFFSET + MENU_SPAN_LENGTH]
    expected = encode_target(TARGET_TEXT)
    if menu != expected:
        raise ValueError("patched menu bytes do not match the bounded target encoding")
    if decode_target(menu) != TARGET_TEXT:
        raise ValueError("bounded menu re-extraction did not recover the target text")

    for character, index in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + index * ALT_GLYPH_STRIDE
        expected_tile = tile_bytes(GLYPH_BITMAPS[character])
        if patched[start:start + ALT_GLYPH_STRIDE] != expected_tile:
            raise ValueError(f"tile mismatch for {character} at 0x{start:06X}")

    ranges = allowed_ranges()
    changed_offsets = [offset for offset, (before, after) in enumerate(zip(clean, patched)) if before != after]
    if any(not any(start <= offset < end for start, end in ranges) for offset in changed_offsets):
        raise ValueError("patched ROM changes bytes outside the bounded menu/font ranges")
    report = {
        "string_id": MENU_STRING_ID,
        "clean_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_sha256": hashlib.sha256(patched).hexdigest(),
        "menu_file_offset": f"0x{MENU_FILE_OFFSET:06X}",
        "menu_span_length": MENU_SPAN_LENGTH,
        "menu_target": TARGET_TEXT,
        "changed_byte_count": len(changed_offsets),
        "allowed_range_count": len(ranges),
        "outside_range_changes": 0,
        "bounded_reextract": "ok",
        "runtime_qa": "not-run",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=pathlib.Path)
    parser.add_argument("patched", type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    try:
        report = verify(args.clean.read_bytes(), args.patched.read_bytes())
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"verify_menu_patch: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
