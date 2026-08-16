#!/usr/bin/env python3
"""Bounded M33 target-text relocation POC for A9PJ.

This is deliberately limited to the already eligible M32 name-entry row and
the static Latin row-2 target subset exposed by ``m20_keyboard_codepage_probe``.
It relocates one pointed-to halfword stream to the end of the ROM image and
rewrites exactly one known caller literal.  It is not a general extractor,
translator, CJK encoder, or patcher for unclassified rows.

The generated image and BPS belong in a caller-selected private/work path. The
receipt is metadata-only and never includes source text or stream bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from m20_keyboard_codepage_probe import (  # noqa: E402
    encode_bounded_target,
    latin_row2_mapping,
)


ROM_BASE = 0x08000000
EXPECTED_A9PJ_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"
CALLER_POINTER_FILE_OFFSET = 0x52720
EXPECTED_OLD_POINTER = 0x081FA4B4
ORIGINAL_STREAM_FILE_OFFSET = 0x1FA4B4
MAX_STREAM_UNITS = 0x100


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_target(rom: bytes, target_text: str) -> tuple[bytes, dict[str, object]]:
    """Build the bounded relocated image and a source-free receipt."""

    if len(rom) < CALLER_POINTER_FILE_OFFSET + 4:
        raise ValueError("ROM is too short for the bounded caller literal")
    old_pointer = struct.unpack_from("<I", rom, CALLER_POINTER_FILE_OFFSET)[0]
    if old_pointer != EXPECTED_OLD_POINTER:
        raise ValueError(
            f"unexpected M32 caller pointer 0x{old_pointer:08X}; refusing relocation"
        )
    encoded = encode_bounded_target(rom, target_text)
    stream = encoded + b"\x00\x00"
    target_offset = len(rom)
    new_pointer = ROM_BASE + target_offset
    patched = bytearray(rom)
    patched[CALLER_POINTER_FILE_OFFSET:CALLER_POINTER_FILE_OFFSET + 4] = struct.pack(
        "<I", new_pointer
    )
    patched.extend(stream)
    receipt = {
        "probe_version": "m33-target-reinsertion-poc-20260816.v1",
        "input_rom_sha256": sha256(rom),
        "input_rom_size": len(rom),
        "target_rom_sha256": sha256(bytes(patched)),
        "target_rom_size": len(patched),
        "caller_pointer_file_offset": f"0x{CALLER_POINTER_FILE_OFFSET:X}",
        "old_pointer_bus": f"0x{old_pointer:08X}",
        "new_pointer_bus": f"0x{new_pointer:08X}",
        "original_stream_file_offset": f"0x{ORIGINAL_STREAM_FILE_OFFSET:X}",
        "relocated_stream_file_offset": f"0x{target_offset:X}",
        "relocated_stream_byte_length": len(stream),
        "relocated_stream_sha256": sha256(stream),
        "encoded_target_byte_length": len(encoded),
        "encoded_target_sha256": sha256(encoded),
        "target_character_count": len(target_text),
        "terminator": "0x0000",
        "relocation_policy": "append-at-end-and-rewrite-one-M32-caller-literal",
        "source_text_emitted": False,
        "general_codepage_confirmed": False,
        "cjk_encoder_confirmed": False,
        "runtime_qa_confirmed": False,
    }
    return bytes(patched), receipt


def verify_target(clean_rom: bytes, target_rom: bytes, receipt: dict[str, object]) -> dict[str, object]:
    """Re-read the relocated stream and verify the bounded target alphabet."""

    if sha256(target_rom) != receipt.get("target_rom_sha256"):
        raise ValueError("target ROM hash does not match the build receipt")
    pointer = struct.unpack_from("<I", target_rom, CALLER_POINTER_FILE_OFFSET)[0]
    stream_offset = pointer - ROM_BASE
    if stream_offset < len(clean_rom) or stream_offset + 2 > len(target_rom):
        raise ValueError("relocated pointer is outside the appended target stream")
    units: list[int] = []
    position = stream_offset
    terminated = False
    while len(units) < MAX_STREAM_UNITS and position + 2 <= len(target_rom):
        unit = int.from_bytes(target_rom[position:position + 2], "little")
        position += 2
        units.append(unit)
        if unit == 0:
            terminated = True
            break
    if not terminated:
        raise ValueError("relocated stream has no bounded 0x0000 terminator")

    mapping = latin_row2_mapping(clean_rom)
    allowed = set(mapping.values()) | {0x0006}
    unresolved = [unit for unit in units[:-1] if unit not in allowed]
    if unresolved:
        raise ValueError("relocated target contains a code unit outside the bounded encoder")
    encoded = b"".join(unit.to_bytes(2, "little") for unit in units[:-1])
    return {
        "pointer_bus": f"0x{pointer:08X}",
        "stream_file_offset": f"0x{stream_offset:X}",
        "units_including_terminator": len(units),
        "terminator_confirmed": True,
        "unresolved_unit_count": len(unresolved),
        "encoded_target_sha256": sha256(encoded),
        "receipt_match": sha256(encoded) == receipt.get("encoded_target_sha256"),
        "original_stream_unchanged": (
            clean_rom[ORIGINAL_STREAM_FILE_OFFSET:ORIGINAL_STREAM_FILE_OFFSET + 0x10]
            == target_rom[ORIGINAL_STREAM_FILE_OFFSET:ORIGINAL_STREAM_FILE_OFFSET + 0x10]
        ),
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--target-text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    clean_rom = args.rom.read_bytes()
    if sha256(clean_rom) != EXPECTED_A9PJ_SHA256:
        raise SystemExit("A9PJ clean-ROM SHA-256 mismatch; refusing target POC")
    target_rom, receipt = build_target(clean_rom, args.target_text)
    receipt["verification"] = verify_target(clean_rom, target_rom, receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target_rom)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "verification"}, sort_keys=True))


if __name__ == "__main__":
    main()
