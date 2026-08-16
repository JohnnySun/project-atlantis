#!/usr/bin/env python3
"""Cross-check the clean menu tile sequence against the ROM glyph table.

The stable second-A capture has ten consecutive BG0 entries at screen-block
offset 0xE844 and their character data starts at VRAM 0xC000.  This command
prints only the matched code units (single-byte indices or pair units); the
local VRAM dump is source-bearing research data and must not be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import zlib


ROM_SIZE = 0x800000
ROM_BASE = 0x08000000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955DAF8D4D438486A9213D407B2B48CE".lower()
GLYPH_TABLE_FILE = 0x2DF3D4
GLYPH_STRIDE = 32
DEFAULT_SCREEN_OFFSET = 0xE844
DEFAULT_CHARBASE = 0xC000
DEFAULT_TILE_COUNT = 10
EXPECTED_MENU_PREFIX = ["33", "26", "34", "52", "2E", "53", "43", "9234", "4B", "55"]


def validate_rom(data: bytes) -> None:
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean ROM: CRC32={crc32:08X}, SHA256={sha256}")


def pair_mask(tile: bytes, lead: int, trail: int, state_byte_10: int) -> bytes:
    if lead == 0x93:
        mask = 0xF1FFFFFF
    elif trail == 0x30 and (state_byte_10 & 1) == 0:
        mask = 0xF1F1FFFF
    else:
        mask = 0xFF1FFFFF
    second = int.from_bytes(tile[4:8], "little") & mask
    return tile[:4] + second.to_bytes(4, "little") + tile[8:]


def table_tile(rom: bytes, index: int) -> bytes:
    start = GLYPH_TABLE_FILE + index * GLYPH_STRIDE
    return rom[start:start + GLYPH_STRIDE]


def match_tile(rom: bytes, tile: bytes, state_byte_10: int) -> list[str]:
    matches = [f"{index:02X}" for index in range(0x100) if table_tile(rom, index) == tile]
    for lead in (0x92, 0x93):
        for trail in range(0x100):
            left = table_tile(rom, lead)
            right = table_tile(rom, trail)
            combined = bytes(a | b for a, b in zip(left, right))
            if pair_mask(combined, lead, trail, state_byte_10) == tile:
                matches.append(f"{lead:02X}{trail:02X}")
    return matches


def read_menu_units(
    rom: bytes,
    vram: bytes,
    screen_offset: int,
    charbase: int,
    tile_count: int,
    state_byte_10: int,
) -> tuple[list[int], list[list[str]]]:
    tile_ids: list[int] = []
    matches: list[list[str]] = []
    for index in range(tile_count):
        entry = int.from_bytes(vram[screen_offset + index * 2:screen_offset + index * 2 + 2], "little")
        tile_id = entry & 0x3FF
        tile_ids.append(tile_id)
        start = charbase + tile_id * GLYPH_STRIDE
        tile = vram[start:start + GLYPH_STRIDE]
        matches.append(match_tile(rom, tile, state_byte_10))
    return tile_ids, matches


def script_prefix(path: pathlib.Path, pointer_cpu: str) -> list[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("pointer_cpu") != pointer_cpu:
            continue
        units: list[str] = []
        for token in record["tokens"]:
            if token["kind"] == "single-byte-candidate":
                units.append(f"{int(token['value']):02X}")
            elif token["kind"] == "pair":
                units.append(f"{int(token['lead']):02X}{int(token['trail']):02X}")
        return units
    raise ValueError(f"script pointer not found: {pointer_cpu}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("vram", type=pathlib.Path)
    parser.add_argument("--screen-offset", type=lambda value: int(value, 0), default=DEFAULT_SCREEN_OFFSET)
    parser.add_argument("--charbase", type=lambda value: int(value, 0), default=DEFAULT_CHARBASE)
    parser.add_argument("--tile-count", type=int, default=DEFAULT_TILE_COUNT)
    parser.add_argument("--state-byte-10", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--decoded", type=pathlib.Path)
    parser.add_argument("--pointer-cpu")
    args = parser.parse_args()
    try:
        if (args.decoded is None) != (args.pointer_cpu is None):
            raise ValueError("--decoded and --pointer-cpu must be provided together")
        rom = args.rom.read_bytes()
        validate_rom(rom)
        vram = args.vram.read_bytes()
        tile_ids, matches = read_menu_units(
            rom, vram, args.screen_offset, args.charbase, args.tile_count, args.state_byte_10
        )
        script_units = None
        if args.decoded is not None and args.pointer_cpu is not None:
            script_units = script_prefix(args.decoded, args.pointer_cpu)
    except (OSError, ValueError, IndexError) as error:
        print(f"verify_menu_glyphs: {error}", file=sys.stderr)
        return 2

    print("rom-sha256", EXPECTED_SHA256)
    print("screen-offset", f"0x{args.screen_offset:X}", "charbase", f"0x{args.charbase:X}")
    print("tile-ids", [f"0x{tile_id:03X}" for tile_id in tile_ids])
    print("matches", matches)
    print("unmatched-indices", [index for index, row in enumerate(matches) if not row])
    if script_units is not None:
        print("script-pointer", args.pointer_cpu)
        print("script-prefix-match", script_units[:len(EXPECTED_MENU_PREFIX)] == EXPECTED_MENU_PREFIX)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
