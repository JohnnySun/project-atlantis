#!/usr/bin/env python3
"""Build a source-safe structural inventory for the A6SJ text pool.

This is deliberately not a semantic translator or a scene extractor.  It
joins the ignored strict source table to the clean ROM, classifies each record
only by the already-proven M1.7 glyph/opaque token contract, and emits counts,
hashes, offset pages, and rejection metadata.  No source text is written to
the output or printed to stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

try:
    from m17_layout import M17Error, ROM_BASE, read_source_records, source_payload, tokenize_payload
except ImportError:  # pragma: no cover - direct invocation from another cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from m17_layout import M17Error, ROM_BASE, read_source_records, source_payload, tokenize_payload


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
SOURCE_START = 0x076000
SOURCE_END = 0x082490
PAGE_SIZE = 0x1000


class InventoryError(ValueError):
    """A source-safe inventory gate rejected an input."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in values).encode("ascii"))


def classify_partition(tokenization: Any) -> str:
    """Classify only structural glyph/opaque shape; never infer semantics."""

    if not tokenization.supported:
        return "opaque_or_unaligned"
    classes = {token.glyph_class for token in tokenization.tokens if token.is_glyph}
    if classes == {"narrow"}:
        return "glyph_only_narrow"
    if classes == {"wide"}:
        return "glyph_only_wide"
    if classes == {"narrow", "wide"}:
        return "glyph_only_mixed"
    raise InventoryError(f"unexpected glyph class set: {sorted(classes)!r}")


def _safe_record_digest(offset: int, payload: bytes, partition: str) -> bytes:
    return f"{offset:08x}:{sha256(payload)}:{partition}\n".encode("ascii")


def _source_table_guard(source_table: Path) -> None:
    if not source_table.name.endswith("-decoded.jsonl"):
        raise InventoryError("refusing non-local-source-table filename")


