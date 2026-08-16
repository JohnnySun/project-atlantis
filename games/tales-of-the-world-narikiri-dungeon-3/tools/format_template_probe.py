#!/usr/bin/env python3
"""Verify one fixed B3TJ control-only format-template edge.

The reviewed game-code caller at ``0x080AEEE0`` loads a ROM pointer to
``0x081474C0`` and routes it through the parser family.  That address is not
one of the 8,938 strict text-record starts: it contains a short control-only
template immediately before a separate strict record.  This probe keeps that
template class separate and emits only token names, lengths, addresses and
hashes, never its full source bytes.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import struct
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import DEFAULT_RANGES, ROM_BASE, strict_records  # noqa: E402


EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

TEMPLATE_OFFSET = 0x1474C0
TEMPLATE_ADDRESS = ROM_BASE + TEMPLATE_OFFSET
TEMPLATE_POINTER_LITERAL = 0xAEF1C
TEMPLATE_CALLER = 0x080AEEE0
FORMAT_WRAPPER = 0x08001660
FORMAT_CALLER = 0x08001640
PARSER_ENTRY = 0x080025CC

TOKEN_RE = re.compile(rb"%[0-9A-Za-z]+")


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def verify_identity(data: bytes) -> dict[str, object]:
    crc32 = binascii.crc32(data) & 0xFFFFFFFF
    title = data[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = data[0xAC:0xB0]
    maker_code = data[0xB0:0xB2]
    result = {
        "size": len(data),
        "crc32": f"{crc32:08X}",
        "title_ascii": title.decode("ascii", errors="replace"),
        "game_code": game_code.decode("ascii", errors="replace"),
        "maker_code": maker_code.decode("ascii", errors="replace"),
    }
    if (
        len(data) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != EXPECTED_TITLE
        or game_code != EXPECTED_GAME_CODE
        or maker_code != EXPECTED_MAKER_CODE
    ):
        raise ValueError(f"ROM identity mismatch: {result}")
    return result


def decode_thumb_bl(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data) or offset % 2:
        return None
    first, second = struct.unpack_from("<HH", data, offset)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    sign = (first >> 10) & 1
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    value = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        value -= 1 << 25
    return ROM_BASE + offset + 4 + value


def parse_control_template(data: bytes, offset: int = TEMPLATE_OFFSET) -> dict[str, object]:
    if offset < 0 or offset + 3 > len(data):
        raise ValueError("format template is outside ROM")
    end = data.find(b"\0", offset, min(len(data), offset + 0x40))
    if end < 0:
        raise ValueError("format template is unterminated")
    raw = data[offset:end]
    tokens = TOKEN_RE.findall(raw)
    if not raw or not tokens or any(not token.startswith(b"%") for token in tokens):
        raise ValueError("expected a control-only template")
    if b"%k" not in tokens:
        raise ValueError("reviewed template token changed")
    return {
        "file_offset": _hex(offset, 6),
        "gba_address": _hex(ROM_BASE + offset),
        "raw_length_without_nul": len(raw),
        "nul_terminated": True,
        "control_tokens": [token.decode("ascii") for token in tokens],
        "token_count": len(tokens),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    pointer = struct.unpack_from("<I", data, TEMPLATE_POINTER_LITERAL)[0]
    if pointer != TEMPLATE_ADDRESS:
        raise ValueError("template pointer literal changed")
    caller_to_format = decode_thumb_bl(data, 0xAEEFC)
    caller_to_wrapper = decode_thumb_bl(data, 0xAEF02)
    wrapper_to_format = decode_thumb_bl(data, 0x1668)
    format_to_parser = decode_thumb_bl(data, 0x164C)
    if (caller_to_format, caller_to_wrapper, wrapper_to_format, format_to_parser) != (
        FORMAT_CALLER,
        FORMAT_WRAPPER,
        FORMAT_CALLER,
        PARSER_ENTRY,
    ):
        raise ValueError("template caller chain changed")

    records = {row.start: row for row in strict_records(data, DEFAULT_RANGES)}
    if TEMPLATE_OFFSET in records:
        raise ValueError("control-only template unexpectedly became strict record")
    adjacent = records.get(TEMPLATE_OFFSET + 4)
    template = parse_control_template(data)
    return {
        "identity": identity,
        "template": template,
        "static_provenance": {
            "pointer_literal_file_offset": _hex(TEMPLATE_POINTER_LITERAL, 6),
            "pointer_value": _hex(pointer),
            "pointer_reference_count_in_reviewed_literal": 1,
            "caller": _hex(TEMPLATE_CALLER),
            "caller_to_format": _hex(caller_to_format),
            "caller_to_wrapper": _hex(caller_to_wrapper),
            "wrapper_to_format": _hex(wrapper_to_format),
            "format_to_parser": _hex(format_to_parser),
            "parser_entry": _hex(PARSER_ENTRY),
            "strict_record_boundary": False,
        },
        "adjacent_strict_record": None
        if adjacent is None
        else {
            "string_id": f"sjis:0x{adjacent.start:06X}",
            "file_offset": _hex(adjacent.start, 6),
            "gba_address": _hex(ROM_BASE + adjacent.start),
            "region": adjacent.region,
            "raw_length": adjacent.raw_length,
            "end_offset_exclusive": _hex(adjacent.end, 6),
        },
        "classification": {
            "control_only_template": "confirmed-static-template",
            "strict_ledger_membership": "negative-by-boundary",
            "static_parser_edge": "confirmed-static",
            "runtime_template_read": "unconfirmed",
            "runtime_source_record_edge": "unconfirmed",
            "template_token_semantics": "unconfirmed",
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
