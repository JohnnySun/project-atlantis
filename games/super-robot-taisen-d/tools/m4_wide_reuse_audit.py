#!/usr/bin/env python3
"""Audit reusable existing wide glyphs without allocating a wide slot.

The source corpus is strict Shift-JIS, so a source-context character provides
an identity-bearing code unit without guessing from a bitmap.  This tool
records that bounded evidence and the existing resource slot only.  It never
creates a target mapping, patches a ROM, or claims that static identity is
runtime validated.  A future encoder may use only codepoints present in this
audit; all other wide target codepoints must remain fail-closed until a
resource expansion strategy is proven.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

try:
    from m17_layout import M17Error, ROM_BASE, code_unit_slot, read_source_records
except ImportError:  # pragma: no cover - direct invocation from another cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from m17_layout import M17Error, ROM_BASE, code_unit_slot, read_source_records


EXPECTED_ROM_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_RECORD_COUNT = 2325
WIDE_RESOURCE_START = 0x08120DBC
WIDE_RESOURCE_END = 0x0814F664
WIDE_STRIDE = 26
WIDE_PAYLOAD_BYTES = 24
# M1.6 confirmed both a narrow and a wide identity.  This audit is wide-only,
# so only the wide code unit is counted as runtime-confirmed here.
RUNTIME_CONFIRMED_WIDE_CODE_UNITS = {0xDA88}


class WideReuseError(ValueError):
    """A wide reuse audit gate rejected an input or identity collision."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_ints(values: Iterable[int]) -> str:
    return sha256(",".join(str(value) for value in values).encode("ascii"))


def _source_table_guard(path: Path) -> None:
    if not path.name.endswith("-decoded.jsonl"):
        raise WideReuseError("refusing non-local-source-table filename")


def _record_index_hash(record_ids: Iterable[int]) -> str:
    return hash_ints(sorted(set(record_ids)))


