#!/usr/bin/env python3
"""Patch one bounded clean A9HJ title-menu block with hand-drawn zh-TW glyphs.

This is a deliberately narrow reinsertion proof, not the game's general
encoder.  It validates the clean ROM, the ledger/source hash, the exact menu
span, and the fact that the allocated E1 slots are unused by the local clean
extractor.  The 8x8 glyph bitmaps are authored in this file; no external or
unlicensed font is imported.  ROM and receipt outputs must remain ignored or
under /private/tmp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import zlib


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
MENU_STRING_ID = "dqmch:a9hj:g06:v00:m0000"
MENU_FILE_OFFSET = 0x28647C
MENU_SPAN_LENGTH = 46
MENU_DATA_LENGTH = 44
MENU_EXPECTED_SHA256 = "39a92ad7e4a4f39ecc62468878ed5f629e8e8e9f46f655445506d982145bbc70"
ALT_GLYPH_TABLE_FILE = 0x2E0BD4
ALT_GLYPH_BANK_BIAS = 0x4000
ALT_GLYPH_STRIDE = 32
ALT_LEAD = 0xE1
SPACE_CODE = 0xBF
TERMINATOR = bytes((0xFF, 0xFF))
TARGET_TEXT = "從頭開始  繼續遊戲  通訊對戰  三連戰"
TARGET_TEXT_HANS = "从头开始  继续游戏  通讯对战  三连战"
SOURCE_HASH = "222553bb3def3cd3da7d145bbf487c2fef8b20fe55b5ceaa3b73625f4f934e8f"

# E1 slots AB, D1..D9, DA..DC, and DE were zero-use in the clean extractor
# corpus.  Keep these assignments stable so the ledger and any later patch
# receipt remain reproducible.  D0 and DD are intentionally not allocated.
GLYPH_SLOTS = {
    "從": 0xAB,
    "頭": 0xD1,
    "開": 0xD2,
    "始": 0xD3,
    "繼": 0xD4,
    "續": 0xD5,
    "遊": 0xD6,
    "戲": 0xD7,
    "通": 0xD8,
    "訊": 0xD9,
    "對": 0xDA,
    "戰": 0xDB,
    "三": 0xDC,
    "連": 0xDE,
}

# 8x8, one character per row.  These are intentionally small authored
# bitmaps, not an extracted font.  '#' becomes palette index 15 and '.' is
# transparent/background.  They are enough for the bounded menu proof.
GLYPH_BITMAPS = {
    "從": ("..#.#...", ".#####..", "..#.#...", "#######.", "..#.#.#.", ".##..#..", "#..##...", "...#...."),
    "頭": (".######.", ".#.#..#.", ".######.", "...##...", "#######.", "..#.#...", ".#..#...", "#...#..."),
    "開": ("#######.", "#..#..#.", "#.###.#.", "#.#.#.#.", "#.###.#.", "#..#..#.", "#######.", "........"),
    "始": ("..#.....", ".#######", "..#.#...", "#######.", "..#.#...", ".#..#...", "#...##..", "....#..."),
    "繼": ("#.#.##..", ".#####..", "#.#.#...", ".#######", "#..#.#..", ".#####..", "#.#...#.", "..#..#.."),
    "續": (".#####..", "#.#.#...", ".#####..", "#..#..#.", ".######.", "#.#.#...", ".#####..", "#...#..."),
    "遊": ("..#.....", ".#####..", "#..#.#..", "..####..", "...#....", ".#####..", "#...#...", "...##..."),
    "戲": ("#######.", "#.#.#...", ".#####..", "#..#.#..", ".#######", "..#.#...", "#.#..#..", "...#...."),
    "通": ("..#.....", ".#####..", "#..#.#..", "..####..", "#######.", "#..#....", "#..#....", "#######."),
    "訊": ("#..#....", "#######.", "#..#....", "#.###...", "#..#....", "#######.", "#..#....", "#..#...."),
    "對": ("#.#.##..", ".#####..", "#.#.#...", "#######.", "..#.....", ".#####..", "#.#.#...", "...#...."),
    "戰": ("#######.", "#.#.#...", ".#####..", "#..#.#..", "#######.", "..#.#...", "#...#...", "...##..."),
    "三": ("#######.", "........", ".#####..", "........", "#######.", "........", ".#####..", "........"),
    "連": ("..#.....", ".#####..", "#..#.#..", "..####..", "#######.", "...#....", "..#.....", "#######."),
}


def validate_rom(data: bytes) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected clean 8 MiB ROM, got {len(data)} bytes")
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X} SHA256={sha256}")


def tile_bytes(rows: tuple[str, ...]) -> bytes:
    if len(rows) != 8 or any(len(row) != 8 for row in rows):
        raise ValueError("glyph bitmap must be exactly 8x8")
    result = bytearray()
    for row in rows:
        for x in range(0, 8, 2):
            lo = 0xF if row[x] == "#" else 0
            hi = 0xF if row[x + 1] == "#" else 0
            result.append(lo | (hi << 4))
    return bytes(result)


def validate_bitmaps() -> dict[str, bytes]:
    if set(GLYPH_SLOTS) != set(GLYPH_BITMAPS):
        raise ValueError("glyph slot and bitmap assignments differ")
    if len(set(GLYPH_SLOTS.values())) != len(GLYPH_SLOTS):
        raise ValueError("duplicate custom glyph slot")
    tiles = {character: tile_bytes(rows) for character, rows in GLYPH_BITMAPS.items()}
    if any(not any(tile) for tile in tiles.values()):
        raise ValueError("custom glyph bitmap is empty")
    return tiles


def load_jsonl_entry(path: pathlib.Path, string_id: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("string_id") == string_id:
                return entry
    raise ValueError(f"missing {string_id} in {path}")


def validate_ledger(ledger: dict[str, object], source: dict[str, object]) -> None:
    if ledger.get("string_id") != MENU_STRING_ID:
        raise ValueError("unexpected menu ledger string_id")
    if ledger.get("source_hash") != SOURCE_HASH:
        raise ValueError("menu ledger source hash is not the clean source hash")
    if hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest() != SOURCE_HASH:
        raise ValueError("local source table does not match menu ledger hash")
    targets = ledger.get("targets")
    if not isinstance(targets, dict):
        raise ValueError("ledger targets missing")
    tw = targets.get("zh-TW")
    hans = targets.get("zh-Hans")
    if not isinstance(tw, dict) or tw.get("text") != TARGET_TEXT:
        raise ValueError("unexpected zh-TW menu target")
    if not isinstance(hans, dict) or hans.get("text") != TARGET_TEXT_HANS:
        raise ValueError("unexpected zh-Hans menu target")


def assert_allocations_unused(decoded: pathlib.Path) -> None:
    allocated = set(GLYPH_SLOTS.values())
    for line in decoded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for token in record.get("tokens", []):
            if token.get("kind") == "alt-glyph" and token.get("lead") == ALT_LEAD and token.get("value") in allocated:
                raise ValueError(f"allocated E1 slot is already used: 0x{int(token['value']):02X}")


def encode_target(text: str) -> bytes:
    output = bytearray()
    for character in text:
        if character == " ":
            output.append(SPACE_CODE)
        else:
            try:
                output.extend((ALT_LEAD, GLYPH_SLOTS[character]))
            except KeyError as error:
                raise ValueError(f"target character has no bounded glyph slot: {character!r}") from error
    if len(output) > MENU_DATA_LENGTH:
        raise ValueError(f"target needs {len(output)} bytes, menu span allows {MENU_DATA_LENGTH}")
    output.extend(bytes((SPACE_CODE,)) * (MENU_DATA_LENGTH - len(output)))
    return bytes(output) + TERMINATOR


def patch(rom: bytes, ledger: dict[str, object], source: dict[str, object], decoded: pathlib.Path) -> tuple[bytes, dict[str, object]]:
    validate_rom(rom)
    validate_ledger(ledger, source)
    assert_allocations_unused(decoded)
    tiles = validate_bitmaps()
    original_span = rom[MENU_FILE_OFFSET:MENU_FILE_OFFSET + MENU_SPAN_LENGTH]
    if hashlib.sha256(original_span).hexdigest() != MENU_EXPECTED_SHA256:
        raise ValueError("menu span changed; refusing to patch a non-baseline input")
    result = bytearray(rom)
    for character, index in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIAS + index * ALT_GLYPH_STRIDE
        result[start:start + ALT_GLYPH_STRIDE] = tiles[character]
    encoded = encode_target(TARGET_TEXT)
    result[MENU_FILE_OFFSET:MENU_FILE_OFFSET + MENU_SPAN_LENGTH] = encoded
    receipt = {
        "rom_sha256": EXPECTED_SHA256,
        "string_id": MENU_STRING_ID,
        "menu_file_offset": f"0x{MENU_FILE_OFFSET:06X}",
        "menu_bytes_before_ff": MENU_DATA_LENGTH,
        "preserved_terminator": TERMINATOR.hex(),
        "allocated_e1_slots": {character: f"0x{index:02X}" for character, index in GLYPH_SLOTS.items()},
        "changed_font_bytes": len(GLYPH_SLOTS) * ALT_GLYPH_STRIDE,
        "changed_menu_bytes": MENU_SPAN_LENGTH,
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
        ledger = load_jsonl_entry(args.ledger, MENU_STRING_ID)
        source = load_jsonl_entry(args.source_table, MENU_STRING_ID)
        patched, receipt = patch(args.rom.read_bytes(), ledger, source, args.decoded)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(patched)
        receipt["patched_sha256"] = hashlib.sha256(patched).hexdigest()
        receipt["output"] = str(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"patch_menu: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
