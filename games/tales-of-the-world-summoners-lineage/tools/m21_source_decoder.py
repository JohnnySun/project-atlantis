#!/usr/bin/env python3
"""Private A9PJ Japanese candidate decoder.

The output is intentionally a local source table.  The default output name
matches the repository ignore rule (``research/*-decoded.jsonl``), and the
decoder never prints decoded rows to stdout.  This is a bounded, auditable
intermediate rather than a translation extractor: the stream roles are still
unclassified, the complete kanji mapping is not established, and ``{FF70}``
is kept as a control candidate.

The default candidate mode only uses the clean ROM's name-entry table and the
visible gojuon keyboard order; unresolved halfwords are rendered as
``{Uxxxx}``.  ``--known-ui-only`` is a separate fixed mode for the two M32/M34
known-screen rows.  It uses only their independently cross-checked code units,
record masks and tilemaps, and must fail closed on any ROM drift.  Neither mode
claims a general Japanese/CJK codepage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

from m20_keyboard_codepage_probe import read_row
from m20_text_record_probe import (
    DEFAULT_TARGET_END,
    DEFAULT_TARGET_START,
    EXPECTED_ROM_SHA256,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    find_pointer_references,
    read_halfword_stream,
    sha256,
    stable_candidate_id,
)


DECODER_VERSION = "m21-source-decoder-20260816.v1"
KNOWN_UI_DECODER_VERSION = "m34-known-ui-decoder-20260816.v1"
ROM_BASE = 0x08000000
DEFAULT_SCAN_START = 0
DEFAULT_SCAN_END = 0x800000
DEFAULT_MAX_UNITS = 0x400

# These are the only non-placeholder mappings allowed by the fixed known-screen
# decoder.  They come from M32/M34 record-raster and BG0 tilemap crosses, not
# from a broad keyboard overlay.  The general decoder below remains conservative.
KNOWN_UI_MAPPING = {
    0x0006: "・",
    0x000C: "ー",
    0x0063: "イ",
    0x0090: "ス",
    0x009C: "タ",
    0x00C8: "フ",
    0x00F6: "レ",
    0x00FE: "ン",
}
KNOWN_UI_ROWS = (
    {
        "string_id": "eb94955ec017c9faff85f062",
        "file_offset": 0x1FA4B4,
        "units": (0x0006, 0x00F6, 0x0090, 0x009C, 0x000C),
        "source_hash": "4055ab372bbb3feadbf21c328f0eb72e9ceb2874c8979383feb193eb722d4c60",
        "scene_role": "ui-name-entry",
        "proof": "M32-known-screen-record-raster-and-bg0-tilemap",
    },
    {
        "string_id": "f4bc65e10318a0204bebc5b0",
        "file_offset": 0x087384,
        "units": (0x00C8, 0x00F6, 0x0063, 0x00FE),
        "source_hash": "8c24214195799be96f68bbd812d4ae8de1a086856c20846cf18c629f1f4283e4",
        "scene_role": "ui-name-entry-protagonist-name-field",
        "proof": "M34-known-screen-static-source-pointer-record-raster-and-tilemap",
    },
)


def keyboard_labels() -> tuple[tuple[str | None, ...], tuple[str | None, ...]]:
    """Return the visible 65-slot hiragana/katakana row labels.

    Slots 50--56 are deliberately left unresolved: they are special/small
    kana positions whose semantic identity is not yet independently proven.
    The two trailing rows are keyboard layout evidence, not a general script
    codepage claim.
    """

    hiragana = list("あいうえおかきくけこさしすせそたちつてとなにぬねの")
    hiragana += ["は", "ひ", "ふ", "へ", "ほ", "ま", "み", "む", "め", "も"]
    hiragana += ["や", None, "ゆ", None, "よ"]
    hiragana += ["ら", "り", "る", "れ", "ろ"]
    hiragana += ["わ", "を", "ん", None, None]
    hiragana += [None] * 7
    if len(hiragana) != 57:
        raise AssertionError("hiragana keyboard labels must cover 57 glyph slots")

    def to_katakana(value: str | None) -> str | None:
        if value is None:
            return None
        return chr(ord(value) + 0x60)

    katakana = [to_katakana(value) for value in hiragana]
    # Keyboard rows have seven additional special positions; leave them
    # unresolved for both scripts until a separate rendered-grid proof exists.
    katakana += [None] * 8
    hiragana += [None] * 8
    if len(hiragana) != 65 or len(katakana) != 65:
        raise AssertionError("keyboard labels must cover one 65-entry row")
    return tuple(hiragana), tuple(katakana)


def build_keyboard_map(data: bytes) -> dict[int, dict[str, object]]:
    """Build code-unit candidates from the clean ROM keyboard table."""

    rows = keyboard_labels()
    result: dict[int, dict[str, object]] = {}
    for row_index, labels in enumerate(rows):
        values = read_row(data, row_index, 65)
        for selection_index, (code_unit, label) in enumerate(zip(values, labels)):
            if label is None or code_unit in (NULL_CODE_UNIT, 0x0001):
                continue
            status = (
                "confirmed-system-row0-first-five"
                if row_index == 0 and selection_index < 5
                else "provisional-keyboard-order"
            )
            candidate = {
                "text": label,
                "mapping_status": status,
                "keyboard_row": row_index,
                "selection_index": selection_index,
                "table_bus_address": f"0x{0x0808884C + 2 * (row_index * 65 + selection_index):08X}",
            }
            # A duplicate would make the codepage ambiguous.  Keep the first
            # table entry and report the ambiguity through a placeholder map.
            if code_unit not in result:
                result[code_unit] = candidate
            elif result[code_unit]["text"] != label:
                result[code_unit] = {
                    "text": None,
                    "mapping_status": "ambiguous-keyboard-entry",
                    "keyboard_row": None,
                    "selection_index": None,
                    "table_bus_address": None,
                }
    return result


def decode_units(
    units: Iterable[int],
    mapping: dict[int, dict[str, object]],
) -> dict[str, object]:
    """Decode a bounded stream without treating unresolved values as text."""

    parts: list[str] = []
    mapping_statuses: Counter[str] = Counter()
    unresolved: list[str] = []
    control_candidates: list[str] = []
    terminated = False
    consumed = 0

    for code_unit in units:
        consumed += 1
        if code_unit == NULL_CODE_UNIT:
            terminated = True
            break
        if code_unit == LINE_ADVANCE_CODE_UNIT:
            parts.append("{FF70}")
            control_candidates.append("0xFF70")
            mapping_statuses["control-candidate"] += 1
            continue
        candidate = mapping.get(code_unit)
        if candidate is None or candidate.get("text") is None:
            parts.append(f"{{U{code_unit:04X}}}")
            unresolved.append(f"0x{code_unit:04X}")
            mapping_statuses["unmapped-code-unit"] += 1
            continue
        parts.append(str(candidate["text"]))
        mapping_statuses[str(candidate["mapping_status"])] += 1

    return {
        "text": "".join(parts),
        "terminated_by_0000": terminated,
        "units_consumed_including_terminator": consumed,
        "unresolved_code_units": sorted(set(unresolved)),
        "control_candidates": sorted(set(control_candidates)),
        "mapping_status_counts": dict(sorted(mapping_statuses.items())),
        "complete_codepage": not unresolved and not control_candidates,
        "source_text_emitted": True,
    }


def stream_units(data: bytes, target: int, max_units: int) -> list[int]:
    end = min(len(data), target + max_units * 2)
    return [
        int.from_bytes(data[offset:offset + 2], "little")
        for offset in range(target, end - 1, 2)
    ]


def decode_known_ui_rows(data: bytes) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Decode only the two fixed known-screen rows, failing closed on drift."""

    rom_digest = sha256(data)
    if rom_digest != EXPECTED_ROM_SHA256:
        raise ValueError("known-screen decoder requires the clean A9PJ ROM hash")
    mapping = {
        unit: {"text": text, "mapping_status": "confirmed-known-screen"}
        for unit, text in KNOWN_UI_MAPPING.items()
    }
    rows: list[dict[str, object]] = []
    for spec in KNOWN_UI_ROWS:
        units = stream_units(data, int(spec["file_offset"]), len(spec["units"]) + 1)
        expected_units = tuple(spec["units"])
        if tuple(units[:-1]) != expected_units or units[-1:] != [NULL_CODE_UNIT]:
            raise ValueError(
                f"known-screen source drift at 0x{int(spec['file_offset']):X}"
            )
        decoded = decode_units(units, mapping)
        if not decoded["complete_codepage"]:
            raise ValueError("known-screen mapping unexpectedly contains unresolved units")
        text = str(decoded["text"])
        source_digest = sha256(text.encode("utf-8"))
        if source_digest != spec["source_hash"]:
            raise ValueError(f"known-screen source hash drift for {spec['string_id']}")
        rows.append(
            {
                "string_id": spec["string_id"],
                "locale": "ja",
                "text": text,
                "source_text_sha256": source_digest,
                "provenance": (
                    f"rom-sha256={rom_digest};file-offset=0x{int(spec['file_offset']):X};"
                    f"terminator=0x0000;decoder={KNOWN_UI_DECODER_VERSION};proof={spec['proof']}"
                ),
                "decoder_version": KNOWN_UI_DECODER_VERSION,
                "source_status": "known-screen-confirmed-bounded",
                "runtime_context": False,
                "known_screen_context": True,
                "scene_role": spec["scene_role"],
                "codepage_status": "bounded-known-screen-only",
                "terminator_status": "0x0000-confirmed-static-span",
                "control_candidates": decoded["control_candidates"],
                "unresolved_code_units": decoded["unresolved_code_units"],
                "mapping_status_counts": decoded["mapping_status_counts"],
                "complete_codepage": True,
                "eligible_for_ledger": True,
                "source_text_emitted": True,
            }
        )
    return rows, {
        "decoder_version": KNOWN_UI_DECODER_VERSION,
        "rom_sha256": rom_digest,
        "expected_a9pj_sha256_match": True,
        "known_rows_considered": len(KNOWN_UI_ROWS),
        "terminated_rows_emitted": len(rows),
        "complete_codepage_rows": len(rows),
        "runtime_context_confirmed": False,
        "known_screen_context_confirmed": True,
        "scene_roles_confirmed": True,
        "eligible_for_ledger": True,
        "general_codepage_confirmed": False,
        "control_code_semantics_confirmed": False,
        "source_text_rows_are_local_only": True,
    }


