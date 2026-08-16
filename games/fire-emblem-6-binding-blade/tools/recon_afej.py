#!/usr/bin/env python3
"""Read-only structural reconnaissance for a Japanese FE6 GBA ROM.

This deliberately does not decode or write game text. It records facts that
can be checked against a locally supplied ROM and labels byte-pattern hits as
candidates rather than conclusions. The report contains hashes and offsets,
not extracted source text.

Usage:
    python3 tools/recon_afej.py roms/base/AFEJ.gba \
        --json-out work/afej-recon.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path


ROM_BASE = 0x08000000
HEADER_END = 0xBE

SHIFT_JIS_PROBES = (
    "はい",
    "いいえ",
    "レベル",
    "たたかう",
    "どうぐ",
    "セーブ",
    "ロード",
    "支援",
    "章",
    "ターン",
    "名前",
    "始めから",
    "続きから",
)

COMPRESSION_TYPES = {
    0x10: "LZ77",
    0x20: "Huffman",
    0x30: "RLE",
    0x40: "Diff8",
    0x80: "Diff16",
}


def digest(data: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, data).hexdigest()


def decode_ascii(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", errors="replace")


def parse_header(data: bytes) -> dict[str, object]:
    if len(data) < HEADER_END:
        raise ValueError(f"ROM is shorter than the GBA header ({len(data)} bytes)")

    actual_complement = data[0xBD]
    calculated_complement = (-((sum(data[0xA0:0xBD]) + 0x19) & 0xFF)) & 0xFF
    return {
        "title": decode_ascii(data[0xA0:0xAC]),
        "game_code": decode_ascii(data[0xAC:0xB0]),
        "maker_code": decode_ascii(data[0xB0:0xB2]),
        "fixed_value": f"0x{data[0xB2]:02x}",
        "main_unit_code": f"0x{data[0xB3]:02x}",
        "device_type": f"0x{data[0xB4]:02x}",
        "software_version": data[0xBC],
        "header_complement": {
            "actual": f"0x{actual_complement:02x}",
            "calculated": f"0x{calculated_complement:02x}",
            "matches": actual_complement == calculated_complement,
        },
    }


def find_all(data: bytes, needle: bytes, limit: int) -> list[int]:
    offsets: list[int] = []
    start = 0
    while len(offsets) < limit:
        found = data.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def shift_jis_probe_report(data: bytes, limit: int) -> list[dict[str, object]]:
    report = []
    for text in SHIFT_JIS_PROBES:
        encoded = text.encode("shift_jis")
        offsets = find_all(data, encoded, limit)
        report.append(
            {
                "text_probe": text,
                "encoded_hex": encoded.hex(),
                "hits": len(offsets),
                "offsets": [f"0x{offset:x}" for offset in offsets],
            }
        )
    return report


def pointer_runs(data: bytes, min_words: int, limit: int) -> list[dict[str, object]]:
    """Find aligned runs of values that point into this ROM's address space."""

    runs: list[dict[str, object]] = []
    run_start: int | None = None
    run_values: list[int] = []

    def finish() -> None:
        nonlocal run_start, run_values
        if run_start is not None and len(run_values) >= min_words and len(runs) < limit:
            addresses = [value - ROM_BASE for value in run_values]
            runs.append(
                {
                    "file_offset": f"0x{run_start:x}",
                    "words": len(run_values),
                    "rom_addresses": [f"0x{value:08x}" for value in run_values[:8]],
                    "target_offsets": [f"0x{value:x}" for value in addresses[:8]],
                    "target_offsets_monotonic": all(
                        left <= right for left, right in zip(addresses, addresses[1:])
                    ),
                }
            )
        run_start = None
        run_values = []

    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if ROM_BASE <= value < ROM_BASE + len(data):
            if run_start is None:
                run_start = offset
            run_values.append(value)
        else:
            finish()
            if len(runs) >= limit:
                break
    finish()
    return runs


