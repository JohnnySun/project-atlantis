#!/usr/bin/env python3
"""Audit clean A9HJ control-parameter consumption boundaries.

The dispatch table alone does not tell the extractor how many bytes a
handler consumes.  This bounded audit records only static Thumb instruction
signatures and state conditions observed in the clean ROM; it never reads or
prints script bytes.  A ``conditional-*`` row must remain context-aware in a
future decoder and is deliberately not consumed by ``extract_text.py`` yet.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import zlib


ROM_SIZE = 0x800000
ROM_BASE = 0x08000000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"


# shape, logical source read, state condition.  ``source+18`` is the parser's
# script pointer field; ``state+14`` and ``state+1c`` are alternate handler
# state paths, not direct script bytes.
CONSUMPTION = {
    0xDF: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE0: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE1: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE2: ("none", "none", "unconditional"),
    0xE3: ("none", "none", "unconditional"),
    0xE4: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE5: ("none", "none", "unconditional"),
    0xE6: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE7: ("conditional-1", "source+18 or state+14", "state+10.bit5 / state+11.bit7"),
    0xE8: ("conditional-2", "source+18", "state+10.bit5 / state+11.bit7"),
    0xE9: ("none", "none", "unconditional"),
    0xEA: ("none", "none", "unconditional"),
    0xEB: ("none", "none", "unconditional"),
    0xEC: ("none", "none", "unconditional"),
    0xED: ("none", "none", "unconditional"),
    0xEE: ("none", "none", "unconditional"),
    0xEF: ("none", "none", "unconditional"),
    0xF0: ("fixed-1", "source+18", "unconditional"),
    0xF1: ("none", "none", "unconditional"),
    0xF2: ("none", "none", "unconditional"),
    0xF3: ("none", "none", "unconditional"),
    0xF4: ("conditional-2", "source+18 or state+22", "state+17 == 0"),
    0xF5: ("none", "none", "unconditional"),
    0xF6: ("none", "none", "unconditional"),
    0xF7: ("none", "none", "unconditional"),
    0xF8: ("none", "none", "unconditional"),
    # F9 has a state-dependent pre-read swap, but both branches fall through
    # or branch to the same source read at 0x0801335A.  It therefore consumes
    # one source byte on every handler entry; the bit does not gate the read.
    0xF9: ("fixed-1", "source+18", "state+10.bit7 selects pre-read swap"),
    0xFA: ("conditional-2", "source+18 or state+22", "state+17 == 0"),
    0xFB: ("none", "none", "unconditional"),
    0xFC: ("none", "none", "unconditional"),
    0xFD: ("none", "none", "unconditional"),
    0xFE: ("none", "none", "unconditional"),
    0xFF: ("none", "none", "unconditional"),
}


# (CPU address, expected little-endian instruction bytes, label).  These
# locations are the source reads that distinguish the fixed/conditional
# shapes.  The exact instruction bytes make the receipt independent of a
# local disassembler version.
READ_SIGNATURES = (
    (0x08012838, bytes.fromhex("aa69"), "DF source pointer load"),
    (0x0801283E, bytes.fromhex("1478"), "DF source byte load"),
    (0x0801287C, bytes.fromhex("aa69"), "E0/E1 source pointer load"),
    (0x08012882, bytes.fromhex("1478"), "E0/E1 source byte load"),
    (0x080128E4, bytes.fromhex("aa69"), "E4 source pointer load"),
    (0x080128EA, bytes.fromhex("1478"), "E4 source byte load"),
    (0x08012984, bytes.fromhex("aa69"), "E6 source pointer load"),
    (0x0801298A, bytes.fromhex("1478"), "E6 source byte load"),
    (0x080129D0, bytes.fromhex("aa69"), "E7 source pointer load"),
    (0x080129D6, bytes.fromhex("1478"), "E7 source byte load"),
    (0x08012A20, bytes.fromhex("aa69"), "E8 first source pointer load"),
    (0x08012A26, bytes.fromhex("1478"), "E8 first source byte load"),
    (0x08012A58, bytes.fromhex("aa69"), "E8 second source pointer load"),
    (0x08012A5E, bytes.fromhex("1178"), "E8 second source byte load"),
    (0x08013044, bytes.fromhex("a869"), "F0 source pointer load"),
    (0x08013046, bytes.fromhex("0178"), "F0 source byte load"),
    (0x080130CE, bytes.fromhex("aa69"), "F4 source pointer load"),
    (0x080130D0, bytes.fromhex("1078"), "F4 low byte load"),
    (0x080130D8, bytes.fromhex("1078"), "F4 high byte load"),
    (0x0801335A, bytes.fromhex("aa69"), "F9 source pointer load"),
    (0x0801335C, bytes.fromhex("1068"), "F9 logical source word load"),
    (0x08013376, bytes.fromhex("aa69"), "FA source pointer load"),
    (0x08013378, bytes.fromhex("1078"), "FA low byte load"),
    (0x08013380, bytes.fromhex("1078"), "FA high byte load"),
)

# These signatures capture the context that makes a raw source-read shape
# safe to interpret.  They contain code only, never script bytes.  In
# particular, F9's conditional branch and fall-through both meet at the same
# source read, while the parser's outer loop and FF handler use state flags
# to decide whether the consumer continues.
CONTEXT_SIGNATURES = (
    (
        0x0801265A,
        bytes.fromhex("217c08200840002800d0"),
        "parser outer-loop tests state+10 bit3",
    ),
    (
        0x0801334A,
        bytes.fromhex("297c80200840002802d1e87ba97ba873aa691068e97be873"),
        "F9 pre-read swap branch joins common source read",
    ),
    (
        0x08013668,
        bytes.fromhex("297c20200840002805d0297c21204042084028744ee0697c8022"),
        "FF clears state+10 bits on bit5 path and branches to alternate path",
    ),
    (
        0x08013694,
        bytes.fromhex("297c0520404208402874297c0920404208402874297c101c"),
        "FF alternate path clears state+10 bit3 before common flush",
    ),
)


def cpu_to_file(address: int) -> int:
    if not ROM_BASE <= address < ROM_BASE + ROM_SIZE:
        raise ValueError(f"address outside ROM: 0x{address:08X}")
    return address - ROM_BASE


def validate_rom(data: bytes) -> dict[str, str | int]:
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")
    return {"size": len(data), "crc32": f"{crc32:08X}", "sha256": sha256}


def audit_signatures(data: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for address, expected, label in READ_SIGNATURES:
        offset = cpu_to_file(address)
        actual = data[offset:offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"instruction signature changed at 0x{address:08X}: "
                f"expected {expected.hex()}, got {actual.hex()}"
            )
        rows.append({"address": f"0x{address:08X}", "bytes": expected.hex(), "label": label})
    return rows


def audit_context_signatures(data: bytes) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for address, expected, label in CONTEXT_SIGNATURES:
        offset = cpu_to_file(address)
        actual = data[offset:offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"context signature changed at 0x{address:08X}: "
                f"expected {expected.hex()}, got {actual.hex()}"
            )
        rows.append({"address": f"0x{address:08X}", "bytes": expected.hex(), "label": label})
    return rows


def audit(data: bytes) -> dict[str, object]:
    validate_rom(data)
    signatures = audit_signatures(data)
    context_signatures = audit_context_signatures(data)
    shapes = {f"{control:02X}": {"shape": row[0], "read": row[1], "condition": row[2]}
              for control, row in sorted(CONSUMPTION.items())}
    counts = {shape: sum(row[0] == shape for row in CONSUMPTION.values())
              for shape in sorted({row[0] for row in CONSUMPTION.values()})}
    return {
        "rom_sha256": EXPECTED_SHA256,
        "controls": shapes,
        "shape_counts": counts,
        "read_signature_count": len(signatures),
        "read_signatures": signatures,
        "context_signature_count": len(context_signatures),
        "context_signatures": context_signatures,
        "f9_read_contract": {
            "control": "F9",
            "handler": "0x0801334A",
            "source_read": "fixed-1",
            "state_bit": "state+0x10.bit7",
            "state_bit_role": "pre-read state+0x0E/state+0x0F swap selector",
            "both_paths_reach_source_read": True,
        },
        "outer_loop_contract": {
            "parser": "0x08012500",
            "continue_test": "state+0x10.bit3",
            "continue_branch": "0x0801265A -> 0x0801251A",
        },
        "ff_contract": {
            "handler": "0x08013668",
            "source_read": "none",
            "state_effect": "state-dependent flag clearing; alternate path clears state+0x10.bit3",
            "terminator_status": "not-proven",
        },
        "extractor_policy": "retain-control-candidates-until-context-decoder-proven",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    args = parser.parse_args()
    try:
        report = audit(args.rom.read_bytes())
    except (OSError, ValueError) as error:
        print(f"audit_control_consumption: {error}", file=sys.stderr)
        return 2
    print("rom-sha256", report["rom_sha256"])
    print("read-signatures", report["read_signature_count"])
    print("context-signatures", report["context_signature_count"])
    print("shape-counts", report["shape_counts"])
    for control, row in report["controls"].items():  # type: ignore[union-attr]
        print(f"{control} shape={row['shape']} read={row['read']} condition={row['condition']}")
    print("extractor-policy", report["extractor_policy"])
    print("f9-read-contract", report["f9_read_contract"])
    print("outer-loop-contract", report["outer_loop_contract"])
    print("ff-contract", report["ff_contract"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