def collect_source_identities(records: Sequence[Mapping[str, Any]]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """Collect one identity row per strict source Unicode/code-unit pair."""

    by_codepoint: Dict[int, Set[int]] = defaultdict(set)
    occurrences: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for row in records:
        record_id = int(row["offset"])
        text = str(row["text"])
        try:
            text.encode("shift_jis", errors="strict")
        except UnicodeError as exc:
            raise WideReuseError(f"source_not_strict_shift_jis: 0x{record_id:x}") from exc
        for character in text:
            encoded = character.encode("shift_jis", errors="strict")
            if len(encoded) != 2 or encoded[0] <= 0x87:
                continue
            code_unit = encoded[0] | (encoded[1] << 8)
            by_codepoint[ord(character)].add(code_unit)
            occurrences[(ord(character), code_unit)].append(record_id)

    collisions = {
        codepoint: sorted(units)
        for codepoint, units in by_codepoint.items()
        if len(units) != 1
    }
    if collisions:
        raise WideReuseError(f"codepoint_to_code_unit_collision: {len(collisions)}")

    identities: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for (codepoint, code_unit), record_ids in sorted(occurrences.items()):
        identities[(codepoint, code_unit)] = {
            "codepoint": codepoint,
            "code_unit": code_unit,
            "occurrence_count": len(record_ids),
            "record_count": len(set(record_ids)),
            "record_index_sha256": _record_index_hash(record_ids),
            "identity_basis": "strict_shift_jis_source_context",
            "runtime_status": (
                "runtime_confirmed_bounded"
                if code_unit in RUNTIME_CONFIRMED_WIDE_CODE_UNITS
                else "static_source_context_only"
            ),
        }
    return identities


def audit(rom: bytes, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if sha256(rom) != EXPECTED_ROM_SHA256:
        raise WideReuseError("rom_hash_mismatch")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise WideReuseError(f"record_count_mismatch: {len(records)}")
    if WIDE_RESOURCE_END <= WIDE_RESOURCE_START:
        raise WideReuseError("wide_resource_range_invalid")
    resource_size = WIDE_RESOURCE_END - WIDE_RESOURCE_START
    if resource_size % WIDE_STRIDE:
        raise WideReuseError("wide_resource_stride_mismatch")

    identities = collect_source_identities(records)
    rows: List[Dict[str, Any]] = []
    for (codepoint, code_unit), identity in identities.items():
        slot = code_unit_slot(code_unit, "wide", resource_size)
        if slot is None:
            raise WideReuseError(f"wide_code_unit_out_of_range: 0x{code_unit:04x}")
        begin = WIDE_RESOURCE_START - ROM_BASE + slot * WIDE_STRIDE
        glyph = rom[begin : begin + WIDE_PAYLOAD_BYTES]
        if len(glyph) != WIDE_PAYLOAD_BYTES or not any(glyph):
            raise WideReuseError(f"wide_slot_not_initialized: {slot}")
        row = dict(identity)
        row.update(
            {
                "codepoint": f"U+{codepoint:04X}",
                "code_unit_little_endian": f"0x{code_unit:04X}",
                "slot": slot,
                "glyph_payload_bytes": WIDE_PAYLOAD_BYTES,
                "glyph_sha256": sha256(glyph),
                "glyph_nonzero_bytes": sum(byte != 0 for byte in glyph),
            }
        )
        row.pop("codepoint", None)
        row["unicode"] = f"U+{codepoint:04X}"
        rows.append(row)

    runtime_rows = [row for row in rows if row["runtime_status"] == "runtime_confirmed_bounded"]
    static_rows = [row for row in rows if row["runtime_status"] == "static_source_context_only"]
    codepoint_index = [int(row["unicode"][2:], 16) for row in rows]
    slot_index = [int(row["slot"]) for row in rows]
    code_unit_index = [int(row["code_unit_little_endian"], 16) for row in rows]
    if len(set(codepoint_index)) != len(codepoint_index):
        raise WideReuseError("unicode_identity_collision")
    if len(set(code_unit_index)) != len(code_unit_index):
        raise WideReuseError("code_unit_identity_collision")
    if len(set(slot_index)) != len(slot_index):
        raise WideReuseError("wide_slot_identity_collision")

    return {
        "schema": "super-robot-taisen-d-m4-wide-reuse-audit-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "source_safe_hashes_only": True,
            "identity_policy": "strict Shift-JIS source context; never bitmap-position inference",
        },
        "rom": {"sha256": sha256(rom)},
        "resource": {
            "start": f"0x{WIDE_RESOURCE_START:08X}",
            "end_exclusive": f"0x{WIDE_RESOURCE_END:08X}",
            "stride": WIDE_STRIDE,
            "glyph_payload_bytes": WIDE_PAYLOAD_BYTES,
            "physical_slots": resource_size // WIDE_STRIDE,
            "new_slot_capacity": 0,
        },
        "source_corpus": {
            "record_count": len(records),
            "wide_identity_count": len(rows),
            "wide_occurrence_count": sum(int(row["occurrence_count"]) for row in rows),
            "codepoint_index_sha256": hash_ints(sorted(codepoint_index)),
            "code_unit_index_sha256": hash_ints(sorted(code_unit_index)),
            "slot_index_sha256": hash_ints(sorted(slot_index)),
            "one_to_one_identity": True,
        },
        "runtime_boundary": {
            "bounded_runtime_confirmed_identity_count": len(runtime_rows),
            "bounded_runtime_confirmed_code_units": [
                f"0x{code_unit:04X}" for code_unit in sorted(RUNTIME_CONFIRMED_WIDE_CODE_UNITS)
            ],
            "static_source_context_only_count": len(static_rows),
            "runtime_status_policy": "static rows are not runtime proof",
        },
        "reusable_existing_wide_policy": {
            "allowed": "only codepoints present in this source-context map and mapped to initialized existing slots",
            "new_wide_slot_allocation": "reject",
            "unmapped_target_codepoint": "reject",
            "font_expansion": "not implemented",
        },
        "identities": rows,
        "gate": {
            "rom_hash_match": True,
            "source_record_count_match": True,
            "strict_source_context": True,
            "initialized_existing_slots": True,
            "codepoint_code_unit_slot_one_to_one": True,
            "wide_new_slot_capacity_zero": True,
            "source_text_emitted": False,
            "rom_modified": False,
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
        report = audit(args.rom.read_bytes(), records)
    except (WideReuseError, M17Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"m4_wide_reuse_rejected={exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "m4_wide_reuse=accepted identities={identities} occurrences={occurrences} "
        "runtime_confirmed={runtime} new_wide_slots=0".format(
            identities=report["source_corpus"]["wide_identity_count"],
            occurrences=report["source_corpus"]["wide_occurrence_count"],
            runtime=report["runtime_boundary"]["bounded_runtime_confirmed_identity_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
