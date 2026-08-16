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

# These are command shapes with a fixed csm3 callsite. The M2.1 report only
# promotes entries that also appear in a bounded window after an accepted
# 0x0308 record. Other words remain opaque; a dispatch-table entry alone is
# not treated as a proven parameter-width contract.
COMMAND_SPECS = {
    0x0001: {
        "handler": "sub_080128BC",
        "parameter_form": "u16,u16,expression_until_0",
        "parser": "u16_u16_expression",
        "evidence": "csm3 asm/code_080123E4.s sub_080128BC reads two u16 then sub_08012578",
    },
    0x0002: {
        "handler": "sub_080131DC",
        "parameter_form": "u16,expression_until_0",
        "parser": "u16_expression",
        "evidence": "csm3 src/script.c sub_080131DC reads one u16 then sub_08012578",
    },
    0x0003: {
        "handler": "sub_08013220",
        "parameter_form": "u16",
        "parser": "u16",
        "evidence": "csm3 src/script.c sub_08013220 reads one aligned stream offset",
    },
    0x0004: {
        "handler": "sub_080129B0",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 asm/code_080123E4.s sub_080129B0 has no stream cursor read",
    },
    0x0005: {
        "handler": "sub_080129EC",
        "parameter_form": "expression_until_0",
        "parser": "expression",
        "evidence": "csm3 asm/code_080123E4.s sub_080129EC calls sub_08012578 once",
    },
    0x0006: {
        "handler": "sub_08012A94",
        "parameter_form": "expression_until_0",
        "parser": "expression",
        "evidence": "csm3 asm/code_080123E4.s sub_08012A94 calls sub_08012578 once",
    },
    0x0007: {
        "handler": "sub_08012B60",
        "parameter_form": "u16",
        "parser": "u16",
        "evidence": "csm3 asm/code_080123E4.s sub_08012B60 reads one u16 offset",
    },
    0x0008: {
        "handler": "sub_08012BA4",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 asm/code_080123E4.s sub_08012BA4 has no stream cursor read",
    },
    0x0009: {
        "handler": "sub_08012BE8",
        "parameter_form": "expression_until_0,u16",
        "parser": "expression_u16",
        "evidence": "csm3 src/script.c sub_08012BE8 calls sub_08012578 then reads one u16",
    },
    0x000A: {
        "handler": "sub_0801324C",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 src/script.c sub_0801324C has no stream cursor read",
    },
    0x000B: {
        "handler": "sub_08013278",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 src/script.c sub_08013278 has no stream cursor read",
    },
    0x000C: {
        "handler": "sub_080132B0",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 src/script.c sub_080132B0 has no stream cursor read",
    },
    0x000D: {
        "handler": "sub_080132B4",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 src/script.c sub_080132B4 has no stream cursor read",
    },
    0x0309: {
        "handler": "sub_0800D36C",
        "parameter_form": "none",
        "parser": "none",
        "evidence": "csm3 asm/code_copy.s sub_0800D36C reads key state and no script cursor",
    },
    0x030A: {
        "handler": "sub_0800D5D0",
        "parameter_form": "expression_until_0,expression_until_0",
        "parser": "expression_expression",
        "evidence": "csm3 asm/code_copy.s sub_0800D5D0 calls sub_08012578 twice",
    },
}

EXPRESSION_SPECS = {
    0x0000: ("terminator", 0),
    0x0001: ("literal_s16", 1),
    0x0002: ("value_slot_u16", 1),
    0x0003: ("value_slot_s16", 1),
    0x0080: ("truth_normalize", 0),
    0x0081: ("bitwise_not", 0),
    0x0082: ("multiply", 0),
    0x0083: ("signed_divide", 0),
    0x0084: ("signed_modulo", 0),
    0x0085: ("add", 0),
    0x0086: ("subtract", 0),
    0x0087: ("less_than", 0),
    0x0088: ("less_or_equal", 0),
    0x0089: ("greater_than", 0),
    0x008A: ("greater_or_equal", 0),
    0x008B: ("equal", 0),
    0x008C: ("not_equal", 0),
    0x008D: ("bitwise_and", 0),
    0x008E: ("bitwise_xor", 0),
    0x008F: ("bitwise_or", 0),
    0x0090: ("logical_and", 0),
    0x0091: ("logical_or", 0),
}


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"u32 read outside input at 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def read_u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"u16 read outside input at 0x{offset:x}")
    return struct.unpack_from("<H", data, offset)[0]


