#!/usr/bin/env python3
"""Expose the bounded, existing-slot-only wide glyph policy.

The contract accepts only Unicode identities already established by strict
source context and mapped to an initialized existing slot.  It deliberately
has no allocator, font expansion, or ROM patch path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


class WidePolicyReject(ValueError):
    """A wide target is not proven reusable."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_identity_map(path: Path) -> Dict[int, Dict[str, Any]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("source_policy", {}).get("source_text_emitted"):
        raise WidePolicyReject("source_text_emitted")
    identities = report.get("identities")
    if not isinstance(identities, list) or not identities:
        raise WidePolicyReject("identity_map_missing")
    result: Dict[int, Dict[str, Any]] = {}
    slots: set[int] = set()
    units: set[int] = set()
    for row in identities:
        if not isinstance(row, Mapping):
            raise WidePolicyReject("identity_row_invalid")
        try:
            codepoint = int(str(row["unicode"])[2:], 16)
            code_unit = int(str(row["code_unit_little_endian"]), 16)
            slot = int(row["slot"])
            glyph_hash = str(row["glyph_sha256"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WidePolicyReject("identity_row_invalid") from exc
        if codepoint in result or code_unit in units or slot in slots:
            raise WidePolicyReject("wide_identity_collision")
        if len(glyph_hash) != 64:
            raise WidePolicyReject("glyph_hash_invalid")
        result[codepoint] = {
            "codepoint": f"U+{codepoint:04X}",
            "code_unit_little_endian": f"0x{code_unit:04X}",
            "slot": slot,
            "glyph_sha256": glyph_hash,
            "runtime_status": str(row.get("runtime_status", "static_source_context_only")),
        }
        units.add(code_unit)
        slots.add(slot)
    return result


def resolve_existing_wide(codepoint: int, identity_map: Mapping[int, Mapping[str, Any]]) -> Mapping[str, Any]:
    row = identity_map.get(codepoint)
    if row is None:
        raise WidePolicyReject(f"unmapped_target_codepoint:U+{codepoint:04X}")
    return row


def build_report(identity_report: Mapping[str, Any], identity_map: Mapping[int, Mapping[str, Any]]) -> Dict[str, Any]:
    source = identity_report.get("source_corpus", {})
    runtime = identity_report.get("runtime_boundary", {})
    return {
        "schema": "super-robot-taisen-d-m4-wide-reuse-contract-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "source_safe_hashes_only": True},
        "identity_map": {
            "count": len(identity_map),
            "codepoint_index_sha256": str(source.get("codepoint_index_sha256", "")),
            "code_unit_index_sha256": str(source.get("code_unit_index_sha256", "")),
            "slot_index_sha256": str(source.get("slot_index_sha256", "")),
            "runtime_confirmed_identity_count": int(runtime.get("bounded_runtime_confirmed_identity_count", 0)),
            "static_only_identity_count": int(runtime.get("static_source_context_only_count", 0)),
        },
        "policy": {
            "accepted": "only mapped existing wide identity",
            "new_wide_slot_allocation": "reject",
            "unmapped_target_codepoint": "reject",
            "font_expansion": "reject_pending_resource_strategy",
            "rom_modified": False,
        },
        "gate": {
            "one_to_one_codepoint_code_unit_slot": True,
            "initialized_existing_slots": True,
            "unknown_target_rejectable": True,
            "wide_new_slots_zero": True,
            "source_text_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.audit.read_text(encoding="utf-8"))
        identity_map = load_identity_map(args.audit)
        output = build_report(report, identity_map)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m4_wide_contract_rejected={exc}")
        return 2
    print(f"m4_wide_contract=accepted identities={output['identity_map']['count']} new_wide_slots=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
