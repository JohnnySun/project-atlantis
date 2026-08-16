#!/usr/bin/env python3
"""Private direct-caller decoder with explicitly provisional glyph overlays.

M21 remains the conservative baseline decoder.  M27 overlays only the
keyboard-layout/context candidates independently recorded by M25/M26, then
decodes the 46 direct static caller rows for local reading and future runtime
alignment.  Every emitted row remains unclassified and ineligible for the
ledger; this tool is not permission to translate candidate text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from m20_text_callsite_probe import NULL_ENTRY, argument_provenance, scan_callsites
from m20_text_record_probe import EXPECTED_ROM_SHA256, read_halfword_stream
from m21_source_decoder import (
    DEFAULT_MAX_UNITS,
    build_keyboard_map,
    decode_units,
    sha256,
    stream_units,
)


DECODER_VERSION = "m27-provisional-decoder-20260816.v1"
ROM_BASE = 0x08000000
PROVISIONAL_OVERLAY = {
    0x0006: ("・", "keyboard-layout-provisional"),
    0x0008: ("?", "keyboard-layout-provisional"),
    0x0009: ("!", "keyboard-layout-provisional"),
    0x000A: ("＿", "keyboard-layout-provisional"),
    0x000C: ("ー", "context-provisional-keyboard-punctuation"),
    0x000D: ("/", "keyboard-layout-provisional"),
    0x00A8: ("ッ", "context-provisional-small-kana"),
}


def overlay_mapping(data: bytes) -> dict[int, dict[str, object]]:
    try:
        mapping = build_keyboard_map(data)
    except ValueError:
        mapping = {}
    for code_unit, (text, status) in PROVISIONAL_OVERLAY.items():
        if code_unit not in mapping:
            mapping[code_unit] = {
                "text": text,
                "mapping_status": status,
                "evidence": "M25/M26 metadata-only candidate overlay",
            }
    return mapping


def stable_id(callsite: int, target: int, byte_length: int) -> str:
    identity = f"a9pj:{DECODER_VERSION}:caller={callsite:x}:target={target:x}:len={byte_length:x}"
    return hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def direct_rows(data: bytes, *, max_units: int = DEFAULT_MAX_UNITS) -> list[dict[str, object]]:
    mapping = overlay_mapping(data)
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
        bounded_units = stream_units(data, target, max_units)
        if 0 in bounded_units:
            bounded_units = bounded_units[:bounded_units.index(0) + 1]
        rows.append(
            {
                "string_id": stable_id(callsite, target, int(profile["byte_length"])),
                "locale": "ja",
                "text": decoded["text"],
                "source_text_sha256": sha256(decoded["text"].encode("utf-8")),
                "provenance": (
                    f"rom-sha256={sha256(data)};consumer=0x{NULL_ENTRY:08X};"
                    f"caller=0x{ROM_BASE + callsite:08X};file-offset=0x{target:X};"
                    f"decoder={DECODER_VERSION};runtime-context=none"
                ),
                "decoder_version": DECODER_VERSION,
                "source_status": "candidate-direct-static-caller-provisional-overlay",
                "runtime_context": False,
                "scene_role": "unclassified",
                "mapping_status_counts": decoded["mapping_status_counts"],
                "control_candidates": decoded["control_candidates"],
                "unresolved_code_units": decoded["unresolved_code_units"],
                "complete_codepage": decoded["complete_codepage"],
                "provisional_overlay_code_units": [
                    f"0x{unit:04X}"
                    for unit in PROVISIONAL_OVERLAY
                    if unit in bounded_units
                ],
                "caller_bus_address": f"0x{ROM_BASE + callsite:08X}",
                "stream_file_offset": f"0x{target:X}",
                "stream_sha256": profile["stream_sha256"],
                "eligible_for_ledger": False,
                "source_text_emitted": True,
            }
        )
    return rows


def summary(data: bytes, rows: list[dict[str, object]]) -> dict[str, object]:
    unresolved = Counter(unit for row in rows for unit in row["unresolved_code_units"])
    overlay = Counter(unit for row in rows for unit in row["provisional_overlay_code_units"])
    return {
        "decoder_version": DECODER_VERSION,
        "rom_sha256": sha256(data),
        "expected_a9pj_sha256_match": sha256(data) == EXPECTED_ROM_SHA256,
        "rows_emitted": len(rows),
        "complete_codepage_rows": sum(bool(row["complete_codepage"]) for row in rows),
        "partial_or_unresolved_rows": sum(not bool(row["complete_codepage"]) for row in rows),
        "distinct_unresolved_code_units": len(unresolved),
        "overlay_occurrence_row_counts": dict(sorted(overlay.items())),
        "overlay_mapping_status": {
            f"0x{unit:04X}": status for unit, (_, status) in PROVISIONAL_OVERLAY.items()
        },
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
    rows = direct_rows(data, max_units=args.max_units)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({**summary(data, rows), "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
