#!/usr/bin/env python3
"""Cross-check one local candidate against the clean A9PJ name-entry screen.

M29 correlates the M27 local row at caller ``0x080526FE``/stream ``0x1FA4B4``
with the M19 runtime keyboard gate and a private BG0 reconstruction.  The
tool emits only screen hashes, addresses, mapping statuses and gate fields;
it never prints the row's source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROBE_VERSION = "m29-ui-row-cross-probe-20260816.v1"
EXPECTED_ROM_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"
EXPECTED_CALLER = "0x080526FE"
EXPECTED_STREAM = "0x1FA4B4"
EXPECTED_BG0_SCREENBLOCK_SHA256 = "e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661"
EXPECTED_BG1_SCREENBLOCK_SHA256 = "5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b"
EXPECTED_BG0_IMAGE_SHA256 = "72d1bf7271453ee012553c152940847c226d82e4470b43009d41963f63410f91"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cross_check(
    rows: list[dict[str, object]],
    screen_summary: dict[str, object],
    *,
    bg0_image_sha256: str | None = None,
) -> dict[str, object]:
    matches = [
        row
        for row in rows
        if row.get("caller_bus_address") == EXPECTED_CALLER
        and row.get("stream_file_offset") == EXPECTED_STREAM
    ]
    screen = screen_summary["starts"][0]["screen"]
    keyboard = screen.get("keyboard_layout", {})
    row = matches[0] if matches else None
    return {
        "probe_version": PROBE_VERSION,
        "candidate_match_count": len(matches),
        "candidate": None
        if row is None
        else {
            "string_id": row.get("string_id"),
            "caller_bus_address": row.get("caller_bus_address"),
            "stream_file_offset": row.get("stream_file_offset"),
            "source_text_sha256": row.get("source_text_sha256"),
            "mapping_status_counts": row.get("mapping_status_counts"),
            "unresolved_code_units": row.get("unresolved_code_units"),
            "control_candidates": row.get("control_candidates"),
            "complete_codepage": row.get("complete_codepage"),
        },
        "rom": {
            "sha256": screen_summary.get("rom", {}).get("sha256"),
            "expected_a9pj_sha256_match": screen_summary.get("rom", {}).get("sha256") == EXPECTED_ROM_SHA256,
        },
        "runtime_screen": {
            "gate_confirmed": screen.get("gate_confirmed"),
            "dispcnt": screen.get("dispcnt"),
            "bgcnt": screen.get("bgcnt"),
            "bg0_screenblock_sha256": screen.get("bg0_screenblock_sha256"),
            "bg1_screenblock_sha256": screen.get("bg1_screenblock_sha256"),
            "bg0_expected_hash_match": screen.get("bg0_screenblock_sha256") == EXPECTED_BG0_SCREENBLOCK_SHA256,
            "bg1_expected_keyboard_hash_match": screen.get("bg1_screenblock_sha256") == EXPECTED_BG1_SCREENBLOCK_SHA256,
            "keyboard_position_match_count": keyboard.get("position_match_count"),
            "keyboard_position_count": len(keyboard.get("selected_positions", [])),
            "bg0_image_sha256": bg0_image_sha256,
            "bg0_image_expected_hash_match": bg0_image_sha256 == EXPECTED_BG0_IMAGE_SHA256
            if bg0_image_sha256 is not None
            else False,
        },
        "classification": {
            "scene_role_candidate": "ui-name-entry" if row is not None else "unknown",
            "runtime_context_proof": "screen-and-static-caller-correlated" if row is not None else "missing",
            "reader_breakpoint_hit": False,
            "glyph_identity_confirmed_by_this_probe": 0,
            "eligible_for_ledger": False,
        },
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local_jsonl", type=Path)
    parser.add_argument("screen_summary", type=Path)
    parser.add_argument("--bg0-image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image_hash = sha256_file(args.bg0_image) if args.bg0_image else None
    result = cross_check(
        load_rows(args.local_jsonl),
        json.loads(args.screen_summary.read_text(encoding="utf-8")),
        bg0_image_sha256=image_hash,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"probe_version": PROBE_VERSION, "output": str(args.output), "source_text_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