def format_word(value: int) -> str:
    return f"0x{value:04x}"


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


def _public_expression(expression: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "expression",
        "parameter_form": "u16_units_until_0x0000",
        "width_units": len(expression["units"]),
        "terminated": expression["terminated"],
        "units": [format_word(value) for value in expression["units"]],
        "known_ops": expression["known_ops"],
        "opaque_ops": [format_word(value) for value in expression["opaque_ops"]],
    }


def parse_expression(
    decoded_script: bytes,
    offset: int,
    max_units: int = 256,
) -> dict[str, object]:
    """Parse csm3's expression VM without assigning meaning to unknown words."""

    start = offset
    units: list[int] = []
    known_ops: list[dict[str, object]] = []
    opaque_ops: list[int] = []
    terminated = False
    while offset + 2 <= len(decoded_script) and len(units) < max_units:
        opcode = read_u16(decoded_script, offset)
        offset += 2
        units.append(opcode)
        if opcode == TEXT_END_WORD:
            terminated = True
            break
        spec = EXPRESSION_SPECS.get(opcode)
        if spec is None:
            # The reviewed evaluator consumes one word per loop for an unknown
            # value. Preserve it as opaque rather than inventing an argument.
            opaque_ops.append(opcode)
            continue
        name, operand_units = spec
        entry: dict[str, object] = {
            "opcode": format_word(opcode),
            "name": name,
            "operand_units": operand_units,
        }
        if operand_units:
            if offset + 2 * operand_units > len(decoded_script):
                entry["truncated"] = True
                known_ops.append(entry)
                break
            operands = [read_u16(decoded_script, offset + 2 * index) for index in range(operand_units)]
            offset += 2 * operand_units
            entry["operands"] = [format_word(value) for value in operands]
            units.extend(operands)
        known_ops.append(entry)
    return {
        "start_offset": start,
        "end_offset": offset,
        "units": units,
        "known_ops": known_ops,
        "opaque_ops": opaque_ops,
        "terminated": terminated,
        "_raw_bytes": decoded_script[start:offset],
    }


def _make_opaque_token(decoded_script: bytes, start: int, end: int, reason: str) -> dict[str, object]:
    raw = decoded_script[start:end]
    token: dict[str, object] = {
        "kind": "opaque",
        "start_offset": start,
        "end_offset": end,
        "byte_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "reason": reason,
        "_raw_bytes": raw,
    }
    if len(raw) == 2:
        token["word"] = format_word(read_u16(decoded_script, start))
    return token


