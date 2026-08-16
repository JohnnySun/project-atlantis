#!/usr/bin/env python3
"""Verify the bounded B3TJ source-pointer-shaped font-loader edge.

The reviewed function at ``0x080021A8`` reads two bytes from its caller's
``r1`` input pointer, applies the same lead/trail arithmetic as the fixed
format path, and selects a 32-byte slot at ``0x080DDCC4 + index*0x20``.  Its
only direct caller is ``0x08015C26``.  This probe verifies that exact callsite,
the preceding ``r8`` input-pointer setup, the five fixed upstream callers of
the object/text builder, and the bounded inline transform/init spans.

It is static metadata only.  It does not claim that the pointer is one of the
8,938 strict records, does not scan pointers, and never emits source, glyph,
RAM or VRAM bytes.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

FONT_LOADER_ENTRY = 0x080021A8
FONT_LOADER_CALLSITE = 0x15C26
FONT_BUILDER_ENTRY = 0x08015B74
FONT_BUILDER_CALLSITE = 0xCD170
OBJECT_TEXT_BUILDER_ENTRY = 0x080CD14C
OBJECT_TEXT_BUILDER_CALLS = (0xD5218, 0xD5224, 0xD5234, 0xD5240, 0xD6C86)
FONT_INIT_ENTRY = 0x08002100
FONT_INIT_CALLS = (0x2146, 0x2174, 0x21E2, 0x22FC)

FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
FONT_LOOKUP_BASE = 0x03001464
FONT_LOOKUP_AUX_BASE = 0x03001462


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


def _read_word(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"word outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<I", data, offset)[0]


def _read_halfword(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"halfword outside ROM at {_hex(offset, 6)}")
    return struct.unpack_from("<H", data, offset)[0]


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
    displacement = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | ((first & 0x03FF) << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        displacement -= 1 << 25
    return ROM_BASE + offset + 4 + displacement


def find_direct_calls(data: bytes, target: int) -> list[int]:
    return [
        offset
        for offset in range(0, len(data) - 4, 2)
        if decode_thumb_bl(data, offset) == target
    ]


def _span(data: bytes, name: str, start: int, end: int) -> dict[str, object]:
    if start < 0 or end <= start or end > len(data):
        raise ValueError(f"invalid bounded span {name}")
    value = data[start:end]
    return {
        "name": name,
        "file_start": _hex(start, 6),
        "file_end_exclusive": _hex(end, 6),
        "byte_length": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def font_asset_address(codepoint_index: int, rom_size: int = EXPECTED_SIZE) -> int:
    if codepoint_index < 0:
        raise ValueError("codepoint index must be non-negative")
    address = FONT_ASSET_BASE + codepoint_index * FONT_ASSET_STRIDE
    if not ROM_BASE <= address < ROM_BASE + rom_size:
        raise ValueError("font asset address outside ROM")
    if address + FONT_ASSET_STRIDE > ROM_BASE + rom_size:
        raise ValueError("font asset slot exceeds ROM")
    return address


def _callset(data: bytes, target: int, expected: tuple[int, ...]) -> dict[str, object]:
    calls = find_direct_calls(data, target)
    if calls != list(expected):
        raise ValueError(
            f"direct-call set changed for {_hex(target)}: {calls!r} != {list(expected)!r}"
        )
    return {
        "target": _hex(target),
        "count": len(calls),
        "file_offsets": [_hex(offset, 6) for offset in calls],
        "all_direct_targets_match": True,
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    direct_calls = {
        "font_loader": _callset(
            data, FONT_LOADER_ENTRY, (FONT_LOADER_CALLSITE,)
        ),
        "font_builder": _callset(
            data, FONT_BUILDER_ENTRY, (FONT_BUILDER_CALLSITE,)
        ),
        "object_text_builder": _callset(
            data, OBJECT_TEXT_BUILDER_ENTRY, OBJECT_TEXT_BUILDER_CALLS
        ),
        "font_init": _callset(data, FONT_INIT_ENTRY, FONT_INIT_CALLS),
    }

    literals = {
        "font_asset_base_loader": _read_word(data, 0x2310),
        "font_lookup_aux_loader": _read_word(data, 0x2314),
        "font_lookup_table_loader": _read_word(data, 0x2318),
        "font_lookup_aux_init": _read_word(data, 0x2120),
        "font_lookup_table_init": _read_word(data, 0x2124),
    }
    expected_literals = {
        "font_asset_base_loader": FONT_ASSET_BASE,
        "font_lookup_aux_loader": FONT_LOOKUP_AUX_BASE,
        "font_lookup_table_loader": FONT_LOOKUP_BASE,
        "font_lookup_aux_init": FONT_LOOKUP_AUX_BASE,
        "font_lookup_table_init": FONT_LOOKUP_BASE,
    }
    literal_checks = {
        name: {
            "value": _hex(value),
            "expected": _hex(expected_literals[name]),
            "matches": value == expected_literals[name],
        }
        for name, value in literals.items()
    }
    if not all(row["matches"] for row in literal_checks.values()):
        raise ValueError("font record consumer literal mismatch")

    instruction_checks = {
        "builder_saves_source_in_r8": _read_halfword(data, 0x15B82) == 0x4688,
        "loader_caller_sets_r0_from_r4": _read_halfword(data, 0x15C22) == 0x1C20,
        "loader_caller_sets_r1_from_r8": _read_halfword(data, 0x15C24) == 0x4641,
        "loader_reads_source_byte_0": _read_halfword(data, 0x21B6) == 0x7808,
        "loader_reads_source_byte_1": _read_halfword(data, 0x21B8) == 0x784A,
        "loader_lead_boundary_0x87": _read_halfword(data, 0x21BA) == 0x2887,
        "loader_asset_stride_shift_left_5": _read_halfword(data, 0x21D2) == 0x0140,
        "loader_initializes_lookup_before_expand": _read_halfword(data, 0x21E0) == 0x2000,
    }
    if not all(instruction_checks.values()):
        raise ValueError("font record consumer instruction signature mismatch")

    return {
        "identity": identity,
        "fixed_entries": {
            "object_text_builder": _hex(OBJECT_TEXT_BUILDER_ENTRY),
            "font_builder": _hex(FONT_BUILDER_ENTRY),
            "font_loader": _hex(FONT_LOADER_ENTRY),
            "font_init": _hex(FONT_INIT_ENTRY),
        },
        "direct_calls": direct_calls,
        "static_pointer_provenance": {
            "object_text_builder_to_font_builder": {
                "callsite": _hex(FONT_BUILDER_CALLSITE, 6),
                "register_setup": "r0=caller_allocated_context; r1=builder_input",
                "status": "confirmed-static-register-shape",
            },
            "font_builder_to_font_loader": {
                "callsite": _hex(FONT_LOADER_CALLSITE, 6),
                "register_setup": "r0=builder_context; r1=r8(saved-builder-input)",
                "status": "confirmed-static-source-pointer-shaped-edge",
            },
            "font_loader_source_read": {
                "instructions": ["0x080021B6:[r1]", "0x080021B8:[r1+1]"],
                "status": "confirmed-static-two-byte-input-read",
            },
        },
        "font_asset_contract": {
            "base": _hex(FONT_ASSET_BASE),
            "stride_bytes": FONT_ASSET_STRIDE,
            "address_formula": "0x080DDCC4 + sjis_like_index*0x20",
            "slot_address_helper": "font_asset_address(index)",
            "status": "confirmed-static-address-math",
        },
        "literals": literal_checks,
        "lookup_init_contract": {
            "aux_base": _hex(FONT_LOOKUP_AUX_BASE),
            "table_base": _hex(FONT_LOOKUP_BASE),
            "initializer": _hex(FONT_INIT_ENTRY),
            "interpretation": "runtime-initialized-lookup/palette-shape",
            "status": "confirmed-static-writes; values-runtime-dependent",
        },
        "bounded_spans": [
            _span(data, "object-text-builder-caller", 0xCD14C, 0xCD18A),
            _span(data, "font-builder", 0x15B74, 0x15C52),
            _span(data, "font-loader-inline-transform", 0x21A8, 0x2310),
            _span(data, "font-init", 0x2100, 0x2128),
        ],
        "instruction_checks": instruction_checks,
        "classification": {
            "source_pointer_shaped_font_loader_edge": "confirmed-static",
            "strict_five_window_record_membership": "unconfirmed",
            "live_source_read": "unconfirmed",
            "font_asset_identity": "provisional-static",
            "complete_japanese_codepage": "unconfirmed",
            "width_semantics": "unconfirmed",
            "loader_destination_buffer": "provisional-static",
            "scratch_or_object_to_vram": "unconfirmed",
            "capacity_roundtrip_and_insertion": "unconfirmed",
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
