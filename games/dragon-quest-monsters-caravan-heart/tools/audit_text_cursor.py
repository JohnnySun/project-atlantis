#!/usr/bin/env python3
"""Audit bounded clean A9HJ text-source and output-slot cursor contracts.

The clean parser has more than one state path, so a pointer span alone is not
enough to call a byte a record boundary.  This audit records only instruction
signatures and the fields they touch.  It deliberately emits no script bytes,
glyph identities, or translation source text, and it does not claim that an
output-slot increment is a VWF width calculation.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


ROM_SIZE = 0x800000
ROM_BASE = 0x08000000


# These are code-only Thumb signatures from the clean ROM.  The signatures
# stop before literal-pool data and are intentionally kept short enough to be
# stable evidence for the field/operation contract, not a copied disassembly.
SIGNATURES = (
    (
        0x080125FA,
        bytes.fromhex("e269501ce061"),
        "alternate state index increments state+0x1C",
    ),
    (
        0x08012628,
        bytes.fromhex("a269501ca0611268"),
        "default parser source pointer loads state+0x18, advances one byte, then reads old cursor",
    ),
    (
        0x08012630,
        bytes.fromhex("201c20300178027000f018f8"),
        "parser stores current low byte at state+0x20 and calls 0x0801266C",
    ),
    (
        0x08012720,
        bytes.fromhex("aa69501ca8611478"),
        "pair path loads state+0x18, advances one byte, and reads the second source byte",
    ),
    (
        0x08012728,
        bytes.fromhex("301c211c01f004f8"),
        "pair path passes first byte and second byte to 0x08013738",
    ),
    (
        0x080137DE,
        bytes.fromhex("b07d61464143b0680918"),
        "pair writer derives destination from state+0x16 and glyph stride",
    ),
    (
        0x08013E1A,
        bytes.fromhex("a87d4243a8681218"),
        "single writer derives destination from state+0x16 and glyph stride",
    ),
)

ADVANCE_SIGNATURES = (
    (
        0x080137FE,
        bytes.fromhex("b07d0130b17db075"),
        "pair writer increments state+0x16 once",
    ),
    (
        0x08013E34,
        bytes.fromhex("a87d0130a97da875"),
        "single writer increments state+0x16 once",
    ),
)


def cpu_to_file(address: int) -> int:
    if not ROM_BASE <= address < ROM_BASE + ROM_SIZE:
        raise ValueError(f"address outside ROM: 0x{address:08X}")
    return address - ROM_BASE


def validate_size(data: bytes) -> None:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")


def check_signatures(data: bytes, entries: tuple[tuple[int, bytes, str], ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for address, expected, label in entries:
        offset = cpu_to_file(address)
        actual = data[offset:offset + len(expected)]
        if actual != expected:
            raise ValueError(
                f"instruction signature changed at 0x{address:08X}: "
                f"expected {expected.hex()}, got {actual.hex()}"
            )
        rows.append({"address": f"0x{address:08X}", "bytes": expected.hex(), "label": label})
    return rows


def audit(data: bytes) -> dict[str, object]:
    validate_size(data)
    signatures = check_signatures(data, SIGNATURES)
    advances = check_signatures(data, ADVANCE_SIGNATURES)
    return {
        "schema": "dqmch-text-cursor-contract-v1",
        "source_cursor_contract": {
            "default_field": "state+0x18",
            "default_advance": "+1 byte before handler read",
            "alternate_index_field": "state+0x1C",
            "current_byte_field": "state+0x20",
            "pair_second_byte": "state+0x18 old cursor, +1 byte before 0x08013738",
            "handler": "0x0801266C",
            "pair_combiner": "0x08013738",
            "scope": "bounded static signatures; alternate handler state and record boundaries remain open",
        },
        "output_slot_contract": {
            "field": "state+0x16",
            "pair_writer": {
                "entry": "0x08013738",
                "destination": "state+0x08 + state[0x16] * glyph_stride",
                "advance": "+1 after DMA3 descriptor setup",
            },
            "single_writer": {
                "entry": "0x08013E00",
                "destination": "state+0x08 + state[0x16] * glyph_stride",
                "advance": "+1 after DMA3 descriptor setup",
            },
            "stride": "32 bytes when state+0x10.bit7 is clear, 64 bytes when set",
        },
        "separation": {
            "source_cursor_field": "state+0x18",
            "output_slot_field": "state+0x16",
            "fields_are_distinct": True,
            "semantic_width_or_vwf": "not-proven",
            "record_boundary": "not-proven",
        },
        "signature_count": len(signatures),
        "signatures": signatures,
        "advance_signature_count": len(advances),
        "advance_signatures": advances,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--expect-size", type=int, required=True)
    parser.add_argument("--expect-game-code", required=True)
    parser.add_argument("--expect-crc32", required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args()
    try:
        repo_root = pathlib.Path(__file__).resolve().parents[3]
        identity = subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "gba-rom-identity.py"),
                str(args.rom.resolve()),
                "--expect-size",
                str(args.expect_size),
                "--expect-game-code",
                args.expect_game_code,
                "--expect-crc32",
                args.expect_crc32,
                "--expect-sha256",
                args.expect_sha256,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if identity.returncode != 0:
            detail = identity.stderr.strip() or identity.stdout.strip()
            raise ValueError(
                f"gba-rom-identity gate failed with exit {identity.returncode}: {detail}"
            )
        report = audit(args.rom.read_bytes())
    except (OSError, ValueError) as error:
        print(f"audit_text_cursor: {error}", file=sys.stderr)
        return 2
    print("schema", report["schema"])
    print("identity-gate", "pass")
    print("source-cursor", report["source_cursor_contract"])
    print("output-slot", report["output_slot_contract"])
    print("separation", report["separation"])
    print("signatures", report["signature_count"], "advance-signatures", report["advance_signature_count"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
