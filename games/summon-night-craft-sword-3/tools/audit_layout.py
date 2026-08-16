#!/usr/bin/env python3
"""Audit B3CJ text pointer, record, and static layout contracts.

The audit reuses the reviewed extractor on the verified Japanese ROM.  It
records only offsets, lengths, opcode shapes, counters, and hashes; it never
writes source text or raw decoded bytes.  Layout semantics that are not
proved by a callsite remain explicitly unknown.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import pathlib
import struct
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTRACTOR_PATH = GAME_ROOT / "tools" / "extract_static.py"
EXPECTED_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_RESOURCE_IDS = (9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 22, 24, 25)
EXPECTED_RECORDS = 361
POINTER_SCALE = 16


def _load_extractor() -> Any:
    spec = importlib.util.spec_from_file_location("b3cj_extract_for_layout_audit", EXTRACTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {EXTRACTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXTRACT = _load_extractor()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _histogram(values: Iterable[int]) -> dict[str, int]:
    counts = collections.Counter(values)
    return {str(key): counts[key] for key in sorted(counts)}


def _code_unit_count(payload: bytes) -> int:
    """Count strict Shift-JIS code units without retaining decoded text."""

    decoded = payload.decode("shift_jis")
    _require(decoded.encode("shift_jis") == payload, "Shift-JIS payload is not lossless")
    return len(decoded)


def _pointer_groups(entries: list[dict[str, int]]) -> dict[str, object]:
    """Classify aliases and validate only pointer facts proved by the table."""

    grouped: dict[int, list[dict[str, int]]] = collections.defaultdict(list)
    for entry in entries:
        grouped[entry["payload_file_offset"]].append(entry)

    groups: list[dict[str, object]] = []
    intervals: list[tuple[int, int, int]] = []
    zero_span_aliases: list[int] = []
    owners: list[int] = []
    for payload_offset, group in sorted(grouped.items()):
        positive = [item for item in group if item["span_bytes"] > 0]
        _require(positive, f"pointer group at 0x{payload_offset:x} has no positive span")
        compressed_sizes = {item["compressed_size"] for item in group}
        _require(len(compressed_sizes) == 1, f"pointer group at 0x{payload_offset:x} disagrees on compressed size")
        compressed_size = next(iter(compressed_sizes))
        for item in positive:
            _require(
                compressed_size <= item["span_bytes"],
                f"resource {item['resource_id']} compressed payload exceeds pointer span",
            )
        if len(positive) == 1:
            owners.append(positive[0]["resource_id"])
            aliases = [item["resource_id"] for item in group if item["span_bytes"] == 0]
            zero_span_aliases.extend(aliases)
            role = "owner_plus_zero_span_aliases" if aliases else "single_owner"
        elif len({item["span_bytes"] for item in positive}) == 1:
            owners.append(min(item["resource_id"] for item in positive))
            aliases = [item["resource_id"] for item in group if item["resource_id"] != min(i["resource_id"] for i in positive)]
            role = "shared_positive_span_aliases"
        else:
            aliases = []
            role = "shared_pointer_span_review_required"
        intervals.append((payload_offset, payload_offset + max(item["span_bytes"] for item in positive), min(item["resource_id"] for item in group)))
        groups.append(
            {
                "payload_file_offset": f"0x{payload_offset:08x}",
                "resource_ids": [item["resource_id"] for item in group],
                "positive_span_resource_ids": [item["resource_id"] for item in positive],
                "zero_span_alias_resource_ids": [item["resource_id"] for item in group if item["span_bytes"] == 0],
                "compressed_size": compressed_size,
                "role": role,
            }
        )

    intervals.sort()
    overlaps: list[dict[str, object]] = []
    for previous, current in zip(intervals, intervals[1:]):
        if previous[1] > current[0]:
            overlaps.append(
                {
                    "left_resource_id": previous[2],
                    "right_resource_id": current[2],
                    "left_end": f"0x{previous[1]:08x}",
                    "right_start": f"0x{current[0]:08x}",
                }
            )
    _require(not overlaps, f"script resource pointer spans overlap: {overlaps}")
    return {
        "pointer_scale_bytes": POINTER_SCALE,
        "pointer_groups": groups,
        "unique_payload_groups": len(groups),
        "zero_span_alias_resource_ids": sorted(zero_span_aliases),
        "owner_resource_ids": sorted(owners),
        "positive_span_intervals_non_overlapping": True,
    }


def audit_rom(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    metadata = EXTRACT.inspect_rom(data)
    mismatches = EXTRACT.validate_rom_identity(metadata)
    if metadata["digests"]["sha256"] != EXPECTED_SHA256:
        mismatches.append("sha256")
    _require(not mismatches, "B3CJ identity mismatch: " + ", ".join(mismatches))

    resource_ids: list[int] = []
    resource_summaries: list[dict[str, object]] = []
    pointer_entries: list[dict[str, int]] = []
    record_contract = hashlib.sha256()
    record_count = 0
    source_reencode_count = 0
    opaque_following_count = 0
    following_opcode_counts: collections.Counter[str] = collections.Counter()
    raw_lengths: list[int] = []
    code_unit_counts: list[int] = []

    for resource_id in range(EXTRACT.SCRIPT_RESOURCE_COUNT):
        resolved = EXTRACT.resolve_script_resource(data, resource_id)
        decoded, compressed_size = EXTRACT.decode_lz77(data, resolved["payload_file_offset"])
        parsed = EXTRACT.parse_script_stream(decoded, resource_id)
        if not parsed["text_records"]:
            continue
        resource_ids.append(resource_id)
        compressed_raw = data[resolved["payload_file_offset"] : resolved["payload_file_offset"] + compressed_size]
        pointer_entry = {
            "resource_id": resource_id,
            "directory_file_offset": resolved["directory_file_offset"],
            "relative_units": resolved["relative_units"],
            "span_bytes": resolved["span_units"] * POINTER_SCALE,
            "payload_file_offset": resolved["payload_file_offset"],
            "compressed_size": compressed_size,
        }
        pointer_entries.append(pointer_entry)
        resource_record_count = 0
        resource_opaque_count = 0
        for record in parsed["text_records"]:
            raw_payload = record["_payload_bytes"]
            raw_length = len(raw_payload)
            code_units = _code_unit_count(raw_payload)
            reencoded = EXTRACT.encode_text_record(record, source_text=record["source_text"])
            _require(reencoded == record["_raw_bytes"], f"record {record['decompressed_offset']:x} source re-encode mismatch")
            record_count += 1
            resource_record_count += 1
            source_reencode_count += 1
            raw_lengths.append(raw_length)
            code_unit_counts.append(code_units)
            for control in record["following_controls"]:
                if control.get("kind") == "opaque":
                    opaque_following_count += 1
                    resource_opaque_count += 1
                else:
                    following_opcode_counts[str(control["opcode"])] += 1
            record_contract.update(
                f"b3cj:t2:{resource_id:03d}:0x{int(record['decompressed_offset']):04x}|"
                f"{raw_length}|{record['raw_sha256']}|{code_units}\n".encode("ascii")
            )
        resource_summaries.append(
            {
                "resource_id": resource_id,
                "directory_file_offset": f"0x{resolved['directory_file_offset']:08x}",
                "pointer_relative_units": f"0x{resolved['relative_units']:x}",
                "span_bytes": resolved["span_units"] * POINTER_SCALE,
                "payload_file_offset": f"0x{resolved['payload_file_offset']:08x}",
                "compressed_size": compressed_size,
                "compressed_sha256": hashlib.sha256(compressed_raw).hexdigest(),
                "decompressed_size": len(decoded),
                "stream_sha256": hashlib.sha256(decoded[EXTRACT.SCRIPT_HEADER_SIZE:]).hexdigest(),
                "record_count": resource_record_count,
                "opaque_following_control_count": resource_opaque_count,
            }
        )
    _require(tuple(resource_ids) == EXPECTED_RESOURCE_IDS, f"record resource IDs changed: {resource_ids}")
    _require(record_count == EXPECTED_RECORDS, f"record count changed: {record_count}")

    pointer = _pointer_groups(pointer_entries)
    return {
        "audit_version": "m2.8-static-layout-v1",
        "game": "summon-night-craft-sword-3",
        "revision": "B3CJ",
        "rom": {
            "sha256": metadata["digests"]["sha256"],
            "crc32": metadata["digests"]["crc32"],
            "size": metadata["file_size"],
        },
        "evidence_level": "confirmed-static-pointer-record-contract-with-unknown-layout-semantics",
        "resources": len(resource_ids),
        "resource_ids": resource_ids,
        "records": record_count,
        "source_reencode_records": source_reencode_count,
        "record_contract_aggregate_sha256": record_contract.hexdigest(),
        "pointer_contract": pointer,
        "text_contract": {
            "marker": "0x0308",
            "terminator": "0x0000",
            "raw_payload_reencode": "byte_identical",
            "raw_length_histogram": _histogram(raw_lengths),
            "code_unit_count_histogram": _histogram(code_unit_counts),
            "max_raw_payload_bytes": max(raw_lengths),
            "max_code_units": max(code_unit_counts),
            "following_opcode_counts": dict(sorted(following_opcode_counts.items())),
            "opaque_following_control_count": opaque_following_count,
        },
        "layout_contract": {
            "inline_text_segments_per_record": 1,
            "known_line_break_or_page_opcodes": [],
            "line_semantics": "unknown_opaque_controls_remain_uninterpreted",
            "glyph_width_semantics": "not_proved_by_static_record_parser",
            "record_length_semantics": "same_byte_length_only",
        },
        "resource_summaries": resource_summaries,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="verified local Japanese B3CJ ROM")
    parser.add_argument("--output", type=pathlib.Path, required=True, help="ignored JSON summary")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = audit_rom(args.rom)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_LAYOUT_AUDIT_OK "
            f"resources={report['resources']} records={report['records']} "
            f"pointer_groups={report['pointer_contract']['unique_payload_groups']} output={args.output}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"audit_layout.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
