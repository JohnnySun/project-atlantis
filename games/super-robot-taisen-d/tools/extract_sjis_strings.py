#!/usr/bin/env python3
"""Extract strict NUL-terminated Shift-JIS candidates into a local source table.

This is intentionally a bounded candidate extractor, not yet the game's
final decoder. The caller must supply a vetted ROM range; binary data can
contain short Shift-JIS-valid fragments. Output is the local source-table
format consumed by the ledger restore tool and must stay under ignored
research/*-decoded.jsonl (or be sent to stdout for inspection).
"""

from __future__ import annotations

import argparse
import json
import pathlib


def looks_like_text(text: str, minimum_script_ratio: float) -> bool:
    if not text:
        return False
    if any(ord(char) < 0x20 for char in text):
        return False
    script = 0
    for char in text:
        code = ord(char)
        if (
            0x3040 <= code <= 0x30FF
            or 0x3400 <= code <= 0x9FFF
            or char.isascii() and (char.isalnum() or char in " .,!?%+-_()[]")
            or char in "。、！？「」『』（）【】　→↓←↑…〜・－―"
        ):
            script += 1
    return script / len(text) >= minimum_script_ratio


def extract(
    data: bytes,
    start: int,
    end: int,
    minimum_bytes: int,
    maximum_bytes: int,
    minimum_script_ratio: float,
):
    position = start
    while position < end:
        terminator = data.find(b"\x00", position, end)
        if terminator < 0:
            break
        raw = data[position:terminator]
        if minimum_bytes <= len(raw) <= maximum_bytes:
            try:
                text = raw.decode("shift_jis", errors="strict")
            except UnicodeDecodeError:
                text = None
            if text is not None and looks_like_text(text, minimum_script_ratio):
                yield position, raw, text
        position = terminator + 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--end", type=lambda value: int(value, 0), required=True)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("games/super-robot-taisen-d/research/super-robot-taisen-d-decoded.jsonl"),
        help="ignored local source-table path, or '-' for no file",
    )
    parser.add_argument("--minimum-bytes", type=int, default=2)
    parser.add_argument("--maximum-bytes", type=int, default=4096)
    parser.add_argument("--minimum-script-ratio", type=float, default=0.6)
    parser.add_argument("--show-text", action="store_true")
    args = parser.parse_args()

    data = args.rom.read_bytes()
    if not 0 <= args.start < args.end <= len(data):
        raise SystemExit("invalid extraction range")

    rows = list(
        extract(
            data,
            args.start,
            args.end,
            args.minimum_bytes,
            args.maximum_bytes,
            args.minimum_script_ratio,
        )
    )
    if args.out.name != "-" and not args.out.name.endswith("-decoded.jsonl"):
        raise SystemExit("refusing non-local-source output; use *-decoded.jsonl or '-' ")

    if args.out.name == "-":
        output = None
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        output = args.out.open("w", encoding="utf-8")

    try:
        for offset, raw, text in rows:
            record = {
                "string_id": offset,
                "locale": "ja",
                "text": text,
                "provenance": (
                    "A6SJ strict Shift-JIS NUL scan v1; "
                    f"rom_offset=0x{offset:06x}; byte_length={len(raw)}"
                ),
            }
            line = json.dumps(record, ensure_ascii=False)
            if output is not None:
                output.write(line + "\n")
            if args.show_text:
                print(f"0x{offset:06x}: {text}")
    finally:
        if output is not None:
            output.close()

    print(
        f"extracted {len(rows)} strict Shift-JIS candidates "
        f"from 0x{args.start:06x}..0x{args.end:06x}"
    )


if __name__ == "__main__":
    main()
