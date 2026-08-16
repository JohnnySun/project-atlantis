#!/usr/bin/env python3
"""Bound the A6SJ wide-identity and target-encoder capacity.

M4 established 743 strict Shift-JIS source-context wide identities, but only
one of them has a bounded runtime confirmation.  M1.13 already makes the
target encoder fail closed; this slice joins that policy to all 2325 source
records so the usable and rejected cohorts are measurable without treating
static source context as renderer proof.

The ignored strict source table is read only in memory.  The output contains
counts, hashes, code-unit/slot metadata, and rejection reasons; it never
contains source text, ROM bytes, or rendered images.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m113_full_encoder_contract import (  # noqa: E402
    EXPECTED_FONT_LICENSE_SHA256,
    EXPECTED_FONT_SOURCE_SHA256,
    EXPECTED_ROM_SHA256,
    EncoderReject,
    hash_ints,
    read_json,
    read_narrow_map_from_report,
    read_wide_map_from_report,
    sha256,
)
from m17_layout import (  # noqa: E402
    code_unit_slot,
    read_source_records,
    source_payload,
    tokenize_payload,
)
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_RECORD_COUNT = 2325
SOURCE_START = 0x076000
SOURCE_END = 0x082490
WIDE_RESOURCE_START = 0x08120DBC
WIDE_RESOURCE_END = 0x0814F664
WIDE_STRIDE = 26
WIDE_PAYLOAD_BYTES = 24
WIDE_NEW_SLOT_CAPACITY = 0
EXPECTED_WIDE_IDENTITY_COUNT = 743
EXPECTED_WIDE_OCCURRENCE_COUNT = 3983
EXPECTED_RUNTIME_WIDE_COUNT = 1
RUNTIME_WIDE_CODEPOINT = 0x79FB
RUNTIME_WIDE_CODE_UNIT = 0xDA88
RUNTIME_WIDE_SLOT = 905
RUNTIME_WIDE_GLYPH_SHA256 = "14b957c056e66cdd282857d73cfa04df932fa7dcaaec7e4a9c026c24c8323515"
EXPECTED_NARROW_ALLOCATION_COUNT = 28


class CapacityReject(ValueError):
    """A M1.21 wide-resource or source-join invariant failed closed."""


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _index_hash(values: Iterable[int]) -> str:
    return hash_ints(values)


def _digest_records(rows: Iterable[Tuple[int, bytes, str]]) -> str:
    digest = hashlib.sha256()
    for offset, payload, partition in rows:
        digest.update(f"{offset:08x}:{sha256(payload)}:{partition}\n".encode("ascii"))
    return digest.hexdigest()


def _resource_guard(wide_report: Mapping[str, Any]) -> Dict[str, Any]:
    resource = wide_report.get("resource")
    if not isinstance(resource, Mapping):
        raise CapacityReject("wide_resource_metadata_missing")
    try:
        start = int(str(resource["start"]), 16)
        end = int(str(resource["end_exclusive"]), 16)
        stride = int(resource["stride"])
        payload_bytes = int(resource["glyph_payload_bytes"])
        physical_slots = int(resource["physical_slots"])
        new_capacity = int(resource["new_slot_capacity"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CapacityReject("wide_resource_metadata_invalid") from exc
    size = end - start
    if (start, end, stride, payload_bytes) != (
        WIDE_RESOURCE_START,
        WIDE_RESOURCE_END,
        WIDE_STRIDE,
        WIDE_PAYLOAD_BYTES,
    ):
        raise CapacityReject("wide_resource_boundary_mismatch")
    if size <= 0 or size % stride or physical_slots != size // stride:
        raise CapacityReject("wide_resource_stride_mismatch")
    if new_capacity != WIDE_NEW_SLOT_CAPACITY:
        raise CapacityReject("wide_new_slot_capacity_nonzero")
    return {
        "start": _address(start),
        "end_exclusive": _address(end),
        "size": size,
        "stride": stride,
        "glyph_payload_bytes": payload_bytes,
        "physical_slots": physical_slots,
        "new_slot_capacity": new_capacity,
    }


def _runtime_identity_guard(
    wide_report: Mapping[str, Any], wide_map: Mapping[int, Mapping[str, Any]]
) -> Dict[str, Any]:
    if len(wide_map) != EXPECTED_WIDE_IDENTITY_COUNT:
        raise CapacityReject("wide_identity_count_mismatch")
    runtime_rows = [
        (codepoint, row)
        for codepoint, row in wide_map.items()
        if row.get("runtime_status") == "runtime_confirmed_bounded"
    ]
    if len(runtime_rows) != EXPECTED_RUNTIME_WIDE_COUNT:
        raise CapacityReject("runtime_wide_identity_count_mismatch")
    codepoint, row = runtime_rows[0]
    if (
        codepoint != RUNTIME_WIDE_CODEPOINT
        or int(row["code_unit"]) != RUNTIME_WIDE_CODE_UNIT
        or int(row["slot"]) != RUNTIME_WIDE_SLOT
    ):
        raise CapacityReject("runtime_wide_identity_mismatch")
    identity_rows = wide_report.get("identities")
    if not isinstance(identity_rows, list):
        raise CapacityReject("wide_identity_rows_missing")
    runtime_audit_rows = [
        identity_row
        for identity_row in identity_rows
        if isinstance(identity_row, Mapping)
        and identity_row.get("runtime_status") == "runtime_confirmed_bounded"
    ]
    if len(runtime_audit_rows) != EXPECTED_RUNTIME_WIDE_COUNT:
        raise CapacityReject("runtime_wide_audit_row_count_mismatch")
    audit_row = runtime_audit_rows[0]
    if (
        str(audit_row.get("unicode")) != f"U+{RUNTIME_WIDE_CODEPOINT:04X}"
        or str(audit_row.get("code_unit_little_endian")) != f"0x{RUNTIME_WIDE_CODE_UNIT:04X}"
        or int(audit_row.get("slot", -1)) != RUNTIME_WIDE_SLOT
    ):
        raise CapacityReject("runtime_wide_audit_identity_mismatch")
    if str(audit_row.get("glyph_sha256")) != RUNTIME_WIDE_GLYPH_SHA256:
        raise CapacityReject("runtime_wide_glyph_hash_mismatch")
    if code_unit_slot(RUNTIME_WIDE_CODE_UNIT, "wide", WIDE_RESOURCE_END - WIDE_RESOURCE_START) != RUNTIME_WIDE_SLOT:
        raise CapacityReject("runtime_wide_slot_formula_mismatch")
    source_corpus = wide_report.get("source_corpus", {})
    if not isinstance(source_corpus, Mapping):
        raise CapacityReject("wide_source_corpus_metadata_missing")
    if int(source_corpus.get("wide_identity_count", -1)) != EXPECTED_WIDE_IDENTITY_COUNT:
        raise CapacityReject("wide_source_identity_count_mismatch")
    if int(source_corpus.get("wide_occurrence_count", -1)) != EXPECTED_WIDE_OCCURRENCE_COUNT:
        raise CapacityReject("wide_source_occurrence_count_mismatch")
    return {
        "unicode": f"U+{codepoint:04X}",
        "code_unit": f"0x{int(row['code_unit']):04X}",
        "slot": int(row["slot"]),
        "glyph_sha256": str(audit_row["glyph_sha256"]),
        "identity_basis": "strict_shift_jis_source_context_plus_bounded_runtime_confirmation",
        "static_only_identity_count": EXPECTED_WIDE_IDENTITY_COUNT - EXPECTED_RUNTIME_WIDE_COUNT,
    }


def _narrow_guard(narrow_map: Mapping[int, Mapping[str, Any]]) -> Dict[str, Any]:
    if len(narrow_map) != EXPECTED_NARROW_ALLOCATION_COUNT:
        raise CapacityReject("narrow_allocation_count_mismatch")
    return {
        "allocation_count": len(narrow_map),
        "identity_policy": "explicit_static_allocation_with_ROM_font_and_slot_gates",
    }


def _source_class(character: str) -> str:
    try:
        encoded = character.encode("shift_jis", errors="strict")
    except UnicodeError:
        return "source_opaque"
    if len(encoded) == 2 and encoded[0] <= 0x87:
        return "source_narrow"
    if len(encoded) == 2:
        return "source_wide"
    return "source_opaque"


def _character_status(
    character: str,
    narrow_map: Mapping[int, Mapping[str, Any]],
    wide_map: Mapping[int, Mapping[str, Any]],
) -> str:
    codepoint = ord(character)
    if codepoint in narrow_map:
        return "target_narrow_known"
    if codepoint in wide_map:
        if wide_map[codepoint].get("runtime_status") == "runtime_confirmed_bounded":
            return "target_wide_runtime_confirmed"
        return "target_wide_static_only"
    return "target_missing"


def _record_category(partition: str, statuses: Set[str]) -> str:
    if partition == "opaque_or_unaligned":
        return "opaque_or_unaligned"
    if "target_wide_static_only" in statuses:
        return "reject_static_only_wide"
    if "target_missing" in statuses:
        return "reject_unmapped_target"
    if "target_wide_runtime_confirmed" in statuses:
        return "admissible_narrow_plus_runtime_wide"
    return "admissible_narrow_only"


def _source_audit(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    narrow_map: Mapping[int, Mapping[str, Any]],
    wide_map: Mapping[int, Mapping[str, Any]],
) -> Dict[str, Any]:
    if len(records) != EXPECTED_RECORD_COUNT:
        raise CapacityReject("source_record_count_mismatch")
    categories: Dict[str, List[int]] = defaultdict(list)
    target_feature_ids: Dict[str, List[int]] = defaultdict(list)
    source_class_ids: Dict[str, List[int]] = defaultdict(list)
    target_occurrences: Counter[str] = Counter()
    source_class_occurrences: Counter[str] = Counter()
    target_source_cross: Counter[str] = Counter()
    partitions: Counter[str] = Counter()
    identity_record_ids: Dict[str, List[int]] = defaultdict(list)
    digest_rows: List[Tuple[int, bytes, str]] = []
    strict_count = 0
    nul_count = 0
    no_op_count = 0
    previous_offset: int | None = None

    for row in records:
        offset = int(row["offset"])
        if not SOURCE_START <= offset < SOURCE_END:
            raise CapacityReject("source_offset_out_of_range")
        if previous_offset is not None and offset <= previous_offset:
            raise CapacityReject("source_offsets_not_strictly_ordered")
        previous_offset = offset
        text = str(row["text"])
        try:
            expected_payload = text.encode("shift_jis", errors="strict")
        except UnicodeError as exc:
            raise CapacityReject("source_not_strict_shift_jis") from exc
        payload, terminator = source_payload(rom, offset)
        if payload != expected_payload:
            raise CapacityReject("source_payload_mismatch")
        if terminator != offset + len(payload):
            raise CapacityReject("source_terminator_mismatch")
        tokenization = tokenize_payload(payload)
        partition = classify_partition(tokenization)
        partitions[partition] += 1
        digest_rows.append((offset, payload, partition))
        strict_count += 1
        nul_count += 1
        no_op_count += int(b"".join(token.raw for token in tokenization.tokens) == payload)

        statuses = {_character_status(character, narrow_map, wide_map) for character in text}
        source_classes = {_source_class(character) for character in text}
        for status in statuses:
            target_feature_ids[status].append(offset)
        for source_class in source_classes:
            source_class_ids[source_class].append(offset)
        missing_source_classes: Set[str] = set()
        for character in text:
            status = _character_status(character, narrow_map, wide_map)
            source_class = _source_class(character)
            target_occurrences[status] += 1
            source_class_occurrences[source_class] += 1
            target_source_cross[f"{status}|{source_class}"] += 1
            if status == "target_missing":
                missing_source_classes.add(source_class)
        if "target_wide_runtime_confirmed" in statuses:
            identity_record_ids["target_wide_runtime_confirmed"].append(offset)
        if "target_wide_static_only" in statuses:
            identity_record_ids["target_wide_static_only"].append(offset)
        category = _record_category(partition, statuses)
        if category == "reject_unmapped_target":
            if "source_wide" in missing_source_classes:
                category = "reject_unmapped_source_wide"
            elif "source_narrow" in missing_source_classes:
                category = "reject_unmapped_source_narrow"
            else:
                category = "reject_opaque_target"
        categories[category].append(offset)

    runtime_records = identity_record_ids["target_wide_runtime_confirmed"]
    static_records = identity_record_ids["target_wide_static_only"]
    wide_occurrences = source_class_occurrences["source_wide"]
    return {
        "record_count": len(records),
        "strict_source_count": strict_count,
        "nul_terminated_count": nul_count,
        "token_encode_no_op_count": no_op_count,
        "record_digest_sha256": _digest_records(digest_rows),
        "partition_counts": dict(sorted(partitions.items())),
        "record_category_counts": dict(sorted((key, len(value)) for key, value in categories.items())),
        "record_category_id_index_sha256": {
            key: _index_hash(value) for key, value in sorted(categories.items())
        },
        "target_identity_occurrence_counts": dict(sorted(target_occurrences.items())),
        "source_glyph_class_occurrence_counts": dict(sorted(source_class_occurrences.items())),
        "target_source_class_cross_counts": dict(sorted(target_source_cross.items())),
        "target_identity_record_counts": {
            key: len(set(value)) for key, value in sorted(target_feature_ids.items())
        },
        "target_identity_record_id_index_sha256": {
            key: _index_hash(value) for key, value in sorted(target_feature_ids.items())
        },
        "source_glyph_class_record_counts": {
            key: len(set(value)) for key, value in sorted(source_class_ids.items())
        },
        "source_glyph_class_record_id_index_sha256": {
            key: _index_hash(value) for key, value in sorted(source_class_ids.items())
        },
        "runtime_confirmed_wide_context": {
            "occurrence_count": target_occurrences["target_wide_runtime_confirmed"],
            "record_count": len(set(runtime_records)),
            "record_id_index_sha256": _index_hash(runtime_records),
        },
        "static_only_wide_context": {
            "occurrence_count": target_occurrences["target_wide_static_only"],
            "record_count": len(set(static_records)),
            "record_id_index_sha256": _index_hash(static_records),
        },
        "source_wide_resource_context": {
            "occurrence_count": wide_occurrences,
            "resource_report_occurrence_count": EXPECTED_WIDE_OCCURRENCE_COUNT,
            "occurrence_count_matches_wide_report": wide_occurrences == EXPECTED_WIDE_OCCURRENCE_COUNT,
            "record_count": len(set(source_class_ids["source_wide"])),
            "record_id_index_sha256": _index_hash(source_class_ids["source_wide"]),
        },
        "source_text_emitted": False,
    }


def build_report(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    narrow_report: Mapping[str, Any],
    wide_report: Mapping[str, Any],
) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise CapacityReject("rom_hash_mismatch")
    if narrow_report.get("source_text_emitted") is True:
        raise CapacityReject("narrow_report_source_text_emitted")
    if wide_report.get("source_policy", {}).get("source_text_emitted") is True:
        raise CapacityReject("wide_report_source_text_emitted")
    resource = _resource_guard(wide_report)
    narrow_map = read_narrow_map_from_report(narrow_report)
    wide_map = read_wide_map_from_report(wide_report)
    narrow = _narrow_guard(narrow_map)
    runtime_identity = _runtime_identity_guard(wide_report, wide_map)
    source = _source_audit(rom, records, narrow_map, wide_map)
    return {
        "schema": "super-robot-taisen-d-m121-wide-encoder-capacity-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "strict_source_table_read_in_memory_only": True,
            "static_source_context_is_not_runtime_proof": True,
        },
        "inputs": {
            "rom_sha256": sha256(rom),
            "narrow": narrow,
            "wide_resource": resource,
            "wide_existing_identity_count": len(wide_map),
            "wide_runtime_confirmed_identity_count": EXPECTED_RUNTIME_WIDE_COUNT,
            "wide_static_only_identity_count": len(wide_map) - EXPECTED_RUNTIME_WIDE_COUNT,
            "wide_new_slot_capacity": WIDE_NEW_SLOT_CAPACITY,
            "font_source_sha256": EXPECTED_FONT_SOURCE_SHA256,
            "font_license_sha256": EXPECTED_FONT_LICENSE_SHA256,
        },
        "runtime_confirmed_wide_identity": runtime_identity,
        "source_corpus": source,
        "encoder_contract": {
            "narrow_target_identity": "accept only explicit 28-entry static allocation map",
            "wide_target_identity": "accept only existing identity with runtime_confirmed_bounded status",
            "wide_static_only": "reject_for_target_until_runtime_confirmation",
            "wide_new_slot": "reject_capacity_zero",
            "unmapped_target": "reject_missing_glyph",
            "opaque_or_control": "reject",
            "variable_length": "reject",
            "source_admissible_record_definition": "strict NUL record whose every character is in the target map and whose tokenization is supported",
            "full_semantic_translation": False,
            "status": "fail_closed_narrow_plus_runtime_confirmed_wide_subset",
        },
        "gate": {
            "rom_hash_match": True,
            "source_records_2325": source["record_count"] == EXPECTED_RECORD_COUNT,
            "source_strict_2325": source["strict_source_count"] == EXPECTED_RECORD_COUNT,
            "source_nul_2325": source["nul_terminated_count"] == EXPECTED_RECORD_COUNT,
            "source_no_op_2325": source["token_encode_no_op_count"] == EXPECTED_RECORD_COUNT,
            "narrow_map_28": len(narrow_map) == EXPECTED_NARROW_ALLOCATION_COUNT,
            "wide_map_743": len(wide_map) == EXPECTED_WIDE_IDENTITY_COUNT,
            "runtime_wide_identity_1": True,
            "wide_resource_stride_26": resource["stride"] == WIDE_STRIDE,
            "wide_payload_24": resource["glyph_payload_bytes"] == WIDE_PAYLOAD_BYTES,
            "wide_new_slot_capacity_zero": resource["new_slot_capacity"] == 0,
            "source_text_emitted": False,
            "rom_modified": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--narrow-report", type=Path, required=True)
    parser.add_argument("--wide-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_json(args.narrow_report),
            read_json(args.wide_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, CapacityReject, EncoderReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m121_wide_encoder_capacity_rejected={exc}", file=sys.stderr)
        return 2
    source = report["source_corpus"]
    print(
        "m121_wide_encoder_capacity=accepted records={} admissible={} runtime_wide_occurrences={} static_wide_records={} new_wide_slots=0".format(
            source["record_count"],
            source["record_category_counts"].get("admissible_narrow_only", 0)
            + source["record_category_counts"].get("admissible_narrow_plus_runtime_wide", 0),
            source["runtime_confirmed_wide_context"]["occurrence_count"],
            source["static_only_wide_context"]["record_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
