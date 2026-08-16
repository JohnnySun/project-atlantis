#!/usr/bin/env python3
"""Small Capstone wrapper for read-only GBA ARM/Thumb reconnaissance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
except ImportError as exc:  # pragma: no cover - depends on local tooling
    raise SystemExit("capstone is required; use the system Python that provides it") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--length", type=lambda value: int(value, 0), default=0x100)
    parser.add_argument("--mode", choices=("arm", "thumb"), required=True)
    args = parser.parse_args()

    data = args.rom.read_bytes()[args.offset : args.offset + args.length]
    mode = CS_MODE_ARM if args.mode == "arm" else CS_MODE_THUMB
    disassembler = Cs(CS_ARCH_ARM, mode)
    disassembler.detail = False
    base = 0x08000000 + args.offset
    for instruction in disassembler.disasm(data, base):
        print(
            f"0x{instruction.address:08x}: "
            f"{instruction.bytes.hex():<12} "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )


if __name__ == "__main__":
    main()
