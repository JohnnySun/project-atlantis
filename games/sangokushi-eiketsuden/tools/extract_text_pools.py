#!/usr/bin/env python3
"""Decode the bounded B3EJ text-pool candidates to an ignored source table.

The four default ranges are candidates established by the static pointer scan.
An additional statically confirmed story/event pool can be requested with
``--include-story``.  This
tool decodes only NUL-terminated, standard Shift-JIS records and reports
metadata to stdout.  The JSONL output may contain Japanese source text and is
therefore intended for the ignored ``research/*-decoded.jsonl`` path only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
EXPECTED_GAME_CODE = common.EXPECTED_GAME_CODE
DECODER_VERSION = "b3ej-text-pools-v1"

POOL_SPECS = (
    ("system-item-class", 0x0CBC54, 183),
    ("table-b", 0x0D1FFC, 44),
    ("table-c", 0x0D20D8, 4),
    ("event-system", 0x0D4D00, 28),
)
STORY_POOL_SPEC = ("story-event", 0x0CDB64, 33)


def _hex(value: int) -> str:
    return f"0x{value:08X}"


def _offset(value: int) -> str:
    return f"0x{value:06X}"


def _read_pointer(data: bytes, file_offset: int) -> tuple[int, int]:
    value = common.read_u32(data, file_offset)
    if not common.is_rom_pointer(value, len(data)):
        raise common.StaticContractError(
            f"pool pointer is outside ROM at {_offset(file_offset)}: {_hex(value)}"
        )
    return value, value - ROM_BASE


def decode_pool(data: bytes, label: str, table_offset: int, count: int) -> list[dict[str, object]]:
    """Return local source records for one explicitly bounded pointer pool."""

    if count <= 0 or table_offset < 0 or table_offset + count * 4 > len(data):
        raise common.StaticContractError(f"invalid pool range {label}:{_offset(table_offset)}:{count}")
    records = []
    for index in range(count):
        pointer_file_offset = table_offset + index * 4
        pointer_value, target = _read_pointer(data, pointer_file_offset)
        payload, terminator = common.read_c_string(data, target)
        structure = common.record_structure(payload)
        source_text = str(structure["text"])
        source_text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        records.append({
            "game": "sangokushi-eiketsuden",
            "revision": EXPECTED_GAME_CODE,
            "string_id": f"b3ej:{label}:{index:03d}",
            "locale": "ja-JP",
            "text": source_text,
            "provenance": {
                "status": "confirmed-static",
                "method": "bounded-absolute-pointer-table",
                "decoder_version": DECODER_VERSION,
                "pool": label,
                "table_file_offset": _offset(table_offset),
                "entry": index,
                "pointer_file_offset": _offset(pointer_file_offset),
                "pointer_value": _hex(pointer_value),
                "record_file_offset": _offset(target),
                "record_gba_address": _hex(pointer_value),
                "terminator_file_offset": _offset(terminator),
                "terminator": "0x00",
                "source_text_hash": source_text_hash,
                **structure,
            },
        })
    return records


def pool_metadata(records: list[dict[str, object]], label: str, table_offset: int) -> dict[str, object]:
    payload_lengths = Counter()
    format_counts = Counter()
    unknown_formats = Counter()
    opaque_controls = Counter()
    unique_targets = set()
    unique_hashes = set()
    line_feed_records = 0
    for record in records:
        provenance = record["provenance"]
        payload_lengths[str(provenance["payload_length"])] += 1
        format_counts.update(provenance["format_counts"])
        unknown_formats.update(provenance["unknown_format_counts"])
        opaque_controls.update(provenance["opaque_control_byte_counts"])
        unique_targets.add(provenance["record_file_offset"])
        unique_hashes.add(provenance["source_hash"])
        line_feed_records += int(provenance["line_feed_count"] > 0)
    return {
        "pool": label,
        "table_file_offset": _offset(table_offset),
        "entry_count": len(records),
        "unique_target_count": len(unique_targets),
        "unique_source_hash_count": len(unique_hashes),
        "payload_length_counts": dict(sorted(payload_lengths.items(), key=lambda item: int(item[0]))),
        "shift_jis_valid_count": sum(bool(record["provenance"]["shift_jis_decodable"]) for record in records),
        "nul_terminated_count": len(records),
        "records_with_line_feed": line_feed_records,
        "format_counts": dict(sorted(format_counts.items())),
        "unknown_format_counts": dict(sorted(unknown_formats.items())),
        "opaque_control_byte_counts": dict(sorted(opaque_controls.items())),
    }


def extract_all(data: bytes, specs: tuple[tuple[str, int, int], ...] = POOL_SPECS) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if len(data) < 0xC0:
        raise common.StaticContractError("ROM is shorter than the GBA header")
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if game_code != EXPECTED_GAME_CODE:
        raise common.StaticContractError(f"unexpected game code: {game_code!r}")
    all_records: list[dict[str, object]] = []
    metadata = []
    for label, table_offset, count in specs:
        records = decode_pool(data, label, table_offset, count)
        all_records.extend(records)
        metadata.append(pool_metadata(records, label, table_offset))
    return all_records, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("games/sangokushi-eiketsuden/research/sangokushi-eiketsuden-decoded.jsonl"),
    )
    parser.add_argument(
        "--include-story",
        action="store_true",
        help="also decode the statically confirmed 33-entry story/event pool",
    )
    args = parser.parse_args()
    specs = POOL_SPECS + (STORY_POOL_SPEC,) if args.include_story else POOL_SPECS
    records, metadata = extract_all(args.rom.read_bytes(), specs=specs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"read_only": True, "decoder_version": DECODER_VERSION, "pools": metadata}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
