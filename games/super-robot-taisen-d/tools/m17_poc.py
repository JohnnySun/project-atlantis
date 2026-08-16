#!/usr/bin/env python3
"""Fail-closed, no-op encoding contract for the M1.7 A6SJ POC.

This is not a translator and does not write a ROM.  It accepts only records
whose source hash, token signature, exact source length, exact source width,
glyph availability, and conservative slot capacity all remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from m17_layout import (
    ROM_BASE,
    M17Error,
    Tokenization,
    code_unit_slot,
    encode_tokens,
    read_source_records,
    resource_capacity,
    sha256,
    source_payload,
    token_summary,
    tokenize_payload,
)


POC_RECORDS = (0x7B380, 0x7B3FC)


class PocReject(ValueError):
    """A candidate violates one or more fail-closed contract clauses."""


@dataclass(frozen=True)
class PocContract:
    source_offset: int
    source_hash: str
    source_length: int
    source_width: int
    token_signature: Tuple[Tuple[str, Optional[str], int], ...]
    required_slots: Tuple[Tuple[str, int], ...]
    max_width: int

    def summary(self) -> Dict[str, Any]:
        required_by_class: Dict[str, int] = {}
        for glyph_class, _slot in self.required_slots:
            required_by_class[glyph_class] = required_by_class.get(glyph_class, 0) + 1
        return {
            "source_string_id": f"0x{self.source_offset:08X}",
            "source_address": f"0x{ROM_BASE + self.source_offset:08X}",
            "source_hash": self.source_hash,
            "source_length": self.source_length,
            "source_width": self.source_width,
            "max_width": self.max_width,
            "token_count": len(self.token_signature),
            "token_signature": [
                {"kind": kind, "glyph_class": glyph_class, "layout_width": width}
                for kind, glyph_class, width in self.token_signature
            ],
            "required_slot_counts": dict(sorted(required_by_class.items())),
            "required_slot_index_sha256": sha256(
                ",".join(f"{glyph_class}:{slot}" for glyph_class, slot in self.required_slots).encode("ascii")
            ),
            "policy": {
                "control_tokens": "exact token signature; opaque/newline candidates reject",
                "line_width": "exact source width and no overflow",
                "variable_length": "reject",
                "missing_glyph": "reject",
                "capacity": "reject when new slots exceed conservative blank-slot capacity",
            },
        }


def _resource_int(resource: Mapping[str, Any], key: str) -> int:
    value = resource[key]
    return int(value, 0) if isinstance(value, str) else int(value)


def glyph_slots(
    payload: bytes, resources: Mapping[str, Mapping[str, Any]]
) -> Optional[Set[Tuple[str, int]]]:
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        return None
    slots: Set[Tuple[str, int]] = set()
    for token in tokenization.tokens:
        assert token.glyph_class is not None
        resource = resources[token.glyph_class]
        slot = code_unit_slot(
            int.from_bytes(token.raw, "little"),
            token.glyph_class,
            int(resource["resource_size"]),
        )
        if slot is None:
            return None
        slots.add((token.glyph_class, slot))
    return slots


def build_contract(
    rom: bytes,
    record: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]],
) -> Tuple[PocContract, bytes, Tokenization]:
    offset = int(record["offset"])
    payload, _terminator = source_payload(rom, offset)
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        raise PocReject(f"POC source record is opaque or unaligned: 0x{offset:x}")
    slots = glyph_slots(payload, resources)
    if slots is None:
        raise PocReject(f"POC source record has an unaddressable glyph: 0x{offset:x}")
    signature = tuple(
        (str(row["kind"]), row["glyph_class"], int(row["layout_width"]))
        for row in tokenization.signature()
    )
    contract = PocContract(
        source_offset=offset,
        source_hash=sha256(payload),
        source_length=len(payload),
        source_width=tokenization.line_width,
        token_signature=signature,
        required_slots=tuple(sorted(slots)),
        max_width=tokenization.line_width,
    )
    return contract, payload, tokenization


def _slot_is_nonzero(
    rom: bytes, resources: Mapping[str, Mapping[str, Any]], glyph_class: str, slot: int
) -> bool:
    resource = resources[glyph_class]
    begin = _resource_int(resource, "resource_start") - ROM_BASE + slot * int(resource["stride"])
    end = begin + int(resource["glyph_payload_bytes"])
    return any(rom[begin:end])


def validate_candidate(
    contract: PocContract,
    candidate_payload: bytes,
    rom: bytes,
    resources: Mapping[str, Mapping[str, Any]],
    *,
    declared_source_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Return metadata or all rejection reasons; never silently relaxes rules."""
    reasons: List[str] = []
    source_hash = sha256(candidate_payload)
    if (declared_source_hash or contract.source_hash) != contract.source_hash:
        reasons.append("source_hash_mismatch")
    tokenization = tokenize_payload(candidate_payload)
    summary = token_summary(tokenization)
    candidate_signature = tuple(
        (str(row["kind"]), row["glyph_class"], int(row["layout_width"]))
        for row in tokenization.signature()
    )
    if not tokenization.supported:
        reasons.append("opaque_token_or_unaligned_record")
    if candidate_signature != contract.token_signature:
        reasons.append("control_token_or_glyph_class_mismatch")
    if len(candidate_payload) != contract.source_length:
        reasons.append("variable_length_rejected")
    if tokenization.line_width != contract.source_width or tokenization.line_width > contract.max_width:
        reasons.append("line_width_rejected")

    candidate_slots = glyph_slots(candidate_payload, resources)
    missing: List[Tuple[str, int]] = []
    new_slots: Set[Tuple[str, int]] = set()
    if candidate_slots is None:
        reasons.append("missing_glyph")
    else:
        for glyph_class, slot in sorted(candidate_slots):
            if not _slot_is_nonzero(rom, resources, glyph_class, slot):
                if (glyph_class, slot) not in set(contract.required_slots):
                    missing.append((glyph_class, slot))
                    new_slots.add((glyph_class, slot))
        if missing:
            reasons.append("missing_glyph")
        new_by_class = {
            glyph_class: sum(1 for item in new_slots if item[0] == glyph_class)
            for glyph_class in {item[0] for item in new_slots}
        }
        for glyph_class, count in new_by_class.items():
            capacity = int(resources[glyph_class]["conservative_new_slot_capacity"])
            if count > capacity:
                reasons.append("capacity_exceeded")

    return {
        "accepted": not reasons,
        "reasons": sorted(set(reasons)),
        "candidate_hash": source_hash,
        "candidate_length": len(candidate_payload),
        "candidate_summary": summary,
        "missing_glyph_slots": [
            {"glyph_class": glyph_class, "slot": slot} for glyph_class, slot in missing
        ],
    }


