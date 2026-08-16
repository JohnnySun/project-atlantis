#!/usr/bin/env python3
"""Patch a bounded clean A9HJ battle-start question.

This is a seventh fixed-span reinsertion proof for ``g06/v00/m0040``.  It
adds two authored E1 glyphs, uses the clean direct question mark, preserves
the final ``FF`` byte, and does not claim to be the game's general encoder.
ROM and generated outputs stay local or ignored.
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
    GLYPH_BITMAPS as MENU_GLYPH_BITMAPS,
    GLYPH_SLOTS as MENU_GLYPH_SLOTS,
    SPACE_CODE,
    tile_bytes,
    validate_rom,
)


MESSAGE_STRING_ID = "dqmch:a9hj:g06:v00:m0040"
MESSAGE_FILE_OFFSET = 0x286756
MESSAGE_SPAN_LENGTH = 15
MESSAGE_DATA_LENGTH = 14
MESSAGE_EXPECTED_SHA256 = "ae2ec0379733912f3c4bc40d11f183dd9c595feed216bf73054e940a17b88f80"
SOURCE_HASH = "4bdffdb8d617207bcb4799bf05d73b879bdc4da6feacfb2a4c8fe256e86b19bf"
TARGET_TEXT = "要開始對戰嗎？"
TARGET_TEXT_HANS = "要开始对战吗？"
PRESERVED_TAIL = bytes.fromhex("ff")
ALT_LEAD = 0xE1

# These two E1 slots are unused in the clean extractor corpus and disjoint
# from all earlier bounded allocations.  Their high-byte placement is safe
# here because the E1 consumer has a fixed one-byte parameter contract.
NEW_GLYPH_SLOTS = {"要": 0xFC, "嗎": 0xFE}
REUSED_GLYPH_SLOTS = {
    "開": MENU_GLYPH_SLOTS["開"],
    "始": MENU_GLYPH_SLOTS["始"],
    "對": MENU_GLYPH_SLOTS["對"],
    "戰": MENU_GLYPH_SLOTS["戰"],
}
GLYPH_SLOTS = {**NEW_GLYPH_SLOTS, **REUSED_GLYPH_SLOTS}

# Authored 8x8 proof tiles, not an imported or unlicensed font.
GLYPH_BITMAPS = {
    "要": ("#######.", "#.....#.", ".#####..", "...#....", ".#####..", "#..#..#.", "#.....#.", "#######."),
    "嗎": ("#..###..", "##.#..#.", "#..###..", ".#####..", "#..#.#..", "#######.", "#..#..#.", "#..#..#."),
    "開": MENU_GLYPH_BITMAPS["開"],
    "始": MENU_GLYPH_BITMAPS["始"],
    "對": MENU_GLYPH_BITMAPS["對"],
    "戰": MENU_GLYPH_BITMAPS["戰"],
}
DIRECT_CODES = {"？": 0x9B}


def validate_bitmaps() -> dict[str, bytes]:
    if set(GLYPH_SLOTS) != set(GLYPH_BITMAPS):
        raise ValueError("glyph slot and bitmap assignments differ")
    if len(set(GLYPH_SLOTS.values())) != len(GLYPH_SLOTS):
        raise ValueError("duplicate new glyph slot")
    tiles = {character: tile_bytes(rows) for character, rows in GLYPH_BITMAPS.items()}
    if any(not any(tile) for tile in tiles.values()):
        raise ValueError("new glyph bitmap is empty")
    return tiles


def load_jsonl_entry(path: pathlib.Path, string_id: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("string_id") == string_id:
                return entry
    raise ValueError(f"missing {string_id} in {path}")


def validate_ledger(ledger: dict[str, object], source: dict[str, object]) -> None:
    if ledger.get("string_id") != MESSAGE_STRING_ID:
        raise ValueError("unexpected message ledger string_id")
    if ledger.get("source_hash") != SOURCE_HASH:
        raise ValueError("message ledger source hash is not the clean source hash")
    if hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest() != SOURCE_HASH:
        raise ValueError("local source table does not match message ledger hash")
    targets = ledger.get("targets")
    if not isinstance(targets, dict):
        raise ValueError("ledger targets missing")
    tw = targets.get("zh-TW")
    hans = targets.get("zh-Hans")
    if not isinstance(tw, dict) or tw.get("text") != TARGET_TEXT:
        raise ValueError("unexpected zh-TW message target")
    if not isinstance(hans, dict) or hans.get("text") != TARGET_TEXT_HANS:
        raise ValueError("unexpected zh-Hans message target")


def assert_allocations_unused(decoded: pathlib.Path) -> None:
    """Ensure the new E1 slots are unused in the clean extractor corpus."""

    validate_bitmaps()
    allocated = set(NEW_GLYPH_SLOTS.values())
    for line in decoded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for token in record.get("tokens", []):
            if token.get("kind") == "alt-glyph" and token.get("lead") == ALT_LEAD and token.get("value") in allocated:
                raise ValueError(f"new E1 slot is already used: 0x{int(token['value']):02X}")


def encode_target(text: str) -> bytes:
    if text != TARGET_TEXT:
        raise ValueError("batch 7 encoder expects the declared visible target")
    output = bytearray()
    for character in text:
        if character == " ":
            output.append(SPACE_CODE)
        elif character in DIRECT_CODES:
            output.append(DIRECT_CODES[character])
        else:
            try:
                output.extend((ALT_LEAD, GLYPH_SLOTS[character]))
            except KeyError as error:
                raise ValueError(f"target character has no bounded glyph slot: {character!r}") from error
    if len(output) > MESSAGE_DATA_LENGTH:
        raise ValueError(f"target needs {len(output)} bytes, message span allows {MESSAGE_DATA_LENGTH}")
    output.extend(bytes((SPACE_CODE,)) * (MESSAGE_DATA_LENGTH - len(output)))
    result = bytes(output) + PRESERVED_TAIL
    if len(result) != MESSAGE_SPAN_LENGTH:
        raise ValueError("encoded message does not retain the fixed span length")
    return result


def patch(
    rom: bytes,
    ledger: dict[str, object],
    source: dict[str, object],
    decoded: pathlib.Path,
) -> tuple[bytes, dict[str, object]]:
    validate_rom(rom)
    validate_ledger(ledger, source)
    assert_allocations_unused(decoded)
    tiles = validate_bitmaps()
    original_span = rom[MESSAGE_FILE_OFFSET:MESSAGE_FILE_OFFSET + MESSAGE_SPAN_LENGTH]
    if hashlib.sha256(original_span).hexdigest() != MESSAGE_EXPECTED_SHA256:
        raise ValueError("message span changed; refusing a non-baseline input")
    result = bytearray(rom)
    for character, index in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + index * ALT_GLYPH_STRIDE
        result[start:start + ALT_GLYPH_STRIDE] = tiles[character]
    result[MESSAGE_FILE_OFFSET:MESSAGE_FILE_OFFSET + MESSAGE_SPAN_LENGTH] = encode_target(TARGET_TEXT)
    receipt = {
        "rom_sha256": "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce",
        "string_id": MESSAGE_STRING_ID,
        "message_file_offset": f"0x{MESSAGE_FILE_OFFSET:06X}",
        "message_span_length": MESSAGE_SPAN_LENGTH,
        "preserved_tail": PRESERVED_TAIL.hex(),
        "new_e1_slots": {character: f"0x{index:02X}" for character, index in NEW_GLYPH_SLOTS.items()},
        "reused_e1_slots": {character: f"0x{index:02X}" for character, index in REUSED_GLYPH_SLOTS.items()},
        "changed_font_bytes": len(GLYPH_SLOTS) * ALT_GLYPH_STRIDE,
        "target_text": TARGET_TEXT,
    }
    return bytes(result), receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("ledger", type=pathlib.Path)
    parser.add_argument("source_table", type=pathlib.Path)
    parser.add_argument("decoded", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--receipt", type=pathlib.Path)
    args = parser.parse_args()
    try:
        ledger = load_jsonl_entry(args.ledger, MESSAGE_STRING_ID)
        source = load_jsonl_entry(args.source_table, MESSAGE_STRING_ID)
        patched, receipt = patch(args.rom.read_bytes(), ledger, source, args.decoded)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(patched)
        receipt["patched_sha256"] = hashlib.sha256(patched).hexdigest()
        receipt["output"] = str(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"patch_message_batch_7: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
