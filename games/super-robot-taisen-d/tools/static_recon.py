#!/usr/bin/env python3
"""Game-agnostic first-pass structural reconnaissance for an A6SJ ROM.

This deliberately reports hypotheses, not decoded script. Shift-JIS validity,
ROM-address-shaped words, BIOS compression headers, and SWI byte patterns are
all noisy signals. A positive result must be confirmed by code/data flow or a
runtime read before it is used by an extractor.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
from collections import Counter

from fingerprint_rom import fingerprint


SWI_NAMES = {
    0x11: "LZ77UnCompWram",
    0x12: "LZ77UnCompVram",
    0x13: "HuffUnComp",
    0x14: "RLUnCompWram",
    0x15: "RLUnCompVram",
}


def sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def sjis_runs(data: bytes, minimum: int = 8) -> list[tuple[int, int, int, int]]:
    """Return (start, end, decoded_chars, unique_chars) for structural runs."""
    runs: list[tuple[int, int, int, int]] = []
    i = 0
    start = None
    end = 0
    chars = 0
    while i < len(data):
        width = 0
        if sjis_lead(data[i]) and i + 1 < len(data) and sjis_trail(data[i + 1]):
            width = 2
        elif 0xA1 <= data[i] <= 0xDF or 0x20 <= data[i] <= 0x7E:
            width = 1
        if width:
            if start is None:
                start = i
                chars = 0
            chars += 1
            i += width
            end = i
            continue
        if start is not None and chars >= minimum:
            text = data[start:end].decode("shift_jis", errors="replace")
            runs.append((start, end, chars, len(set(text))))
        start = None
        chars = 0
        i += 1
    if start is not None and chars >= minimum:
        text = data[start:end].decode("shift_jis", errors="replace")
        runs.append((start, end, chars, len(set(text))))
    return runs


def pointer_runs(data: bytes, minimum: int = 8) -> list[tuple[int, int, int, int]]:
    words = struct.unpack("<%dI" % (len(data) // 4), data[: len(data) // 4 * 4])
    low = 0x08000000
    high = low + len(data) - 1
    candidates = []
    i = 0
    while i < len(words):
        if not low <= words[i] <= high:
            i += 1
            continue
        j = i
        while j + 1 < len(words) and low <= words[j + 1] <= high and words[j + 1] >= words[j]:
            j += 1
        if j - i + 1 >= minimum:
            candidates.append((i * 4, j - i + 1, words[i], words[j]))
        i = j + 1
    return sorted(candidates, key=lambda row: (-row[1], row[0]))


def compression_candidates(data: bytes) -> Counter[int]:
    counts: Counter[int] = Counter()
    for offset in range(0, len(data) - 4, 4):
        tag = data[offset]
        if tag not in (0x10, 0x24, 0x30):
            continue
        size = data[offset + 1] | data[offset + 2] << 8 | data[offset + 3] << 16
        if 16 <= size <= 2 * 1024 * 1024:
            counts[tag] += 1
    return counts


def swi_counts(data: bytes) -> Counter[int]:
    counts: Counter[int] = Counter()
    for offset in range(0, len(data) - 1, 2):
        if data[offset + 1] == 0xDF and data[offset] in SWI_NAMES:
            counts[data[offset]] += 1
    return counts


def exact_sjis_offsets(data: bytes, words: dict[str, bytes]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for label, needle in words.items():
        result[label] = [
            offset for offset in range(0, len(data) - len(needle) + 1)
            if data.startswith(needle, offset)
        ][:20]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--min-sjis-chars", type=int, default=8)
    parser.add_argument("--min-pointer-run", type=int, default=8)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    data = args.rom.read_bytes()
    print("=== identity ===")
    print(fingerprint(args.rom))

    runs = sorted(sjis_runs(data, args.min_sjis_chars), key=lambda row: (-row[2], row[0]))
    print(f"=== structural Shift-JIS runs >= {args.min_sjis_chars}: {len(runs)} ===")
    for start, end, chars, unique in runs[: args.top]:
        print(f"  0x{start:06x}-0x{end:06x} chars={chars} unique={unique}")

    sentinel_hex = {
        "hai": "82cd82a2",
        "iie": "82a282a282a682a6",
        "level": "838c8378838b",
        "tatakau": "82bd82bd82a982a4",
        "nigeru": "82c982b082e9",
        "dougu": "82c782a482ae",
        "save": "835a815b8375",
        "load": "838d815b8368",
        "command": "8352837d83938368",
    }
    print("=== standard Shift-JIS sentinel offsets (first 20 each) ===")
    for label, offsets in exact_sjis_offsets(
        data, {key: bytes.fromhex(value) for key, value in sentinel_hex.items()}
    ).items():
        print(f"  {label}: {len(offsets)} shown={','.join(f'0x{x:06x}' for x in offsets) or '-'}")

    pointers = pointer_runs(data, args.min_pointer_run)
    print(f"=== non-decreasing ROM-pointer candidates: {len(pointers)} ===")
    for offset, length, first, last in pointers[: args.top]:
        print(
            f"  0x{offset:06x} words={length} "
            f"first=0x{first:08x} last=0x{last:08x} span=0x{last-first:x}"
        )

    compression = compression_candidates(data)
    print("=== BIOS compression-header candidates (4-byte aligned) ===")
    for tag, name in ((0x10, "LZ77"), (0x24, "Huffman"), (0x30, "RLE")):
        print(f"  {name} 0x{tag:02x}: {compression[tag]}")

    print("=== halfword-aligned compression-related SWI byte candidates ===")
    for imm, name in SWI_NAMES.items():
        print(f"  swi 0x{imm:02x} {name}: {swi_counts(data)[imm]}")


if __name__ == "__main__":
    main()
