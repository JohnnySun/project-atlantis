#!/usr/bin/env python3
"""Read-only structural reconnaissance for Tales of the World: Narikiri Dungeon 3.

The first pass deliberately reports offsets, counts, hashes and structural
statistics only.  It does not emit decoded game text, OCR output or rendered
glyph data.  Those belong in the local ``research/``/``work/`` split described
by ``docs/TRANSLATION-LEDGER.md`` and must never be copied into a committed
translation ledger.

The heuristics here are signals, not confirmations.  In particular, GBA
graphics and executable data can look like Shift-JIS, pointer tables or BIOS
compression blocks by accident.  A candidate becomes confirmed only after a
runtime consumer or a byte-accurate renderer independently corroborates it.

Usage:
    python3 tools/recon_rom.py roms/base/Tales_of_the_World_....gba
    python3 tools/recon_rom.py ROM --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


ROM_BASE = 0x08000000
EXPECTED_TITLE = "TOWNARIKIRI3"
EXPECTED_GAME_CODE = "B3TJ"
EXPECTED_MAKER_CODE = "AF"
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF


def gba_header_checksum(data: bytes) -> int:
    """Return the GBA complement check for header bytes A0..BC.

    The check is ``0x19 - sum`` in the usual unsigned-byte notation, i.e.
    ``-0x19 - sum`` modulo 256.  The latter form avoids the common mistake of
    using ``0x19 - sum`` (which is the wrong constant for this header field).
    """

    return (-0x19 - sum(data[0xA0:0xBD])) & 0xFF


def read_c_string(data: bytes, start: int, length: int) -> str:
    return data[start : start + length].split(b"\0", 1)[0].decode("ascii", "replace")


def header_record(data: bytes) -> dict[str, object]:
    actual = data[0xBD] if len(data) > 0xBD else None
    expected = gba_header_checksum(data) if len(data) >= 0xBD else None
    return {
        "title": read_c_string(data, 0xA0, 12),
        "game_code": data[0xAC:0xB0].decode("ascii", "replace"),
        "maker_code": data[0xB0:0xB2].decode("ascii", "replace"),
        "fixed_96": data[0xB2] if len(data) > 0xB2 else None,
        "main_unit_code": data[0xB3] if len(data) > 0xB3 else None,
        "device_type": data[0xB4] if len(data) > 0xB4 else None,
        "software_version": data[0xBC] if len(data) > 0xBC else None,
        "header_complement": actual,
        "header_complement_calculated": expected,
        "header_complement_ok": actual == expected,
    }


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((count / n) * math.log2(count / n) for count in counts.values())


def non_ff_extent(data: bytes) -> int:
    trimmed = data.rstrip(b"\xff")
    return len(trimmed)


def block_statistics(data: bytes, block_size: int = 0x10000) -> list[dict[str, object]]:
    rows = []
    for start in range(0, len(data), block_size):
        block = data[start : start + block_size]
        rows.append(
            {
                "offset": start,
                "size": len(block),
                "entropy": round(entropy(block), 4),
                "ff_ratio": round(block.count(0xFF) / len(block), 4),
                "zero_ratio": round(block.count(0x00) / len(block), 4),
            }
        )
    return rows


def sjis_lead(value: int) -> bool:
    return 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC


def sjis_trail(value: int) -> bool:
    return 0x40 <= value <= 0x7E or 0x80 <= value <= 0xFC


def sjis_units(data: bytes, start: int) -> tuple[int, int, int, int]:
    """Parse a structurally valid Shift-JIS run from ``start``.

    Returns ``(end, units, double_byte_units, ascii_or_kana_units)``.  The
    parser intentionally uses byte-range validity rather than semantic
    decoding, so the result can be compared without embedding source text in
    the report.
    """

    i = start
    units = 0
    double = 0
    single = 0
    while i < len(data):
        value = data[i]
        if sjis_lead(value) and i + 1 < len(data) and sjis_trail(data[i + 1]):
            i += 2
            units += 1
            double += 1
            continue
        if value == 0x00:
            break
        if 0x20 <= value <= 0x7E or 0xA1 <= value <= 0xDF:
            i += 1
            units += 1
            single += 1
            continue
        break
    return i, units, double, single


@dataclass(frozen=True)
class SjisRun:
    start: int
    end: int
    units: int
    double_byte_units: int
    single_byte_units: int
    unique_bytes: int

    @property
    def byte_length(self) -> int:
        return self.end - self.start

    @property
    def diversity(self) -> float:
        return self.unique_bytes / self.byte_length if self.byte_length else 0.0


def scan_sjis_runs(data: bytes, min_units: int = 8) -> list[SjisRun]:
    runs: list[SjisRun] = []
    i = 0
    while i < len(data):
        end, units, double, single = sjis_units(data, i)
        if units >= min_units:
            runs.append(
                SjisRun(
                    start=i,
                    end=end,
                    units=units,
                    double_byte_units=double,
                    single_byte_units=single,
                    unique_bytes=len(set(data[i:end])),
                )
            )
            i = end
        else:
            i += 1
    return runs


def exact_phrase_hits(data: bytes, phrases: Iterable[str]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for phrase in phrases:
        encoded = phrase.encode("shift_jis")
        positions = []
        cursor = 0
        while True:
            found = data.find(encoded, cursor)
            if found < 0:
                break
            positions.append(found)
            cursor = found + 1
        result[phrase] = positions
    return result


def pointer_runs(
    data: bytes, min_run: int = 8, alignment: int = 4
) -> list[dict[str, object]]:
    """Find non-decreasing runs of in-ROM absolute pointers.

    This is intentionally stricter than a density scan: a candidate needs
    consecutive words, all pointing into the ROM image, with no backwards
    step.  It still remains only a candidate because executable literal pools
    and resource tables satisfy the same shape.
    """

    lo = ROM_BASE
    hi = ROM_BASE + len(data) - 1
    limit = len(data) - 3
    runs: list[dict[str, object]] = []
    for aligned_start in range(0, alignment):
        i = aligned_start
        while i < limit:
            value = struct.unpack_from("<I", data, i)[0]
            if not (lo <= value <= hi):
                i += alignment
                continue
            j = i
            previous = value
            while j + alignment < limit:
                current = struct.unpack_from("<I", data, j + alignment)[0]
                if not (lo <= current <= hi) or current < previous:
                    break
                previous = current
                j += alignment
            words = (j - i) // alignment + 1
            if words >= min_run:
                runs.append(
                    {
                        "table_offset": i,
                        "words": words,
                        "first_target": value - ROM_BASE,
                        "last_target": previous - ROM_BASE,
                        "span": previous - value,
                        "alignment": alignment,
                    }
                )
            i = j + alignment if j > i else i + alignment
    # A run found at one alignment should not be repeated for the default
    # alignment; sorting and de-duplicating also makes JSON output stable.
    unique = {(row["table_offset"], row["alignment"]): row for row in runs}
    return sorted(unique.values(), key=lambda row: (-int(row["words"]), int(row["table_offset"])))


COMPRESSION_TAGS = {0x10: "LZ77", 0x24: "Huffman", 0x30: "RLE"}


def compression_candidates(
    data: bytes, min_size: int = 16, max_size: int = 2 * 1024 * 1024, alignment: int = 4
) -> dict[str, list[dict[str, int]]]:
    hits: dict[str, list[dict[str, int]]] = {name: [] for name in COMPRESSION_TAGS.values()}
    for off in range(0, len(data) - 4, alignment):
        tag = data[off]
        name = COMPRESSION_TAGS.get(tag)
        if name is None:
            continue
        size = data[off + 1] | (data[off + 2] << 8) | (data[off + 3] << 16)
        if min_size <= size <= max_size:
            hits[name].append({"offset": off, "decompressed_size": size})
    return hits


def swi_candidates(data: bytes) -> Counter[int]:
    counts: Counter[int] = Counter()
    for off in range(0, len(data) - 1, 2):
        word = struct.unpack_from("<H", data, off)[0]
        if word & 0xFF00 == 0xDF00:
            counts[word & 0xFF] += 1
    return counts


def ascii_runs(data: bytes, min_length: int = 8) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    i = 0
    while i < len(data):
        if 0x20 <= data[i] <= 0x7E:
            start = i
            i += 1
            while i < len(data) and 0x20 <= data[i] <= 0x7E:
                i += 1
            if i - start >= min_length:
                rows.append((start, i))
        else:
            i += 1
    return rows


def build_report(data: bytes, path: Path, limit: int = 20) -> dict[str, object]:
    runs = scan_sjis_runs(data)
    # The largest runs are generally graphics/data false positives.  Sorting
    # by diversity gives a second view that favours less repetitive candidates
    # without pretending either ranking is semantic proof.
    longest = sorted(runs, key=lambda row: (-row.units, row.start))[:limit]
    diverse = sorted(runs, key=lambda row: (-row.diversity, -row.units, row.start))[:limit]
    sjis_summary = {
        "min_units": 8,
        "run_count": len(runs),
        "longest": [run.__dict__ | {"diversity": round(run.diversity, 4)} for run in longest],
        "most_diverse": [run.__dict__ | {"diversity": round(run.diversity, 4)} for run in diverse],
        "exact_phrase_hits": exact_phrase_hits(
            data,
            [
                "はい",
                "いいえ",
                "戦う",
                "逃げる",
                "道具",
                "セーブ",
                "ロード",
                "レベル",
                "衣装",
                "スキル",
                "イベント",
            ],
        ),
    }

    compression = compression_candidates(data)
    pointers = pointer_runs(data)
    stats = block_statistics(data)
    top_entropy = sorted(stats, key=lambda row: (-float(row["entropy"]), int(row["offset"])))[:limit]
    low_ff = sorted(stats, key=lambda row: (float(row["ff_ratio"]), int(row["offset"])))[:limit]
    swi = swi_candidates(data)
    ascii_candidates = ascii_runs(data)

    header = header_record(data)
    return {
        "rom": str(path),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08X}",
        "expected_identity": {
            "title": EXPECTED_TITLE,
            "game_code": EXPECTED_GAME_CODE,
            "maker_code": EXPECTED_MAKER_CODE,
            "size": EXPECTED_SIZE,
            "crc32": f"{EXPECTED_CRC32:08X}",
        },
        "header": header,
        "identity_matches_expected": (
            header["title"] == EXPECTED_TITLE
            and header["game_code"] == EXPECTED_GAME_CODE
            and header["maker_code"] == EXPECTED_MAKER_CODE
            and len(data) == EXPECTED_SIZE
            and (zlib.crc32(data) & 0xFFFFFFFF) == EXPECTED_CRC32
        ),
        "non_ff_extent": non_ff_extent(data),
        "block_statistics": {
            "block_size": 0x10000,
            "block_count": len(stats),
            "highest_entropy": top_entropy,
            "lowest_ff_ratio": low_ff,
        },
        "sjis_scan": sjis_summary,
        "ascii_runs": {
            "min_bytes": 8,
            "count": len(ascii_candidates),
            "offsets": [
                {"start": start, "end": end, "length": end - start}
                for start, end in ascii_candidates[:limit]
            ],
        },
        "pointer_scan": {"min_run": 8, "candidates": pointers[:limit], "total": len(pointers)},
        "compression_scan": {
            "alignment": 4,
            "min_size": 16,
            "max_size": 2 * 1024 * 1024,
            "candidates": {
                name: {"total": len(rows), "first": rows[:limit]}
                for name, rows in compression.items()
            },
        },
        "swi_scan": {
            "alignment": 2,
            "counts": {f"0x{imm:02X}": count for imm, count in sorted(swi.items())},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    data = args.rom.read_bytes()
    report = build_report(data, args.rom, args.limit)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print(f"ROM: {report['rom']}")
    print(
        f"size={report['size']} crc32={report['crc32']} "
        f"sha256={report['sha256']}"
    )
    print(f"header: {report['header']}")
    print(f"expected identity: {report['identity_matches_expected']}")
    print(f"non-FF extent: 0x{report['non_ff_extent']:x}")
    sjis = report["sjis_scan"]
    print(f"Shift-JIS structural runs >= {sjis['min_units']} units: {sjis['run_count']}")
    print(f"exact Shift-JIS phrase hits: {sjis['exact_phrase_hits']}")
    print(f"ASCII runs >= {report['ascii_runs']['min_bytes']} bytes: {report['ascii_runs']['count']}")
    print(f"pointer candidates: {report['pointer_scan']['total']}")
    for name, row in report["compression_scan"]["candidates"].items():
        print(f"{name} signature candidates: {row['total']}")
    print(f"SWI candidates by immediate: {report['swi_scan']['counts']}")


if __name__ == "__main__":
    main()
