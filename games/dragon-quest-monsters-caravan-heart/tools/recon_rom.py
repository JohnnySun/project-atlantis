#!/usr/bin/env python3
"""Read-only structural reconnaissance for the A9HJ GBA ROM.

The report deliberately avoids printing decoded game text.  It records ROM
identity and counts/locations of candidate structures so a later reverse-
engineering pass can be reproduced without turning this tool into a source
script dump.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
ROM_MIRROR_BASE = 0x09000000
GBA_HEADER_END = 0xC0

# These are short, conventional UI sentinels.  We report labels and offsets,
# never their decoded content, because this tool must remain safe to commit.
SJIS_SENTINELS = {
    "yes": "はい",
    "no": "いいえ",
    "level": "レベル",
    "fight": "たたかう",
    "run": "にげる",
    "item": "どうぐ",
    "save": "セーブ",
    "load": "ロード",
    "name": "なまえ",
    "monster": "モンスター",
    "caravan": "キャラバン",
    "dragon_quest": "ドラゴンクエスト",
}


def gba_header_checksum(data: bytes) -> tuple[int, int]:
    """Return (stored, calculated) Nintendo GBA header complement checksum."""

    stored = data[0xBD]
    calculated = (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF
    return stored, calculated


def trailing_fill(data: bytes, fill: int = 0xFF) -> int:
    index = len(data)
    while index and data[index - 1] == fill:
        index -= 1
    return len(data) - index


def ascii_runs(data: bytes, minimum: int = 4) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(data):
        printable = 0x20 <= value <= 0x7E
        if printable and start is None:
            start = index
        elif not printable and start is not None:
            if index - start >= minimum:
                runs.append((start, index - start))
            start = None
    if start is not None and len(data) - start >= minimum:
        runs.append((start, len(data) - start))
    return runs


def sjis_pair(value: int) -> bool:
    return (0x81 <= value <= 0x9F) or (0xE0 <= value <= 0xFC)


def sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0xFC and value != 0x7F


def sjis_like_runs(data: bytes) -> list[tuple[int, int]]:
    """Find contiguous byte spans that can be partitioned as Shift-JIS.

    This is only a structural signal.  It intentionally does not decode or
    print any candidate text; binary data often produces false positives.
    """

    runs: list[tuple[int, int]] = []
    start: int | None = None
    index = 0
    while index < len(data):
        value = data[index]
        valid = False
        width = 1
        if value <= 0x7F or 0xA1 <= value <= 0xDF:
            valid = True
        elif sjis_pair(value) and index + 1 < len(data) and sjis_trail(data[index + 1]):
            valid = True
            width = 2
        if valid:
            if start is None:
                start = index
            index += width
        else:
            if start is not None and index - start >= 8:
                runs.append((start, index - start))
            start = None
            index += 1
    if start is not None and len(data) - start >= 8:
        runs.append((start, len(data) - start))
    return runs


def pointer_summary(data: bytes) -> dict[str, object]:
    counts = {"rom_080": 0, "rom_090": 0, "all_rom": 0}
    offsets: list[int] = []
    by_alignment: dict[str, int] = {"aligned_4": 0, "unaligned_4": 0}
    for position in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, position)[0]
        in_rom = False
        if ROM_BASE <= value < ROM_BASE + len(data):
            counts["rom_080"] += 1
            in_rom = True
        elif ROM_MIRROR_BASE <= value < ROM_MIRROR_BASE + len(data):
            counts["rom_090"] += 1
            in_rom = True
        if in_rom:
            counts["all_rom"] += 1
            offsets.append(position)
            if position % 4 == 0:
                by_alignment["aligned_4"] += 1
            else:
                by_alignment["unaligned_4"] += 1
    clusters: list[dict[str, int]] = []
    if offsets:
        cluster_start = previous = offsets[0]
        for position in offsets[1:]:
            if position - previous > 4:
                clusters.append({"offset": cluster_start, "count": (previous - cluster_start) // 4 + 1})
                cluster_start = position
            previous = position
        clusters.append({"offset": cluster_start, "count": (previous - cluster_start) // 4 + 1})
    clusters.sort(key=lambda item: (-item["count"], item["offset"]))
    return {
        "counts": counts,
        "alignment": by_alignment,
        "largest_clusters": clusters[:20],
    }


def compression_summary(data: bytes) -> dict[str, object]:
    signatures = {"lz77_10": 0, "lz77_11": 0, "huffman_20": 0, "rle_30": 0}
    in_file: dict[str, int] = {key: 0 for key in signatures}
    examples: dict[str, list[int]] = {key: [] for key in signatures}
    for offset in range(0, len(data) - 3):
        marker = data[offset]
        key = {0x10: "lz77_10", 0x11: "lz77_11", 0x20: "huffman_20", 0x30: "rle_30"}.get(marker)
        if key is None:
            continue
        signatures[key] += 1
        expanded_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
        # The header itself does not prove that a candidate is used; this only
        # filters impossible sizes and records no more than five examples.
        if 0 < expanded_size <= len(data) * 8:
            in_file[key] += 1
            if len(examples[key]) < 5:
                examples[key].append(offset)
    return {"all_byte_offsets": signatures, "plausible_size": in_file, "examples": examples}


def sentinel_summary(data: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    for label, text in SJIS_SENTINELS.items():
        encoded = text.encode("shift_jis")
        offsets: list[int] = []
        start = 0
        while True:
            found = data.find(encoded, start)
            if found < 0:
                break
            offsets.append(found)
            start = found + 1
        result[label] = {"byte_length": len(encoded), "matches": len(offsets), "offsets": offsets[:20]}
    return result


def header_report(data: bytes) -> dict[str, object]:
    stored, calculated = gba_header_checksum(data)
    title = data[0xA0:0xAC].decode("ascii", errors="replace").rstrip("\0 ")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    maker_code = data[0xB0:0xB2].decode("ascii", errors="replace")
    return {
        "title": title,
        "game_code": game_code,
        "maker_code": maker_code,
        "software_version": data[0xBC],
        "header_complement_stored": stored,
        "header_complement_calculated": calculated,
        "header_complement_matches": stored == calculated,
    }


def report(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    runs = ascii_runs(data)
    sjis_runs = sjis_like_runs(data)
    return {
        "path": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08X}",
        "trailing_ff_bytes": trailing_fill(data),
        "header": header_report(data),
        "ascii": {
            "run_count_min_4": len(runs),
            "longest_runs": [
                {"offset": offset, "length": length} for offset, length in sorted(runs, key=lambda item: (-item[1], item[0]))[:20]
            ],
        },
        "shift_jis_structural": {
            "run_count_min_8": len(sjis_runs),
            "longest_runs": [
                {"offset": offset, "length": length}
                for offset, length in sorted(sjis_runs, key=lambda item: (-item[1], item[0]))[:20]
            ],
        },
        "shift_jis_sentinels": sentinel_summary(data),
        "rom_pointer_candidates": pointer_summary(data),
        "bios_compression_signatures": compression_summary(data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.rom), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
