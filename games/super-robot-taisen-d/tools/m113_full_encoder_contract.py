#!/usr/bin/env python3
"""Audit the fail-closed full encoder boundary for A6SJ.

The encoder is deliberately complete for *validation* and source no-op
round-trip, but it is not a claim of complete translation coverage.  Narrow
allocations come from the already committed bounded static POC batches.  Wide
targets are accepted only when the existing slot identity has a bounded live
runtime confirmation; static-source-only wide identities remain rejected.
No ROM is modified and no source text is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m17_layout import ROM_BASE, code_unit_slot, read_source_records, source_payload, tokenize_payload  # noqa: E402
from m4_corpus_inventory import classify_partition  # noqa: E402


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
NARROW_RESOURCE_SIZE = 0x1980
WIDE_NEW_SLOT_CAPACITY = 0
EXPECTED_FONT_SOURCE_SHA256 = "c1768bd7fea203db1f419045d5a9e4d420772445e29b96c8873471d3f46c5b53"
EXPECTED_FONT_LICENSE_SHA256 = "869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded"


class EncoderReject(ValueError):
    """A fail-closed encoder contract rejected an input."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in sorted(set(values))).encode("ascii"))


def parse_codepoint(value: str) -> int:
    if not isinstance(value, str) or not value.startswith("U+"):
        raise EncoderReject("invalid_codepoint_identity")
    return int(value[2:], 16)


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EncoderReject(f"expected_object:{path}")
    return value


def encode_text(
    text: str,
    narrow_map: Mapping[int, Mapping[str, Any]],
    wide_map: Mapping[int, Mapping[str, Any]],
) -> Tuple[bytes, Dict[str, int]]:
    if not isinstance(text, str) or not text:
        raise EncoderReject("empty_target")
    output = bytearray()
    modes: Counter[str] = Counter()
    for character in text:
        codepoint = ord(character)
        if codepoint in narrow_map:
            entry = narrow_map[codepoint]
            output.extend(int(entry["code_unit"]).to_bytes(2, "little"))
            modes["narrow"] += 1
            continue
        if codepoint in wide_map:
            entry = wide_map[codepoint]
            if entry.get("runtime_status") != "runtime_confirmed_bounded":
                raise EncoderReject("wide_static_only_identity")
            output.extend(int(entry["code_unit"]).to_bytes(2, "little"))
            modes["wide_runtime_confirmed"] += 1
            continue
        if character in "\x00\n\r":
            raise EncoderReject("opaque_or_control")
        raise EncoderReject("missing_glyph")
    return bytes(output), dict(sorted(modes.items()))


def read_ledger_rows(paths: Sequence[Path]) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                raise EncoderReject(f"invalid_ledger_row:{path}:{line_number}")
            if "source" in row:
                raise EncoderReject(f"source_text_emitted:{path}:{line_number}")
            rows.append(row)
    return rows


