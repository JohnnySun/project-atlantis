#!/usr/bin/env python3
"""Bounded static scan for B3CJ text, pointers, and real GBA LZ/RLE decodes.

This scanner never writes a ROM and never emits decoded source text.  Candidate
records contain offsets, lengths, scores, hashes, and pointer references only;
they are evidence for a later runtime/code-flow check, not a text extractor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Iterable


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

MAX_OFFSETS = 16
MAX_SEGMENTS = 32
MAX_DECODE_ATTEMPTS = 2048
MAX_DECODED_SIZE = 0x40000

_SJIS_PAIR = {
    "big": re.compile(rb"(?:[\x81-\x9f\xe0-\xef][\x40-\x7e\x80-\xfc])+"),
    "little": re.compile(rb"(?:[\x40-\x7e\x80-\xfc][\x81-\x9f\xe0-\xef])+"),
}


def valid_sjis_code(value: int) -> bool:
    lead = value >> 8
    trail = value & 0xFF
    return (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xEF) and 0x40 <= trail <= 0xFC and trail != 0x7F


def find_offsets(data: bytes, needle: bytes, limit: int = MAX_OFFSETS) -> list[int]:
    result: list[int] = []
    start = 0
    while len(result) < limit:
        offset = data.find(needle, start)
        if offset < 0:
            break
        result.append(offset)
        start = offset + 1
    return result


def scan_probe_bytes(data: bytes) -> dict[str, object]:
    result: dict[str, object] = {}
    for label, text in SJIS_PROBES.items():
        direct = text.encode("shift_jis")
        swapped = b"".join(direct[index:index + 2][::-1] for index in range(0, len(direct), 2))
        result[label] = {
            "direct_count": data.count(direct),
            "direct_offsets": find_offsets(data, direct),
            "swapped_pair_count": data.count(swapped),
            "swapped_pair_offsets": find_offsets(data, swapped),
        }
    return result


def scan_sjis16_runs(
    data: bytes, min_units: int = 8, alignments: tuple[int, ...] = (0,)
) -> list[dict[str, object]]:
    """Find bounded runs of valid 16-bit SJIS-shaped units.

    The default is halfword-aligned scanning, which matches the normal GBA
    data alignment and keeps the full-ROM pass backed by the C regex engine.
    Callers may opt into alignment 1 for a separate exploratory pass.
    """

    candidates: list[dict[str, object]] = []
    for endian in ("big", "little"):
        pattern = _SJIS_PAIR[endian]
        for alignment in alignments:
            if alignment not in (0, 1):
                raise ValueError("SJIS alignment must be 0 or 1")
            aligned_data = data[alignment:]
            for match in pattern.finditer(aligned_data):
                # finditer may start at either byte parity; retain only the
                # requested halfword alignment.
                if match.start() & 1:
                    continue
                run_start = alignment + match.start()
                run_end = alignment + match.end()
                unit_count = (run_end - run_start) // 2
                if unit_count < min_units:
                    continue
                raw = data[run_start:run_end]
                candidates.append({
                    "endian": endian,
                    "alignment": alignment,
                    "file_offset": run_start,
                    "unit_count": unit_count,
                    "byte_length": len(raw),
                    "printable_units": None,
                    "byte_sha256": hashlib.sha256(raw).hexdigest(),
                    "rom_pointer": f"0x{0x08000000 + run_start:08x}",
                })

    candidates.sort(key=lambda item: int(item["unit_count"]), reverse=True)
    selected = candidates[:MAX_SEGMENTS]
    for item in selected:
        start = int(item["file_offset"])
        end = start + int(item["byte_length"])
        raw = data[start:end]
        printable = 0
        for index in range(0, len(raw), 2):
            pair = raw[index:index + 2]
            if item["endian"] == "little":
                pair = pair[::-1]
            try:
                char = pair.decode("shift_jis")
            except UnicodeDecodeError:
                continue
            printable += int(char.isprintable() or char in "\n\r\t")
        item["printable_units"] = printable
    # Resolve pointer references only for the bounded result set.  Doing a
    # full-ROM bytes.find for every short candidate makes a 32 MiB scan
    # needlessly unbounded while adding no evidence to discarded candidates.
    for item in selected:
        pointer = int(str(item["rom_pointer"]), 16).to_bytes(4, "little")
        refs = find_offsets(data, pointer)
        item["pointer_ref_count"] = len(refs)
        item["pointer_ref_offsets"] = refs[:MAX_OFFSETS]
    return selected


def decode_lz77(data: bytes, offset: int) -> tuple[int, int] | None:
    if offset + 4 > len(data) or data[offset] != 0x10:
        return None
    size = int.from_bytes(data[offset + 1:offset + 4], "little")
    if not 0 < size <= MAX_DECODED_SIZE:
        return None
    source = offset + 4
    output = bytearray()
    try:
        while len(output) < size:
            flags = data[source]
            source += 1
            for bit in range(8):
                if len(output) >= size:
                    break
                if flags & (0x80 >> bit):
                    first = data[source]
                    second = data[source + 1]
                    source += 2
                    length = (first >> 4) + 3
                    distance = ((first & 0x0F) << 8) | second
                    if distance >= len(output):
                        return None
                    for _ in range(length):
                        output.append(output[-distance - 1])
                        if len(output) == size:
                            break
                else:
                    output.append(data[source])
                    source += 1
    except (IndexError, ValueError):
        return None
    return size, source - offset


def decode_rle(data: bytes, offset: int) -> tuple[int, int] | None:
    if offset + 4 > len(data) or data[offset] != 0x30:
        return None
    size = int.from_bytes(data[offset + 1:offset + 4], "little")
    if not 0 < size <= MAX_DECODED_SIZE:
        return None
    source = offset + 4
    output_size = 0
    try:
        while output_size < size:
            control = data[source]
            source += 1
            if control & 0x80:
                count = (control & 0x7F) + 3
                data_byte = data[source]
                source += 1
                output_size += count
            else:
                count = control + 1
                source += count
                output_size += count
            if output_size > size:
                return None
    except IndexError:
        return None
    return size, source - offset


def scan_real_decodes(data: bytes) -> dict[str, object]:
    records: dict[str, list[dict[str, object]]] = {"lz77": [], "rle": []}
    attempts = {"lz77": 0, "rle": 0}
    decoders = {0x10: ("lz77", decode_lz77), 0x30: ("rle", decode_rle)}
    for offset in range(0, len(data) - 3, 4):
        marker = data[offset]
        selected = decoders.get(marker)
        if selected is None:
            continue
        name, decoder = selected
        if attempts[name] >= MAX_DECODE_ATTEMPTS:
            continue
        declared_size = int.from_bytes(data[offset + 1:offset + 4], "little")
        if not 0 < declared_size <= MAX_DECODED_SIZE:
            continue
        attempts[name] += 1
        result = decoder(data, offset)
        if result is None:
            continue
        expanded, consumed = result
        raw = data[offset:offset + consumed]
        records[name].append({
            "file_offset": offset,
            "expanded_size": expanded,
            "compressed_size": consumed,
            "compression_ratio": round(expanded / consumed, 3),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        })
    for name in records:
        records[name].sort(key=lambda item: (int(item["expanded_size"]), int(item["compression_ratio"])), reverse=True)
        records[name] = records[name][:MAX_SEGMENTS]
    records["limits"] = {
        "max_decode_attempts_per_format": MAX_DECODE_ATTEMPTS,
        "max_declared_expanded_size": MAX_DECODED_SIZE,
        "attempted_per_format": attempts,
    }
    return records


def scan_pointer_runs(data: bytes) -> dict[str, object]:
    start = 0x08000000
    end = start + len(data)
    runs: list[dict[str, int]] = []
    count = 0
    run_start: int | None = None
    run_length = 0
    for offset in range(0, len(data) - 3, 4):
        value = int.from_bytes(data[offset:offset + 4], "little")
        if start <= value < end:
            count += 1
            if run_start is None:
                run_start = offset
            run_length += 1
        else:
            if run_start is not None and run_length >= 4:
                runs.append({"file_offset": run_start, "word_count": run_length})
            run_start = None
            run_length = 0
    if run_start is not None and run_length >= 4:
        runs.append({"file_offset": run_start, "word_count": run_length})
    return {
        "aligned_pointer_word_count": count,
        "runs_at_least_4_words": len(runs),
        "first_runs": runs[:MAX_SEGMENTS],
    }


def inspect(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    header = {
        "title": data[0xA0:0xAC].rstrip(b"\0").decode("ascii", "replace"),
        "game_code": data[0xAC:0xB0].decode("ascii", "replace"),
        "maker_code": data[0xB0:0xB2].decode("ascii", "replace"),
        "revision": data[0xBC],
        "header_checksum": f"{data[0xBD]:02x}",
    }
    return {
        "file_size": len(data),
        "header": header,
        "sha256": hashlib.sha256(data).hexdigest(),
        "sjis_probe_bytes": scan_probe_bytes(data),
        "sjis16_runs": scan_sjis16_runs(data),
        "pointer_runs": scan_pointer_runs(data),
        "validated_compression_decodes": scan_real_decodes(data),
        "scan_limits": {
            "sjis16_min_units": 8,
            "sjis16_alignments": [0],
            "max_reported_sjis16_runs": MAX_SEGMENTS,
            "max_reported_pointer_runs": MAX_SEGMENTS,
        },
        "limitations": [
            "16-bit Shift-JIS runs are halfword-aligned hypotheses; alignment-1 data needs a separate opt-in pass.",
            "Pointer references do not establish a string table without code-flow or runtime confirmation.",
            "Validated LZ/RLE streams are capped at 2048 attempts per format and 0x40000 expanded bytes; they prove only that a decoder can consume the bytes, not that the payload is text.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    report = inspect(args.rom)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