def decode_candidates(
    data: bytes,
    *,
    scan_start: int = DEFAULT_SCAN_START,
    scan_end: int = DEFAULT_SCAN_END,
    target_start: int = DEFAULT_TARGET_START,
    target_end: int = DEFAULT_TARGET_END,
    max_units: int = DEFAULT_MAX_UNITS,
    candidate_limit: int = 0,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not 0 <= scan_start <= scan_end <= len(data):
        raise ValueError("scan range is outside ROM")
    if not 0 <= target_start <= target_end <= len(data):
        raise ValueError("target range is outside ROM")
    if max_units <= 0:
        raise ValueError("max_units must be positive")

    rom_digest = sha256(data)
    mapping = build_keyboard_map(data)
    references = find_pointer_references(
        data,
        scan_start=scan_start,
        scan_end=scan_end,
        target_start=target_start,
        target_end=target_end,
    )
    if candidate_limit > 0:
        references = references[:candidate_limit]

    rows: list[dict[str, object]] = []
    terminated_count = 0
    complete_count = 0
    unresolved_units: Counter[str] = Counter()
    for pointer_offset, target in references:
        profile = read_halfword_stream(data, target, max_units=max_units)
        if not profile["terminated_by_0000"]:
            continue
        decoded = decode_units(stream_units(data, target, max_units), mapping)
        byte_length = int(profile["byte_length"])
        string_id = stable_candidate_id(pointer_offset, target, byte_length)
        if decoded["terminated_by_0000"]:
            terminated_count += 1
        if decoded["complete_codepage"]:
            complete_count += 1
        for unit in decoded["unresolved_code_units"]:
            unresolved_units[unit] += 1
        rows.append(
            {
                "string_id": string_id,
                "locale": "ja",
                "text": decoded["text"],
                "source_text_sha256": sha256(decoded["text"].encode("utf-8")),
                "provenance": (
                    f"rom-sha256={rom_digest};file-offset=0x{target:X};"
                    f"pointer-file-offset=0x{pointer_offset:X};terminator=0x0000;"
                    f"decoder={DECODER_VERSION};runtime-context=none"
                ),
                "decoder_version": DECODER_VERSION,
                "source_status": "candidate-unclassified-partial-codepage",
                "runtime_context": False,
                "scene_role": "unclassified",
                "codepage_status": "partial-keyboard-kana-16bit",
                "terminator_status": "0x0000-observed-static-candidate",
                "control_candidates": decoded["control_candidates"],
                "unresolved_code_units": decoded["unresolved_code_units"],
                "mapping_status_counts": decoded["mapping_status_counts"],
                "complete_codepage": decoded["complete_codepage"],
                "eligible_for_ledger": False,
                "source_text_emitted": True,
            }
        )

    summary = {
        "decoder_version": DECODER_VERSION,
        "rom_sha256": rom_digest,
        "expected_a9pj_sha256_match": rom_digest == EXPECTED_ROM_SHA256,
        "scan_file_range": [f"0x{scan_start:X}", f"0x{scan_end:X}"],
        "target_file_range": [f"0x{target_start:X}", f"0x{target_end:X}"],
        "pointer_references_considered": len(references),
        "terminated_rows_emitted": len(rows),
        "terminated_count": terminated_count,
        "complete_codepage_rows": complete_count,
        "partial_or_unresolved_rows": len(rows) - complete_count,
        "distinct_unresolved_code_units": len(unresolved_units),
        "source_text_rows_are_local_only": True,
        "runtime_context_confirmed": False,
        "scene_roles_confirmed": False,
        "eligible_for_ledger": False,
    }
    return rows, summary


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--scan-start", type=lambda value: int(value, 0), default=DEFAULT_SCAN_START)
    parser.add_argument("--scan-end", type=lambda value: int(value, 0), default=DEFAULT_SCAN_END)
    parser.add_argument("--target-start", type=lambda value: int(value, 0), default=DEFAULT_TARGET_START)
    parser.add_argument("--target-end", type=lambda value: int(value, 0), default=DEFAULT_TARGET_END)
    parser.add_argument("--max-units", type=lambda value: int(value, 0), default=DEFAULT_MAX_UNITS)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument(
        "--known-ui-only",
        action="store_true",
        help="decode only the fixed M32/M34 known-screen rows; no candidate scan",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.candidate_limit < 0:
        parser.error("candidate-limit must be non-negative")
    data = args.rom.read_bytes()
    if args.known_ui_only:
        rows, summary = decode_known_ui_rows(data)
    else:
        rows, summary = decode_candidates(
            data,
            scan_start=args.scan_start,
            scan_end=args.scan_end,
            target_start=args.target_start,
            target_end=args.target_end,
            max_units=args.max_units,
            candidate_limit=args.candidate_limit,
        )
    write_jsonl(args.output, rows)
    print(json.dumps({**summary, "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
