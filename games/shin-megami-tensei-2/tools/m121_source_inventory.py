#!/usr/bin/env python3
"""Bounded inventory of source candidates at named A5TJ text readers.

M1.21 consumes only the already-indexed direct callers of the M1.18 readers.
It groups caller-local r0 literal candidates and runtime/table-derived forms,
then probes each candidate for a bounded 16-bit terminator.  This is an
inventory of edges, not a ROM string scan or a translation source table.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import ROM_BASE, address_metadata, hex_address, sha256  # noqa: E402
from m118_codeunit_font import (  # noqa: E402
    CODEUNIT_STRING_LARGE,
    CODEUNIT_STRING_SMALL,
    _function_end,
)
from m119_source_family import (  # noqa: E402
    MAX_DIRECT_CALLERS,
    _direct_callers,
    _source_terminator_metadata,
    _window,
)


SCHEMA = "smt2.m1.21.source-inventory.v1"
MAX_CANDIDATES = 128


def _entry_address(item: dict[str, object]) -> int | None:
    boundary = item.get("caller_function")
    if not isinstance(boundary, dict):
        return None
    entry = boundary.get("entry")
    if not isinstance(entry, dict):
        return None
    value = entry.get("address")
    if not isinstance(value, str):
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def _candidate_values(item: dict[str, object]) -> list[int]:
    evidence = item.get("argument_evidence")
    if not isinstance(evidence, dict):
        return []
    result: list[int] = []
    for candidate in evidence.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("kind") != "rom_literal_r0_candidate":
            continue
        value = candidate.get("value")
        if not isinstance(value, dict):
            continue
        address = value.get("address")
        if not isinstance(address, str):
            continue
        try:
            parsed = int(address, 16)
        except ValueError:
            continue
        if ROM_BASE <= parsed:
            result.append(parsed)
    return result


def _caller_inventory(data: bytes, target: int) -> list[dict[str, object]]:
    caller_items = _direct_callers(data, target)
    grouped: dict[int, dict[str, object]] = {}
    for item in caller_items:
        entry = _entry_address(item)
        if entry is None:
            continue
        group = grouped.setdefault(
            entry,
            {
                "caller_function": item["caller_function"],
                "reader_target": hex_address(target),
                "reader_callsite_count": 0,
                "callsite_addresses": [],
                "candidate_pointers": set(),
                "stack_buffer_callsite_count": 0,
                "runtime_or_unknown_callsite_count": 0,
            },
        )
        group["reader_callsite_count"] = int(group["reader_callsite_count"]) + 1
        group["callsite_addresses"].append(item["callsite"])
        values = _candidate_values(item)
        group["candidate_pointers"].update(values)
        evidence = item.get("argument_evidence")
        candidates = evidence.get("candidates", []) if isinstance(evidence, dict) else []
        kinds = {
            candidate.get("kind")
            for candidate in candidates
            if isinstance(candidate, dict)
        }
        if "stack_buffer_r0_candidate" in kinds:
            group["stack_buffer_callsite_count"] = int(
                group["stack_buffer_callsite_count"]
            ) + 1
        if not values and "stack_buffer_r0_candidate" not in kinds:
            group["runtime_or_unknown_callsite_count"] = int(
                group["runtime_or_unknown_callsite_count"]
            ) + 1

    result: list[dict[str, object]] = []
    for entry in sorted(grouped):
        group = grouped[entry]
        pointers = sorted(group.pop("candidate_pointers"))[:MAX_CANDIDATES]
        pointer_records = []
        for pointer in pointers:
            pointer_records.append(
                {
                    "source_pointer": address_metadata(pointer, len(data)),
                    "bounded_probe": _source_terminator_metadata(data, pointer, None),
                }
            )
        term_counts = Counter(
            str(item["bounded_probe"].get("termination"))
            for item in pointer_records
            if isinstance(item.get("bounded_probe"), dict)
        )
        group["candidate_pointer_count"] = len(pointers)
        group["candidate_pointer_region_counts"] = dict(
            sorted(
                Counter(
                    str(item["source_pointer"].get("region"))
                    for item in pointer_records
                ).items()
            )
        )
        group["termination_counts"] = dict(sorted(term_counts.items()))
        group["terminated_candidate_count"] = sum(
            int(
                item["bounded_probe"].get("termination")
                in {"zero_0000", "terminator_0301"}
            )
            for item in pointer_records
        )
        group["records"] = pointer_records
        group["source_identity_confirmed"] = False
        result.append(group)
    return result


def static_report(data: bytes) -> dict[str, object]:
    small = _caller_inventory(data, CODEUNIT_STRING_SMALL)
    large = _caller_inventory(data, CODEUNIT_STRING_LARGE)
    families = small + large
    all_records = [
        record
        for family in families
        for record in family.get("records", [])
        if isinstance(record, dict)
    ]
    termination_counts = Counter(
        str(record["bounded_probe"].get("termination"))
        for record in all_records
        if isinstance(record.get("bounded_probe"), dict)
    )
    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "known_reader_direct_callers_only_bounded_pointer_inventory",
            "direct_caller_cap": MAX_DIRECT_CALLERS,
            "per_pointer_probe_limit": 0x100,
            "full_rom_string_scan": False,
            "full_rom_glyph_scan": False,
            "raw_source_emitted": False,
            "decoded_text_emitted": False,
            "translation_ledger_created": False,
        },
        "reader_targets": {
            "small": hex_address(CODEUNIT_STRING_SMALL),
            "large": hex_address(CODEUNIT_STRING_LARGE),
        },
        "caller_families": families,
        "summary": {
            "caller_family_count": len(families),
            "candidate_pointer_count_with_duplicates": len(all_records),
            "candidate_termination_counts": dict(sorted(termination_counts.items())),
            "terminated_candidate_count_with_duplicates": sum(
                int(
                    record["bounded_probe"].get("termination")
                    in {"zero_0000", "terminator_0301"}
                )
                for record in all_records
                if isinstance(record.get("bounded_probe"), dict)
            ),
        },
        "conclusions": {
            "confirmed": [
                "inventory_is_limited_to_named_reader_direct_callers",
                "caller_local_literal_and_stack_or_runtime_forms_are_separated",
                "each_candidate_probe_is_bounded_to_0x100_bytes",
            ],
            "provisional": [
                "terminated_candidate_groups_are_text_source_family_candidates",
                "caller_function_is_a_category_boundary_but_not_semantic_proof",
            ],
            "unknown": [
                "natural_scene_and_runtime_selection",
                "main_event_demon_skill_item_system_category_names",
                "unicode_identity_and_codepage",
                "control_codes_and_width_budget",
                "reinsert_and_roundtrip_contract",
            ],
            "translation_ledger": "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = static_report(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