def compression_candidates(data: bytes, limit: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for offset, marker in enumerate(data):
        kind = COMPRESSION_TYPES.get(marker)
        if kind is None or offset + 4 > len(data):
            continue
        size = int.from_bytes(data[offset + 1 : offset + 4], "little")
        if size == 0 or size > 0x400000:
            continue
        candidates.append(
            {
                "file_offset": f"0x{offset:x}",
                "type": kind,
                "header_hex": data[offset : offset + 4].hex(),
                "declared_output_size": size,
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def shannon_entropy(block: bytes) -> float:
    if not block:
        return 0.0
    counts = [0] * 256
    for value in block:
        counts[value] += 1
    size = len(block)
    return -sum(
        (count / size) * math.log2(count / size)
        for count in counts
        if count
    )


def tile_window_candidates(
    data: bytes, window_tiles: int, limit: int
) -> list[dict[str, object]]:
    """Rank sparse 4bpp windows; this is a font candidate heuristic only."""

    tile_size = 32
    window_size = window_tiles * tile_size
    scored: list[tuple[float, dict[str, object]]] = []
    for offset in range(0, len(data) - window_size + 1, window_size):
        window = data[offset : offset + window_size]
        nonempty = sum(
            1
            for tile_offset in range(0, window_size, tile_size)
            if any(window[tile_offset : tile_offset + tile_size])
        )
        if nonempty < window_tiles // 2:
            continue
        unique_tiles = len(
            {
                window[tile_offset : tile_offset + tile_size]
                for tile_offset in range(0, window_size, tile_size)
            }
        )
        entropy = shannon_entropy(window)
        nonzero_fraction = sum(value != 0 for value in window) / window_size
        sparsity = 1.0 - nonzero_fraction
        score = (nonempty / window_tiles) + sparsity + (unique_tiles / window_tiles) * 0.25
        scored.append(
            (
                score,
                {
                    "file_offset": f"0x{offset:x}",
                    "window_bytes": window_size,
                    "tile_count": window_tiles,
                    "nonempty_tiles": nonempty,
                    "unique_tiles": unique_tiles,
                    "nonzero_fraction": round(nonzero_fraction, 4),
                    "entropy_bits_per_byte": round(entropy, 4),
                    "evidence": "heuristic_4bpp_candidate_only",
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def ascii_runs(data: bytes, min_length: int, limit: int) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    start: int | None = None
    for offset, value in enumerate(data + b"\0"):
        printable = 0x20 <= value <= 0x7E
        if printable and start is None:
            start = offset
        elif not printable and start is not None:
            if offset - start >= min_length:
                raw = data[start:offset]
                runs.append(
                    {
                        "file_offset": f"0x{start:x}",
                        "length": len(raw),
                        "text": raw.decode("ascii", errors="replace"),
                    }
                )
                if len(runs) >= limit:
                    break
            start = None
    return runs


def build_report(data: bytes, path: Path, args: argparse.Namespace) -> dict[str, object]:
    header = parse_header(data)
    identity_match = header["game_code"] == args.expected_game_code
    return {
        "tool": "recon_afej.py",
        "tool_version": "2026-08-16.1",
        "read_only": True,
        "input": str(path),
        "size": len(data),
        "hashes": {
            "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
            "md5": digest(data, "md5"),
            "sha1": digest(data, "sha1"),
            "sha256": digest(data, "sha256"),
        },
        "header": header,
        "identity": {
            "expected_game_code": args.expected_game_code,
            "game_code_matches": identity_match,
            "status": "candidate_match" if identity_match else "mismatch",
        },
        "probes": {
            "standard_shift_jis": shift_jis_probe_report(data, args.max_offsets),
            "ascii_runs": ascii_runs(data, args.min_ascii_length, args.max_candidates),
        },
        "pointer_candidates": {
            "address_base": f"0x{ROM_BASE:08x}",
            "minimum_words": args.min_pointer_run,
            "runs": pointer_runs(data, args.min_pointer_run, args.max_candidates),
            "interpretation": "candidate_only_until_disassembly_or_runtime_consumer_confirms",
        },
        "compression_candidates": {
            "types": {f"0x{key:02x}": value for key, value in COMPRESSION_TYPES.items()},
            "entries": compression_candidates(data, args.max_candidates),
            "interpretation": "magic_header_candidates_only_not_text_evidence",
        },
        "font_candidates": {
            "tile_format_tested": "GBA_4bpp_8x8_32_bytes",
            "windows": tile_window_candidates(
                data, args.font_window_tiles, args.max_candidates
            ),
            "interpretation": "sparse_tile_heuristic_only_requires_VRAM_and_byte_match",
        },
        "unresolved": [
            "text_location",
            "font_location_and_identity",
            "codepage",
            "pointer_semantics",
            "compression_consumer",
            "control_codes",
            "reversible_insertion_path",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--json-out", type=Path, help="write a local report outside tracked files")
    parser.add_argument("--expected-game-code", default="AFEJ")
    parser.add_argument("--max-candidates", type=int, default=64)
    parser.add_argument("--max-offsets", type=int, default=16)
    parser.add_argument("--min-pointer-run", type=int, default=4)
    parser.add_argument("--min-ascii-length", type=int, default=8)
    parser.add_argument("--font-window-tiles", type=int, default=64)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.rom.resolve()
    if not path.is_file():
        raise SystemExit(f"ROM not found: {path}")
    data = path.read_bytes()
    report = build_report(data, path, args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_out:
        output = args.json_out.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote read-only reconnaissance report: {output}")
    else:
        print(rendered, end="")
    print(
        "identity="
        f"{report['identity']['status']} "
        f"game_code={report['header']['game_code']} "
        f"crc32={report['hashes']['crc32']} "
        f"sha256={report['hashes']['sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
