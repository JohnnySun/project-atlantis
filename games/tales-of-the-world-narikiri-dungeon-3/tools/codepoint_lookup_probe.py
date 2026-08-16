#!/usr/bin/env python3
"""Verify the bounded B3TJ codepoint-lookup pointer pool.

The format loop has one reviewed direct call to ``0x08004D90``.  That helper
uses five fixed literal-pool slots to select ROM halfword tables.  This probe
checks only those slots and bounded 0x100-byte table windows; it emits pointer
values, hashes and counts, never raw lookup bytes or source text.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import ROM_BASE  # noqa: E402


EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

LOOKUP_ENTRY = 0x4D90
LOOKUP_CALLSITES = (0x15C4, 0x4D60)
POINTER_POOL = {
    0x741D80: 0x080FFE80,
    0x741D84: 0x080FFF40,
    0x741D88: 0x080FFFBC,
    0x741D8C: 0x080FFFF4,
    0x741D90: 0x08100070,
}
TABLE_WINDOW = 0x100


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


def summarize_table(data: bytes, address: int, *, window: int = TABLE_WINDOW) -> dict[str, object]:
    if not ROM_BASE <= address < ROM_BASE + len(data):
        raise ValueError("lookup target is not in ROM")
    offset = address - ROM_BASE
    raw = data[offset : offset + window]
    if len(raw) != window or len(raw) % 2:
        raise ValueError("lookup table window is truncated or not halfword-aligned")
    values = struct.unpack(f"<{len(raw) // 2}H", raw)
    return {
        "gba_address": _hex(address),
        "file_offset": _hex(offset, 6),
        "window_bytes": len(raw),
        "halfword_count": len(values),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "nonzero_bytes": sum(value != 0 for value in raw),
        "unique_halfword_count": len(set(values)),
        "signed_halfword_min": min(struct.unpack(f"<{len(values)}h", raw)),
        "signed_halfword_max": max(struct.unpack(f"<{len(values)}h", raw)),
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    if data[LOOKUP_ENTRY : LOOKUP_ENTRY + 2] != b"\x10\xB5":
        raise ValueError("codepoint lookup entry signature changed")
    callsites = [
        offset
        for offset in range(0, len(data) - 4, 2)
        if decode_thumb_bl(data, offset) == ROM_BASE + LOOKUP_ENTRY
    ]
    if callsites != list(LOOKUP_CALLSITES):
        raise ValueError(f"codepoint lookup callsite set changed: {callsites!r}")

    slots = []
    tables = []
    for slot, expected in sorted(POINTER_POOL.items()):
        value = struct.unpack_from("<I", data, slot)[0]
        if value != expected:
            raise ValueError(f"lookup pointer slot changed at {_hex(slot, 6)}")
        slots.append(
            {
                "literal_file_offset": _hex(slot, 6),
                "value": _hex(value),
                "matches_expected": True,
            }
        )
        tables.append(summarize_table(data, value))

    return {
        "identity": identity,
        "lookup": {
            "entry": _hex(ROM_BASE + LOOKUP_ENTRY),
            "direct_callsite_count": len(callsites),
            "direct_callsites": [_hex(ROM_BASE + offset) for offset in callsites],
            "pointer_pool": slots,
            "table_window_bytes": TABLE_WINDOW,
            "tables": tables,
        },
        "classification": {
            "static_codepoint_lookup": "confirmed-static",
            "rom_table_pool": "confirmed-static",
            "width_semantics": "provisional-static",
            "glyph_identity": "unconfirmed",
            "runtime_source_record_edge": "unconfirmed",
            "runtime_glyph_vram_edge": "unconfirmed",
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
