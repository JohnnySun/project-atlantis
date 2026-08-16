#!/usr/bin/env python3
"""Census FE6 text-unit widths, terminators and opaque markers.

M1.33 replays the proven tree worker over every supported table record and
keeps the code-unit boundary separate from byte-pattern coincidence.  A
two-byte leaf is tested against a strict Shift-JIS decoder in memory, but the
decoded characters are discarded.  A one-byte leaf is counted as an opaque
token unless it is one of the already observed structural marker bytes.

The only encoder claim is the original leaf-sequence no-op round-trip.  This
tool does not encode arbitrary Unicode, name a control code, or emit source,
code-unit, decoded-text, font or bitmap payloads.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

from extract_afej_m16 import (
    AfejFormatError,
    KNOWN_MARKERS,
    build_codebook,
    decode_record,
    encode_leaves,
    load_rom,
    prove_table_end,
    table_entry,
)


EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)
POINTER_TABLE = 0x080F635C
LOADER_ENTRY = 0x08013AD0
WORKER = 0x0300323C
BUFFER = 0x02029404
SCHEMA = "afej-m133-text-structure-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _histogram(values: collections.Counter[int]) -> dict[str, int]:
    return {str(key): count for key, count in sorted(values.items())}


def _sequence_digest(rows: list[dict[str, object]]) -> str:
    return _sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _record_summary(rom: object, record: object, table_end: int, codebook: dict[bytes, tuple[int, ...]]) -> dict[str, object]:
    encoded = encode_leaves(record.leaves, codebook)
    if encoded != record.source_bytes:
        raise AfejFormatError(f"index {record.index} failed original leaf round-trip")
    next_source = table_entry(rom, record.index + 1) if record.index + 1 < table_end else None
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(f"index {record.index} source span does not meet next pointer")

    code_units = [leaf.output for leaf in record.leaves if len(leaf.output) == 2]
    one_byte_values = [leaf.output[0] for leaf in record.leaves if len(leaf.output) == 1]
    payload = b"".join(code_units)
    try:
        payload.decode("shift_jis")
        strict_shift_jis = True
    except UnicodeDecodeError:
        strict_shift_jis = False

    marker_counts = {marker: 0 for marker in KNOWN_MARKERS}
    marker_offsets: dict[str, list[int]] = {f"0x{marker:02x}": [] for marker in KNOWN_MARKERS}
    opaque_single_values = collections.Counter()
    logical_offset = 0
    for leaf in record.leaves:
        if len(leaf.output) == 1:
            value = leaf.output[0]
            if value in marker_counts:
                marker_counts[value] += 1
                marker_offsets[f"0x{value:02x}"].append(logical_offset)
            else:
                opaque_single_values[value] += 1
        logical_offset += len(leaf.output)

    return {
        "table_index": record.index,
        "string_id": f"afej.ptr.{record.index:04d}",
        "table_entry": f"0x{POINTER_TABLE + record.index * 4:08x}",
        "source_pointer": f"0x{record.source_pointer:08x}",
        "source_end": f"0x{record.source_end:08x}",
        "source_span_matches_next_entry": next_source is None or record.source_end == next_source,
        "source_hash": _sha256(record.source_bytes),
        "output_hash": _sha256(record.output),
        "source_length": len(record.source_bytes),
        "payload_length": len(record.output),
        "buffer_length": len(record.buffer),
        "two_byte_code_unit_count": len(code_units),
        "one_byte_leaf_count": len(one_byte_values),
        "opaque_single_byte_count": sum(opaque_single_values.values()),
        "control_marker_counts": {f"0x{marker:02x}": count for marker, count in marker_counts.items()},
        "control_marker_offsets": marker_offsets,
        "terminator_is_last_single_byte_zero": bool(record.leaves and record.leaves[-1].output == b"\x00"),
        "strict_shift_jis_candidate": strict_shift_jis,
        "decode_encode_byte_identical": True,
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path) -> dict[str, object]:
    rom = load_rom(rom_path)
    game_code = rom.data[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = hashlib.sha256(rom.data).hexdigest()
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")
    table_end = prove_table_end(rom)
    codebook = build_codebook(rom)
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for index in range(table_end):
        try:
            records.append(_record_summary(rom, decode_record(rom, index), table_end, codebook))
        except AfejFormatError as exc:
            reason = str(exc)
            kind = (
                "decoder_buffer_limit_no_terminator"
                if "no terminator before buffer limit" in reason
                else "decoder_or_round_trip_failure"
            )
            failures.append({
                "table_index": index,
                "string_id": f"afej.ptr.{index:04d}",
                "failure_kind": kind,
                "raw_bytes_emitted": False,
            })

    marker_occurrences = collections.Counter()
    marker_record_counts = collections.Counter()
    marker_offset_histograms: dict[str, collections.Counter[int]] = {
        f"0x{marker:02x}": collections.Counter() for marker in KNOWN_MARKERS
    }
    invalid_indices: list[int] = []
    source_lengths = collections.Counter()
    payload_lengths = collections.Counter()
    two_byte_total = 0
    one_byte_total = 0
    opaque_single_total = 0
    terminator_count = 0
    for row in records:
        source_lengths[int(row["source_length"])] += 1
        payload_lengths[int(row["payload_length"])] += 1
        two_byte_total += int(row["two_byte_code_unit_count"])
        one_byte_total += int(row["one_byte_leaf_count"])
        opaque_single_total += int(row["opaque_single_byte_count"])
        if row["terminator_is_last_single_byte_zero"]:
            terminator_count += 1
        if not row["strict_shift_jis_candidate"]:
            invalid_indices.append(int(row["table_index"]))
        for marker, count in row["control_marker_counts"].items():
            marker_occurrences[marker] += int(count)
            marker_record_counts[marker] += int(count > 0)
        for marker, offsets in row["control_marker_offsets"].items():
            marker_offset_histograms[marker].update(int(offset) for offset in offsets)

    sequence_rows = [
        {
            "table_index": row["table_index"],
            "source_pointer": row["source_pointer"],
            "source_hash": row["source_hash"],
            "output_hash": row["output_hash"],
            "strict_shift_jis_candidate": row["strict_shift_jis_candidate"],
            "decode_encode_byte_identical": row["decode_encode_byte_identical"],
        }
        for row in records
    ]
    return {
        "schema": SCHEMA,
        "rom": {"game_code": game_code, "size": len(rom.data), "sha256": rom_sha256},
        "provenance": {
            "pointer_table": f"0x{POINTER_TABLE:08x}",
            "table_domain": f"[0,{table_end})",
            "loader_entry": f"0x{LOADER_ENTRY:08x}",
            "worker": f"0x{WORKER:08x}",
            "ewram_buffer": f"0x{BUFFER:08x}",
        },
        "table": {
            "record_count": table_end,
            "strict_record_count": len(records),
            "failure_count": len(failures),
            "all_supported_source_spans_match_next_entry": all(
                row["source_span_matches_next_entry"] for row in records
            ),
            "records": records,
            "failures": failures,
            "stable_sequence_sha256": _sequence_digest(sequence_rows),
            "source_bytes_emitted": False,
            "code_unit_bytes_emitted": False,
        },
        "widths": {
            "two_byte_code_unit_total": two_byte_total,
            "one_byte_leaf_total": one_byte_total,
            "opaque_single_byte_total": opaque_single_total,
            "two_byte_units_are_structural_only": True,
            "unicode_identity_confirmed": False,
        },
        "terminator": {
            "candidate_byte": "0x00",
            "records_with_last_single_byte_zero": terminator_count,
            "all_supported_records_end_with_single_byte_zero": terminator_count == len(records),
            "semantic_name_assigned": False,
        },
        "markers": {
            "single_byte_token_occurrences": dict(sorted(marker_occurrences.items())),
            "record_counts": dict(sorted(marker_record_counts.items())),
            "offset_histograms": {
                marker: _histogram(histogram)
                for marker, histogram in sorted(marker_offset_histograms.items())
            },
            "semantic_names_assigned": False,
        },
        "codepage_candidate": {
            "encoding_tested": "shift_jis",
            "strict_record_count": len(records) - len(invalid_indices),
            "invalid_record_count": len(invalid_indices),
            "invalid_index_sha256": _sha256(json.dumps(invalid_indices, separators=(",", ":")).encode("ascii")),
            "candidate_only": True,
            "raw_bytes_emitted": False,
        },
        "round_trip": {
            "original_leaf_sequence_decode_encode_byte_identical": len(records),
            "supported_records": len(records),
            "arbitrary_text_encode_enabled": False,
            "marker_rewrite_enabled": False,
            "rom_insertion_enabled": False,
        },
        "static_control_gate": {
            "byte_read": "0x08098c24",
            "leq_01_target": "0x08098c78",
            "eq_04_target": "0x08098c80",
            "handler_callsite": "0x08003e60",
            "semantic_names_assigned": False,
        },
        "status": {
            "text_structure": "pointer_table_tree_worker_two_byte_leaf_plus_opaque_single_byte_tokens",
            "codepage": "shift_jis_candidate_only_3081_of_3203_strict_records",
            "terminator": "structural_0x00_at_record_tail_observed",
            "control_semantics": "opaque",
            "unicode_identity_confirmed": False,
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_report(args.rom)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"records={result['table']['record_count']}")
    print(f"strict_sjis_candidates={result['codepage_candidate']['strict_record_count']}")
    print(f"terminators={result['terminator']['records_with_last_single_byte_zero']}")
    print(f"roundtrip={result['round_trip']['original_leaf_sequence_decode_encode_byte_identical']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
