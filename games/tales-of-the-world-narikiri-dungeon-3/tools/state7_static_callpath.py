#!/usr/bin/env python3
"""Verify two fixed B3TJ state-7-to-text candidate call chains.

This is a bounded static call-edge receipt, not a pointer scan. It checks
only BL instructions already reviewed while tracing state 7: one chain ends
at the formatter entry and one ends at the parser entry. It emits addresses,
edge counts and hashes of the checked instruction words only; it never emits
source text, raw instruction bytes, RAM, VRAM or screenshots.

The chains make useful runtime breakpoint candidates. They do not prove that
state 7 reaches a five-window record, that the parser is called at runtime, or
that a glyph reaches VRAM.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import verify_b3tj  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
STATE7_ENTRY = 0x080A85D8
FORMATTER_ENTRY = 0x080014F4
PARSER_ENTRY = 0x080025CC

# (callsite, target), kept intentionally fixed and small. These are direct
# BL edges observed in the state-7 static trace, not results of a new scan.
STATE7_TO_FORMATTER = (
    (0x080A85FA, 0x080C7B58),
    (0x080C7B6C, 0x080C6F58),
    (0x080C70E0, 0x080C7550),
    (0x080C7584, 0x08001660),
    (0x08001668, 0x08001640),
    (0x08001652, FORMATTER_ENTRY),
)
STATE7_TO_PARSER = (
    (0x080A85FE, 0x080D5ECC),
    (0x080D5ECE, 0x080D5FAC),
    (0x080D601E, 0x08001DA8),
    (0x08001DB0, 0x08001D88),
    (0x08001D92, PARSER_ENTRY),
)


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def decode_thumb_bl(data: bytes, file_offset: int) -> int | None:
    """Decode one Thumb-2 BL at a file offset."""

    if file_offset < 0 or file_offset + 4 > len(data) or file_offset % 2:
        return None
    first, second = struct.unpack_from("<HH", data, file_offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    displacement = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        displacement -= 1 << 25
    return ROM_BASE + file_offset + 4 + displacement


def _edge_row(data: bytes, callsite: int, expected_target: int) -> dict[str, object]:
    file_offset = callsite - ROM_BASE
    actual_target = decode_thumb_bl(data, file_offset)
    if actual_target != expected_target:
        actual = None if actual_target is None else _hex(actual_target)
        raise ValueError(
            f"fixed BL edge changed at {_hex(callsite)}: "
            f"got {actual}, expected {_hex(expected_target)}"
        )
    return {
        "callsite": _hex(callsite),
        "target": _hex(expected_target),
        "file_offset": f"0x{file_offset:06X}",
    }


def _chain(data: bytes, edges: tuple[tuple[int, int], ...]) -> dict[str, object]:
    rows = [_edge_row(data, callsite, target) for callsite, target in edges]
    instruction_bytes = b"".join(
        data[callsite - ROM_BASE : callsite - ROM_BASE + 4]
        for callsite, _ in edges
    )
    return {
        "edge_count": len(rows),
        "edges": rows,
        "checked_instruction_sha256": hashlib.sha256(instruction_bytes).hexdigest(),
    }


def analyze(data: bytes) -> dict[str, object]:
    if len(data) != EXPECTED_SIZE:
        raise ValueError(f"unexpected ROM size: {len(data)}")
    verify_b3tj(data)
    formatter = _chain(data, STATE7_TO_FORMATTER)
    parser = _chain(data, STATE7_TO_PARSER)
    return {
        "identity": {
            "size": len(data),
            "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08X}",
            "sha256": hashlib.sha256(data).hexdigest(),
            "game_code": "B3TJ",
        },
        "fixed_roots": {
            "state7_entry": _hex(STATE7_ENTRY),
            "formatter_entry": _hex(FORMATTER_ENTRY),
            "parser_entry": _hex(PARSER_ENTRY),
        },
        "chains": {
            "state7_to_formatter": formatter,
            "state7_to_parser": parser,
        },
        "classification": {
            "state7_to_formatter": "confirmed-static-bounded-direct-call-chain",
            "state7_to_parser": "confirmed-static-bounded-direct-call-chain",
            "runtime_state7_entry": "unconfirmed",
            "runtime_parser_hit": "unconfirmed",
            "five_window_source_record": "unconfirmed",
            "decoder_codepage_glyph_vram": "unconfirmed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze(args.rom.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(text, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