def _parse_text_record_at(
    decoded_script: bytes,
    offset: int,
) -> tuple[dict[str, object] | None, dict[str, object]]:
    """Parse one marker candidate and return (record, candidate evidence)."""

    if offset + 2 > len(decoded_script) or read_u16(decoded_script, offset) != TEXT_START_WORD:
        raise ValueError("text record parser called at a non-0308 word")
    payload_start = offset + 2
    terminator_offset = payload_start
    while terminator_offset + 2 <= len(decoded_script):
        if read_u16(decoded_script, terminator_offset) == TEXT_END_WORD:
            break
        terminator_offset += 2
    candidate: dict[str, object] = {
        "offset": offset,
        "opcode": format_word(TEXT_START_WORD),
        "status": "rejected",
    }
    if terminator_offset + 2 > len(decoded_script):
        candidate["reason"] = "missing_0x0000_terminator"
        candidate["payload_length"] = len(decoded_script) - payload_start
        candidate["payload_sha256"] = hashlib.sha256(decoded_script[payload_start:]).hexdigest()
        return None, candidate
    payload = decoded_script[payload_start:terminator_offset]
    candidate["payload_length"] = len(payload)
    candidate["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    if not payload:
        candidate["reason"] = "empty_payload"
        return None, candidate
    try:
        source_text = payload.decode("shift_jis")
    except UnicodeDecodeError as exc:
        candidate["reason"] = "strict_shift_jis_decode_failed"
        candidate["decode_error"] = str(exc)
        return None, candidate
    end_offset = terminator_offset + 2
    record: dict[str, object] = {
        "kind": "text_record",
        "decompressed_offset": offset,
        "end_offset": end_offset,
        "source_text": source_text,
        "raw_length": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "record_sha256": hashlib.sha256(decoded_script[offset:end_offset]).hexdigest(),
        "control_tokens": [format_word(TEXT_START_WORD), format_word(TEXT_END_WORD)],
        "control_structure": [
            {
                "kind": "opcode",
                "opcode": format_word(TEXT_START_WORD),
                "width_units": 1,
                "handler": "sub_0800D084",
            },
            {
                "kind": "text_payload",
                "encoding": "shift_jis",
                "byte_length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            {
                "kind": "terminator",
                "opcode": format_word(TEXT_END_WORD),
                "width_units": 1,
            },
        ],
        "_raw_bytes": decoded_script[offset:end_offset],
        "_payload_bytes": payload,
    }
    candidate["status"] = "accepted"
    candidate["end_offset"] = end_offset
    return record, candidate


def _parse_known_control(decoded_script: bytes, offset: int) -> dict[str, object] | None:
    """Parse only commands whose stream shape is supported by csm3 evidence."""

    if offset + 2 > len(decoded_script):
        return None
    opcode = read_u16(decoded_script, offset)
    if opcode == TEXT_START_WORD:
        record, _candidate = _parse_text_record_at(decoded_script, offset)
        if record is None:
            return None
        return {
            "kind": "next_text_record",
            "opcode": format_word(TEXT_START_WORD),
            "decompressed_offset": record["decompressed_offset"],
            "width_units": (int(record["end_offset"]) - offset) // 2,
            "handler": "sub_0800D084",
            "parameter_form": "text_bytes_until_0x0000",
            "_raw_bytes": record["_raw_bytes"],
            "end_offset": record["end_offset"],
        }
    spec = COMMAND_SPECS.get(opcode)
    if spec is None:
        return None
    cursor = offset + 2
    parameters: list[object] = []
    parser = spec["parser"]

    def take_u16() -> bool:
        nonlocal cursor
        if cursor + 2 > len(decoded_script):
            return False
        parameters.append({"kind": "u16", "value": format_word(read_u16(decoded_script, cursor))})
        cursor += 2
        return True

    def take_expression() -> bool:
        nonlocal cursor
        expression = parse_expression(decoded_script, cursor)
        if not expression["terminated"]:
            return False
        parameters.append(_public_expression(expression))
        cursor = int(expression["end_offset"])
        return True

    if parser == "none":
        pass
    elif parser == "u16":
        if not take_u16():
            return None
    elif parser == "expression":
        if not take_expression():
            return None
    elif parser == "u16_expression":
        if not take_u16() or not take_expression():
            return None
    elif parser == "u16_u16_expression":
        if not take_u16() or not take_u16() or not take_expression():
            return None
    elif parser == "expression_u16":
        if not take_expression() or not take_u16():
            return None
    elif parser == "expression_expression":
        if not take_expression() or not take_expression():
            return None
    else:
        return None
    return {
        "kind": "control",
        "opcode": format_word(opcode),
        "handler": spec["handler"],
        "parameter_form": spec["parameter_form"],
        "parameter_units": (cursor - (offset + 2)) // 2,
        "parameters": parameters,
        "evidence": spec["evidence"],
        "start_offset": offset,
        "end_offset": cursor,
        "width_units": (cursor - offset) // 2,
        "_raw_bytes": decoded_script[offset:cursor],
    }


def parse_control_window(
    decoded_script: bytes,
    offset: int,
    max_tokens: int = 8,
) -> list[dict[str, object]]:
    """Summarize a bounded post-record command window; unknowns stay opaque."""

    controls: list[dict[str, object]] = []
    cursor = offset
    for _ in range(max_tokens):
        if cursor + 2 > len(decoded_script):
            break
        parsed = _parse_known_control(decoded_script, cursor)
        if parsed is not None:
            public = {key: value for key, value in parsed.items() if not key.startswith("_")}
            controls.append(public)
            cursor = int(parsed["end_offset"])
            if parsed["kind"] == "next_text_record":
                break
            continue
        opaque = _make_opaque_token(decoded_script, cursor, cursor + 2, "unknown_control_boundary")
        controls.append({key: value for key, value in opaque.items() if not key.startswith("_")})
        break
    return controls


def parse_script_stream(decoded_script: bytes, resource_id: int) -> dict[str, object]:
    """Losslessly tokenize a PSI3 stream while structurally recognizing text."""

    if len(decoded_script) < SCRIPT_HEADER_SIZE or decoded_script[:4] != SCRIPT_MAGIC:
        raise ValueError(f"resource {resource_id} is not a PSI3 script")
    if len(decoded_script) % 2:
        raise ValueError(f"resource {resource_id} has an odd decoded size")
    tokens: list[dict[str, object]] = []
    text_records: list[dict[str, object]] = []
    marker_candidates: list[dict[str, object]] = []
    cursor = SCRIPT_HEADER_SIZE
    opaque_start = cursor
    while cursor + 2 <= len(decoded_script):
        if read_u16(decoded_script, cursor) != TEXT_START_WORD:
            cursor += 2
            continue
        record, candidate = _parse_text_record_at(decoded_script, cursor)
        marker_candidates.append(candidate)
        if record is None:
            cursor += 2
            continue
        if opaque_start < cursor:
            tokens.append(_make_opaque_token(decoded_script, opaque_start, cursor, "between_known_records"))
        record["following_controls"] = parse_control_window(decoded_script, int(record["end_offset"]))
        tokens.append(record)
        text_records.append(record)
        cursor = int(record["end_offset"])
        opaque_start = cursor
    if opaque_start < len(decoded_script):
        tokens.append(_make_opaque_token(decoded_script, opaque_start, len(decoded_script), "stream_tail"))
    return {
        "resource_id": resource_id,
        "stream_offset": SCRIPT_HEADER_SIZE,
        "stream_size": len(decoded_script) - SCRIPT_HEADER_SIZE,
        "tokens": tokens,
        "text_records": text_records,
        "marker_candidates": marker_candidates,
    }


def encode_text_record(record: dict[str, object], source_text: str | None = None) -> bytes:
    """Encode one record at the record layer; no pointer or LZ77 rebuild occurs."""

    if source_text is None:
        payload = record["_payload_bytes"]
    else:
        payload = source_text.encode("shift_jis")
    if not isinstance(payload, bytes):
        raise TypeError("text record payload must be bytes")
    return struct.pack("<H", TEXT_START_WORD) + payload + struct.pack("<H", TEXT_END_WORD)


def encode_script_stream(parsed_stream: dict[str, object]) -> bytes:
    """Re-emit every parsed token, including opaque spans, byte-for-byte."""

    return b"".join(token["_raw_bytes"] for token in parsed_stream["tokens"])


def parse_text_records(decoded_script: bytes, resource_id: int) -> Iterator[dict[str, object]]:
    """Yield accepted text records from the lossless PSI3 stream parser."""

    parsed_stream = parse_script_stream(decoded_script, resource_id)
    yield from parsed_stream["text_records"]


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
        parsed_stream = parse_script_stream(decoded, resource_id)
        encoded_stream = encode_script_stream(parsed_stream)
        original_stream = decoded[SCRIPT_HEADER_SIZE:]
        if encoded_stream != original_stream:
            raise ValueError(f"resource {resource_id}: lossless stream encoder mismatch")
        stream_sha256 = hashlib.sha256(original_stream).hexdigest()
        rejected_marker_count = sum(
            candidate["status"] != "accepted" for candidate in parsed_stream["marker_candidates"]
        )
        for parsed in parsed_stream["text_records"]:
            if len(records) >= max_records:
                return records
            decompressed_offset = int(parsed["decompressed_offset"])
            source_reencoded = encode_text_record(parsed, source_text=parsed["source_text"])
            if source_reencoded != parsed["_raw_bytes"]:
                raise ValueError(
                    f"resource {resource_id} record 0x{decompressed_offset:x}: "
                    "Shift-JIS source re-encode mismatch"
                )
            record = {
                "string_id": f"b3cj:t2:{resource_id:03d}:0x{decompressed_offset:04x}",
                "locale": "ja-JP",
                "source_text": parsed["source_text"],
                "raw_length": parsed["raw_length"],
                "raw_sha256": parsed["raw_sha256"],
                "record_sha256": parsed["record_sha256"],
                "control_tokens": parsed["control_tokens"],
                "control_structure": parsed["control_structure"],
                "following_controls": parsed["following_controls"],
                "length_contract": {
                    "same_byte_length": "in_place_record_stream_confirmed",
                    "shorter_with_zero_padding": "blocked_zero_is_record_terminator",
                    "longer": "resource_rebuild_required",
                    "terminator": "0x0000_must_remain_after_payload",
                    "evidence": [
                        "csm3 sub_0800D084 receives inline stream pointer and consumes u16 until zero",
                        "csm3 sub_080131DC/sub_08013220 use decompressed stream offsets for control flow",
                        "pointer/LZ77 container rebuild is outside this M2.1 proof layer",
                    ],
                },
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
                    "stream_size": len(original_stream),
                    "stream_sha256": stream_sha256,
                    "stream_token_count": len(parsed_stream["tokens"]),
                    "stream_opaque_token_count": sum(
                        token["kind"] == "opaque" for token in parsed_stream["tokens"]
                    ),
                    "marker_candidate_count": len(parsed_stream["marker_candidates"]),
                    "rejected_marker_candidate_count": rejected_marker_count,
                    "record_stream_roundtrip": "byte_identical",
                    "source_reencode": "byte_identical",
                    "consumer_evidence": CONSUMER_EVIDENCE,
                },
            }
            records.append(record)
    # The table is deterministic; a final sort makes output stable even if a
    # caller supplies resource IDs in a different order in a future review.
    records.sort(key=lambda item: str(item["string_id"]))
    return records


