#!/usr/bin/env python3
"""Rebuild every non-zero B3CJ type-2 PSI3 payload as a semantic no-op.

This is a release-gate coverage check, not a translation builder.  It walks
the fixed type-2 directory, classifies zero-span aliases, parses and
re-encodes every non-zero PSI3 stream, recompresses each unique payload, and
keeps the result inside its existing pointer span.  Reports contain hashes,
offsets, counters, and control-shape metadata only; ROMs and complete source
tables belong under the ignored work boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
from collections import defaultdict
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REBUILD_PATH = GAME_ROOT / "tools" / "rebuild_container.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module("b3cj_rebuild_container_for_full_audit", REBUILD_PATH)
EXTRACT = BASE.EXTRACT
LZ_ENCODER = BASE.LZ_ENCODER

EXPECTED_RESOURCE_COUNT = 79
EXPECTED_NONZERO_RESOURCE_IDS = (
    0, 1, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    24, 25, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
    46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
    63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78,
)
EXPECTED_ZERO_SPAN_RESOURCE_IDS = (2, 3, 4, 5, 9, 10, 26, 27, 28, 29, 30)
ALL_RESOURCE_IDS = tuple(range(EXPECTED_RESOURCE_COUNT))
EXPECTED_LOGICAL_RECORDS = 361
EXPECTED_UNIQUE_RECORDS = 235
POINTER_SCALE = EXTRACT.SCRIPT_TABLE_POINTER_SCALE


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _directory_entries(data: bytes) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    for resource_id in ALL_RESOURCE_IDS:
        resolved = EXTRACT.resolve_script_resource(data, resource_id)
        entries.append(
            {
                "resource_id": resource_id,
                "directory_file_offset": int(resolved["directory_file_offset"]),
                "relative_units": int(resolved["relative_units"]),
                "span_units": int(resolved["span_units"]),
                "span_bytes": int(resolved["span_units"]) * POINTER_SCALE,
                "payload_file_offset": int(resolved["payload_file_offset"]),
            }
        )
    return entries


def _group_entries(entries: list[dict[str, int]]) -> list[dict[str, object]]:
    grouped: dict[int, list[dict[str, int]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["payload_file_offset"]].append(entry)

    groups: list[dict[str, object]] = []
    for payload_offset, members in sorted(grouped.items()):
        positive = [entry for entry in members if entry["span_units"] > 0]
        if not positive:
            raise ValueError(f"zero-span-only pointer group at 0x{payload_offset:x}")
        span_units = {entry["span_units"] for entry in positive}
        if len(span_units) != 1:
            raise ValueError(f"positive alias span mismatch at 0x{payload_offset:x}")
        owner = min(entry["resource_id"] for entry in positive)
        groups.append(
            {
                "payload_file_offset": payload_offset,
                "span_units": next(iter(span_units)),
                "span_bytes": next(iter(span_units)) * POINTER_SCALE,
                "resource_ids": [entry["resource_id"] for entry in members],
                "positive_span_resource_ids": [entry["resource_id"] for entry in positive],
                "zero_span_alias_resource_ids": [
                    entry["resource_id"] for entry in members if entry["span_units"] == 0
                ],
                "owner_resource_id": owner,
            }
        )

    intervals = sorted(
        (
            int(group["payload_file_offset"]),
            int(group["payload_file_offset"]) + int(group["span_bytes"]),
            int(group["owner_resource_id"]),
        )
        for group in groups
    )
    overlaps = [
        (left, right)
        for left, right in zip(intervals, intervals[1:])
        if left[1] > right[0]
    ]
    if overlaps:
        raise ValueError(f"positive payload spans overlap: {overlaps}")
    return groups


def _record_identity(records: list[dict[str, object]]) -> list[tuple[str, str, str]]:
    return [
        (str(record["string_id"]), str(record["raw_sha256"]), str(record["record_sha256"]))
        for record in sorted(records, key=lambda item: str(item["string_id"]))
    ]


def rebuild(data: bytes) -> tuple[bytes, dict[str, object]]:
    """Return the all-payload semantic no-op rebuild and its receipt."""

    metadata = BASE._validate_clean_rom(data)
    entries = _directory_entries(data)
    _require(len(entries) == EXPECTED_RESOURCE_COUNT, "type-2 resource count drifted")
    nonzero_ids = tuple(entry["resource_id"] for entry in entries if entry["span_units"] > 0)
    zero_ids = tuple(entry["resource_id"] for entry in entries if entry["span_units"] == 0)
    _require(nonzero_ids == EXPECTED_NONZERO_RESOURCE_IDS, "non-zero type-2 resource IDs drifted")
    _require(zero_ids == EXPECTED_ZERO_SPAN_RESOURCE_IDS, "zero-span type-2 resource IDs drifted")

    groups = _group_entries(entries)
    _require(len(groups) == len(EXPECTED_NONZERO_RESOURCE_IDS), "unique payload group count drifted")
    before_records = EXTRACT.extract_records(data, resource_ids=ALL_RESOURCE_IDS)
    _require(len(before_records) == EXPECTED_LOGICAL_RECORDS, "logical record count drifted")
    unique_records = EXTRACT.extract_records(data, resource_ids=EXPECTED_NONZERO_RESOURCE_IDS)
    _require(len(unique_records) == EXPECTED_UNIQUE_RECORDS, "unique record count drifted")
    table_start = EXTRACT.SCRIPT_TABLE_FILE_OFFSET
    table_end = table_start + EXTRACT.SCRIPT_TABLE_SIZE
    table_before = data[table_start:table_end]

    patched = bytearray(data)
    reports: list[dict[str, object]] = []
    allowed_ranges: list[tuple[int, int]] = []
    for group in groups:
        payload_offset = int(group["payload_file_offset"])
        span_bytes = int(group["span_bytes"])
        owner_resource_id = int(group["owner_resource_id"])
        decoded, original_compressed_size = EXTRACT.decode_lz77(data, payload_offset)
        parsed = EXTRACT.parse_script_stream(decoded, owner_resource_id)
        encoded_stream = EXTRACT.encode_script_stream(parsed)
        rebuilt_decoded = decoded[: EXTRACT.SCRIPT_HEADER_SIZE] + encoded_stream
        _require(rebuilt_decoded == decoded, f"resource {owner_resource_id} PSI3 stream is not lossless")
        compressed = LZ_ENCODER.lz77_compress(rebuilt_decoded)
        _require(
            len(compressed) <= span_bytes,
            f"resource group 0x{payload_offset:x} compressed output exceeds span {span_bytes}",
        )
        end = payload_offset + span_bytes
        _require(end <= len(data), f"resource group 0x{payload_offset:x} span is outside ROM")
        patched[payload_offset:end] = compressed + bytes(span_bytes - len(compressed))
        allowed_ranges.append((payload_offset, end))
        reports.append(
            {
                "owner_resource_id": owner_resource_id,
                "resource_ids": list(group["resource_ids"]),
                "zero_span_alias_resource_ids": list(group["zero_span_alias_resource_ids"]),
                "payload_file_offset": f"0x{payload_offset:x}",
                "span_bytes": span_bytes,
                "decoded_size": len(decoded),
                "original_compressed_size": original_compressed_size,
                "rebuilt_compressed_size": len(compressed),
                "decoded_sha256": sha256_bytes(decoded),
                "original_compressed_sha256": sha256_bytes(
                    data[payload_offset : payload_offset + original_compressed_size]
                ),
                "rebuilt_compressed_sha256": sha256_bytes(compressed),
                "stream_byte_identical": True,
                "record_count": len(parsed["text_records"]),
                "stream_token_count": len(parsed["tokens"]),
                "capacity_ok": True,
            }
        )

    final = bytes(patched)
    _require(final[table_start:table_end] == table_before, "full rebuild changed type-2 directory")
    after_records = EXTRACT.extract_records(final, resource_ids=ALL_RESOURCE_IDS)
    _require(_record_identity(before_records) == _record_identity(after_records), "full rebuild changed record identity")
    roundtrip = EXTRACT.verify_roundtrip(final, ALL_RESOURCE_IDS)
    _require(bool(roundtrip["byte_identical"]), "full rebuild failed PSI3 stream round-trip")

    changed_offsets = {
        index for index, (before, after) in enumerate(zip(data, final)) if before != after
    }
    changed_outside = [
        index
        for index in changed_offsets
        if not any(start <= index < end for start, end in allowed_ranges)
    ]
    _require(not changed_outside, "full rebuild changed bytes outside positive payload spans")
    final_metadata = EXTRACT.inspect_rom(final)
    summary: dict[str, object] = {
        "tool_version": "b3cj-full-container-rebuild-v1",
        "evidence_level": "all-nonzero-type2-psi3-semantic-rebuild",
        "static_only": True,
        "translation_targets_added": 0,
        "clean_rom": {
            "sha256": metadata["digests"]["sha256"],
            "crc32": metadata["digests"]["crc32"],
            "header_checksum": f"0x{int(metadata['stored_header_checksum']):02x}",
        },
        "rebuilt_rom": {
            "sha256": final_metadata["digests"]["sha256"],
            "crc32": final_metadata["digests"]["crc32"],
            "header_checksum_unchanged": final_metadata["stored_header_checksum"] == metadata["stored_header_checksum"],
        },
        "directory": {
            "resource_count": EXPECTED_RESOURCE_COUNT,
            "nonzero_resource_count": len(EXPECTED_NONZERO_RESOURCE_IDS),
            "zero_span_resource_ids": list(EXPECTED_ZERO_SPAN_RESOURCE_IDS),
            "zero_span_alias_groups": [
                {
                    "resource_ids": list(group["resource_ids"]),
                    "positive_span_resource_ids": list(group["positive_span_resource_ids"]),
                }
                for group in groups
                if group["zero_span_alias_resource_ids"]
            ],
            "unique_positive_payload_groups": len(groups),
            "positive_spans_non_overlapping": True,
            "byte_identical": True,
        },
        "payload_groups": {
            "rewritten_count": len(reports),
            "capacity_ok": True,
            "groups": reports,
        },
        "records": {
            "logical_before": len(before_records),
            "logical_after": len(after_records),
            "unique_positive_payload_records": len(unique_records),
            "identity_byte_identical": True,
        },
        "roundtrip": {
            "layer": roundtrip["layer"],
            "resources": roundtrip["resources"],
            "records": roundtrip["records"],
            "source_reencode_records": roundtrip["source_reencode_records"],
            "opaque_tokens": roundtrip["opaque_tokens"],
            "rejected_marker_candidates": roundtrip["rejected_marker_candidates"],
            "original_aggregate_sha256": roundtrip["original_aggregate_sha256"],
            "encoded_aggregate_sha256": roundtrip["encoded_aggregate_sha256"],
            "record_aggregate_sha256": roundtrip["record_aggregate_sha256"],
            "byte_identical": True,
        },
        "byte_level": {
            "changed_byte_count": len(changed_offsets),
            "changed_outside_positive_payload_spans": False,
            "directory_byte_identical": True,
        },
        "boundary": "All non-zero type-2 PSI3 payloads were semantically rebuilt with no translation; this does not prove variable-length translated insertion, runtime reachability, live rendering, or a release patch.",
    }
    return final, summary


def run_bps(source_path: pathlib.Path, target_path: pathlib.Path, bps_path: pathlib.Path, applied_path: pathlib.Path) -> dict[str, object]:
    if source_path.resolve() == target_path.resolve() or source_path.resolve() == applied_path.resolve():
        raise ValueError("refusing to overwrite or apply over the clean ROM")
    create = GAME_ROOT.parents[1] / "core" / "patches" / "bps_create.rb"
    apply = GAME_ROOT.parents[1] / "core" / "patches" / "bps_apply.rb"
    bps_path.parent.mkdir(parents=True, exist_ok=True)
    applied_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ruby", str(create), str(source_path), str(target_path), str(bps_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["ruby", str(apply), str(source_path), str(bps_path), str(applied_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    applied = applied_path.read_bytes()
    target = target_path.read_bytes()
    _require(applied == target, "BPS apply is not byte-identical to full rebuild")
    bps = bps_path.read_bytes()
    return {
        "bps_size": len(bps),
        "bps_sha256": sha256_bytes(bps),
        "applied_sha256": sha256_bytes(applied),
        "applied_byte_identical": True,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="clean B3CJ ROM")
    parser.add_argument("--output", type=pathlib.Path, required=True, help="ignored rebuilt ROM")
    parser.add_argument("--summary-output", type=pathlib.Path, required=True, help="ignored summary")
    parser.add_argument("--bps-output", type=pathlib.Path)
    parser.add_argument("--bps-applied-output", type=pathlib.Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        rebuilt, summary = rebuild(args.rom.read_bytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(rebuilt)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_FULL_CONTAINER_REBUILD_OK "
            f"resources={summary['directory']['resource_count']} "
            f"groups={summary['payload_groups']['rewritten_count']} "
            f"records={summary['records']['logical_after']} "
            f"changed_bytes={summary['byte_level']['changed_byte_count']}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"rebuild_full_container.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
