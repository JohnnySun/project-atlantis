#!/usr/bin/env python3
"""Static fail-closed POC for relocating one B3CJ type-2 resource.

This tool does not change text.  It proves only that a reviewed type-2
directory entry can be redirected to an explicitly zero-filled, aligned ROM
region, with the original compressed payload copied there and the pointer/span
updated.  It rejects non-zero/free-space uncertainty, pointer references into
the destination, table/resource overlap, and capacity overflow.  The output
ROM and summary are caller-supplied ignored artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTRACT_PATH = GAME_ROOT / "tools" / "extract_static.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXTRACT = _load_module("b3cj_extract_for_relocation", EXTRACT_PATH)

EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
DEFAULT_RESOURCE_ID = 24
DEFAULT_DESTINATION = 0x1FBB1FC
DEFAULT_SPAN_UNITS = 0x57


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _rom_identity(data: bytes) -> dict[str, Any]:
    identity = EXTRACT.inspect_rom(data)
    _require(identity["digests"]["sha256"] == EXPECTED_ROM_SHA256, "clean ROM SHA-256 mismatch")
    _require(not EXTRACT.validate_rom_identity(identity), "clean ROM B3CJ identity mismatch")
    return identity


def _pointer_reference_count(data: bytes, start: int, end: int) -> int:
    count = 0
    for offset in range(0, len(data) - 3, 4):
        word = struct.unpack_from("<I", data, offset)[0]
        if 0x08000000 + start <= word < 0x08000000 + end:
            count += 1
    return count


def _resource_ranges(data: bytes) -> list[tuple[int, int]]:
    ranges = [(EXTRACT.SCRIPT_TABLE_FILE_OFFSET, EXTRACT.SCRIPT_TABLE_FILE_OFFSET + EXTRACT.SCRIPT_TABLE_SIZE)]
    for resource_id in range(EXTRACT.SCRIPT_RESOURCE_COUNT):
        resolved = EXTRACT.resolve_script_resource(data, resource_id)
        if int(resolved["span_units"]) == 0:
            continue
        start = int(resolved["payload_file_offset"])
        end = start + int(resolved["span_units"]) * EXTRACT.SCRIPT_TABLE_POINTER_SCALE
        ranges.append((start, end))
    return ranges


def _stable_record_digest(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(records, key=lambda item: str(item["string_id"])):
        digest.update(str(row["string_id"]).encode("ascii"))
        digest.update(str(row["raw_sha256"]).encode("ascii"))
        digest.update(str(row["record_sha256"]).encode("ascii"))
    return digest.hexdigest()


def validate_destination(data: bytes, destination: int, span_bytes: int) -> dict[str, object]:
    _require((destination - EXTRACT.SCRIPT_TABLE_FILE_OFFSET) % EXTRACT.SCRIPT_TABLE_POINTER_SCALE == 0, "destination is not aligned to the type-2 table base")
    _require(destination >= 0 and destination + span_bytes <= len(data), "destination is outside ROM")
    _require(destination >= EXTRACT.SCRIPT_TABLE_FILE_OFFSET + EXTRACT.SCRIPT_TABLE_SIZE, "destination overlaps script directory")
    for start, end in _resource_ranges(data):
        _require(destination + span_bytes <= start or destination >= end, f"destination overlaps known resource/table range 0x{start:x}..0x{end:x}")
    region = data[destination : destination + span_bytes]
    _require(region == bytes(span_bytes), "destination is not an explicitly zero-filled region")
    pointer_refs = _pointer_reference_count(data, destination, destination + span_bytes)
    _require(pointer_refs == 0, f"destination has {pointer_refs} aligned ROM pointer reference(s)")
    return {"destination_file_offset": f"0x{destination:x}", "span_bytes": span_bytes, "zero_filled": True, "aligned_pointer_references": pointer_refs}


def relocate(data: bytes, resource_id: int = DEFAULT_RESOURCE_ID, destination: int = DEFAULT_DESTINATION, span_units: int = DEFAULT_SPAN_UNITS) -> tuple[bytes, dict[str, object]]:
    _rom_identity(data)
    _require(0 <= resource_id < EXTRACT.SCRIPT_RESOURCE_COUNT, "resource id is outside reviewed table")
    _require(span_units > 0, "destination span must be positive")
    resolved = EXTRACT.resolve_script_resource(data, resource_id)
    decoded, compressed_size = EXTRACT.decode_lz77(data, int(resolved["payload_file_offset"]))
    span_bytes = span_units * EXTRACT.SCRIPT_TABLE_POINTER_SCALE
    _require(compressed_size <= span_bytes, f"compressed payload {compressed_size} exceeds destination span {span_bytes}")
    destination_report = validate_destination(data, destination, span_bytes)
    table_offset = int(resolved["directory_file_offset"])
    relative_bytes = destination - EXTRACT.SCRIPT_TABLE_FILE_OFFSET
    _require(relative_bytes % EXTRACT.SCRIPT_TABLE_POINTER_SCALE == 0, "destination relative pointer is not aligned")
    relative_units = relative_bytes // EXTRACT.SCRIPT_TABLE_POINTER_SCALE
    patched = bytearray(data)
    struct.pack_into("<I", patched, table_offset, relative_units)
    struct.pack_into("<I", patched, table_offset + 4, span_units)
    compressed = data[int(resolved["payload_file_offset"]) : int(resolved["payload_file_offset"]) + compressed_size]
    patched[destination : destination + span_bytes] = compressed + bytes(span_bytes - compressed_size)
    final = bytes(patched)
    relocated = EXTRACT.resolve_script_resource(final, resource_id)
    _require(int(relocated["payload_file_offset"]) == destination and int(relocated["span_units"]) == span_units, "directory redirect did not persist")
    relocated_decoded, relocated_compressed_size = EXTRACT.decode_lz77(final, destination)
    _require(relocated_decoded == decoded and relocated_compressed_size == compressed_size, "relocated resource decode is not byte-identical")

    resource_ids = sorted({int(row["provenance"]["resource_id"]) for row in EXTRACT.extract_records(data) if isinstance(row.get("provenance"), dict)})
    before_records = EXTRACT.extract_records(data, resource_ids=resource_ids)
    after_records = EXTRACT.extract_records(final, resource_ids=resource_ids)
    _require(len(before_records) == 361 and len(after_records) == 361, "relocation did not preserve bounded 361-record extraction")
    before_identity = [(row["string_id"], row["raw_sha256"], row["record_sha256"]) for row in before_records]
    after_identity = [(row["string_id"], row["raw_sha256"], row["record_sha256"]) for row in after_records]
    _require(before_identity == after_identity, "relocation changed extracted record identity")
    before_roundtrip = EXTRACT.verify_roundtrip(data, resource_ids)
    after_roundtrip = EXTRACT.verify_roundtrip(final, resource_ids)
    _require(after_roundtrip["byte_identical"] and after_roundtrip["record_aggregate_sha256"] == before_roundtrip["record_aggregate_sha256"], "relocated round-trip receipt changed")
    summary: dict[str, object] = {
        "poc_version": "m5.1-static-pointer-relocation-v1",
        "evidence_level": "static-directory-redirect-and-reextract-only",
        "resource_id": resource_id,
        "source": {"payload_file_offset": f"0x{int(resolved['payload_file_offset']):x}", "relative_units": f"0x{int(resolved['relative_units']):x}", "span_units": int(resolved["span_units"]), "compressed_size": compressed_size, "decoded_size": len(decoded)},
        "destination": {**destination_report, "relative_units": f"0x{relative_units:x}", "span_units": span_units},
        "directory_file_offset": f"0x{table_offset:x}",
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "clean_rom_sha256": EXPECTED_ROM_SHA256,
        "relocated_rom_sha256": sha256_bytes(final),
        "records": {"before": len(before_records), "after": len(after_records), "stable_record_digest": _stable_record_digest(after_records), "byte_identity": True},
        "roundtrip": {"before_record_aggregate_sha256": before_roundtrip["record_aggregate_sha256"], "after_record_aggregate_sha256": after_roundtrip["record_aggregate_sha256"], "decoded_stream_byte_identical": True},
        "boundary": "No text translation, no pointer aliases, no runtime QA, and no release patch claim.",
    }
    return final, summary


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--resource-id", type=int, default=DEFAULT_RESOURCE_ID)
    parser.add_argument("--destination", type=lambda value: int(value, 0), default=DEFAULT_DESTINATION)
    parser.add_argument("--span-units", type=lambda value: int(value, 0), default=DEFAULT_SPAN_UNITS)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary-output", type=pathlib.Path, required=True)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        final, summary = relocate(args.rom.read_bytes(), args.resource_id, args.destination, args.span_units)
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(final)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_RELOCATION_POC_OK resource={args.resource_id} records={summary['records']['after']} destination={summary['destination']['destination_file_offset']}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"relocate_resource_poc.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
