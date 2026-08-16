#!/usr/bin/env python3
"""Extract a bounded, hash-only FE6 corpus around the natural index 3087.

This is deliberately narrower than a translation extractor.  It reuses the
reviewed M1.6 custom tree worker and inverse encoder, then records only stable
IDs, pointer provenance, hashes, lengths, marker offsets and a Shift-JIS
candidate's aggregate script counts.  A natural runtime report may be joined
for loader/caller/display provenance, but no source bytes or decoded text are
written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any, Optional

from extract_afej_m16 import (
    AfejFormatError,
    AfejRom,
    BUFFER,
    LOADER_ENTRY,
    POINTER_TABLE,
    TABLE_END_INDEX,
    build_codebook,
    decode_record,
    encode_leaves,
    load_rom,
    marker_offsets,
    prove_table_end,
    table_entry,
)


DEFAULT_START = 3064
DEFAULT_COUNT = 32
KNOWN_MARKERS = (0x00, 0x01, 0x04, 0xFF)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _script_counts(text: str) -> dict[str, int]:
    counts = {"hiragana": 0, "katakana": 0, "han": 0, "latin": 0, "digit": 0, "other": 0}
    for char in text:
        codepoint = ord(char)
        if 0x3040 <= codepoint <= 0x309F:
            counts["hiragana"] += 1
        elif 0x30A0 <= codepoint <= 0x30FF:
            counts["katakana"] += 1
        elif 0x3400 <= codepoint <= 0x9FFF:
            counts["han"] += 1
        elif char.isdigit():
            counts["digit"] += 1
        elif char.isascii() and (char.isalpha() or char in " -'.,!?()"):
            counts["latin"] += 1
        else:
            counts["other"] += 1
    return counts


def _codepage_candidate(leaves: Any) -> dict[str, object]:
    # Only the proven two-byte leaves are candidate text units.  Single-byte
    # controls/opaque bytes are excluded from this test.
    units = [leaf.output for leaf in leaves if len(leaf.output) == 2]
    payload = b"".join(units)
    try:
        decoded = payload.decode("shift_jis")
    except UnicodeDecodeError:
        return {
            "encoding_tested": "shift_jis",
            "strict_decode": False,
            "code_unit_count": len(units),
            "decoded_character_count": None,
            "decoded_utf8_sha256": None,
            "script_counts": None,
            "candidate_only": True,
        }
    return {
        "encoding_tested": "shift_jis",
        "strict_decode": True,
        "code_unit_count": len(units),
        "decoded_character_count": len(decoded),
        "decoded_utf8_sha256": _sha256(decoded.encode("utf-8")),
        "script_counts": _script_counts(decoded),
        "candidate_only": True,
    }


def _record_summary(rom: AfejRom, record: Any, table_end: int, codebook: dict[bytes, tuple[int, ...]]) -> dict[str, object]:
    encoded = encode_leaves(record.leaves, codebook)
    if encoded != record.source_bytes:
        raise AfejFormatError(f"index {record.index} failed decode->encode equality")
    next_source = table_entry(rom, record.index + 1) if record.index + 1 < table_end else None
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(f"index {record.index} source span does not meet next pointer")
    return {
        "string_id": f"afej.ptr.{record.index:04d}",
        "table_index": record.index,
        "table_entry": f"0x{POINTER_TABLE + record.index * 4:08x}",
        "source_pointer": f"0x{record.source_pointer:08x}",
        "source_end": f"0x{record.source_end:08x}",
        "next_source_pointer": f"0x{next_source:08x}" if next_source is not None else None,
        "source_span_matches_next_entry": next_source is None or record.source_end == next_source,
        "source_hash": _sha256(record.source_bytes),
        "payload_hash": _sha256(record.output),
        "output_hash": _sha256(record.buffer),
        "source_length": record.source_length,
        "payload_length": record.payload_length,
        "buffer_length": len(record.buffer),
        "control_marker_offsets": marker_offsets(record.output),
        "opaque_single_byte_count": sum(
            len(leaf.output) == 1 and leaf.output[0] not in KNOWN_MARKERS
            for leaf in record.leaves
        ),
        "opaque_control_count": sum(
            len(leaf.output) == 1 and leaf.output[0] in KNOWN_MARKERS
            for leaf in record.leaves
        ),
        "decode_encode_byte_identical": True,
        "codepage_candidate": _codepage_candidate(record.leaves),
        "loader_entry": f"0x{LOADER_ENTRY:08x}",
        "pointer_table": f"0x{POINTER_TABLE:08x}",
        "table_domain": f"[0, {table_end})",
        "worker_output": f"0x{BUFFER:08x}",
        "raw_bytes_emitted": False,
    }


def _runtime_summary(runtime_path: Path, records: list[dict[str, object]]) -> dict[str, object]:
    report = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime report has no runtime object")
    loader_rows = runtime.get("loader_records", [])
    if not isinstance(loader_rows, list):
        loader_rows = []
    bounded = []
    record_by_index = {row["table_index"]: row for row in records}
    for row in loader_rows[:32]:
        if not isinstance(row, dict):
            continue
        index = row.get("loader_index")
        if not isinstance(index, int):
            continue
        buffer = row.get("buffer", {})
        if not isinstance(buffer, dict):
            buffer = {}
        static = record_by_index.get(index)
        bounded.append({
            "table_index": index,
            "caller_callsite": row.get("caller_callsite"),
            "caller_lr": row.get("caller_lr"),
            "source_pointer": row.get("source_pointer"),
            "buffer_hash": buffer.get("buffer_sha256"),
            "static_output_hash": static.get("output_hash") if static else None,
            "buffer_hash_matches_static": bool(static and buffer.get("buffer_sha256") == static.get("output_hash")),
            "reachability": row.get("reachability"),
        })
    display = runtime.get("final_display_io")
    display_bytes = json.dumps(display, sort_keys=True, separators=(",", ":")).encode("utf-8")
    route = report.get("route", {})
    return {
        "route_name": route.get("name"),
        "natural_reachability": route.get("natural_reachability"),
        "input_sequence": route.get("sequence"),
        "loader_receipt_count": len(bounded),
        "loader_receipts": bounded,
        "final_display_io_sha256": _sha256(display_bytes),
        "scene_or_content_category": "unknown_natural_route_context",
        "raw_bytes_emitted": False,
    }


def build_report(
    rom_path: Path,
    *,
    start: int = DEFAULT_START,
    count: int = DEFAULT_COUNT,
    runtime_path: Optional[Path] = None,
) -> dict[str, object]:
    rom = load_rom(rom_path)
    table_end = prove_table_end(rom)
    if count <= 0 or count > 32 or start < 0 or start + count > table_end:
        raise ValueError("bounded cohort must contain 1..32 records within proven table")
    codebook = build_codebook(rom)
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for index in range(start, start + count):
        try:
            records.append(_record_summary(rom, decode_record(rom, index), table_end, codebook))
        except AfejFormatError:
            failures.append({"table_index": index, "failure_kind": "strict_decode_or_roundtrip_failure"})
    result: dict[str, object] = {
        "schema": "afej-m123-bounded-corpus-v1",
        "rom": {
            "game_code": rom.data[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom.data),
            "sha256": _sha256(rom.data),
        },
        "cohort": {
            "start": start,
            "count_requested": count,
            "count_extracted": len(records),
            "count_failed": len(failures),
            "end_exclusive": start + count,
            "table_domain": f"[0, {table_end})",
            "bounded_max": 32,
        },
        "records": records,
        "failures": failures,
        "runtime_input": None,
        "runtime": None,
        "status": {
            "decode_encode_roundtrip": all(row["decode_encode_byte_identical"] for row in records) and not failures,
            "codepage": "shift_jis_candidate_only",
            "unicode_identity_confirmed": False,
            "scene_or_content_category": "unknown",
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }
    if runtime_path is not None:
        result["runtime_input"] = str(runtime_path)
        result["runtime"] = _runtime_summary(runtime_path, records)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.rom, start=args.start, count=args.count, runtime_path=args.runtime_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
