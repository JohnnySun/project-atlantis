#!/usr/bin/env python3
"""Analyze A9PJ's name-entry BG1 tilemap without emitting glyph bytes.

The final M1.5 capture showed a regular kana keyboard in BG1.  This tool
keeps the known screen coordinates, tilemap flags, runtime tile addresses,
SHA-256 values, and clean-ROM exact-match offsets.  It never writes the ROM
or includes tile/source bytes in its JSON output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from m15_navigate_probe import identity  # noqa: E402


VRAM_BASE = 0x06000000
VRAM_SIZE = 0x18000
BG1_CHARBASE = 0x4000
BG1_SCREENBASE = 0x0800
TILE_BYTES = 32
SCREENBLOCK_WIDTH = 32
SCREENBLOCK_HEIGHT = 32

# These are known positions in the rendered, fixed-order kana grid.  The
# labels are ground-truth layout annotations, not extracted game script.
KNOWN_KANA = (
    ("a-row-1", "あ", 1, 7),
    ("a-row-2", "い", 2, 7),
    ("a-row-3", "う", 3, 7),
    ("a-row-4", "え", 4, 7),
    ("a-row-5", "お", 5, 7),
    ("ka-row-1", "か", 1, 8),
    ("ka-row-2", "き", 2, 8),
    ("ka-row-3", "く", 3, 8),
)


def tilemap_entry(vram: bytes, x: int, y: int) -> dict[str, int]:
    """Decode one regular BG screenblock entry into metadata fields."""

    if len(vram) < VRAM_SIZE:
        raise ValueError(f"VRAM must be at least 0x{VRAM_SIZE:X} bytes")
    if not 0 <= x < SCREENBLOCK_WIDTH or not 0 <= y < SCREENBLOCK_HEIGHT:
        raise ValueError("tilemap coordinate outside 32x32 screenblock")
    offset = BG1_SCREENBASE + 2 * (y * SCREENBLOCK_WIDTH + x)
    entry = int.from_bytes(vram[offset:offset + 2], "little")
    return {
        "x": x,
        "y": y,
        "entry": entry,
        "tile_id": entry & 0x03FF,
        "hflip": (entry >> 10) & 1,
        "vflip": (entry >> 11) & 1,
        "palette_bank": (entry >> 12) & 0x0F,
        "map_file_offset": offset,
    }


def tile_bytes(vram: bytes, tile_id: int) -> bytes:
    """Return one runtime 4bpp tile for hashing/matching only."""

    if not 0 <= tile_id < 0x400:
        raise ValueError("tile ID outside regular BG range")
    start = BG1_CHARBASE + tile_id * TILE_BYTES
    end = start + TILE_BYTES
    if end > len(vram):
        raise ValueError("tile extends past supplied VRAM")
    return vram[start:end]


def exact_matches(rom: bytes, needle: bytes, *, limit: int = 32) -> list[int]:
    """Find bounded exact matches without returning the matched bytes."""

    offsets: list[int] = []
    start = 0
    while len(offsets) < limit:
        offset = rom.find(needle, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    return offsets


def analyze(rom: bytes, vram: bytes) -> dict[str, object]:
    """Build commit-safe metadata for the selected known kana positions."""

    if len(vram) < VRAM_SIZE:
        raise ValueError(f"VRAM must be at least 0x{VRAM_SIZE:X} bytes")
    records: list[dict[str, object]] = []
    exact_match_count = 0
    aligned_exact_match_count = 0
    for slot, label, x, y in KNOWN_KANA:
        entry = tilemap_entry(vram, x, y)
        pixels = tile_bytes(vram, entry["tile_id"])
        matches = exact_matches(rom, pixels)
        aligned = [offset for offset in matches if offset % TILE_BYTES == 0]
        exact_match_count += bool(matches)
        aligned_exact_match_count += bool(aligned)
        records.append(
            {
                "slot": slot,
                "known_layout_label": label,
                "tilemap": entry,
                "runtime_tile_address": f"0x{VRAM_BASE + BG1_CHARBASE + entry['tile_id'] * TILE_BYTES:08X}",
                "runtime_tile_stride": TILE_BYTES,
                "tile_sha256": hashlib.sha256(pixels).hexdigest(),
                "rom_exact_match_count": len(matches),
                "rom_exact_match_offsets": [f"0x{offset:06X}" for offset in matches],
                "rom_exact_match_32byte_aligned_offsets": [
                    f"0x{offset:06X}" for offset in aligned
                ],
                "identity_status": (
                    "provisional"
                    if not (len(matches) == 1 and len(aligned) == 1)
                    else "provisional-aligned-single-match"
                ),
            }
        )

    tile_ids = [int(record["tilemap"]["tile_id"]) for record in records]
    return {
        "format": {
            "bg": "BG1",
            "bpp": 4,
            "charbase": BG1_CHARBASE,
            "screenbase": BG1_SCREENBASE,
            "tile_bytes": TILE_BYTES,
            "screenblock_dimensions": [SCREENBLOCK_WIDTH, SCREENBLOCK_HEIGHT],
        },
        "selected_position_count": len(records),
        "selected_tile_ids": tile_ids,
        "selected_tile_id_deltas": [
            tile_ids[index + 1] - tile_ids[index]
            for index in range(len(tile_ids) - 1)
        ],
        "runtime_fixed_stride": TILE_BYTES,
        "records": records,
        "exact_match_position_count": exact_match_count,
        "aligned_exact_match_position_count": aligned_exact_match_count,
        "confirmed_identity_count": 0,
        "identity_rule": (
            "requires known keyboard position + exact byte match + fixed-stride/table arithmetic; "
            "no selected position meets all three in this capture"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("vram", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    report = {
        "rom": identity(args.rom),
        "vram": {
            "path": str(args.vram),
            "sha256": hashlib.sha256(args.vram.read_bytes()).hexdigest(),
            "length": args.vram.stat().st_size,
        },
        "analysis": analyze(rom, args.vram.read_bytes()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
