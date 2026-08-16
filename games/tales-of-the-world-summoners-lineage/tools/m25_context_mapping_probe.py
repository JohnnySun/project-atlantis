#!/usr/bin/env python3
"""Metadata-only audit of two context-derived A9PJ glyph candidates.

The visible name-entry layout and direct static renderer candidates provide
useful evidence for ``0x000C`` (long-vowel mark) and ``0x00A8`` (small
katakana-tsu).  This probe keeps both at a context-provisional tier: it emits
table positions, record hashes, bitmap counts and direct-candidate occurrence
counts, never source strings or OCR output, and never changes the M21
confirmed mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m20_keyboard_codepage_probe import read_row
from m20_text_callsite_probe import NULL_ENTRY, argument_provenance, scan_callsites
from m20_text_record_probe import (
    EXPECTED_ROM_SHA256,
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_STRIDE,
)
from m21_source_decoder import stream_units


PROBE_VERSION = "m25-context-mapping-probe-20260816.v1"
ROM_BASE = 0x08000000
CONTEXT_PROVISIONAL = {
    0x000C: {
        "unicode_candidate": "ー",
        "reason": "hiragana-page punctuation slot plus repeated direct-candidate phrase context",
    },
    0x00A8: {
        "unicode_candidate": "ッ",
        "reason": "katakana-page small-kana slot plus repeated direct-candidate phrase context",
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_metadata(data: bytes, code_unit: int) -> dict[str, object]:
    offset = FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE
    record = data[offset:offset + FONT_RECORD_STRIDE]
    if len(record) != FONT_RECORD_STRIDE:
        return {
            "record_bus_address": f"0x{ROM_BASE + offset:08X}",
            "record_file_offset": f"0x{offset:X}",
            "record_available": False,
            "rows_emitted": False,
        }
    return {
        "record_bus_address": f"0x{ROM_BASE + offset:08X}",
        "record_file_offset": f"0x{offset:X}",
        "record_sha256": sha256(record),
        "record_available": True,
        "record_nonzero_bytes": sum(byte != 0 for byte in record),
        "record_ink_bit_count": sum(bin(byte).count("1") for byte in record),
        "rows_emitted": False,
    }


def table_hits(data: bytes, code_unit: int) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for row in range(4):
        try:
            values = read_row(data, row, 65)
        except ValueError:
            return hits
        for selection, value in enumerate(values):
            if value == code_unit:
                hits.append({"table_row": row, "selection_index": selection})
    return hits


def direct_occurrences(data: bytes, code_unit: int) -> dict[str, object]:
    target_counts: dict[int, int] = {}
    caller_count = 0
    occurrence_count = 0
    for callsite in scan_callsites(data, NULL_ENTRY):
        provenance = argument_provenance(data, callsite)
        pointer_value = provenance["simple_register_values"].get("r2")
        if not isinstance(pointer_value, str):
            continue
        pointer = int(pointer_value, 16)
        if not ROM_BASE <= pointer < ROM_BASE + len(data):
            continue
        target = pointer - ROM_BASE
        units = stream_units(data, target, max_units=0x400)
        if 0 in units:
            units = units[:units.index(0) + 1]
        occurrences = units.count(code_unit)
        if occurrences:
            caller_count += 1
            occurrence_count += occurrences
            target_counts[target] = target_counts.get(target, 0) + occurrences
    return {
        "direct_caller_count": caller_count,
        "direct_occurrence_count": occurrence_count,
        "direct_target_count": len(target_counts),
        "direct_target_file_offsets": [f"0x{target:X}" for target in sorted(target_counts)],
        "source_text_emitted": False,
    }


def probe(data: bytes) -> dict[str, object]:
    candidates = []
    for code_unit, evidence in CONTEXT_PROVISIONAL.items():
        candidates.append(
            {
                "code_unit": f"0x{code_unit:04X}",
                "unicode_candidate": evidence["unicode_candidate"],
                "identity_status": "context-provisional",
                "evidence": evidence["reason"],
                "keyboard_table_hits": table_hits(data, code_unit),
                "record": record_metadata(data, code_unit),
                "direct_occurrences": direct_occurrences(data, code_unit),
            }
        )
    return {
        "probe_version": PROBE_VERSION,
        "rom": {
            "sha256": sha256(data),
            "expected_a9pj_sha256_match": sha256(data) == EXPECTED_ROM_SHA256,
            "source_text_emitted": False,
        },
        "candidates": candidates,
        "gate": {
            "confirmed_identity_count_added": 0,
            "runtime_scene_context_confirmed": False,
            "control_semantics_confirmed": False,
            "eligible_for_ledger": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"probe_version": PROBE_VERSION, "output": str(args.output), "source_text_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
