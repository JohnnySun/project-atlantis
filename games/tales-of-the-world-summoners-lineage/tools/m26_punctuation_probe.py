#!/usr/bin/env python3
"""Metadata-only audit of A9PJ keyboard punctuation candidates.

The M19 private keyboard render exposes a fixed punctuation cluster.  M26
crosses its clean-ROM table entries with the 24-byte record metadata and
bounded direct-caller occurrence counts.  These are keyboard-layout
provisional identities, not control-code semantics or ledger-ready mappings.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from m25_context_mapping_probe import (
    CONTEXT_PROVISIONAL,
    direct_occurrences,
    probe as context_probe,
    record_metadata,
    sha256,
    table_hits,
)
from m20_text_record_probe import EXPECTED_ROM_SHA256


PROBE_VERSION = "m26-punctuation-probe-20260816.v1"
PUNCTUATION_CANDIDATES = {
    0x0006: {"unicode_candidate": "・", "layout_label": "middle-dot"},
    0x0008: {"unicode_candidate": "?", "layout_label": "question-mark"},
    0x0009: {"unicode_candidate": "!", "layout_label": "exclamation-mark"},
    0x000A: {"unicode_candidate": "＿", "layout_label": "fullwidth-low-line"},
    0x000C: {"unicode_candidate": "ー", "layout_label": "long-vowel-mark"},
    0x000D: {"unicode_candidate": "/", "layout_label": "slash"},
}


def probe(data: bytes) -> dict[str, object]:
    candidates = []
    for code_unit, evidence in PUNCTUATION_CANDIDATES.items():
        candidates.append(
            {
                "code_unit": f"0x{code_unit:04X}",
                "unicode_candidate": evidence["unicode_candidate"],
                "layout_label": evidence["layout_label"],
                "identity_status": "keyboard-layout-provisional",
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
        "comparison": {
            "context_provisional_candidates_kept_separate": sorted(
                f"0x{unit:04X}" for unit in CONTEXT_PROVISIONAL
            ),
            "m25_probe_available": bool(context_probe(data)),
        },
        "gate": {
            "confirmed_identity_count_added": 0,
            "control_semantics_confirmed": False,
            "runtime_scene_context_confirmed": False,
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
