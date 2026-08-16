#!/usr/bin/env python3
"""Rebuild the bounded B3CJ script container without changing its records.

This is a semantic no-op verifier for the 13 reviewed type-2 resources.  It
re-emits each decoded PSI3 stream losslessly, recompresses each unique
non-zero payload with the deterministic GBA LZ77 encoder, and writes it back
inside the existing pointer span with zero fill.  It never translates text,
relocates a pointer, or emits source text.  The output ROM and optional BPS
artifacts belong under ignored ``games/.../work/``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import struct
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
EXTRACT_PATH = GAME_ROOT / "tools" / "extract_static.py"
LZ_ENCODER_PATH = GAME_ROOT / "tools" / "encode_m2_3_poc.py"

EXPECTED_GAME = "B3CJ"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_ROM_CRC32 = "12afae5d"
EXPECTED_HEADER_CHECKSUM = 0x6B
REVIEWED_RESOURCE_IDS = (9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 22, 24, 25)


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXTRACT = _load_module("b3cj_extract_for_container_rebuild", EXTRACT_PATH)
LZ_ENCODER = _load_module("b3cj_lz_encoder_for_container_rebuild", LZ_ENCODER_PATH)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _record_digest(records: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: str(item["string_id"])):
        digest.update(str(record["string_id"]).encode("ascii"))
        digest.update(str(record["raw_sha256"]).encode("ascii"))
        digest.update(str(record["record_sha256"]).encode("ascii"))
    return digest.hexdigest()


def _record_identity(records: list[dict[str, object]]) -> list[tuple[str, str, str]]:
    return [
        (str(record["string_id"]), str(record["raw_sha256"]), str(record["record_sha256"]))
        for record in sorted(records, key=lambda item: str(item["string_id"]))
    ]


def _validate_clean_rom(data: bytes) -> dict[str, object]:
    metadata = EXTRACT.inspect_rom(data)
    _require(metadata["file_size"] == 0x02000000, "B3CJ ROM size mismatch")
    _require(metadata["game_code"] == EXPECTED_GAME, "B3CJ game code mismatch")
    _require(metadata["stored_header_checksum"] == EXPECTED_HEADER_CHECKSUM, "B3CJ stored header checksum mismatch")
    _require(metadata["calculated_header_checksum"] == EXPECTED_HEADER_CHECKSUM, "B3CJ calculated header checksum mismatch")
    _require(metadata["digests"]["sha256"] == EXPECTED_ROM_SHA256, "clean B3CJ SHA-256 mismatch")
    _require(metadata["digests"]["crc32"] == EXPECTED_ROM_CRC32, "clean B3CJ CRC32 mismatch")
    return metadata


def _resource_groups(data: bytes) -> list[dict[str, object]]:
    by_payload: dict[int, dict[str, object]] = {}
    for resource_id in REVIEWED_RESOURCE_IDS:
        resolved = EXTRACT.resolve_script_resource(data, resource_id)
        span_units = int(resolved["span_units"])
        if span_units == 0:
            continue
        payload = int(resolved["payload_file_offset"])
        group = by_payload.setdefault(
            payload,
            {
                "payload_file_offset": payload,
                "span_units": span_units,
                "span_bytes": span_units * EXTRACT.SCRIPT_TABLE_POINTER_SCALE,
                "resource_ids": [],
                "directory_file_offsets": [],
            },
        )
        _require(int(group["span_units"]) == span_units, "aliased payload group span drifted")
        group["resource_ids"].append(resource_id)
        group["directory_file_offsets"].append(int(resolved["directory_file_offset"]))
    groups = sorted(by_payload.values(), key=lambda item: int(item["payload_file_offset"]))
    _require(len(groups) == 11, f"expected 11 non-zero payload groups, got {len(groups)}")
    return groups


def rebuild(data: bytes) -> tuple[bytes, dict[str, object]]:
    """Return a semantic no-op container rebuild and a bounded receipt."""

    metadata = _validate_clean_rom(data)
    groups = _resource_groups(data)
    before_records = EXTRACT.extract_records(data, resource_ids=REVIEWED_RESOURCE_IDS)
    _require(len(before_records) == 361, "reviewed source does not contain 361 records")
    script_table_before = data[EXTRACT.SCRIPT_TABLE_FILE_OFFSET : EXTRACT.SCRIPT_TABLE_FILE_OFFSET + EXTRACT.SCRIPT_TABLE_SIZE]
    patched = bytearray(data)
    group_reports: list[dict[str, object]] = []
    allowed_ranges: list[tuple[int, int]] = []

    for group in groups:
        payload_offset = int(group["payload_file_offset"])
        span_bytes = int(group["span_bytes"])
        decoded, original_compressed_size = EXTRACT.decode_lz77(data, payload_offset)
        parsed_stream = EXTRACT.parse_script_stream(decoded, int(group["resource_ids"][0]))
        encoded_stream = EXTRACT.encode_script_stream(parsed_stream)
        rebuilt_decoded = decoded[: EXTRACT.SCRIPT_HEADER_SIZE] + encoded_stream
        _require(rebuilt_decoded == decoded, f"resource group 0x{payload_offset:x} PSI3 stream is not lossless")
        compressed = LZ_ENCODER.lz77_compress(rebuilt_decoded)
        _require(len(compressed) <= span_bytes, f"resource group 0x{payload_offset:x} compressed output exceeds span {span_bytes}")
        end = payload_offset + span_bytes
        _require(end <= len(data), f"resource group 0x{payload_offset:x} span is outside ROM")
        patched[payload_offset:end] = compressed + bytes(span_bytes - len(compressed))
        allowed_ranges.append((payload_offset, end))
        group_reports.append(
            {
                "resource_ids": list(group["resource_ids"]),
                "payload_file_offset": f"0x{payload_offset:x}",
                "span_bytes": span_bytes,
                "decoded_size": len(decoded),
                "original_compressed_size": original_compressed_size,
                "rebuilt_compressed_size": len(compressed),
                "decoded_sha256": sha256_bytes(decoded),
                "original_compressed_sha256": sha256_bytes(data[payload_offset : payload_offset + original_compressed_size]),
                "rebuilt_compressed_sha256": sha256_bytes(compressed),
                "decoded_stream_byte_identical": True,
                "capacity_ok": True,
            }
        )

    final = bytes(patched)
    script_table_after = final[EXTRACT.SCRIPT_TABLE_FILE_OFFSET : EXTRACT.SCRIPT_TABLE_FILE_OFFSET + EXTRACT.SCRIPT_TABLE_SIZE]
    _require(script_table_before == script_table_after, "container rebuild changed the type-2 directory")
    after_records = EXTRACT.extract_records(final, resource_ids=REVIEWED_RESOURCE_IDS)
    _require(_record_identity(before_records) == _record_identity(after_records), "container rebuild changed record identity")
    roundtrip = EXTRACT.verify_roundtrip(final, REVIEWED_RESOURCE_IDS)
    _require(bool(roundtrip["byte_identical"]), "rebuilt resources failed PSI3 stream round-trip")

    changed_offsets = {
        index
        for index, (before, after) in enumerate(zip(data, final))
        if before != after
    }
    changed_outside = [
        index
        for index in changed_offsets
        if not any(start <= index < end for start, end in allowed_ranges)
    ]
    _require(not changed_outside, "container rebuild changed bytes outside reviewed payload spans")
    final_metadata = EXTRACT.inspect_rom(final)
    summary: dict[str, object] = {
        "tool_version": "b3cj-container-rebuild-v1",
        "evidence_level": "semantic-psi3-and-lz77-container-rebuild",
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
        "resources": {
            "resource_ids": list(REVIEWED_RESOURCE_IDS),
            "resource_count": len(REVIEWED_RESOURCE_IDS),
            "payload_group_count": len(group_reports),
            "groups": group_reports,
        },
        "records": {
            "before": len(before_records),
            "after": len(after_records),
            "identity_byte_identical": True,
            "stable_identity_sha256": _record_digest(after_records),
        },
        "roundtrip": {
            "psi3_stream_byte_identical": bool(roundtrip["byte_identical"]),
            "stream_bytes": int(roundtrip["stream_bytes"]),
            "source_reencode_records": int(roundtrip["source_reencode_records"]),
            "opaque_tokens": int(roundtrip["opaque_tokens"]),
            "rejected_marker_candidates": int(roundtrip["rejected_marker_candidates"]),
            "record_aggregate_sha256": roundtrip["record_aggregate_sha256"],
        },
        "byte_level": {
            "changed_byte_count": len(changed_offsets),
            "changed_outside_payload_spans": False,
            "directory_byte_identical": True,
        },
        "boundary": "Semantic no-op container rebuild only; no translation, pointer relocation, runtime screen claim, or release-patch claim.",
    }
    return final, summary


def run_bps(source_path: pathlib.Path, target_path: pathlib.Path, bps_path: pathlib.Path, applied_path: pathlib.Path) -> dict[str, object]:
    if source_path.resolve() == target_path.resolve() or source_path.resolve() == applied_path.resolve():
        raise ValueError("refusing to overwrite or apply over the clean ROM")
    create = REPO_ROOT / "core" / "patches" / "bps_create.rb"
    apply = REPO_ROOT / "core" / "patches" / "bps_apply.rb"
    bps_path.parent.mkdir(parents=True, exist_ok=True)
    applied_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ruby", str(create), str(source_path), str(target_path), str(bps_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["ruby", str(apply), str(source_path), str(bps_path), str(applied_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    target = target_path.read_bytes()
    applied = applied_path.read_bytes()
    _require(target == applied, "BPS apply is not byte-identical to rebuilt ROM")
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
    parser.add_argument("--summary-output", type=pathlib.Path, required=True)
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
            "B3CJ_CONTAINER_REBUILD_OK "
            f"resources={summary['resources']['resource_count']} "
            f"groups={summary['resources']['payload_group_count']} "
            f"records={summary['records']['after']} "
            f"changed_bytes={summary['byte_level']['changed_byte_count']}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"rebuild_container.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
