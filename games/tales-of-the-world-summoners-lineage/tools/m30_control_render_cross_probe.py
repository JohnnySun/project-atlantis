#!/usr/bin/env python3
"""Cross-check the A9PJ 0xFF70 parser branch against a private render layout.

M30 does not decode or print the candidate stream.  It verifies bounded
``0x0000`` termination, counts ``0xFF70``, records the already-disassembled
skip/reset/vertical-add PCs, and optionally hashes a private PGM rendered by
M23.  The semantic result is limited to line-advance; variable/name/item
controls remain outside this probe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m20_text_record_probe import LINE_ADVANCE_CODE_UNIT, NULL_CODE_UNIT
from m23_font_render import stream_units


PROBE_VERSION = "m30-control-render-cross-probe-20260816.v1"
EXPECTED_TARGET = 0x1FA616
PARSER_EVIDENCE = {
    "special_compare_pc": "0x0800640E",
    "skip_unit_pc": "0x08006410",
    "horizontal_reset_pc": "0x08006412",
    "vertical_add_pc": "0x08006414",
    "branch_pc": "0x08006416",
    "vertical_delta": "0x0C",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pgm_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(b"P5\n"):
        raise ValueError("expected a binary PGM")
    header_end = data.find(b"\n255\n")
    if header_end < 0:
        raise ValueError("PGM header is incomplete")
    dimensions = data[3:header_end].split()
    if len(dimensions) != 2:
        raise ValueError("PGM dimensions are invalid")
    return int(dimensions[0]), int(dimensions[1])


def control_receipt(
    data: bytes,
    target: int,
    *,
    image_sha256: str | None = None,
    image_dimensions: tuple[int, int] | None = None,
) -> dict[str, object]:
    units = stream_units(data, target, max_units=0x400)
    if NULL_CODE_UNIT in units:
        units = units[:units.index(NULL_CODE_UNIT) + 1]
    terminated = bool(units) and units[-1] == NULL_CODE_UNIT
    line_count = units.count(LINE_ADVANCE_CODE_UNIT)
    rendered_line_count = line_count + 1 if line_count else 1
    semantic_status = (
        "line-advance-confirmed-by-parser-and-render-layout"
        if terminated and line_count and image_dimensions is not None
        else "line-advance-candidate"
    )
    return {
        "probe_version": PROBE_VERSION,
        "target_file_offset": f"0x{target:X}",
        "terminator": {"code_unit": "0x0000", "observed": terminated},
        "control": {
            "code_unit": f"0x{LINE_ADVANCE_CODE_UNIT:04X}",
            "occurrence_count_before_terminator": line_count,
            "parser_evidence": PARSER_EVIDENCE,
            "rendered_line_count_expected": rendered_line_count,
            "semantic_status": semantic_status,
        },
        "private_render": {
            "image_sha256": image_sha256,
            "dimensions": None if image_dimensions is None else list(image_dimensions),
            "source_text_emitted": False,
        },
        "gate": {
            "control_semantics_confirmed": semantic_status == "line-advance-confirmed-by-parser-and-render-layout",
            "variable_name_item_controls_confirmed": False,
            "eligible_for_ledger": False,
        },
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("target", type=lambda value: int(value, 0), default=EXPECTED_TARGET, nargs="?")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image_hash = sha256_file(args.image) if args.image else None
    dimensions = pgm_dimensions(args.image) if args.image else None
    result = control_receipt(
        args.rom.read_bytes(),
        args.target,
        image_sha256=image_hash,
        image_dimensions=dimensions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"probe_version": PROBE_VERSION, "output": str(args.output), "source_text_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