def no_op_roundtrip(payload: bytes) -> Dict[str, Any]:
    tokenization = tokenize_payload(payload)
    if not tokenization.supported:
        raise PocReject("no-op roundtrip refuses opaque or unaligned record")
    original = payload + b"\x00"
    encoded = encode_tokens(tokenization, include_terminator=True)
    return {
        "accepted": encoded == original,
        "byte_identical": encoded == original,
        "source_length_with_terminator": len(original),
        "encoded_length_with_terminator": len(encoded),
        "source_hash": sha256(payload),
        "encoded_hash": sha256(encoded[:-1]),
        "encoded_record_hash": sha256(encoded),
    }


def run_poc(
    rom: bytes,
    records: Sequence[Mapping[str, Any]],
    *,
    offsets: Sequence[int] = POC_RECORDS,
) -> Dict[str, Any]:
    resources = resource_capacity(rom, records)
    selected = {int(record["offset"]): record for record in records}
    contracts: List[PocContract] = []
    payloads: Dict[int, bytes] = {}
    tokenizations: Dict[int, Tokenization] = {}
    for offset in offsets:
        if offset not in selected:
            raise PocReject(f"POC record missing: 0x{offset:x}")
        contract, payload, tokenization = build_contract(rom, selected[offset], resources)
        contracts.append(contract)
        payloads[offset] = payload
        tokenizations[offset] = tokenization
    lengths = {contract.source_length for contract in contracts}
    if len(lengths) != 1:
        raise PocReject("POC records must have equal source payload length")

    rows: List[Dict[str, Any]] = []
    for contract in contracts:
        payload = payloads[contract.source_offset]
        validation = validate_candidate(
            contract,
            payload,
            rom,
            resources,
            declared_source_hash=contract.source_hash,
        )
        roundtrip = no_op_roundtrip(payload)
        if not validation["accepted"] or not roundtrip["byte_identical"]:
            raise PocReject(f"no-op POC failed at 0x{contract.source_offset:x}")
        rows.append(
            {
                **contract.summary(),
                "no_op_roundtrip": {**roundtrip, "validation": validation},
            }
        )
    return {
        "schema": "super-robot-taisen-d-m17-poc-v1",
        "game_code": "A6SJ",
        "record_count": len(rows),
        "equal_source_length": len(lengths) == 1,
        "records": rows,
        "rejection_contract": [
            "source_hash_mismatch",
            "opaque_token_or_unaligned_record",
            "control_token_or_glyph_class_mismatch",
            "line_width_rejected",
            "missing_glyph",
            "capacity_exceeded",
            "variable_length_rejected",
        ],
        "translation_started": False,
        "rom_modified": False,
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("source_table", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    records = read_source_records(args.source_table)
    report = run_poc(rom, records)
    write_report(args.output, report)
    print(
        f"poc_records={report['record_count']} equal_source_length={report['equal_source_length']} "
        f"translation_started={report['translation_started']} output={args.output}"
    )


if __name__ == "__main__":
    main()
