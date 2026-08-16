#!/usr/bin/env python3
"""Read-only first-pass reconnaissance for the Japanese GBA ROM.

This tool intentionally reports structure and counts, not decoded source text.
It accepts either a raw ROM or a ZIP containing exactly one GBA-like member, so
the contributor can inspect a legally obtained dump without copying it into
the repository workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zipfile
import zlib
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence


ROM_MIN = 0x08000000
ROM_MAX = 0x0A000000
BLOCK_SIZE = 0x4000
COMPRESSED_HEADERS = {
    0x10: "lz77",
    0x11: "lz77_11",
    0x20: "huffman",
    0x30: "rl",
}

# These are only byte-pattern sentinels used to test whether ordinary
# Shift-JIS appears verbatim.  They are not extracted source records.
SHIFT_JIS_SENTINELS = {
    "yes": "はい",
    "no": "いいえ",
    "level": "レベル",
    "fight": "たたかう",
    "run": "にげる",
    "item": "どうぐ",
    "save": "セーブ",
    "load": "ロード",
    "command": "コマンド",
    "demon": "悪魔",
    "companion": "仲魔",
    "magic": "魔法",
}


def load_rom(path: Path) -> tuple[bytes, dict[str, object]]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith((".gba", ".agb", ".rom"))
            ]
            if len(members) != 1:
                raise ValueError(
                    f"expected one GBA-like ZIP member, found {len(members)}"
                )
            info = members[0]
            return archive.read(info), {
                "container": "zip",
                "member_size": info.file_size,
                "member_crc32": f"{info.CRC:08x}",
            }
    return path.read_bytes(), {"container": "raw", "member_size": path.stat().st_size}


def find_occurrences(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return offsets
        offsets.append(found)
        start = found + 1


def shannon_entropy(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    counts = Counter(chunk)
    total = len(chunk)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def entropy_summary(data: bytes) -> dict[str, object]:
    blocks = []
    for offset in range(0, len(data), BLOCK_SIZE):
        chunk = data[offset : offset + BLOCK_SIZE]
        blocks.append(
            {
                "offset": offset,
                "size": len(chunk),
                "entropy": round(shannon_entropy(chunk), 5),
                "distinct_bytes": len(set(chunk)),
            }
        )
    non_ff = len(data.rstrip(b"\xff"))
    non_zero = len(data.rstrip(b"\x00"))
    return {
        "block_size": BLOCK_SIZE,
        "block_count": len(blocks),
        "last_non_ff_offset": non_ff - 1 if non_ff else None,
        "ff_tail_bytes": len(data) - non_ff,
        "last_non_zero_offset": non_zero - 1 if non_zero else None,
        "zero_tail_bytes": len(data) - non_zero,
        "highest_entropy_blocks": sorted(
            blocks, key=lambda block: block["entropy"], reverse=True
        )[:12],
        "lowest_entropy_blocks": sorted(blocks, key=lambda block: block["entropy"])[:12],
    }


def header_summary(data: bytes) -> dict[str, object]:
    if len(data) < 0xC0:
        return {"available": False}
    title_bytes = data[0xA0:0xAC]
    game_code = data[0xAC:0xB0]
    maker_code = data[0xB0:0xB2]
    stored = data[0xBD]
    calculated = (0x19 - sum(data[0xA0:0xBD])) & 0xFF
    return {
        "available": True,
        "title_ascii": title_bytes.rstrip(b"\x00").decode("ascii", "replace"),
        "title_bytes_hex": title_bytes.hex(),
        "game_code_ascii": game_code.decode("ascii", "replace"),
        "maker_code_ascii": maker_code.decode("ascii", "replace"),
        "software_version": data[0xBC],
        "header_complement_stored": f"{stored:02x}",
        "header_complement_calculated": f"{calculated:02x}",
        "header_complement_matches": stored == calculated,
    }


def shift_jis_summary(data: bytes) -> dict[str, object]:
    matches: dict[str, dict[str, object]] = {}
    for label, text in SHIFT_JIS_SENTINELS.items():
        encoded = text.encode("shift_jis")
        offsets = find_occurrences(data, encoded)
        matches[label] = {
            "byte_length": len(encoded),
            "count": len(offsets),
            "offsets": offsets[:20],
        }
    return {"sentinels": matches}


def is_sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xEF


def is_sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def sjis_run_summary(data: bytes, minimum_pairs: int = 6) -> dict[str, object]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index + 1 < len(data):
        start = index
        pairs = 0
        while index + 1 < len(data) and is_sjis_lead(data[index]) and is_sjis_trail(data[index + 1]):
            pairs += 1
            index += 2
        if pairs >= minimum_pairs:
            runs.append((start, pairs))
        index = max(index + 1, start + 1) if pairs == 0 else index
    return {
        "minimum_pairs": minimum_pairs,
        "run_count": len(runs),
        "longest_runs": [
            {"offset": offset, "pairs": pairs}
            for offset, pairs in sorted(runs, key=lambda item: item[1], reverse=True)[:20]
        ],
    }


def pointer_summary(data: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    for alignment in range(4):
        valid_offsets: list[int] = []
        target_offsets: list[int] = []
        for offset in range(alignment, len(data) - 3, 4):
            value = struct.unpack_from("<I", data, offset)[0]
            target = value - ROM_MIN
            if ROM_MIN <= value < ROM_MAX and target < len(data):
                valid_offsets.append(offset)
                target_offsets.append(target)

        runs: list[dict[str, object]] = []
        if valid_offsets:
            run_start = valid_offsets[0]
            previous = valid_offsets[0]
            for offset in valid_offsets[1:]:
                if offset == previous + 4:
                    previous = offset
                    continue
                length = (previous - run_start) // 4 + 1
                if length >= 4:
                    first_target = struct.unpack_from("<I", data, run_start)[0] - ROM_MIN
                    last_target = struct.unpack_from("<I", data, previous)[0] - ROM_MIN
                    runs.append(
                        {
                            "offset": run_start,
                            "entries": length,
                            "first_target": first_target,
                            "last_target": last_target,
                        }
                    )
                run_start = previous = offset
            length = (previous - run_start) // 4 + 1
            if length >= 4:
                first_target = struct.unpack_from("<I", data, run_start)[0] - ROM_MIN
                last_target = struct.unpack_from("<I", data, previous)[0] - ROM_MIN
                runs.append(
                    {
                        "offset": run_start,
                        "entries": length,
                        "first_target": first_target,
                        "last_target": last_target,
                    }
                )
        result[str(alignment)] = {
            "valid_pointer_entries": len(valid_offsets),
            "longest_contiguous_runs": sorted(
                runs, key=lambda run: run["entries"], reverse=True
            )[:20],
        }
    return {
        "rom_address_range": [f"0x{ROM_MIN:08x}", f"0x{ROM_MAX:08x}"],
        "by_alignment": result,
    }


def compression_summary(data: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    for alignment in range(4):
        by_kind = Counter()
        for offset in range(alignment, len(data) - 3, 4):
            kind = COMPRESSED_HEADERS.get(data[offset])
            if kind is None:
                continue
            unpacked_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
            if 0 < unpacked_size <= 0x400000:
                by_kind[kind] += 1
        result[str(alignment)] = dict(sorted(by_kind.items()))
    return {
        "candidate_rule": "aligned magic byte plus 24-bit unpacked size in 1..0x400000",
        "by_alignment": result,
    }


def ascii_summary(data: bytes, minimum_length: int = 8) -> dict[str, object]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(data):
        if 0x20 <= data[index] <= 0x7E:
            start = index
            while index < len(data) and 0x20 <= data[index] <= 0x7E:
                index += 1
            if index - start >= minimum_length:
                runs.append((start, index - start))
        else:
            index += 1
    return {
        "minimum_length": minimum_length,
        "run_count": len(runs),
        "longest_runs": [
            {"offset": offset, "length": length}
            for offset, length in sorted(runs, key=lambda item: item[1], reverse=True)[:20]
        ],
    }


def build_report(path: Path) -> dict[str, object]:
    data, container = load_rom(path)
    return {
        "input": str(path),
        "container": container,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "header": header_summary(data),
        "entropy": entropy_summary(data),
        "shift_jis": shift_jis_summary(data),
        "shift_jis_runs": sjis_run_summary(data),
        "pointers": pointer_summary(data),
        "compression_signatures": compression_summary(data),
        "ascii_runs": ascii_summary(data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="raw GBA ROM or ZIP containing one")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()
    report = build_report(args.input)
    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
