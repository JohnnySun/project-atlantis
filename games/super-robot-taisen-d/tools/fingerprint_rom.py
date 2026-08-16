#!/usr/bin/env python3
"""Read-only GBA ROM identity and checksum verifier for Super Robot Taisen D.

This tool intentionally reports only cartridge metadata and hashes. It never
extracts or writes game text, so its JSON output is safe to keep as a local
reproducibility receipt (the ROM itself remains under ignored roms/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import zlib


def fingerprint(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 0xC0:
        raise ValueError(f"ROM is shorter than the GBA header: {len(data)} bytes")

    title_raw = data[0xA0:0xAC]
    game_code_raw = data[0xAC:0xB0]
    maker_code_raw = data[0xB0:0xB2]
    try:
        title = title_raw.rstrip(b"\x00").decode("ascii")
        game_code = game_code_raw.decode("ascii")
        maker_code = maker_code_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("GBA identity fields are not ASCII") from exc

    stored_complement = data[0xBD]
    calculated_complement = (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF
    return {
        "path": str(path),
        "size_bytes": len(data),
        "title": title,
        "game_code": game_code,
        "maker_code": maker_code,
        "software_version": data[0xBC],
        "header_complement": {
            "stored": f"0x{stored_complement:02x}",
            "calculated": f"0x{calculated_complement:02x}",
            "matches": stored_complement == calculated_complement,
        },
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--expected-game-code")
    parser.add_argument("--expected-crc32")
    args = parser.parse_args()

    result = fingerprint(args.rom)
    if not result["header_complement"]["matches"]:
        raise SystemExit("GBA header complement mismatch")
    if args.expected_game_code and result["game_code"] != args.expected_game_code:
        raise SystemExit(
            f"game code mismatch: expected {args.expected_game_code}, "
            f"got {result['game_code']}"
        )
    if args.expected_crc32 and result["crc32"] != args.expected_crc32.lower():
        raise SystemExit(
            f"CRC32 mismatch: expected {args.expected_crc32.lower()}, "
            f"got {result['crc32']}"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
