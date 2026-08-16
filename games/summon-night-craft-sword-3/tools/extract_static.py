#!/usr/bin/env python3
"""Bounded extraction of the csm3-identified B3CJ script text records.

The extractor is deliberately tied to the verified Japanese B3CJ ROM.  It
uses only the type-2 resource table and callsites reviewed in the fixed csm3
checkout; it does not scan arbitrary ROM bytes or assume another game's
format.  The output contains the Japanese source text, so callers must write
it to the ignored ``research/*-decoded.jsonl`` boundary.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import pathlib
import struct
import sys
from typing import Iterable, Iterator, Sequence


EXPECTED_GAME_CODE = "B3CJ"
EXPECTED_FILE_SIZE = 0x02000000
EXPECTED_CRC32 = "12afae5d"
EXPECTED_SHA1 = "3f5253fcf57e07ce52472bd29a61d16b98a12376"
EXPECTED_HEADER_CHECKSUM = 0x6B

# csm3: gUnk_09718FFC, type 2, data/data1.s @ 0x1718FFC, 0x284 bytes.
SCRIPT_TABLE_FILE_OFFSET = 0x1718FFC
SCRIPT_TABLE_SIZE = 0x284
SCRIPT_TABLE_POINTER_SCALE = 16
SCRIPT_HEADER_SIZE = 0x10
SCRIPT_MAGIC = b"PSI3"
TEXT_START_WORD = 0x0308
TEXT_END_WORD = 0x0000
MAX_DECODED_SIZE = 0x40000
MAX_RECORDS = 8192
SCRIPT_RESOURCE_COUNT = (SCRIPT_TABLE_SIZE // 4 - 2) // 2

CONSUMER_EVIDENCE = {
    "pointer_resolver": "csm3 sub_08001D3C at 0x08001D3C",
    "decompressor_callsite": "csm3 sub_08012D30 at 0x08012D30 -> LZ77UnCompWram",
    "stream_consumer": "csm3 sub_08012E14 at 0x08012E14 reads u16 from buffer+0x10",
}


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 read outside input at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def decode_lz77(data: bytes, offset: int, max_decoded_size: int = MAX_DECODED_SIZE) -> tuple[bytes, int]:
    """Decode one standard GBA LZ77 blob and return (output, consumed_size)."""

    if offset < 0 or offset + 4 > len(data) or data[offset] != 0x10:
        raise ValueError(f"missing GBA LZ77 header at 0x{offset:x}")
    decoded_size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if not 0 < decoded_size <= max_decoded_size:
        raise ValueError(f"invalid LZ77 expanded size 0x{decoded_size:x} at 0x{offset:x}")

    source = offset + 4
    output = bytearray()
    while len(output) < decoded_size:
        if source >= len(data):
            raise ValueError(f"truncated LZ77 flags at 0x{source:x}")
        flags = data[source]
        source += 1
        for bit in range(7, -1, -1):
            if len(output) >= decoded_size:
                break
            if flags & (1 << bit):
                if source + 2 > len(data):
                    raise ValueError(f"truncated LZ77 back-reference at 0x{source:x}")
                first = data[source]
                second = data[source + 1]
                source += 2
                length = (first >> 4) + 3
                distance = ((first & 0x0F) << 8) | second
                if distance >= len(output):
                    raise ValueError(
                        f"invalid LZ77 distance {distance + 1} at output 0x{len(output):x}"
                    )
                for _ in range(length):
                    output.append(output[-distance - 1])
                    if len(output) >= decoded_size:
                        break
            else:
                if source >= len(data):
                    raise ValueError(f"truncated LZ77 literal at 0x{source:x}")
                output.append(data[source])
                source += 1
    return bytes(output), source - offset


def resolve_script_resource(
    data: bytes,
    resource_id: int,
    table_file_offset: int = SCRIPT_TABLE_FILE_OFFSET,
    table_size: int = SCRIPT_TABLE_SIZE,
) -> dict[str, int]:
    """Resolve csm3's type-2 directory entry without following arbitrary data."""

    resource_count = (table_size // 4 - 2) // 2
    if not 0 <= resource_id < resource_count:
        raise ValueError(f"script resource id {resource_id} outside 0..{resource_count - 1}")
    if table_file_offset < 0 or table_file_offset + table_size > len(data):
        raise ValueError("script resource table is outside the input ROM")

    directory_file_offset = table_file_offset + 4 * (resource_id * 2 + 2)
    relative_units = read_u32(data, directory_file_offset)
    span_units = read_u32(data, directory_file_offset + 4)
    payload_file_offset = table_file_offset + relative_units * SCRIPT_TABLE_POINTER_SCALE
    if payload_file_offset < 0 or payload_file_offset + 4 > len(data):
        raise ValueError(f"script resource {resource_id} points outside the input ROM")
    return {
        "directory_file_offset": directory_file_offset,
        "relative_units": relative_units,
        "span_units": span_units,
        "payload_file_offset": payload_file_offset,
    }


def parse_text_records(decoded_script: bytes, resource_id: int) -> Iterator[dict[str, object]]:
    """Yield strict ``0x0308 <Shift-JIS bytes> 0x0000`` records from PSI3 data."""

    if len(decoded_script) < SCRIPT_HEADER_SIZE or decoded_script[:4] != SCRIPT_MAGIC:
        raise ValueError(f"resource {resource_id} is not a PSI3 script")
    if len(decoded_script) % 2:
        raise ValueError(f"resource {resource_id} has an odd decoded size")

    words = struct.unpack_from(f"<{(len(decoded_script) - SCRIPT_HEADER_SIZE) // 2}H", decoded_script, SCRIPT_HEADER_SIZE)
    for index, word in enumerate(words):
        if word != TEXT_START_WORD:
            continue
        terminator_index = index + 1
        while terminator_index < len(words) and words[terminator_index] != TEXT_END_WORD:
            terminator_index += 1
        if terminator_index >= len(words):
            continue
        raw_start = SCRIPT_HEADER_SIZE + 2 * (index + 1)
        raw_end = SCRIPT_HEADER_SIZE + 2 * terminator_index
        raw = decoded_script[raw_start:raw_end]
        if not raw:
            continue
        try:
            source_text = raw.decode("shift_jis")
        except UnicodeDecodeError:
            # A coincidental 0x0308 in non-text script data is not promoted.
            continue
        yield {
            "decompressed_offset": SCRIPT_HEADER_SIZE + 2 * index,
            "source_text": source_text,
            "raw_length": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "control_tokens": [f"0x{TEXT_START_WORD:04x}", f"0x{TEXT_END_WORD:04x}"],
        }


def inspect_rom(data: bytes) -> dict[str, object]:
    if len(data) < 0xBE:
        raise ValueError("ROM is too short to contain a GBA header")
    stored_checksum = data[0xBD]
    calculated_checksum = (0x100 - 0x19 - sum(data[0xA0:0xBD])) & 0xFF
    digests = {
        "crc32": f"{binascii.crc32(data) & 0xFFFFFFFF:08x}",
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return {
        "file_size": len(data),
        "game_code": data[0xAC:0xB0].decode("ascii", "replace"),
        "stored_header_checksum": stored_checksum,
        "calculated_header_checksum": calculated_checksum,
        "digests": digests,
    }


def validate_rom_identity(metadata: dict[str, object]) -> list[str]:
    digests = metadata["digests"]
    assert isinstance(digests, dict)
    mismatches: list[str] = []
    if metadata["file_size"] != EXPECTED_FILE_SIZE:
        mismatches.append("file_size")
    if metadata["game_code"] != EXPECTED_GAME_CODE:
        mismatches.append("game_code")
    if metadata["stored_header_checksum"] != EXPECTED_HEADER_CHECKSUM:
        mismatches.append("stored_header_checksum")
    if metadata["calculated_header_checksum"] != EXPECTED_HEADER_CHECKSUM:
        mismatches.append("calculated_header_checksum")
    if digests["crc32"] != EXPECTED_CRC32:
        mismatches.append("crc32")
    if digests["sha1"] != EXPECTED_SHA1:
        mismatches.append("sha1")
    return mismatches


def extract_records(
    data: bytes,
    resource_ids: Sequence[int] | None = None,
    max_records: int = MAX_RECORDS,
) -> list[dict[str, object]]:
    """Extract a bounded source table from the csm3 type-2 script resources."""

    if max_records <= 0:
        raise ValueError("max_records must be positive")
    selected_ids = list(range(SCRIPT_RESOURCE_COUNT)) if resource_ids is None else list(resource_ids)
    records: list[dict[str, object]] = []
    for resource_id in selected_ids:
        resolved = resolve_script_resource(data, resource_id)
        payload_offset = resolved["payload_file_offset"]
        try:
            decoded, compressed_size = decode_lz77(data, payload_offset)
        except ValueError as exc:
            raise ValueError(f"resource {resource_id}: {exc}") from exc
        if len(decoded) < SCRIPT_HEADER_SIZE or decoded[:4] != SCRIPT_MAGIC:
            raise ValueError(f"resource {resource_id}: decoded payload is not PSI3")
        compressed_raw = data[payload_offset : payload_offset + compressed_size]
        for parsed in parse_text_records(decoded, resource_id):
            if len(records) >= max_records:
                return records
            decompressed_offset = int(parsed["decompressed_offset"])
            record = {
                "string_id": f"b3cj:t2:{resource_id:03d}:0x{decompressed_offset:04x}",
                "locale": "ja-JP",
                "source_text": parsed["source_text"],
                "raw_length": parsed["raw_length"],
                "raw_sha256": parsed["raw_sha256"],
                "control_tokens": parsed["control_tokens"],
                "provenance": {
                    "resource_type": 2,
                    "resource_id": resource_id,
                    "directory_file_offset": f"0x{resolved['directory_file_offset']:08x}",
                    "pointer_relative_units": f"0x{resolved['relative_units']:x}",
                    "pointer_scale_bytes": SCRIPT_TABLE_POINTER_SCALE,
                    "payload_file_offset": f"0x{payload_offset:08x}",
                    "payload_cpu_address": f"0x{0x08000000 + payload_offset:08x}",
                    "compressed_size": compressed_size,
                    "compressed_sha256": hashlib.sha256(compressed_raw).hexdigest(),
                    "decompressed_size": len(decoded),
                    "decompressed_offset": f"0x{decompressed_offset:04x}",
                    "script_data_base": f"0x{SCRIPT_HEADER_SIZE:02x}",
                    "script_magic": SCRIPT_MAGIC.decode("ascii"),
                    "consumer_evidence": CONSUMER_EVIDENCE,
                },
            }
            records.append(record)
    # The table is deterministic; a final sort makes output stable even if a
    # caller supplies resource IDs in a different order in a future review.
    records.sort(key=lambda item: str(item["string_id"]))
    return records


def write_jsonl(records: Iterable[dict[str, object]], output: pathlib.Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="verified local Japanese B3CJ ROM")
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        required=True,
        help="ignored JSONL destination, normally research/*-decoded.jsonl",
    )
    parser.add_argument("--first-resource", type=int, default=0)
    parser.add_argument("--last-resource", type=int, default=SCRIPT_RESOURCE_COUNT - 1)
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        data = args.rom.read_bytes()
        metadata = inspect_rom(data)
        mismatches = validate_rom_identity(metadata)
        if mismatches:
            print("B3CJ identity mismatch: " + ", ".join(mismatches), file=sys.stderr)
            return 1
        if not 0 <= args.first_resource <= args.last_resource < SCRIPT_RESOURCE_COUNT:
            raise ValueError("resource range must stay within the fixed type-2 table")
        records = extract_records(
            data,
            resource_ids=range(args.first_resource, args.last_resource + 1),
            max_records=args.max_records,
        )
        count = write_jsonl(records, args.output)
    except (OSError, ValueError) as exc:
        print(f"extract_static.py: {exc}", file=sys.stderr)
        return 2
    print(
        f"B3CJ_STATIC_EXTRACT_OK records={count} resources="
        f"{args.first_resource}..{args.last_resource} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
