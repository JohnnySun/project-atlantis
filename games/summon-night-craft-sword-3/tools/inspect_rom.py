#!/usr/bin/env python3
"""Read-only first-pass inspection for the Japanese B3CJ ROM.

This tool deliberately emits metadata and bounded candidate counts only.  It
does not write a ROM, decode or save the original script, or treat any static
scan hit as a confirmed text structure.  Future game-specific extractors must
be added only after a clean local ROM has been checked against this report.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import pathlib
import sys
from collections import Counter
from typing import Dict, Iterable, List, Tuple


EXPECTED_GAME_CODE = "B3CJ"
EXTERNAL_REFERENCE = {
    "size": 33554432,
    "crc32": "12afae5d",
    "header_checksum": "6b",
    "sha1": "3f5253fcf57e07ce52472bd29a61d16b98a12376",
}

# These are short, common probes for detecting an uncompressed Shift-JIS
# design.  A hit is only a lead: binary GBA assets can contain the same bytes.
SJIS_PROBES = {
    "yes": "はい",
    "no": "いいえ",
    "level": "レベル",
    "attack": "こうげき",
    "defense": "ぼうぎょ",
    "item": "どうぐ",
    "save": "セーブ",
    "load": "ロード",
    "command": "コマンド",
}

MAX_OFFSETS_PER_SCAN = 16


def gba_header_checksum(data: bytes) -> int:
    """Return the GBA complement checksum for header bytes A0..BC."""

    if len(data) < 0xBE:
        raise ValueError("ROM is too short to contain a GBA header")
    return (0x19 - sum(data[0xA0:0xBD])) & 0xFF


def _find_offsets(data: bytes, needle: bytes, limit: int = MAX_OFFSETS_PER_SCAN) -> List[int]:
    offsets: List[int] = []
    start = 0
    while len(offsets) < limit:
        found = data.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def scan_sjis_probes(data: bytes) -> Dict[str, List[int]]:
    hits: Dict[str, List[int]] = {}
    for label, text in SJIS_PROBES.items():
        encoded = text.encode("shift_jis")
        hits[label] = _find_offsets(data, encoded)
    return hits


def scan_pointer_runs(data: bytes) -> Dict[str, object]:
    """Summarize aligned runs of words pointing into this ROM's address space."""

    rom_start = 0x08000000
    rom_end = rom_start + len(data)
    word_count = 0
    runs: List[Tuple[int, int]] = []
    run_start = None
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
            word_count += 1
            if run_start is None:
                run_start = offset
            run_length += 1
        else:
            finish_run()
    finish_run()

    return {
        "aligned_rom_pointer_words": word_count,
        "runs_at_least_4_words": len(runs),
        "first_runs": [
            {"file_offset": start, "word_count": count}
            for start, count in runs[:MAX_OFFSETS_PER_SCAN]
        ],
        "address_range": [hex(rom_start), hex(rom_end - 1)],
        "note": "Heuristic only; code literal pools and jump tables also produce runs.",
    }


def scan_thumb_swi_candidates(data: bytes) -> Dict[str, object]:
    """Count halfword-aligned Thumb SVC/SWI-looking words, without disassembly."""

    counts: Counter[str] = Counter()
    first_offsets: Dict[str, List[int]] = {}
    for offset in range(0, len(data) - 1, 2):
        halfword = int.from_bytes(data[offset : offset + 2], "little")
        if halfword & 0xFF00 == 0xDF00:
            immediate = halfword & 0xFF
            key = f"0x{immediate:02x}"
            counts[key] += 1
            first_offsets.setdefault(key, [])
            if len(first_offsets[key]) < MAX_OFFSETS_PER_SCAN:
                first_offsets[key].append(offset)
    return {
        "candidate_count": sum(counts.values()),
        "by_immediate": dict(sorted(counts.items())),
        "first_offsets": dict(sorted(first_offsets.items())),
        "note": "Not evidence of executable code until control flow is verified.",
    }


def scan_compression_signatures(data: bytes) -> Dict[str, object]:
    """Count plausible aligned GBA compression headers; intentionally conservative."""

    markers = {0x10: "lz77", 0x20: "huffman", 0x30: "rle", 0x80: "diff"}
    counts: Counter[str] = Counter()
    first_offsets: Dict[str, List[int]] = {}
    for offset in range(0, len(data) - 3, 4):
        marker = data[offset]
        name = markers.get(marker)
        if name is None:
            continue
        expanded_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
        if not 0 < expanded_size <= 0x01000000:
            continue
        counts[name] += 1
        first_offsets.setdefault(name, [])
        if len(first_offsets[name]) < MAX_OFFSETS_PER_SCAN:
            first_offsets[name].append(offset)
    return {
        "plausible_aligned_headers": dict(sorted(counts.items())),
        "first_offsets": dict(sorted(first_offsets.items())),
        "note": "Signatures alone are noisy and do not identify text compression.",
    }


def inspect(path: pathlib.Path) -> Dict[str, object]:
    data = path.read_bytes()
    title = data[0xA0:0xAC].rstrip(b"\0").decode("ascii", "replace") if len(data) >= 0xAC else ""
    game_code = data[0xAC:0xB0].decode("ascii", "replace") if len(data) >= 0xB0 else ""
    maker_code = data[0xB0:0xB2].decode("ascii", "replace") if len(data) >= 0xB2 else ""
    version = data[0xBC] if len(data) > 0xBC else None
    stored_checksum = data[0xBD] if len(data) > 0xBD else None
    calculated_checksum = gba_header_checksum(data)

    digests = {
        "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    reference_comparisons = {
        "size": len(data) == EXTERNAL_REFERENCE["size"],
        "crc32": digests["crc32"] == EXTERNAL_REFERENCE["crc32"],
        "header_checksum": stored_checksum == int(EXTERNAL_REFERENCE["header_checksum"], 16),
        "sha1": digests["sha1"] == EXTERNAL_REFERENCE["sha1"],
    }

    return {
        "path": str(path),
        "read_only": True,
        "file_size": len(data),
        "header": {
            "title": title,
            "game_code": game_code,
            "maker_code": maker_code,
            "software_version": version,
            "stored_checksum": None if stored_checksum is None else f"{stored_checksum:02x}",
            "calculated_checksum": f"{calculated_checksum:02x}",
            "checksum_matches": stored_checksum == calculated_checksum,
        },
        "digests": digests,
        "external_reference": EXTERNAL_REFERENCE,
        "matches_external_reference": reference_comparisons,
        "scans": {
            "shift_jis_probe_offsets": scan_sjis_probes(data),
            "pointer_runs": scan_pointer_runs(data),
            "thumb_swi_candidates": scan_thumb_swi_candidates(data),
            "compression_signatures": scan_compression_signatures(data),
        },
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="path to a local, legally dumped Japanese GBA ROM")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if the game code, GBA header checksum, or external reference differs",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = inspect(args.rom)
    except (OSError, ValueError) as exc:
        print(f"inspect_rom.py: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.strict:
        return 0

    mismatches = []
    if report["header"]["game_code"] != EXPECTED_GAME_CODE:
        mismatches.append("game_code")
    if not report["header"]["checksum_matches"]:
        mismatches.append("header_checksum")
    mismatches.extend(
        field for field, matches in report["matches_external_reference"].items() if not matches
    )
    if mismatches:
        print("strict reference mismatch: " + ", ".join(sorted(set(mismatches))), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
