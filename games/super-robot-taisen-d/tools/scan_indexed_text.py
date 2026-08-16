#!/usr/bin/env python3
"""Probe a hypothesized indexed text/codepage table without writing output.

The table is supplied by the caller because this game's format is not known
yet. A table entry is interpreted as one Shift-JIS character only for this
local experiment. The scanner looks for contiguous little-endian halfwords
that are valid table indices and ranks runs by Japanese-script/punctuation
content. It is candidate evidence, not a decoder: use --show-text only in a
local terminal and never copy its output into a translation ledger.
"""

from __future__ import annotations

import argparse
import pathlib
import struct


def read_table(data: bytes, offset: int, count: int) -> list[str]:
    end = offset + count * 2
    if offset < 0 or end > len(data):
        raise ValueError("table is outside ROM")
    chars: list[str] = []
    for pos in range(offset, end, 2):
        raw = data[pos : pos + 2]
        try:
            text = raw.decode("shift_jis", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError(f"table entry at 0x{pos:06x} is not Shift-JIS") from exc
        if len(text) != 1:
            raise ValueError(f"table entry at 0x{pos:06x} is not one character")
        chars.append(text)
    return chars


def score(text: str) -> int:
    score_value = 0
    for char in text:
        code = ord(char)
        if 0x3040 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF:
            score_value += 3
        elif char in "。、！？「」『』（）【】　→↓←↑…〜・":
            score_value += 2
        elif char.isascii() and (char.isalnum() or char in " -_.,!?%"):
            score_value += 1
    return score_value


def scan(data: bytes, table: list[str], start: int, end: int, minimum: int):
    candidates = []
    for pos in range(start & ~1, min(end, len(data) - 1), 2):
        current = pos
        indices: list[int] = []
        while current + 2 <= end:
            value = struct.unpack_from("<H", data, current)[0]
            if value >= len(table):
                break
            indices.append(value)
            current += 2
        if len(indices) < minimum:
            continue
        text = "".join(table[value] for value in indices)
        candidates.append((score(text), pos, current, indices, text))
    return sorted(candidates, key=lambda row: (-row[0], -(row[2] - row[1]), row[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--table-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--table-count", type=int, required=True)
    parser.add_argument("--start", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--end", type=lambda value: int(value, 0))
    parser.add_argument("--min-run", type=int, default=8)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--show-text", action="store_true")
    args = parser.parse_args()

    data = args.rom.read_bytes()
    table = read_table(data, args.table_offset, args.table_count)
    end = len(data) if args.end is None else args.end
    candidates = scan(data, table, args.start, end, args.min_run)
    print(
        f"table=0x{args.table_offset:06x} entries={len(table)} "
        f"scan=0x{args.start:06x}..0x{end:06x} candidates={len(candidates)}"
    )
    for value, pos, finish, indices, text in candidates[: args.limit]:
        preview = text if args.show_text else "<hidden>"
        print(
            f"0x{pos:06x}-0x{finish:06x} codes={len(indices)} score={value} "
            f"preview={preview}"
        )


if __name__ == "__main__":
    main()
