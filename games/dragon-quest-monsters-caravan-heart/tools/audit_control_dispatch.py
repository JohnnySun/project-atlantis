#!/usr/bin/env python3
"""Audit the clean A9HJ text control dispatch table.

The parser subtracts 0xDF from a control byte and indexes a table through a
literal at file offset 0x12780.  The literal points at the first entry at
0x12784; the table targets remain Thumb addresses even though their low bit is
clear because the parser uses Thumb ``mov pc, r0``.  This command verifies the
table against the clean ROM and prints only handler addresses and static
parameter-shape labels.  It does not read or emit script bytes.
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
TABLE_LITERAL_CPU = 0x08012780
TABLE_CPU = 0x08012784
CONTROL_FIRST = 0xDF
CONTROL_LAST = 0xFF


HANDLERS = (
    0x08012808, 0x0801284A, 0x0801284A, 0x080129DE,
    0x080128A4, 0x080128AC, 0x08012910, 0x08012952,
    0x0801299E, 0x080129EE, 0x08012A6E, 0x080130B0,
    0x08012BE0, 0x08012BF2, 0x08012C74, 0x08012E58,
    0x08012F18, 0x0801303C, 0x08013058, 0x080130B0,
    0x080130C0, 0x080130C8, 0x0801325C, 0x0801326C,
    0x08013318, 0x0801332E, 0x0801334A, 0x08013370,
    0x08013460, 0x080135F0, 0x080135FA, 0x08013638,
    0x08013668,
)

# These labels describe static source-pointer reads, not guessed semantics.
# A conditional shape means that the handler has state-dependent branches
# which either consume the shown number of bytes from state+0x18 or operate on
# an already-pending state value.
PARAMETER_SHAPES = (
    "may-read-1", "may-read-1", "may-read-1", "none",
    "none", "may-read-1", "none", "may-read-1",
    "may-read-1", "conditional-2", "none", "none",
    "none", "none", "none", "none",
    "none", "read-1", "none", "none",
    "none", "conditional-2", "none", "none",
    "none", "none", "conditional-1", "conditional-2",
    "none", "none", "none", "none",
    "none",
)


def cpu_to_file(address: int) -> int:
    if not ROM_BASE <= address < ROM_BASE + ROM_SIZE:
        raise ValueError(f"address outside ROM: 0x{address:08X}")
    return address - ROM_BASE


def read_u32(data: bytes, address: int) -> int:
    offset = cpu_to_file(address)
    return int.from_bytes(data[offset:offset + 4], "little")


def validate_rom(data: bytes) -> None:
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean ROM: CRC32={crc32:08X}, SHA256={sha256}")


def audit_table(data: bytes) -> list[tuple[int, int, str]]:
    literal = read_u32(data, TABLE_LITERAL_CPU)
    if literal != TABLE_CPU:
        raise ValueError(
            f"dispatch literal changed: expected 0x{TABLE_CPU:08X}, got 0x{literal:08X}"
        )
    rows: list[tuple[int, int, str]] = []
    for index, expected in enumerate(HANDLERS):
        control = CONTROL_FIRST + index
        actual = read_u32(data, TABLE_CPU + index * 4)
        if actual != expected:
            raise ValueError(
                f"handler mismatch {control:02X}: expected 0x{expected:08X}, got 0x{actual:08X}"
            )
        rows.append((control, actual, PARAMETER_SHAPES[index]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    args = parser.parse_args()
    try:
        data = args.rom.read_bytes()
        validate_rom(data)
        rows = audit_table(data)
    except (OSError, ValueError) as error:
        print(f"audit_control_dispatch: {error}", file=sys.stderr)
        return 2

    print("rom-sha256", EXPECTED_SHA256)
    print("literal", f"0x{TABLE_LITERAL_CPU:08X}", "table", f"0x{TABLE_CPU:08X}")
    print("entries", len(rows), "controls", f"0x{CONTROL_FIRST:02X}-0x{CONTROL_LAST:02X}")
    for control, handler, shape in rows:
        print(f"{control:02X} handler=0x{handler:08X} shape={shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
