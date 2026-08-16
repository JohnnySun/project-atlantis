"""Game-agnostic GBA ROM identity inspection and fail-closed verification."""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path
from typing import Any, Mapping


HEADER_MIN_SIZE = 0xBE


class RomIdentityError(ValueError):
    """Raised when a ROM is malformed or does not match its identity contract."""


def header_complement(data: bytes) -> int:
    """Return the GBA header complement for bytes ``0xA0..0xBC``.

    Nintendo's check is ``-(sum(header[0xA0:0xBD]) + 0x19) mod 256``.
    Keeping the formula here avoids the two commonly-confused ``0x19 - sum``
    and ``0x100 - 0x19 - sum`` variants.
    """

    if len(data) < HEADER_MIN_SIZE:
        raise RomIdentityError("ROM is shorter than the complete GBA header")
    return (-sum(data[0xA0:0xBD]) - 0x19) & 0xFF


def _ascii_field(data: bytes, start: int, end: int, *, trim_nul: bool = False) -> str:
    value = data[start:end]
    if trim_nul:
        value = value.rstrip(b"\0")
    return value.decode("ascii", errors="replace")


def inspect_bytes(data: bytes) -> dict[str, Any]:
    """Return copyright-safe identity metadata without exposing ROM bytes."""

    if len(data) < HEADER_MIN_SIZE:
        raise RomIdentityError("ROM is shorter than the complete GBA header")
    calculated = header_complement(data)
    stored = data[0xBD]
    return {
        "size": len(data),
        "crc32": f"{zlib.crc32(data) & 0xFFFFFFFF:08x}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "header": {
            "title": _ascii_field(data, 0xA0, 0xAC, trim_nul=True),
            "game_code": _ascii_field(data, 0xAC, 0xB0),
            "game_code_hex": data[0xAC:0xB0].hex(),
            "maker_code": _ascii_field(data, 0xB0, 0xB2),
            "fixed_value": data[0xB2],
            "main_unit_code": data[0xB3],
            "device_type": data[0xB4],
            "software_version": data[0xBC],
            "stored_complement": f"{stored:02x}",
            "calculated_complement": f"{calculated:02x}",
            "complement_valid": stored == calculated,
        },
    }


def inspect_path(path: Path) -> dict[str, Any]:
    return inspect_bytes(path.read_bytes())


def verify_identity(
    actual: Mapping[str, Any], expected: Mapping[str, Any], *, require_valid_header: bool = True
) -> list[dict[str, str]]:
    """Compare identity metadata and return machine-readable diagnostics.

    Expected keys may be ``size``, ``crc32``, ``sha256``, ``title``,
    ``game_code``, ``maker_code``, or ``software_version``. Unknown keys are
    rejected so a misspelled gate cannot silently pass.
    """

    allowed = {
        "size",
        "crc32",
        "sha256",
        "title",
        "game_code",
        "maker_code",
        "software_version",
    }
    unknown = sorted(set(expected) - allowed)
    if unknown:
        raise RomIdentityError(f"unknown expected identity fields: {', '.join(unknown)}")

    header = actual.get("header")
    if not isinstance(header, Mapping):
        raise RomIdentityError("actual identity is missing header metadata")
    locations: dict[str, object] = {
        "size": actual.get("size"),
        "crc32": actual.get("crc32"),
        "sha256": actual.get("sha256"),
        "title": header.get("title"),
        "game_code": header.get("game_code"),
        "maker_code": header.get("maker_code"),
        "software_version": header.get("software_version"),
    }
    diagnostics: list[dict[str, str]] = []
    if require_valid_header:
        diagnostics.append(
            {
                "check": "header_complement",
                "status": "pass" if header.get("complement_valid") is True else "fail",
                "message": "GBA header complement is valid"
                if header.get("complement_valid") is True
                else "GBA header complement is invalid",
            }
        )
    for key, wanted in expected.items():
        observed = locations[key]
        if key in {"crc32", "sha256"}:
            wanted = str(wanted).lower()
            observed = str(observed).lower()
        matched = observed == wanted
        diagnostics.append(
            {
                "check": key,
                "status": "pass" if matched else "fail",
                "message": f"{key} matches identity contract"
                if matched
                else f"{key} does not match identity contract",
            }
        )
    return diagnostics


def report(path: Path, expected: Mapping[str, Any], *, require_valid_header: bool = True) -> dict[str, Any]:
    actual = inspect_path(path)
    diagnostics = verify_identity(actual, expected, require_valid_header=require_valid_header)
    return {
        "format": "project-atlantis-gba-rom-identity-v1",
        "status": "pass" if all(item["status"] == "pass" for item in diagnostics) else "fail",
        "rom": actual,
        "diagnostics": diagnostics,
    }