def source_noop_audit(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise EncoderReject("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise EncoderReject("source_record_count_mismatch")
    partitions: Counter[str] = Counter()
    no_op = 0
    for row in records:
        offset = int(row["offset"])
        expected = str(row["text"]).encode("shift_jis", errors="strict")
        payload, terminator = source_payload(rom, offset)
        if payload != expected or terminator != offset + len(payload):
            raise EncoderReject("source_payload_mismatch")
        tokenization = tokenize_payload(payload)
        partitions[classify_partition(tokenization)] += 1
        no_op += int(b"".join(token.raw for token in tokenization.tokens) == payload)
    return {
        "record_count": len(records),
        "strict_source_count": len(records),
        "token_encode_no_op_count": no_op,
        "partition_counts": dict(sorted(partitions.items())),
        "source_record_id_index_sha256": hash_ints(int(row["offset"]) for row in records),
    }


def audit_ledgers(
    rom: bytes,
    rows: Sequence[Mapping[str, Any]],
    source_records: Mapping[int, Mapping[str, Any]],
    narrow_map: Mapping[int, Mapping[str, Any]],
    wide_map: Mapping[int, Mapping[str, Any]],
) -> Dict[str, Any]:
    accepted = 0
    rejected: Counter[str] = Counter()
    modes: Counter[str] = Counter()
    lengths_equal = 0
    accepted_ids: List[int] = []
    for row in rows:
        try:
            string_id = int(row["string_id"])
            target = row["targets"]["zh-TW"]["text"]
            source_record = source_records.get(string_id)
            if source_record is None:
                raise EncoderReject("source_hash_mismatch")
            source_text = str(source_record["text"])
            if row.get("source_hash") != sha256(source_text.encode("utf-8")):
                raise EncoderReject("source_hash_mismatch")
            source_expected = source_text.encode("shift_jis", errors="strict")
            encoded, target_modes = encode_text(str(target), narrow_map, wide_map)
            source_payload_bytes, terminator = source_payload(rom, string_id)
            if source_payload_bytes != source_expected:
                raise EncoderReject("source_hash_mismatch")
            if terminator != string_id + len(source_payload_bytes):
                raise EncoderReject("source_terminator_mismatch")
            if len(encoded) != len(source_payload_bytes):
                raise EncoderReject("variable_length")
            lengths_equal += 1
            accepted += 1
            accepted_ids.append(string_id)
            for mode, count in target_modes.items():
                modes[mode] += count
        except EncoderReject as exc:
            rejected[str(exc)] += 1
    return {
        "record_count": len(rows),
        "accepted_count": accepted,
        "rejected_counts": dict(sorted(rejected.items())),
        "same_length_count": lengths_equal,
        "accepted_id_index_sha256": hash_ints(accepted_ids),
        "encoded_mode_counts": dict(sorted(modes.items())),
        "source_text_emitted": False,
    }


def build_report(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    narrow_report: Mapping[str, Any],
    wide_report: Mapping[str, Any],
    ledgers: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    # The maps are reconstructed from ignored reports, while the output keeps
    # only counts and index hashes.
    narrow_map = read_narrow_map_from_report(narrow_report)
    wide_map = read_wide_map_from_report(wide_report)
    source_index = {int(row["offset"]): row for row in records}
    source = source_noop_audit(rom, records)
    ledger = audit_ledgers(rom, ledgers, source_index, narrow_map, wide_map)
    runtime_wide_count = sum(
        entry.get("runtime_status") == "runtime_confirmed_bounded" for entry in wide_map.values()
    )
    static_wide_count = len(wide_map) - runtime_wide_count
    return {
        "schema": "super-robot-taisen-d-m113-full-encoder-contract-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "rom_modified": False,
            "wide_identity_policy": "strict source context plus bounded runtime confirmation for target acceptance",
        },
        "inputs": {
            "rom_sha256": sha256(rom),
            "narrow_allocation_count": len(narrow_map),
            "narrow_codepoint_index_sha256": hash_ints(narrow_map),
            "wide_existing_identity_count": len(wide_map),
            "wide_codepoint_index_sha256": hash_ints(wide_map),
            "wide_runtime_confirmed_identity_count": runtime_wide_count,
            "wide_static_only_identity_count": static_wide_count,
            "wide_new_slot_capacity": WIDE_NEW_SLOT_CAPACITY,
        },
        "source_noop": source,
        "translation_ledger": ledger,
        "contract": {
            "narrow_existing_and_allocated_slots": "accepted only after source/font/hash/slot/length gates",
            "wide_runtime_confirmed_existing_slot": "accepted only for bounded runtime-confirmed identity",
            "wide_static_only_existing_slot": "reject_for_new_target_until_runtime_confirmed",
            "wide_new_slot": "reject_capacity_zero",
            "opaque_or_control": "reject",
            "missing_glyph": "reject",
            "variable_length": "reject",
            "full_semantic_translation": False,
            "full_encoder_status": "fail_closed_narrow_plus_runtime_confirmed_wide_subset",
        },
        "gate": {
            "rom_hash_match": sha256(rom) == EXPECTED_ROM_SHA256,
            "source_records_2325": source["record_count"] == EXPECTED_RECORD_COUNT,
            "source_no_op_2325": source["token_encode_no_op_count"] == EXPECTED_RECORD_COUNT,
            "ledger_source_safe": ledger["source_text_emitted"] is False,
            "wide_new_slot_capacity_zero": WIDE_NEW_SLOT_CAPACITY == 0,
            "no_rom_modified": True,
        },
    }


def read_narrow_map_from_report(report: Mapping[str, Any]) -> Dict[int, Dict[str, Any]]:
    if report.get("rom", {}).get("source_sha256") != EXPECTED_ROM_SHA256:
        raise EncoderReject("rom_hash_mismatch")
    font = report.get("font")
    if not isinstance(font, Mapping):
        raise EncoderReject("font_metadata_missing")
    if font.get("source_sha256") != EXPECTED_FONT_SOURCE_SHA256:
        raise EncoderReject("font_hash_mismatch")
    if font.get("license_sha256") != EXPECTED_FONT_LICENSE_SHA256:
        raise EncoderReject("font_license_hash_mismatch")
    if report.get("allocator", {}).get("font_hash_match") is not True:
        raise EncoderReject("font_hash_mismatch")
    allocations = report.get("allocations")
    if not isinstance(allocations, list):
        raise EncoderReject("narrow_allocations_missing")
    result: Dict[int, Dict[str, Any]] = {}
    slots: set[int] = set()
    units: set[int] = set()
    for row in allocations:
        if not isinstance(row, Mapping):
            raise EncoderReject("invalid_narrow_allocation")
        codepoint = parse_codepoint(str(row["codepoint"]))
        unit = int(str(row["code_unit_little_endian"]), 16)
        slot = int(row["slot"])
        if codepoint in result or unit in units or slot in slots:
            raise EncoderReject("narrow_codepoint_or_slot_collision")
        if code_unit_slot(unit, "narrow", NARROW_RESOURCE_SIZE) != slot:
            raise EncoderReject("narrow_code_unit_slot_mismatch")
        result[codepoint] = {"code_unit": unit, "slot": slot}
        slots.add(slot)
        units.add(unit)
    return result


def read_wide_map_from_report(report: Mapping[str, Any]) -> Dict[int, Dict[str, Any]]:
    if report.get("rom", {}).get("sha256") != EXPECTED_ROM_SHA256:
        raise EncoderReject("rom_hash_mismatch")
    resource = report.get("resource")
    if not isinstance(resource, Mapping):
        raise EncoderReject("wide_resource_metadata_missing")
    try:
        resource_size = int(str(resource["end_exclusive"]), 16) - int(str(resource["start"]), 16)
    except (KeyError, TypeError, ValueError) as exc:
        raise EncoderReject("wide_resource_metadata_missing") from exc
    if resource.get("new_slot_capacity") != WIDE_NEW_SLOT_CAPACITY:
        raise EncoderReject("wide_new_slot_capacity_nonzero")
    identities = report.get("identities")
    if not isinstance(identities, list):
        raise EncoderReject("wide_identity_rows_missing")
    result: Dict[int, Dict[str, Any]] = {}
    slots: set[int] = set()
    units: set[int] = set()
    for row in identities:
        if not isinstance(row, Mapping):
            raise EncoderReject("invalid_wide_identity")
        codepoint = parse_codepoint(str(row["unicode"]))
        unit = int(row["code_unit"])
        slot = int(row["slot"])
        if codepoint in result or unit in units or slot in slots:
            raise EncoderReject("wide_codepoint_or_slot_collision")
        if code_unit_slot(unit, "wide", resource_size) != slot:
            raise EncoderReject("wide_code_unit_slot_mismatch")
        result[codepoint] = {
            "code_unit": int(row["code_unit"]),
            "slot": slot,
            "runtime_status": str(row.get("runtime_status", "static_source_context_only")),
        }
        slots.add(slot)
        units.add(unit)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--narrow-report", type=Path, required=True)
    parser.add_argument("--wide-report", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(
            args.rom.read_bytes(),
            read_source_records(args.source_table),
            read_json(args.narrow_report),
            read_json(args.wide_report),
            read_ledger_rows(args.ledger),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m113_full_encoder_contract_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m113_full_encoder_contract=accepted source={} ledger={}/{} wide_runtime={}".format(
            report["source_noop"]["token_encode_no_op_count"],
            report["translation_ledger"]["accepted_count"],
            report["translation_ledger"]["record_count"],
            report["inputs"]["wide_runtime_confirmed_identity_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
