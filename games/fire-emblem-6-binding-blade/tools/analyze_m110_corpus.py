#!/usr/bin/env python3
"""Build a hash-only structural census of the proven AFEJ text table.

M1.10 deliberately expands the already-proven M1.6 tree decoder to all 3342
pointer-table records, but does not emit code-unit bytes, Japanese text, or
the full source bitstreams.  The committed research JSON contains only
stable IDs, pointer provenance, lengths, hashes, marker offsets/counts, and
decode-to-encode results.  The decoder still validates every source span and
round-trip in memory before writing the summary.

This census is structural coverage, not a claim that all records belong to a
single semantic category.  Caller/scene evidence remains a separate runtime
requirement.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from extract_afej_m16 import (  # noqa: E402
    AfejFormatError,
    AfejRom,
    TABLE_END_INDEX,
    build_codebook,
    decode_record,
    load_rom,
    prove_table_end,
    record_to_json,
)


SCHEMA = "afej-m110-table-census-v1"


def _histogram(values: Iterable[int]) -> dict[str, int]:
    return {
        str(key): count
        for key, count in sorted(collections.Counter(values).items())
    }


def _record_summary(record: dict[str, object]) -> dict[str, object]:
    provenance = record["provenance"]
    assert isinstance(provenance, dict)
    markers = record["control_marker_offsets"]
    assert isinstance(markers, dict)
    tokens = record["tokens"]
    assert isinstance(tokens, list)
    token_kinds = collections.Counter(str(token["kind"]) for token in tokens)
    return {
        "string_id": record["string_id"],
        "table_index": provenance["table_index"],
        "table_entry": provenance["table_entry"],
        "source_pointer": provenance["source_pointer"],
        "source_end": provenance["source_end"],
        "next_source_pointer": provenance["next_source_pointer"],
        "source_span_matches_next_entry": provenance["source_span_matches_next_entry"],
        "source_hash": record["source_hash"],
        "output_hash": record["output_hash"],
        "source_length": record["source_length"],
        "payload_length": record["payload_length"],
        "buffer_length": record["buffer_length"],
        "control_marker_counts": {
            marker: len(offsets) for marker, offsets in markers.items()
        },
        "token_kind_counts": dict(sorted(token_kinds.items())),
        "opaque_token_count": record["opaque_token_count"],
        "decode_encode_byte_identical": record["decode_encode_byte_identical"],
    }


def build_census(rom: AfejRom) -> dict[str, object]:
    table_end = prove_table_end(rom)
    codebook = build_codebook(rom)
    summaries: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    marker_offsets_by_value: dict[str, list[int]] = {
        marker: [] for marker in ("0x00", "0x01", "0x04", "0xff")
    }
    for index in range(table_end):
        try:
            record = record_to_json(
                rom,
                decode_record(rom, index),
                table_end=table_end,
                codebook=codebook,
            )
        except AfejFormatError as exc:
            reason = str(exc)
            if "no terminator before buffer limit" in reason:
                failure_kind = "decoder_buffer_limit_no_terminator"
            elif "source span ends" in reason:
                failure_kind = "source_span_does_not_match_next_pointer"
            else:
                failure_kind = "decoder_or_round_trip_failure"
            failures.append({
                "string_id": f"afej.ptr.{index:04d}",
                "table_index": index,
                "failure_kind": failure_kind,
            })
            continue
        summary = _record_summary(record)
        summaries.append(summary)
        markers = record["control_marker_offsets"]
        assert isinstance(markers, dict)
        for marker, offsets in markers.items():
            marker_offsets_by_value[str(marker)].extend(int(offset) for offset in offsets)
    span_matches = [row["source_span_matches_next_entry"] for row in summaries]
    source_lengths = [int(row["source_length"]) for row in summaries]
    payload_lengths = [int(row["payload_length"]) for row in summaries]
    source_hashes = [str(row["source_hash"]) for row in summaries]
    output_hashes = [str(row["output_hash"]) for row in summaries]

    marker_record_counts: dict[str, int] = {}
    marker_offset_histograms: dict[str, dict[str, int]] = {}
    for marker in ("0x00", "0x01", "0x04", "0xff"):
        offsets = [
            int(offset) for offset in marker_offsets_by_value[marker]
        ]
        marker_record_counts[marker] = sum(
            row["control_marker_counts"][marker] > 0 for row in summaries
        )
        marker_offset_histograms[marker] = _histogram(offsets)

    return {
        "schema": SCHEMA,
        "game": "fire-emblem-6-binding-blade",
        "revision": "AFEJ",
        "rom_sha256": hashlib.sha256(rom.data).hexdigest(),
        "table": {
            "pointer_table": "0x080f635c",
            "domain_start": 0,
            "domain_end_exclusive": table_end,
            "record_count": table_end,
            "strictly_supported_record_count": len(summaries),
            "decoder_failure_count": len(failures),
            "all_source_spans_match_next_entry": all(span_matches),
            "first_source_pointer": summaries[0]["source_pointer"],
            "last_source_end": summaries[-1]["source_end"],
        },
        "round_trip": {
            "decode_encode_byte_identical": sum(
                bool(row["decode_encode_byte_identical"]) for row in summaries
            ),
            "records": len(summaries),
            "unsupported_records": len(failures),
        },
        "lengths": {
            "source_min": min(source_lengths),
            "source_max": max(source_lengths),
            "payload_min": min(payload_lengths),
            "payload_max": max(payload_lengths),
            "source_histogram": _histogram(source_lengths),
            "payload_histogram": _histogram(payload_lengths),
        },
        "hash_uniqueness": {
            "distinct_source_hashes": len(set(source_hashes)),
            "distinct_output_hashes": len(set(output_hashes)),
        },
        "marker_records": marker_record_counts,
        "marker_offset_histograms": marker_offset_histograms,
        "records": summaries,
        "decoder_failures": failures,
        "semantic_boundary": {
            "content_categories": "unknown_without_caller_or_scene_evidence",
            "worker_coverage": "3203_strict_records;_139_buffer_limit_failures",
            "unicode_or_codepage": "not_established",
            "control_marker_semantics": "opaque",
            "source_bytes_emitted": False,
            "code_unit_bytes_emitted": False,
        },
    }


def main() -> int:
    default_rom = Path(__file__).resolve().parents[1] / "roms/base/AFEJ.gba"
    default_output = Path(__file__).resolve().parents[1] / "research/m110-table-census.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=default_rom)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()
    try:
        rom = load_rom(args.rom)
        census = build_census(rom)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(census, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, AfejFormatError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"output={args.output}")
    print(f"records={census['table']['record_count']}")
    print(f"round_trip={census['round_trip']['decode_encode_byte_identical']}/{census['round_trip']['records']}")
    print(f"all_source_spans_match_next_entry={census['table']['all_source_spans_match_next_entry']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