def verify_roundtrip(data: bytes, resource_ids: Sequence[int]) -> dict[str, object]:
    """Verify decoded PSI3 stream identity without rebuilding LZ77 or pointers."""

    resource_summaries: list[dict[str, object]] = []
    original_aggregate = hashlib.sha256()
    encoded_aggregate = hashlib.sha256()
    record_aggregate = hashlib.sha256()
    stream_bytes = 0
    record_count = 0
    source_reencode_count = 0
    rejected_marker_count = 0
    opaque_token_count = 0
    for resource_id in resource_ids:
        resolved = resolve_script_resource(data, resource_id)
        decoded, _compressed_size = decode_lz77(data, resolved["payload_file_offset"])
        parsed_stream = parse_script_stream(decoded, resource_id)
        original_stream = decoded[SCRIPT_HEADER_SIZE:]
        encoded_stream = encode_script_stream(parsed_stream)
        rebuilt_decoded = decoded[:SCRIPT_HEADER_SIZE] + encoded_stream
        if rebuilt_decoded != decoded:
            raise ValueError(f"resource {resource_id}: decoded stream is not byte-identical")
        original_hash = hashlib.sha256(original_stream).hexdigest()
        encoded_hash = hashlib.sha256(encoded_stream).hexdigest()
        original_aggregate.update(struct.pack("<I", resource_id))
        original_aggregate.update(original_stream)
        encoded_aggregate.update(struct.pack("<I", resource_id))
        encoded_aggregate.update(encoded_stream)
        resource_record_count = len(parsed_stream["text_records"])
        resource_rejected = sum(
            candidate["status"] != "accepted" for candidate in parsed_stream["marker_candidates"]
        )
        resource_opaque = sum(token["kind"] == "opaque" for token in parsed_stream["tokens"])
        for record in parsed_stream["text_records"]:
            record_count += 1
            source_payload = encode_text_record(record, source_text=record["source_text"])[2:-2]
            if source_payload != record["_payload_bytes"]:
                raise ValueError(
                    f"resource {resource_id} record 0x{record['decompressed_offset']:x}: "
                    "source re-encode is not byte-identical"
                )
            source_reencode_count += 1
            record_aggregate.update(
                f"{resource_id}:{record['decompressed_offset']}:{record['record_sha256']}\n".encode()
            )
        stream_bytes += len(original_stream)
        rejected_marker_count += resource_rejected
        opaque_token_count += resource_opaque
        resource_summaries.append(
            {
                "resource_id": resource_id,
                "stream_size": len(original_stream),
                "record_count": resource_record_count,
                "marker_candidate_count": len(parsed_stream["marker_candidates"]),
                "rejected_marker_candidate_count": resource_rejected,
                "opaque_token_count": resource_opaque,
                "original_stream_sha256": original_hash,
                "encoded_stream_sha256": encoded_hash,
                "byte_identical": original_stream == encoded_stream,
            }
        )
    return {
        "layer": "decoded_psi3_stream_only",
        "resources": len(resource_summaries),
        "resource_ids": list(resource_ids),
        "records": record_count,
        "stream_bytes": stream_bytes,
        "source_reencode_records": source_reencode_count,
        "rejected_marker_candidates": rejected_marker_count,
        "opaque_tokens": opaque_token_count,
        "original_aggregate_sha256": original_aggregate.hexdigest(),
        "encoded_aggregate_sha256": encoded_aggregate.hexdigest(),
        "record_aggregate_sha256": record_aggregate.hexdigest(),
        "byte_identical": original_aggregate.digest() == encoded_aggregate.digest(),
        "container_rebuild": "not_attempted",
        "resource_summaries": resource_summaries,
    }


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
    parser.add_argument(
        "--verify-roundtrip",
        action="store_true",
        help="verify decoded PSI3 stream and Shift-JIS record no-op round-trip",
    )
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
        roundtrip = None
        if args.verify_roundtrip:
            record_resource_ids = sorted(
                {int(record["provenance"]["resource_id"]) for record in records}
            )
            roundtrip = verify_roundtrip(data, record_resource_ids)
    except (OSError, ValueError) as exc:
        print(f"extract_static.py: {exc}", file=sys.stderr)
        return 2
    print(
        f"B3CJ_STATIC_EXTRACT_OK records={count} resources="
        f"{args.first_resource}..{args.last_resource} output={args.output}"
    )
    if roundtrip is not None:
        print(
            "B3CJ_ROUNDTRIP_OK "
            f"resources={roundtrip['resources']} records={roundtrip['records']} "
            f"stream_bytes={roundtrip['stream_bytes']} "
            f"rejected_markers={roundtrip['rejected_marker_candidates']} "
            f"opaque_tokens={roundtrip['opaque_tokens']} "
            f"original_sha256={roundtrip['original_aggregate_sha256']} "
            f"encoded_sha256={roundtrip['encoded_aggregate_sha256']} "
            f"record_sha256={roundtrip['record_aggregate_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