def inventory(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise InventoryError("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise InventoryError(f"record_count_mismatch: {len(records)}")

    partitions: Counter[str] = Counter()
    token_kinds: Counter[str] = Counter()
    glyph_classes: Counter[str] = Counter()
    page_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    partition_offsets: Dict[str, List[int]] = defaultdict(list)
    source_digest = hashlib.sha256()
    unique_code_units = set()
    unique_source_codepoints = set()
    widths: List[int] = []
    payload_lengths: List[int] = []
    nul_count = 0
    source_identity_count = 0
    no_op_count = 0
    records_with_zero_width = 0

    previous_offset = None
    for row in records:
        offset = int(row["offset"])
        if not SOURCE_START <= offset < SOURCE_END:
            raise InventoryError(f"source_offset_out_of_range: 0x{offset:x}")
        if previous_offset is not None and offset <= previous_offset:
            raise InventoryError("source_offsets_not_strictly_ordered")
        previous_offset = offset
        text = str(row["text"])
        try:
            expected_payload = text.encode("shift_jis", errors="strict")
        except UnicodeError as exc:
            raise InventoryError(f"source_not_strict_shift_jis: 0x{offset:x}") from exc
        payload, terminator = source_payload(rom, offset)
        if payload != expected_payload:
            raise InventoryError(f"source_byte_mismatch: 0x{offset:x}")
        if terminator != offset + len(payload):
            raise InventoryError(f"terminator_boundary_mismatch: 0x{offset:x}")
        tokenization = tokenize_payload(payload)
        partition = classify_partition(tokenization)
        partitions[partition] += 1
        partition_offsets[partition].append(offset)
        page = f"0x{(offset // PAGE_SIZE) * PAGE_SIZE:06X}"
        page_counts[page][partition] += 1
        for token in tokenization.tokens:
            token_kinds[token.kind] += 1
            if token.is_glyph:
                glyph_classes[str(token.glyph_class)] += 1
                unique_code_units.add(int.from_bytes(token.raw, "little"))
        unique_source_codepoints.update(ord(char) for char in text)
        widths.append(tokenization.line_width)
        payload_lengths.append(len(payload))
        nul_count += 1
        source_identity_count += payload == expected_payload
        no_op_count += b"".join(token.raw for token in tokenization.tokens) + b"\x00" == payload + b"\x00"
        records_with_zero_width += tokenization.line_width == 0
        source_digest.update(_safe_record_digest(offset, payload, partition))

    def hash_partition(name: str) -> str:
        return hash_ints(partition_offsets[name])

    page_report = {
        page: {
            "record_count": sum(counter.values()),
            "partition_counts": dict(sorted(counter.items())),
        }
        for page, counter in sorted(page_counts.items())
    }
    partition_report = {
        name: {
            "record_count": partitions[name],
            "offset_index_sha256": hash_partition(name),
            "first_offset": f"0x{min(partition_offsets[name]):06X}",
            "last_offset": f"0x{max(partition_offsets[name]):06X}",
        }
        for name in sorted(partitions)
    }
    return {
        "schema": "super-robot-taisen-d-m4-corpus-inventory-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "classification_policy": "structural glyph/opaque shape only; no semantic labels",
        },
        "rom": {
            "sha256": sha256(rom),
            "source_range": {
                "start": f"0x{SOURCE_START:06X}",
                "end_exclusive": f"0x{SOURCE_END:06X}",
            },
        },
        "source_corpus": {
            "record_count": len(records),
            "record_digest_sha256": source_digest.hexdigest(),
            "strict_shift_jis_identity_count": source_identity_count,
            "nul_terminated_count": nul_count,
            "no_op_token_encode_count": no_op_count,
            "zero_width_record_count": records_with_zero_width,
            "unique_source_codepoint_count": len(unique_source_codepoints),
            "unique_source_codepoint_index_sha256": hash_ints(sorted(unique_source_codepoints)),
            "unique_glyph_code_unit_count": len(unique_code_units),
            "unique_glyph_code_unit_index_sha256": hash_ints(sorted(unique_code_units)),
            "payload_length_min": min(payload_lengths),
            "payload_length_max": max(payload_lengths),
            "line_width_min": min(widths),
            "line_width_max": max(widths),
            "line_width_distinct_count": len(set(widths)),
        },
        "structural_partitions": partition_report,
        "token_kind_counts": dict(sorted(token_kinds.items())),
        "glyph_class_counts": dict(sorted(glyph_classes.items())),
        "offset_page_counts": page_report,
        "narrow_reinsert_boundary": {
            "structurally_narrow_only_records": partitions["glyph_only_narrow"],
            "structurally_rejected_records": len(records) - partitions["glyph_only_narrow"],
            "accepted_shape": "glyph_only_narrow, two-byte units, NUL-terminated, same-length only",
            "rejected_shapes": [
                "glyph_only_mixed",
                "glyph_only_wide",
                "opaque_or_unaligned",
            ],
            "wide_new_slot_capacity": 0,
            "semantic_translation_status": "not_started",
        },
        "gate": {
            "rom_hash_match": True,
            "record_count_match": len(records) == EXPECTED_RECORD_COUNT,
            "strict_source_identity": source_identity_count == len(records),
            "all_nul_terminated": nul_count == len(records),
            "token_encode_no_op": no_op_count == len(records),
            "structural_partition_complete": sum(partitions.values()) == len(records),
            "source_text_emitted": False,
            "translation_started": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.parent.name != "work":
        raise SystemExit("refusing non-work output; use games/.../work/*.json")
    try:
        _source_table_guard(args.source_table)
        records = read_source_records(args.source_table)
        report = inventory(args.rom.read_bytes(), records)
    except (InventoryError, M17Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"m4_inventory_rejected={exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "m4_inventory=accepted records={record_count} partitions={partitions} "
        "narrow_only={narrow_only} rejected={rejected}".format(
            record_count=report["source_corpus"]["record_count"],
            partitions={key: value["record_count"] for key, value in report["structural_partitions"].items()},
            narrow_only=report["narrow_reinsert_boundary"]["structurally_narrow_only_records"],
            rejected=report["narrow_reinsert_boundary"]["structurally_rejected_records"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
