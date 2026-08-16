#!/usr/bin/env python3
"""Verify one clean script record against a local text VRAM capture.

The decoded JSONL and VRAM dump are local source-bearing research artifacts.
This command prints only counts and mismatch positions, not raw text or tile
bytes.  It models the proven 32-byte table lookup, OR operation, and the
second-dword masks observed in the clean `0x08013738` routine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path


ROM_SIZE = 0x800000
ROM_BASE = 0x08000000
GLYPH_TABLE_FILE = 0x2DF3D4
GLYPH_STRIDE = 32
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"


def validate_rom(data: bytes) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean ROM: CRC32={crc32:08X}, SHA256={sha256}")


def load_record(path: Path, pointer: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("pointer_cpu") == pointer:
            return record
    raise ValueError(f"pointer not found in decoded JSONL: {pointer}")


def apply_pair_mask(tile: bytes, lead: int, trail: int, state_byte_10: int) -> bytes:
    if lead not in (0x92, 0x93):
        return tile
    if lead == 0x93:
        mask = 0xF1FFFFFF
    elif trail == 0x30 and (state_byte_10 & 1) == 0:
        mask = 0xF1F1FFFF
    else:
        mask = 0xFF1FFFFF
    masked = int.from_bytes(tile[4:8], "little") & mask
    return tile[:4] + masked.to_bytes(4, "little") + tile[8:]


def model_tiles(rom: bytes, record: dict[str, object], state_byte_10: int) -> list[bytes]:
    tiles: list[bytes] = []
    for token in record["tokens"]:  # type: ignore[union-attr]
        kind = token["kind"]
        if kind == "single-byte-candidate":
            codes = (int(token["value"]),)
            pair = None
        elif kind == "pair":
            codes = (int(token["lead"]), int(token["trail"]))
            pair = (codes[0], codes[1])
        else:
            continue
        entries = [
            rom[GLYPH_TABLE_FILE + code * GLYPH_STRIDE:GLYPH_TABLE_FILE + (code + 1) * GLYPH_STRIDE]
            for code in codes
        ]
        tile = entries[0] if len(entries) == 1 else bytes(a | b for a, b in zip(*entries))
        if pair is not None:
            tile = apply_pair_mask(tile, pair[0], pair[1], state_byte_10)
        tiles.append(tile)
    return tiles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("decoded", type=Path)
    parser.add_argument("vram", type=Path)
    parser.add_argument("--pointer-cpu", required=True)
    parser.add_argument("--vram-offset", type=lambda value: int(value, 0), default=0xC800)
    parser.add_argument("--state-byte-10", type=lambda value: int(value, 0), default=0)
    args = parser.parse_args()

    try:
        rom = args.rom.read_bytes()
        validate_rom(rom)
        record = load_record(args.decoded, args.pointer_cpu.upper().replace("0X", "0x"))
        actual = args.vram.read_bytes()
        expected = model_tiles(rom, record, args.state_byte_10)
        mismatches: list[int] = []
        diff_bytes: list[int] = []
        for index, tile in enumerate(expected):
            start = args.vram_offset + index * GLYPH_STRIDE
            observed = actual[start:start + GLYPH_STRIDE]
            if len(observed) != GLYPH_STRIDE or observed != tile:
                mismatches.append(index)
                diff_bytes.append(sum(a != b for a, b in zip(observed, tile)))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"verify_glyph_output: {error}", file=sys.stderr)
        return 2

    print("rom-sha256", EXPECTED_SHA256)
    print("pointer", record["pointer_cpu"], "glyph-tokens", len(expected))
    print("vram-offset", f"0x{args.vram_offset:X}")
    print("state-byte-10", f"0x{args.state_byte_10:02X}")
    print("exact-matches", len(expected) - len(mismatches), "/", len(expected))
    print("mismatch-indices", mismatches)
    print("mismatch-diff-bytes", diff_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
