#!/usr/bin/env python3
"""Verify the bounded g06/v00/m0001 fixed-span reinsertion."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from patch_message_batch_2 import (
    ALT_GLYPH_BANK_BIAS,
    ALT_GLYPH_STRIDE,
    ALT_GLYPH_TABLE_FILE,
    GLYPH_BITMAPS,
    GLYPH_SLOTS,
    MESSAGE_FILE_OFFSET,
    MESSAGE_SPAN_LENGTH,
    PRESERVED_TAIL,
    TARGET_TEXT,
    encode_target,
    tile_bytes,
    validate_rom,
)


def decode_target(encoded: bytes) -> str:
    if len(encoded) != MESSAGE_SPAN_LENGTH or encoded[-len(PRESERVED_TAIL):] != PRESERVED_TAIL:
        raise ValueError("patched message does not preserve its dynamic tail")
    text: list[str] = []
    cursor = 0
    data_end = MESSAGE_SPAN_LENGTH - len(PRESERVED_TAIL)
    reverse = {index: character for character, index in GLYPH_SLOTS.items()}
    while cursor < data_end:
        value = encoded[cursor]
        if value == 0xBF:
            text.append(" ")
            cursor += 1
            continue
        if value != 0xE1 or cursor + 1 >= data_end:
            raise ValueError(f"unexpected patched message byte at {cursor}: 0x{value:02X}")
        try:
            text.append(reverse[encoded[cursor + 1]])
        except KeyError as error:
            raise ValueError(f"unexpected allocated E1 slot: 0x{encoded[cursor + 1]:02X}") from error
        cursor += 2
    return "".join(text).rstrip(" ")


def allowed_ranges() -> list[tuple[int, int]]:
    ranges = [(MESSAGE_FILE_OFFSET, MESSAGE_FILE_OFFSET + MESSAGE_SPAN_LENGTH)]
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
    message = patched[MESSAGE_FILE_OFFSET:MESSAGE_FILE_OFFSET + MESSAGE_SPAN_LENGTH]
    if message != encode_target(TARGET_TEXT):
        raise ValueError("patched message bytes do not match the bounded target")
    if decode_target(message) != TARGET_TEXT:
        raise ValueError("bounded message re-extraction did not recover the target")
    for character, index in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + index * ALT_GLYPH_STRIDE
        if patched[start:start + ALT_GLYPH_STRIDE] != tile_bytes(GLYPH_BITMAPS[character]):
            raise ValueError(f"tile mismatch for {character} at 0x{start:06X}")
    ranges = allowed_ranges()
    changed_offsets = [offset for offset, (before, after) in enumerate(zip(clean, patched)) if before != after]
    if any(not any(start <= offset < end for start, end in ranges) for offset in changed_offsets):
        raise ValueError("patched ROM changes bytes outside bounded message/font ranges")
    return {
        "string_id": "dqmch:a9hj:g06:v00:m0001",
        "clean_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_sha256": hashlib.sha256(patched).hexdigest(),
        "message_target": TARGET_TEXT,
        "message_span_length": MESSAGE_SPAN_LENGTH,
        "preserved_tail": PRESERVED_TAIL.hex(),
        "changed_byte_count": len(changed_offsets),
        "allowed_range_count": len(ranges),
        "outside_range_changes": 0,
        "bounded_reextract": "ok",
        "runtime_qa": "not-run",
    }


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
        print(f"verify_message_batch_2: {error}")
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
