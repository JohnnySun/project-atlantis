#!/usr/bin/env python3
"""Fail-closed equal-length B3TJ record round-trip proof of concept.

This tool is deliberately narrower than a localization builder.  It accepts
one exact strict-record start and a replacement byte payload of exactly the
same length, preserves the record terminator and low control-byte sequence,
then re-extracts the patched in-memory ROM with the reviewed strict parser.
The patched ROM and JSON summary are caller-supplied local outputs and must
remain ignored or under ``/private/tmp``.  No source text or raw bytes are
printed or written to tracked files.

The result proves only equal-length static record mechanics.  It does not
prove the game's live consumer, private codepage, glyph identity, capacity
outside the selected record, pointer rewriting, compression, or runtime QA.
The generic BPS create/apply scripts in ``core/patches`` can be run against
the two ignored ROM files after this tool passes.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import ParsedString, strict_records, verify_b3tj  # noqa: E402


class PocReject(ValueError):
    """Raised when the bounded record contract cannot be proven."""


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def control_signature(payload: bytes) -> tuple[int, ...]:
    """Return low control/newline bytes without retaining text or raw output."""

    return tuple(value for value in payload if 0x01 <= value <= 0x1F)


def patch_equal_length_record(
    rom: bytes, record: ParsedString, replacement: bytes
) -> bytes:
    """Patch one reviewed record payload while preserving its strict boundary."""

    original = rom[record.start : record.end]
    if len(original) != record.raw_length:
        raise PocReject("source record span does not match strict raw_length")
    if len(replacement) != record.raw_length:
        raise PocReject("replacement length differs from strict record raw_length")
    if b"\x00" in replacement:
        raise PocReject("replacement contains an interior NUL")
    if b"\xFF" in replacement:
        raise PocReject("replacement contains rejected 0xFF byte")
    if control_signature(original) != control_signature(replacement):
        raise PocReject("replacement changes low control/newline byte sequence")

    patched = bytearray(rom)
    patched[record.start : record.end] = replacement
    if patched[record.end] != 0:
        raise PocReject("record terminator is not NUL after replacement")
    return bytes(patched)


def _identity(data: bytes) -> dict[str, object]:
    verify_b3tj(data)
    return {
        "size": len(data),
        "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08X}",
        "title_ascii": data[0xA0:0xAC].split(b"\0", 1)[0].decode(
            "ascii", errors="replace"
        ),
        "game_code": data[0xAC:0xB0].decode("ascii", errors="replace"),
    }


def _record_at(records: list[ParsedString], offset: int) -> ParsedString:
    for record in records:
        if record.start == offset:
            return record
    raise PocReject("record offset is not an exact strict record start")


def _payload_hash(data: bytes, record: ParsedString) -> str:
    return hashlib.sha256(data[record.start : record.end]).hexdigest()


def build_poc(
    rom: bytes, record_offset: int, replacement: bytes
) -> tuple[bytes, dict[str, object]]:
    """Build one in-memory bounded patch and audit strict re-extraction."""

    identity = _identity(rom)
    source_records = strict_records(rom)
    source_record = _record_at(source_records, record_offset)
    patched = patch_equal_length_record(rom, source_record, replacement)
    target_records = strict_records(patched)

    source_by_start = {record.start: record for record in source_records}
    target_by_start = {record.start: record for record in target_records}
    if set(source_by_start) != set(target_by_start):
        raise PocReject("strict record start set changed after replacement")
    for start, source in source_by_start.items():
        target = target_by_start[start]
        if target.raw_length != source.raw_length:
            raise PocReject("strict record raw_length changed after replacement")
        if start != record_offset:
            if patched[source.start : source.end] != rom[source.start : source.end]:
                raise PocReject("untouched strict record bytes changed")
        elif control_signature(rom[source.start : source.end]) != control_signature(
            patched[target.start : target.end]
        ):
            raise PocReject("target control/newline sequence changed")

    target_record = target_by_start[record_offset]
    changed_bytes = sum(left != right for left, right in zip(rom, patched))
    target_span = range(source_record.start, source_record.end)
    outside_target_equal = all(
        rom[index] == patched[index] for index in range(len(rom)) if index not in target_span
    )
    if not outside_target_equal or changed_bytes > source_record.raw_length:
        raise PocReject("changed bytes escaped the selected record payload")

    report: dict[str, object] = {
        "mode": "b3tj-bounded-equal-length-record-roundtrip-poc",
        "identity": identity,
        "record": {
            "string_id": f"sjis:0x{record_offset:06X}",
            "file_offset": _hex(record_offset, 6),
            "region": source_record.region,
            "raw_length": source_record.raw_length,
            "source_payload_sha256": _payload_hash(rom, source_record),
            "target_payload_sha256": _payload_hash(patched, target_record),
            "control_sequence_preserved": True,
        },
        "reextract": {
            "source_record_count": len(source_records),
            "target_record_count": len(target_records),
            "target_crc32": f"{binascii.crc32(patched) & 0xFFFFFFFF:08X}",
            "record_start_set_equal": True,
            "target_raw_length_equal": True,
            "untouched_record_bytes_equal": True,
            "outside_target_record_equal": outside_target_equal,
            "changed_bytes": changed_bytes,
            "target_payload_reextract_match": patched[
                target_record.start : target_record.end
            ]
            == replacement,
        },
        "bps": {
            "status": "run_core_bps_create_apply_on_ignored_roms",
            "create": "core/patches/bps_create.rb",
            "apply": "core/patches/bps_apply.rb",
        },
        "classification": {
            "equal_length_static_builder": "confirmed-poc-only",
            "strict_parser_roundtrip": "confirmed-bounded",
            "translation_status": "untranslated",
            "live_text_consumer": "unconfirmed",
            "private_codepage_and_glyph_identity": "unconfirmed",
            "capacity_pointer_rewrite_compression": "unconfirmed",
            "runtime_qa": "unconfirmed",
        },
    }
    return patched, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--record-offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--replacement-hex", required=True)
    parser.add_argument("--patched-rom", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    try:
        replacement = bytes.fromhex(args.replacement_hex)
    except ValueError as exc:
        parser.error(f"replacement-hex is not valid hex: {exc}")
    if not replacement:
        parser.error("replacement-hex must not be empty")
    try:
        if args.rom.resolve() == args.patched_rom.resolve():
            raise PocReject("patched-rom must differ from clean ROM path")
        patched, report = build_poc(
            args.rom.read_bytes(), args.record_offset, replacement
        )
    except (OSError, PocReject, ValueError) as exc:
        parser.error(str(exc))

    args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
    args.patched_rom.write_bytes(patched)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.summary is None:
        print(text, end="")
    else:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(text, encoding="utf-8")
        print(f"wrote {args.summary}")


if __name__ == "__main__":
    main()
