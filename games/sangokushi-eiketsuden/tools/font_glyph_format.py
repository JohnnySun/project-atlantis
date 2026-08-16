#!/usr/bin/env python3
"""Verify the B3EJ two-plane glyph expansion contract.

The reviewed Thumb routine at 0x080650DC combines two 0x20-byte source planes
into a 0x80-byte cache record.  This tool reproduces that byte-level operation
and reports only offsets, counts and hashes.  It never writes glyph bytes,
images, ROMs or fonts; any future licensed font input remains caller-owned and
ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ROM_BASE = 0x08000000
CODEPAGE_TABLE_FILE_OFFSET = 0x024110C
CODEPAGE_COUNT = 0x729 + 1
GLYPH_SOURCE_BASES = (0x08232BCC, 0x0822468C)
GLYPH_STRIDE = 0x20
CACHE_BYTES = 0x80


def expand_source_planes(
    first_plane: bytes, second_plane: bytes, *, selector: int = 0
) -> bytes:
    """Reproduce the reviewed Thumb plane-to-cache expansion."""

    if len(first_plane) != GLYPH_STRIDE or len(second_plane) != GLYPH_STRIDE:
        raise ValueError("each glyph source plane must be exactly 0x20 bytes")
    if not 0 <= selector <= 0xFF:
        raise ValueError("selector must fit the renderer byte")

    # The routine executes ``r2 += 2`` before deriving the masks used by the
    # second plane.  The first plane contributes output bits 0/4; the second
    # contributes the selector-derived bits.  Four output bytes are emitted for
    # every source byte, in the exact order used by the ROM routine.
    adjusted = selector + 2
    first_mask = adjusted & 0xFF
    second_mask = (adjusted & 0x0F) << 4
    output = bytearray(CACHE_BYTES)
    for index, (first, second) in enumerate(zip(first_plane, second_plane)):
        offset = index * 4
        if first & 0x80:
            output[offset] |= 0x01
        if first & 0x40:
            output[offset] |= 0x10
        if first & 0x20:
            output[offset + 1] |= 0x01
        if first & 0x10:
            output[offset + 1] |= 0x10
        if first & 0x08:
            output[offset + 2] |= 0x01
        if first & 0x04:
            output[offset + 2] |= 0x10
        if first & 0x02:
            output[offset + 3] |= 0x01
        if first & 0x01:
            output[offset + 3] |= 0x10
        if second & 0x80:
            output[offset] |= first_mask
        if second & 0x40:
            output[offset] |= second_mask
        if second & 0x20:
            output[offset + 1] |= first_mask
        if second & 0x10:
            output[offset + 1] |= second_mask
        if second & 0x08:
            output[offset + 2] |= first_mask
        if second & 0x04:
            output[offset + 2] |= second_mask
        if second & 0x02:
            output[offset + 3] |= first_mask
        if second & 0x01:
            output[offset + 3] |= second_mask
    return bytes(output)


def read_codepage(data: bytes) -> list[int]:
    end = CODEPAGE_TABLE_FILE_OFFSET + CODEPAGE_COUNT * 2
    if end > len(data):
        raise ValueError("codepage table exceeds ROM")
    return [
        struct.unpack_from("<H", data, CODEPAGE_TABLE_FILE_OFFSET + index * 2)[0]
        for index in range(CODEPAGE_COUNT)
    ]


def glyph_receipt(data: bytes, index: int, *, selector: int = 0) -> dict[str, object]:
    """Return a hash-only receipt for one reviewed codepage index."""

    if not 0 <= index < CODEPAGE_COUNT:
        raise ValueError("codepage index outside the reviewed inclusive range")
    planes = []
    for base in GLYPH_SOURCE_BASES:
        offset = base - ROM_BASE + index * GLYPH_STRIDE
        plane = data[offset:offset + GLYPH_STRIDE]
        if len(plane) != GLYPH_STRIDE:
            raise ValueError("glyph source plane exceeds ROM")
        planes.append({
            "source_gba_address": f"0x{base + index * GLYPH_STRIDE:08X}",
            "source_file_offset": f"0x{offset:06X}",
            "sha256": hashlib.sha256(plane).hexdigest(),
            "nonzero_byte_count": sum(value != 0 for value in plane),
        })
    expanded = expand_source_planes(
        data[GLYPH_SOURCE_BASES[0] - ROM_BASE + index * GLYPH_STRIDE:
             GLYPH_SOURCE_BASES[0] - ROM_BASE + (index + 1) * GLYPH_STRIDE],
        data[GLYPH_SOURCE_BASES[1] - ROM_BASE + index * GLYPH_STRIDE:
             GLYPH_SOURCE_BASES[1] - ROM_BASE + (index + 1) * GLYPH_STRIDE],
        selector=selector,
    )
    codepage = read_codepage(data)
    return {
        "codepage_index": index,
        "code_unit": f"0x{codepage[index]:04X}",
        "selector": selector,
        "plane_stride": GLYPH_STRIDE,
        "cache_length": len(expanded),
        "cache_sha256": hashlib.sha256(expanded).hexdigest(),
        "cache_nonzero_byte_count": sum(value != 0 for value in expanded),
        "source_planes": planes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--selector", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"read_only": True, **glyph_receipt(args.rom.read_bytes(), args.index, selector=args.selector)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("read_only", "codepage_index", "code_unit", "selector", "cache_length", "cache_sha256")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
