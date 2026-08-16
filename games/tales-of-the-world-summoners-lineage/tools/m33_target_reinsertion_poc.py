#!/usr/bin/env python3
"""Bounded M33/M34 target-text relocation POC for A9PJ.

The fixed profiles are limited to the already eligible M32 surname row and
M34 protagonist-name row, both using the static Latin row-2 target subset
exposed by ``m20_keyboard_codepage_probe``. Each profile relocates one pointed-
to halfword stream to the end of the ROM image and rewrites exactly one known
caller literal. It is not a general extractor, translator, CJK encoder, or
patcher for unclassified rows.

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
PROFILES = {
    "m32": {
        "caller_pointer_file_offset": 0x52720,
        "expected_old_pointer": 0x081FA4B4,
        "original_stream_file_offset": 0x1FA4B4,
        "original_stream_byte_length": 0x10,
        "policy": "append-at-end-and-rewrite-one-M32-caller-literal",
    },
    "m34": {
        "caller_pointer_file_offset": 0x003E34,
        "expected_old_pointer": 0x08087384,
        "original_stream_file_offset": 0x087384,
        "original_stream_byte_length": 0x0A,
        "policy": "append-at-end-and-rewrite-one-M34-source-pointer-literal",
    },
}
# Backward-compatible aliases used by the M33 unit tests and callers.
CALLER_POINTER_FILE_OFFSET = PROFILES["m32"]["caller_pointer_file_offset"]
EXPECTED_OLD_POINTER = PROFILES["m32"]["expected_old_pointer"]
ORIGINAL_STREAM_FILE_OFFSET = PROFILES["m32"]["original_stream_file_offset"]
MAX_STREAM_UNITS = 0x100


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def profile_metadata(name: str) -> dict[str, int | str]:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown bounded relocation profile: {name}") from exc


def build_target(
    rom: bytes,
    target_text: str,
    *,
    profile: str = "m32",
) -> tuple[bytes, dict[str, object]]:
    """Build the bounded relocated image and a source-free receipt."""

    selected = profile_metadata(profile)
    pointer_file_offset = int(selected["caller_pointer_file_offset"])
    expected_old_pointer = int(selected["expected_old_pointer"])
    original_stream_file_offset = int(selected["original_stream_file_offset"])
    if len(rom) < pointer_file_offset + 4:
        raise ValueError("ROM is too short for the bounded caller literal")
    old_pointer = struct.unpack_from("<I", rom, pointer_file_offset)[0]
    if old_pointer != expected_old_pointer:
        raise ValueError(
            f"unexpected {profile} caller pointer 0x{old_pointer:08X}; refusing relocation"
        )
    encoded = encode_bounded_target(rom, target_text)
    stream = encoded + b"\x00\x00"
    target_offset = len(rom)
    new_pointer = ROM_BASE + target_offset
    patched = bytearray(rom)
    patched[pointer_file_offset:pointer_file_offset + 4] = struct.pack(
        "<I", new_pointer
    )
    patched.extend(stream)
    receipt = {
        "probe_version": "m33-m34-target-reinsertion-poc-20260816.v2",
        "profile": profile,
        "input_rom_sha256": sha256(rom),
        "input_rom_size": len(rom),
        "target_rom_sha256": sha256(bytes(patched)),
        "target_rom_size": len(patched),
        "caller_pointer_file_offset": f"0x{pointer_file_offset:X}",
        "old_pointer_bus": f"0x{old_pointer:08X}",
        "new_pointer_bus": f"0x{new_pointer:08X}",
        "original_stream_file_offset": f"0x{original_stream_file_offset:X}",
        "relocated_stream_file_offset": f"0x{target_offset:X}",
        "relocated_stream_byte_length": len(stream),
        "relocated_stream_sha256": sha256(stream),
        "encoded_target_byte_length": len(encoded),
        "encoded_target_sha256": sha256(encoded),
        "target_character_count": len(target_text),
        "terminator": "0x0000",
        "relocation_policy": selected["policy"],
        "source_text_emitted": False,
        "general_codepage_confirmed": False,
        "cjk_encoder_confirmed": False,
        "runtime_qa_confirmed": False,
    }
    return bytes(patched), receipt


def verify_target(clean_rom: bytes, target_rom: bytes, receipt: dict[str, object]) -> dict[str, object]:
    """Re-read the relocated stream and verify the bounded target alphabet."""

    selected = profile_metadata(str(receipt.get("profile", "m32")))
    pointer_file_offset = int(selected["caller_pointer_file_offset"])
    original_stream_file_offset = int(selected["original_stream_file_offset"])
    original_stream_byte_length = int(selected["original_stream_byte_length"])
    if sha256(target_rom) != receipt.get("target_rom_sha256"):
        raise ValueError("target ROM hash does not match the build receipt")
    pointer = struct.unpack_from("<I", target_rom, pointer_file_offset)[0]
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
            clean_rom[original_stream_file_offset:original_stream_file_offset + original_stream_byte_length]
            == target_rom[original_stream_file_offset:original_stream_file_offset + original_stream_byte_length]
        ),
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="m32")
    parser.add_argument("--target-text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    clean_rom = args.rom.read_bytes()
    if sha256(clean_rom) != EXPECTED_A9PJ_SHA256:
        raise SystemExit("A9PJ clean-ROM SHA-256 mismatch; refusing target POC")
    target_rom, receipt = build_target(clean_rom, args.target_text, profile=args.profile)
    receipt["verification"] = verify_target(clean_rom, target_rom, receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(target_rom)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "verification"}, sort_keys=True))


if __name__ == "__main__":
    main()
