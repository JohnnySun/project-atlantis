#!/usr/bin/env python3
"""Patch two bounded clean A9HJ battle-decline messages.

This is an eighth fixed-span reinsertion proof for ``g06/v00/m0042`` and
``m0043``.  It deliberately exercises both alternate glyph banks: two new
glyphs are authored in the E0 bank and one in the E1 bank, while existing
bounded glyphs are reused.  The final ``FF`` byte of each fixed span is
preserved.  This is not the game's general encoder; ROM and source-bearing
outputs remain local or ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import patch_menu
import patch_message_batch_2


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
ALT_GLYPH_TABLE_FILE = 0x2E0BD4
ALT_GLYPH_STRIDE = 0x20
ALT_GLYPH_BANK_BIASES = {0xE0: 0x0000, 0xE1: 0x4000}
SPACE_CODE = 0xBF
DIRECT_CODES = {"。": 0x94}
PRESERVED_TAIL = bytes.fromhex("ff")


MESSAGE_SPECS = (
    {
        "string_id": "dqmch:a9hj:g06:v00:m0042",
        "file_offset": 0x286773,
        "span_length": 15,
        "data_length": 14,
        "expected_sha256": "75bec2c93420027364ba14a0f34ca6d835c729dd65fa356696183633b964bbf2",
        "source_hash": "bbfc4f6a5bc385cbb04598b9b3337a1598207a017e015c1f97ccdb8b56527719",
        "target": "已拒絕對戰。",
        "target_hans": "已拒绝对战。",
    },
    {
        "string_id": "dqmch:a9hj:g06:v00:m0043",
        "file_offset": 0x286782,
        "span_length": 16,
        "data_length": 15,
        "expected_sha256": "0121725cf66a099c558398c377bb7370751dfc2d015ebf33424c04f48eea66e2",
        "source_hash": "f7319c4fcb2304ca7ff5dfbc72446d8ad7859d216d86cd6a262a529fceaa5452",
        "target": "對方拒絕對戰。",
        "target_hans": "对方拒绝对战。",
    },
)


# These slots are clean-unused and disjoint from every earlier bounded
# allocation.  E0/F7 is distinct from E1/F7, which is already used by batch 5.
NEW_GLYPH_SLOTS = {
    "方": (0xE1, 0xFF),
    "拒": (0xE0, 0x22),
    "絕": (0xE0, 0xF7),
}
REUSED_GLYPH_SLOTS = {
    "已": (0xE1, patch_message_batch_2.GLYPH_SLOTS["已"]),
    "對": (0xE1, patch_menu.GLYPH_SLOTS["對"]),
    "戰": (0xE1, patch_menu.GLYPH_SLOTS["戰"]),
}
GLYPH_SLOTS = {**NEW_GLYPH_SLOTS, **REUSED_GLYPH_SLOTS}


# Authored 8x8 proof tiles, not an imported or unlicensed font.
NEW_GLYPH_BITMAPS = {
    "方": ("#######.", "#.....#.", "#.....#.", "#######.", "#..#....", "#..#....", "#...#...", "#....##."),
    "拒": ("#..#....", "#######.", "#..#....", "#######.", "#..#.#..", "#...##..", "#..#.#..", "#...#..."),
    "絕": ("#.#.##..", ".#####..", "#.#.#...", "#######.", "#..#....", ".#####..", "#.#.#...", "...#...."),
}
GLYPH_BITMAPS = {
    **NEW_GLYPH_BITMAPS,
    "已": patch_message_batch_2.GLYPH_BITMAPS["已"],
    "對": patch_menu.GLYPH_BITMAPS["對"],
    "戰": patch_menu.GLYPH_BITMAPS["戰"],
}


def validate_rom(data: bytes) -> dict[str, str | int]:
    crc32 = __import__("zlib").crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected clean 8 MiB ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")
    return {"size": len(data), "crc32": f"{crc32:08X}", "sha256": sha256}


def load_jsonl_entry(path: pathlib.Path, string_id: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("string_id") == string_id:
                return entry
    raise ValueError(f"missing {string_id} in {path}")


def validate_bitmaps() -> dict[str, bytes]:
    if set(GLYPH_SLOTS) != set(GLYPH_BITMAPS):
        raise ValueError("glyph slot and bitmap assignments differ")
    if len(set(GLYPH_SLOTS.values())) != len(GLYPH_SLOTS):
        raise ValueError("duplicate alternate glyph slot")
    tiles = {character: patch_menu.tile_bytes(rows) for character, rows in GLYPH_BITMAPS.items()}
    if any(not any(tile) for tile in tiles.values()):
        raise ValueError("authored glyph bitmap is empty")
    return tiles


def validate_ledger(ledger: dict[str, object], source: dict[str, object], spec: dict[str, object]) -> None:
    string_id = spec["string_id"]
    if ledger.get("string_id") != string_id:
        raise ValueError(f"unexpected ledger string_id for {string_id}")
    source_hash = spec["source_hash"]
    if ledger.get("source_hash") != source_hash:
        raise ValueError(f"ledger source hash mismatch for {string_id}")
    if hashlib.sha256(str(source.get("text", "")).encode("utf-8")).hexdigest() != source_hash:
        raise ValueError(f"local source table hash mismatch for {string_id}")
    targets = ledger.get("targets")
    if not isinstance(targets, dict):
        raise ValueError(f"ledger targets missing for {string_id}")
    tw = targets.get("zh-TW")
    hans = targets.get("zh-Hans")
    if not isinstance(tw, dict) or tw.get("text") != spec["target"]:
        raise ValueError(f"unexpected zh-TW target for {string_id}")
    if not isinstance(hans, dict) or hans.get("text") != spec["target_hans"]:
        raise ValueError(f"unexpected zh-Hans target for {string_id}")


def assert_new_allocations_unused(decoded: pathlib.Path) -> None:
    allocated = set(NEW_GLYPH_SLOTS.values())
    for line in decoded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        for token in record.get("tokens", []):
            if token.get("kind") != "alt-glyph":
                continue
            slot = (int(token.get("lead")), int(token.get("value")))
            if slot in allocated:
                raise ValueError(f"new alternate glyph slot is already used: {slot[0]:02X}/{slot[1]:02X}")


def encode_target(text: str, data_length: int) -> bytes:
    output = bytearray()
    for character in text:
        if character == " ":
            output.append(SPACE_CODE)
        elif character in DIRECT_CODES:
            output.append(DIRECT_CODES[character])
        else:
            try:
                lead, index = GLYPH_SLOTS[character]
            except KeyError as error:
                raise ValueError(f"target character has no bounded glyph slot: {character!r}") from error
            output.extend((lead, index))
    if len(output) > data_length:
        raise ValueError(f"target needs {len(output)} bytes, message allows {data_length}")
    output.extend(bytes((SPACE_CODE,)) * (data_length - len(output)))
    result = bytes(output) + PRESERVED_TAIL
    return result


def patch(
    rom: bytes,
    ledger: pathlib.Path,
    source_table: pathlib.Path,
    decoded: pathlib.Path,
) -> tuple[bytes, dict[str, object]]:
    validate_rom(rom)
    tiles = validate_bitmaps()
    assert_new_allocations_unused(decoded)
    result = bytearray(rom)
    for spec in MESSAGE_SPECS:
        string_id = str(spec["string_id"])
        validate_ledger(load_jsonl_entry(ledger, string_id), load_jsonl_entry(source_table, string_id), spec)
        offset = int(spec["file_offset"])
        span_length = int(spec["span_length"])
        original_span = rom[offset:offset + span_length]
        if hashlib.sha256(original_span).hexdigest() != spec["expected_sha256"]:
            raise ValueError(f"message span changed for {string_id}; refusing non-baseline input")
        encoded = encode_target(str(spec["target"]), int(spec["data_length"]))
        if len(encoded) != span_length:
            raise ValueError(f"encoded span length mismatch for {string_id}")
        result[offset:offset + span_length] = encoded
    for character, (lead, index) in GLYPH_SLOTS.items():
        start = ALT_GLYPH_TABLE_FILE + ALT_GLYPH_BANK_BIASES[lead] + index * ALT_GLYPH_STRIDE
        result[start:start + ALT_GLYPH_STRIDE] = tiles[character]
    changed = sum(before != after for before, after in zip(rom, result))
    return bytes(result), {
        "rom_sha256": EXPECTED_SHA256,
        "string_ids": [spec["string_id"] for spec in MESSAGE_SPECS],
        "new_glyph_slots": {character: f"{lead:02X}/{index:02X}" for character, (lead, index) in NEW_GLYPH_SLOTS.items()},
        "reused_glyph_slots": {character: f"{lead:02X}/{index:02X}" for character, (lead, index) in REUSED_GLYPH_SLOTS.items()},
        "changed_byte_count": changed,
        "runtime_qa": "not-run",
    }


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
        patched, receipt = patch(args.rom.read_bytes(), args.ledger, args.source_table, args.decoded)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(patched)
        receipt["output"] = str(args.out)
        receipt["patched_sha256"] = hashlib.sha256(patched).hexdigest()
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"patch_message_batch_8: {error}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
