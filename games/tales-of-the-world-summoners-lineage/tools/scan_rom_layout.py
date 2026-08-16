#!/usr/bin/env python3
"""Read-only first-pass structural scan for the Summoner's Lineage JP ROM.

This deliberately reports aggregate evidence rather than dumping candidate bytes
or recovered game text.  It is a reconnaissance tool, not a decoder: a hit in a
binary scan is only a candidate until a runtime or byte-identical corroboration
is recorded in the game's research notes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path


ROM_BASE = 0x08000000
HEADER_CHECKSUM_START = 0xA0
HEADER_CHECKSUM_END = 0xBD  # exclusive; checksum byte itself is at 0xBD
# This is a noise-control bound for the unvalidated signature scan, not a
# claim about every resource's possible decompressed size.  Real GBA tile,
# map, and font payloads are normally far below this; larger candidates need a
# dedicated decoder/reference proof before they are worth reporting.
MAX_SYNTACTIC_COMPRESSION_OUTPUT = 0x40000

# These are intentionally ordinary UI/gameplay sentinels.  They are used only
# to test for literal Shift-JIS storage, not as a source-text corpus.
SHIFT_JIS_SENTINELS = (
    "はい",
    "いいえ",
    "セーブ",
    "ロード",
    "戦闘",
    "出撃",
    "編成",
    "召喚",
    "ステータス",
    "アイテム",
    "レベル",
    "名前",
    "地図",
    "イベント",
    "終了",
    "はじめから",
    "つづきから",
)


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        hit = data.find(needle, start)
        if hit < 0:
            return offsets
        offsets.append(hit)
        start = hit + 1


def entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = [0] * 256
    for value in chunk:
        counts[value] += 1
    length = len(chunk)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts
        if count
    )


def scan_compression_candidates(data: bytes) -> dict[str, object]:
    # GBA BIOS formats use a one-byte tag followed by a 24-bit little-endian
    # decompressed size.  This only checks syntactic plausibility and alignment;
    # it does not claim that any candidate is actually consumed by the game.
    tags = {
        0x10: "lz77",
        0x11: "lz77-variant",
        0x20: "huffman",
        0x24: "huffman-variant",
        0x30: "rle",
        0x40: "diff8-variant",
        0x80: "diff16-variant",
    }
    # A decompressor can theoretically produce more bytes than the ROM stores,
    # but a first-pass ROM-local scan has no reason to treat a declaration larger
    # than the entire input image as useful.  This removes the most spectacular
    # binary-noise false positives while keeping the result explicitly
    # syntactic-only.
    maximum_declared_size = min(len(data), MAX_SYNTACTIC_COMPRESSION_OUTPUT)
    result: dict[str, object] = {
        "syntactic_only": True,
        "maximum_declared_size": f"0x{maximum_declared_size:x}",
    }
    for tag, label in tags.items():
        all_hits: list[tuple[int, int]] = []
        aligned_hits: list[tuple[int, int]] = []
        needle = bytes((tag,))
        for offset in find_all(data, needle):
            if offset + 4 > len(data):
                continue
            size = data[offset + 1] | (data[offset + 2] << 8) | (data[offset + 3] << 16)
            # Avoid treating absurd sizes or empty headers as useful candidates.
            if not 0 < size <= maximum_declared_size:
                continue
            candidate = (offset, size)
            all_hits.append(candidate)
            if offset % 4 == 0:
                aligned_hits.append(candidate)
        result[label] = {
            "tag": f"0x{tag:02x}",
            "plausible_hits": len(all_hits),
            "aligned_hits": len(aligned_hits),
            "largest_declared_sizes": sorted(
                (size for _, size in all_hits), reverse=True
            )[:10],
            "first_aligned_offsets": [
                f"0x{offset:x}" for offset, _ in aligned_hits[:10]
            ],
        }
    return result


def scan_pointer_runs(data: bytes) -> list[dict[str, object]]:
    candidates: list[tuple[int, int]] = []
    upper = ROM_BASE + len(data)
    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if ROM_BASE <= value < upper:
            candidates.append((offset, value - ROM_BASE))

    runs: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for candidate in candidates:
        if current and candidate[0] != current[-1][0] + 4:
            if len(current) >= 4:
                runs.append(current)
            current = []
        current.append(candidate)
    if len(current) >= 4:
        runs.append(current)

    summarized = []
    for run in runs:
        summarized.append(
            {
                "file_range": [f"0x{run[0][0]:x}", f"0x{run[-1][0] + 4:x}"],
                "word_count": len(run),
                "pointed_file_range": [
                    f"0x{min(value for _, value in run):x}",
                    f"0x{max(value for _, value in run) + 1:x}",
                ],
                "monotonic_non_decreasing": all(
                    run[index][1] <= run[index + 1][1]
                    for index in range(len(run) - 1)
                ),
            }
        )
    summarized.sort(key=lambda item: item["word_count"], reverse=True)
    return summarized[:20]


def scan_ascii_runs(data: bytes) -> dict[str, object]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for offset, value in enumerate(data + b"\0"):
        printable = 0x20 <= value <= 0x7E
        if printable and start is None:
            start = offset
        elif not printable and start is not None:
            length = offset - start
            if length >= 8:
                runs.append((start, length))
            start = None
    return {
        "runs_at_least_8": len(runs),
        "runs_at_least_16": sum(length >= 16 for _, length in runs),
        "longest_lengths": sorted((length for _, length in runs), reverse=True)[:20],
        "first_offsets": [f"0x{offset:x}" for offset, _ in runs[:20]],
    }


def scan_rom(path: Path, chunk_size: int) -> dict[str, object]:
    data = path.read_bytes()
    header = data[0xA0:0xC0]
    title = data[0xA0:0xAC].rstrip(b"\0").decode("ascii", errors="replace")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    maker_code = data[0xB0:0xB2].decode("ascii", errors="replace")
    actual_checksum = data[0xBD]
    calculated_checksum = (
        0x19 - sum(data[HEADER_CHECKSUM_START:HEADER_CHECKSUM_END])
    ) & 0xFF

    sentinels = {}
    for text in SHIFT_JIS_SENTINELS:
        encoded = text.encode("shift_jis")
        offsets = find_all(data, encoded)
        sentinels[text] = {
            "encoded_length": len(encoded),
            "hits": len(offsets),
            "first_offsets": [f"0x{offset:x}" for offset in offsets[:8]],
        }

    chunks = []
    for offset in range(0, len(data), chunk_size):
        chunk = data[offset : offset + chunk_size]
        chunks.append(
            {
                "offset": f"0x{offset:x}",
                "size": len(chunk),
                "entropy": round(entropy(chunk), 5),
                "all_ff": all(value == 0xFF for value in chunk),
                "all_zero": all(value == 0 for value in chunk),
            }
        )

    return {
        "rom_path": str(path),
        "size": len(data),
        "hashes": {
            "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
            "md5": hashlib.md5(data).hexdigest(),
            "sha1": hashlib.sha1(data).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
        },
        "gba_header": {
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "software_version": data[0xBC],
            "header_checksum": f"0x{actual_checksum:02x}",
            "calculated_header_checksum": f"0x{calculated_checksum:02x}",
            "header_checksum_valid": actual_checksum == calculated_checksum,
            "header_bytes_0xa0_0xbf": header.hex(),
        },
        "literal_shift_jis_sentinels": sentinels,
        "ascii_runs": scan_ascii_runs(data),
        "compression_candidates": scan_compression_candidates(data),
        "four_byte_rom_pointer_runs": scan_pointer_runs(data),
        "entropy_chunks": chunks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--chunk-size",
        type=lambda value: int(value, 0),
        default=0x10000,
        help="entropy chunk size (default: 0x10000)",
    )
    args = parser.parse_args()
    json.dump(scan_rom(args.rom, args.chunk_size), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
