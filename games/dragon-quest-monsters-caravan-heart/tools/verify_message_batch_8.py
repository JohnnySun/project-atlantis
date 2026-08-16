#!/usr/bin/env python3
"""Verify the bounded g06/v00/m0042-m0043 fixed-span reinsertion."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from patch_message_batch_8 import (
    ALT_GLYPH_BANK_BIASES,
    ALT_GLYPH_STRIDE,
    ALT_GLYPH_TABLE_FILE,
    DIRECT_CODES,
    GLYPH_BITMAPS,
    GLYPH_SLOTS,
    MESSAGE_SPECS,
    PRESERVED_TAIL,
    encode_target,
    patch_menu,
    validate_rom,
)


def decode_target(encoded: bytes, spec: dict[str, object]) -> str:
    span_length = int(spec["span_length"])
    if len(encoded) != span_length or encoded[-len(PRESERVED_TAIL):] != PRESERVED_TAIL:
        raise ValueError("patched message does not preserve its terminator")
    reverse = {slot: character for character, slot in GLYPH_SLOTS.items()}
    reverse.update({(0, value): character for character, value in DIRECT_CODES.items()})
    text: list[str] = []
    cursor = 0
    data_end = span_length - len(PRESERVED_TAIL)
    while cursor < data_end:
        value = encoded[cursor]
        if value == 0xBF:
            text.append(" ")
            cursor += 1
            continue
        if value in ALT_GLYPH_BANK_BIASES and cursor + 1 < data_end:
            slot = (value, encoded[cursor + 1])
            try:
                text.append(reverse[slot])
            except KeyError as error:
                raise ValueError(f"unexpected alternate glyph slot: {value:02X}/{encoded[cursor + 1]:02X}") from error
            cursor += 2
            continue
        try:
            text.append(reverse[(0, value)])
        except KeyError as error:
            raise ValueError(f"unexpected patched message byte at {cursor}: 0x{value:02X}") from error
        cursor += 1
    return "".join(text).rstrip(" ")


def allowed_ranges() -> list[tuple[int, int]]:
    ranges = [
        (int(spec["file_offset"]), int(spec["file_offset"]) + int(spec["span_length"]))
        for spec in MESSAGE_SPECS
    ]
    ranges.extend(
        (
            ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIASES[lead] + index * ALT_GLYPH_STRIDE,
            ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIASES[lead] + (index + 1) * ALT_GLYPH_STRIDE,
        )
        for lead, index in GLYPH_SLOTS.values()
    )
    return ranges


def verify(clean: bytes, patched: bytes) -> dict[str, object]:
    validate_rom(clean)
    if len(patched) != len(clean):
        raise ValueError("patched ROM size differs from clean ROM")
    for spec in MESSAGE_SPECS:
        offset = int(spec["file_offset"])
        span_length = int(spec["span_length"])
        message = patched[offset:offset + span_length]
        target = str(spec["target"])
        if message != encode_target(target, int(spec["data_length"])):
            raise ValueError(f"patched message bytes do not match {spec['string_id']}")
        if decode_target(message, spec) != target:
            raise ValueError(f"bounded message re-extraction did not recover {spec['string_id']}")
    for character, (lead, index) in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIASES[lead] + index * ALT_GLYPH_STRIDE
        if patched[start:start + ALT_GLYPH_STRIDE] != patch_menu.tile_bytes(GLYPH_BITMAPS[character]):
            raise ValueError(f"tile mismatch for {character} at 0x{start:06X}")
    ranges = allowed_ranges()
    changed_offsets = [offset for offset, (before, after) in enumerate(zip(clean, patched)) if before != after]
    if any(not any(start <= offset < end for start, end in ranges) for offset in changed_offsets):
        raise ValueError("patched ROM changes bytes outside bounded message/font ranges")
    return {
        "string_ids": [spec["string_id"] for spec in MESSAGE_SPECS],
        "clean_sha256": hashlib.sha256(clean).hexdigest(),
        "patched_sha256": hashlib.sha256(patched).hexdigest(),
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
        print(f"verify_message_batch_8: {error}")
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
