#!/usr/bin/env python3
"""Private A9PJ decoder for direct static null-renderer callsites.

M21 intentionally scanned a broad pointer pool.  This narrower candidate
decoder keeps only ROM literal pointers loaded in callers of the already
identified ``0x080063E0`` null-terminated consumer.  It is useful for local
font/context work, but a static BL caller is not runtime scene proof, so every
row remains unclassified and ineligible for the translation ledger.

The JSONL output contains decoded candidate text and therefore must be written
only to an ignored/private path.  Stdout contains counts and hashes only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from m20_text_callsite_probe import (
    NULL_ENTRY,
    argument_provenance,
    scan_callsites,
)
from m20_text_record_probe import (
    EXPECTED_ROM_SHA256,
    read_halfword_stream,
)
from m21_source_decoder import (
    DEFAULT_MAX_UNITS,
    build_keyboard_map,
    decode_units,
    sha256,
    stream_units,
)


DECODER_VERSION = "m24-direct-callsite-decoder-20260816.v1"
ROM_BASE = 0x08000000


def stable_direct_candidate_id(callsite: int, target: int, byte_length: int) -> str:
    identity = (
        f"a9pj:{DECODER_VERSION}:callsite={callsite:x}:target={target:x}:len={byte_length:x}"
    )
    return hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def direct_callsite_rows(data: bytes, *, max_units: int = DEFAULT_MAX_UNITS) -> list[dict[str, object]]:
    mapping = build_keyboard_map(data)
    rows: list[dict[str, object]] = []
    for callsite in scan_callsites(data, NULL_ENTRY):
        provenance = argument_provenance(data, callsite)
        pointer_value = provenance["simple_register_values"].get("r2")
        if not isinstance(pointer_value, str):
            continue
        pointer = int(pointer_value, 16)
        if not ROM_BASE <= pointer < ROM_BASE + len(data):
            continue
        target = pointer - ROM_BASE
        profile = read_halfword_stream(data, target, max_units=max_units)
        if not profile["terminated_by_0000"]:
            continue
        decoded = decode_units(stream_units(data, target, max_units), mapping)
        byte_length = int(profile["byte_length"])
        rows.append(
            {
                "string_id": stable_direct_candidate_id(callsite, target, byte_length),
                "locale": "ja",
                "text": decoded["text"],
                "source_text_sha256": sha256(decoded["text"].encode("utf-8")),
                "provenance": (
                    f"rom-sha256={sha256(data)};consumer=0x{NULL_ENTRY:08X};"
                    f"caller=0x{ROM_BASE + callsite:08X};file-offset=0x{target:X};"
                    f"pointer-file-offset=0x{callsite:X};terminator=0x0000;"
                    f"decoder={DECODER_VERSION};runtime-context=none"
                ),
                "decoder_version": DECODER_VERSION,
                "source_status": "candidate-direct-static-caller-partial-codepage",
                "runtime_context": False,
                "scene_role": "unclassified",
                "consumer_entry": f"0x{NULL_ENTRY:08X}",
                "caller_bus_address": f"0x{ROM_BASE + callsite:08X}",
                "stream_file_offset": f"0x{target:X}",
                "stream_sha256": profile["stream_sha256"],
                "control_candidates": decoded["control_candidates"],
                "unresolved_code_units": decoded["unresolved_code_units"],
                "mapping_status_counts": decoded["mapping_status_counts"],
                "complete_codepage": decoded["complete_codepage"],
                "eligible_for_ledger": False,
                "source_text_emitted": True,
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def summary(data: bytes, rows: list[dict[str, object]]) -> dict[str, object]:
    unresolved = Counter(
        unit
        for row in rows
        for unit in row["unresolved_code_units"]
    )
    controls = Counter(
        control
        for row in rows
        for control in row["control_candidates"]
    )
    return {
        "decoder_version": DECODER_VERSION,
        "rom_sha256": sha256(data),
        "expected_a9pj_sha256_match": sha256(data) == EXPECTED_ROM_SHA256,
        "null_consumer": f"0x{NULL_ENTRY:08X}",
        "direct_rows_emitted": len(rows),
        "complete_codepage_rows": sum(bool(row["complete_codepage"]) for row in rows),
        "partial_or_unresolved_rows": sum(not bool(row["complete_codepage"]) for row in rows),
        "distinct_stream_targets": len({row["stream_file_offset"] for row in rows}),
        "distinct_unresolved_code_units": len(unresolved),
        "control_candidate_counts": dict(sorted(controls.items())),
        "runtime_context_confirmed": False,
        "scene_roles_confirmed": False,
        "eligible_for_ledger": False,
        "source_text_rows_are_local_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=DEFAULT_MAX_UNITS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_units <= 0:
        parser.error("max-units must be positive")
    data = args.rom.read_bytes()
    rows = direct_callsite_rows(data, max_units=args.max_units)
    write_jsonl(args.output, rows)
    print(json.dumps({**summary(data, rows), "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
