#!/usr/bin/env python3
"""Read-only identity and bounded static reconnaissance for the B3EJ ROM.

This helper deliberately reports metadata and candidate counts only.  It does
not decode or save the original script, dump a font, or mutate the ROM.  The
static probes are leads for later execution-time validation, not proof of a
text format.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter
from typing import Iterable
import zlib


EXPECTED_GAME_CODE = "B3EJ"
MAX_REPORTED_OFFSETS = 16

# Short UI terms are only probes for a possible uncompressed Shift-JIS layer.
# A hit can also come from data or graphics and must be validated at runtime.
SJIS_PROBES = {
    "command": "コマンド",
    "status": "ステータス",
    "strategy": "策略",
    "save": "セーブ",
    "yes": "はい",
    "no": "いいえ",
    "援軍": "援軍",
    "劉備": "劉備",
}


def gba_header_checksum(data: bytes) -> int:
    """Calculate the standard GBA complement checksum for A0..BC."""

    if len(data) < 0xBE:
        raise ValueError("ROM is shorter than the GBA header")
    return (0x19 - sum(data[0xA0:0xBD])) & 0xFF


def _bounded_find(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while len(offsets) < MAX_REPORTED_OFFSETS:
        found = data.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def scan_sjis_probes(data: bytes) -> dict[str, object]:
    hits: dict[str, object] = {}
    for label, text in SJIS_PROBES.items():
        encoded = text.encode("shift_jis")
        offsets = _bounded_find(data, encoded)
        hits[label] = {
            "probe_byte_length": len(encoded),
            "reported_offsets": [f"0x{offset:06x}" for offset in offsets],
            "reported_count": len(offsets),
            "truncated": len(offsets) == MAX_REPORTED_OFFSETS,
        }
    return hits


def scan_pointer_runs(data: bytes) -> dict[str, object]:
    """Summarize aligned words pointing into the ROM address window."""

    rom_start = 0x08000000
    rom_end = rom_start + len(data)
    pointer_words = 0
    runs: list[tuple[int, int]] = []
    run_start: int | None = None
    run_length = 0

    def finish_run() -> None:
        nonlocal run_start, run_length
        if run_start is not None and run_length >= 4:
            runs.append((run_start, run_length))
        run_start = None
        run_length = 0

    for offset in range(0, len(data) - 3, 4):
        value = int.from_bytes(data[offset : offset + 4], "little")
        if rom_start <= value < rom_end:
            pointer_words += 1
            if run_start is None:
                run_start = offset
            run_length += 1
        else:
            finish_run()
    finish_run()

    return {
        "aligned_pointer_word_count": pointer_words,
        "runs_at_least_4_words": len(runs),
        "first_runs": [
            {
                "file_offset": f"0x{start:06x}",
                "word_count": count,
                "first_target_file_offset": f"0x{int.from_bytes(data[start:start + 4], 'little') - rom_start:06x}",
            }
            for start, count in runs[:MAX_REPORTED_OFFSETS]
        ],
        "address_window": [f"0x{rom_start:08x}", f"0x{rom_end - 1:08x}"],
        "note": "Heuristic only; code literals and jump tables also produce runs.",
    }


def scan_thumb_swi_candidates(data: bytes) -> dict[str, object]:
    """Count halfword-aligned Thumb SWI-looking instructions without disassembly."""

    counts: Counter[str] = Counter()
    first_offsets: dict[str, list[str]] = {}
    for offset in range(0, len(data) - 1, 2):
        halfword = int.from_bytes(data[offset : offset + 2], "little")
        if halfword & 0xFF00 != 0xDF00:
            continue
        immediate = halfword & 0xFF
        key = f"0x{immediate:02x}"
        counts[key] += 1
        first_offsets.setdefault(key, [])
        if len(first_offsets[key]) < MAX_REPORTED_OFFSETS:
            first_offsets[key].append(f"0x{offset:06x}")
    return {
        "candidate_count": sum(counts.values()),
        "by_immediate": dict(sorted(counts.items())),
        "first_offsets": dict(sorted(first_offsets.items())),
        "note": "Not evidence of executable code until control flow is verified.",
    }


def scan_compression_signatures(data: bytes) -> dict[str, object]:
    """Count plausible aligned GBA BIOS decompression headers."""

    markers = {0x10: "lz77", 0x20: "huffman", 0x30: "rle", 0x80: "diff"}
    counts: Counter[str] = Counter()
    first_offsets: dict[str, list[str]] = {}
    for offset in range(0, len(data) - 3, 4):
        name = markers.get(data[offset])
        if name is None:
            continue
        expanded_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
        if not 0 < expanded_size <= 0x01000000:
            continue
        counts[name] += 1
        first_offsets.setdefault(name, [])
        if len(first_offsets[name]) < MAX_REPORTED_OFFSETS:
            first_offsets[name].append(f"0x{offset:06x}")
    return {
        "plausible_aligned_header_count": sum(counts.values()),
        "by_type": dict(sorted(counts.items())),
        "first_offsets": dict(sorted(first_offsets.items())),
        "note": "Signatures alone do not identify text or prove a valid stream.",
    }


def inspect(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 0xC0:
        raise ValueError(f"ROM is shorter than the GBA header: {len(data)} bytes")

    title = data[0xA0:0xAC].rstrip(b"\0").decode("ascii", "replace")
    game_code = data[0xAC:0xB0].decode("ascii", "replace")
    maker_code = data[0xB0:0xB2].decode("ascii", "replace")
    stored_checksum = data[0xBD]
    calculated_checksum = gba_header_checksum(data)

    digests = {
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return {
        "path": str(path),
        "read_only": True,
        "size_bytes": len(data),
        "header": {
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "software_version": data[0xBC],
            "stored_complement": f"0x{stored_checksum:02x}",
            "calculated_complement": f"0x{calculated_checksum:02x}",
            "complement_matches": stored_checksum == calculated_checksum,
        },
        "digests": digests,
        "scans": {
            "shift_jis_probes": scan_sjis_probes(data),
            "pointer_runs": scan_pointer_runs(data),
            "thumb_swi_candidates": scan_thumb_swi_candidates(data),
            "compression_signatures": scan_compression_signatures(data),
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument(
        "--strict-identity",
        action="store_true",
        help="fail if the game code is not B3EJ or the header complement differs",
    )
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    try:
        report = inspect(args.rom)
    except (OSError, ValueError) as exc:
        print(f"inspect_rom.py: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if args.strict_identity:
        if report["header"]["game_code"] != EXPECTED_GAME_CODE:
            print("unexpected game code", file=sys.stderr)
            return 1
        if not report["header"]["complement_matches"]:
            print("GBA header complement mismatch", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
