#!/usr/bin/env python3
"""Audit clean A9HJ glyph-writer and layout constants.

This is a bounded static check for the already identified text consumer.  It
does not attach a semantic name to any unknown glyph or control byte and does
not attempt to run a second GDB infrastructure.  The receipt records the
parts needed by an eventual encoder: glyph stride, pair masks, DMA3 tile copy,
output index, and the alternate layout destination branch.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
import zlib
from pathlib import Path


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"

STATE_POINTER = 0x03002830
DMA3_SOURCE_REGISTER = 0x040000D4
ALTERNATE_GLYPH_TABLE = 0x082E0BD4
ALTERNATE_GLYPH_BANK_BIAS = 0x4000
GLYPH_STRIDE_NARROW = 0x20
GLYPH_STRIDE_WIDE = 0x40
PAIR_MASK_GENERAL = 0xFF1FFFFF
PAIR_MASK_93 = 0xF1FFFFFF
PAIR_MASK_9230 = 0xF1F1FFFF

# Thumb signatures for the output-slot advance in the two proven writers:
# ldrb state+0x16; adds #1; ldrb state+0x16; strb state+0x16.
ADVANCE_SIGNATURES = (
    (0x080137FE, bytes.fromhex("b07d0130b17db075"), "pair output-index +1"),
    (0x08013E34, bytes.fromhex("a87d0130a97da875"), "single output-index +1"),
)


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def validate_rom(data: bytes) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")


def audit_advance_signatures(data: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for address, expected, label in ADVANCE_SIGNATURES:
        offset = address - 0x08000000
        actual = data[offset:offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"output-index signature changed at 0x{address:08X}: "
                f"expected {expected.hex()}, got {actual.hex()}"
            )
        rows.append({"address": f"0x{address:08X}", "bytes": expected.hex(), "label": label})
    return rows


def audit(data: bytes) -> dict[str, object]:
    validate_rom(data)
    advance_signatures = audit_advance_signatures(data)
    values = {
        "state_pointer": read_u32(data, 0x13790),
        "pair_mask_93": read_u32(data, 0x13794),
        "pair_mask_9230": read_u32(data, 0x137BC),
        "pair_mask_general": read_u32(data, 0x13814),
        "dma3_register_pair": read_u32(data, 0x13818),
        "state_pointer_single": read_u32(data, 0x13E44),
        "dma3_register_single": read_u32(data, 0x13E48),
        "state_pointer_layout": read_u32(data, 0x13E9C),
        "alternate_glyph_table": read_u32(data, 0x13EA0),
        "dma3_register_layout": read_u32(data, 0x13EA4),
    }
    expected = {
        "state_pointer": STATE_POINTER,
        "pair_mask_93": PAIR_MASK_93,
        "pair_mask_9230": PAIR_MASK_9230,
        "pair_mask_general": PAIR_MASK_GENERAL,
        "dma3_register_pair": DMA3_SOURCE_REGISTER,
        "state_pointer_single": STATE_POINTER,
        "dma3_register_single": DMA3_SOURCE_REGISTER,
        "state_pointer_layout": STATE_POINTER,
        "alternate_glyph_table": ALTERNATE_GLYPH_TABLE,
        "dma3_register_layout": DMA3_SOURCE_REGISTER,
    }
    mismatches = {
        key: {"expected": f"0x{value:08X}", "actual": f"0x{values[key]:08X}"}
        for key, value in expected.items()
        if values[key] != value
    }
    if mismatches:
        raise ValueError(f"layout literal mismatch: {mismatches}")

    return {
        "rom_sha256": EXPECTED_SHA256,
        "combiner_entry": "0x08013738",
        "single_glyph_entry": "0x08013E00",
        "layout_branch_entry": "0x08013E4C",
        "state_pointer": f"0x{STATE_POINTER:08X}",
        "glyph_stride": {"state_bit_7_clear": GLYPH_STRIDE_NARROW, "state_bit_7_set": GLYPH_STRIDE_WIDE},
        "pair_loop_words": 8,
        "pair_masks": {
            "general_second_dword": f"0x{PAIR_MASK_GENERAL:08X}",
            "lead_93_second_dword": f"0x{PAIR_MASK_93:08X}",
            "lead_92_trail_30_second_dword_when_state_bit_0_clear": f"0x{PAIR_MASK_9230:08X}",
        },
        "dma3": {
            "source_register": f"0x{DMA3_SOURCE_REGISTER:08X}",
            "copy_words": "glyph_stride / 4",
            "destination": "state + 0x08 + state[0x16] * glyph_stride",
        },
        "layout_branch": {
            "state_bit": "state[0x10].bit1",
            "alternate_source_bias": f"0x{ALTERNATE_GLYPH_BANK_BIAS:04X}",
            "alternate_glyph_table": f"0x{ALTERNATE_GLYPH_TABLE:08X}",
            "alt_glyph_controls": ["0xE0", "0xE1"],
            "alt_glyph_bank_by_lead": {"0xE0": "0x0000", "0xE1": "0x4000"},
            "alt_glyph_handler": "0x0801284A",
            "output_index": "state[0x16]",
        },
        "advance_model": {
            "pair": "state[0x16] read, +1, write after 8-word combiner",
            "single": "state[0x16] read, +1, write after one glyph slot",
            "output_slot_stride": "glyph_stride",
            "bounded_vwf_status": "not-proven; clean writer evidence is fixed-cell output-slot advance",
            "signature_count": len(advance_signatures),
            "signatures": advance_signatures,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args()
    try:
        receipt = audit(args.rom.read_bytes())
    except (OSError, ValueError, struct.error) as error:
        print(f"audit_text_layout: {error}", file=sys.stderr)
        return 2
    print("rom-sha256", receipt["rom_sha256"])
    print("combiner", receipt["combiner_entry"], "single", receipt["single_glyph_entry"], "layout", receipt["layout_branch_entry"])
    print("state-pointer", receipt["state_pointer"])
    print("glyph-stride", receipt["glyph_stride"])
    print("pair-loop-words", receipt["pair_loop_words"])
    print("pair-masks", receipt["pair_masks"])
    print("dma3", receipt["dma3"])
    print("layout-branch", receipt["layout_branch"])
    print("advance-model", receipt["advance_model"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
