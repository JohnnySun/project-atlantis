#!/usr/bin/env python3
"""Verify one reviewed B3TJ direct-record pointer table.

This is deliberately not a pointer scanner.  The table location was already
identified by the M1.5 concrete record provenance.  The probe checks only its
12 absolute words against strict record boundaries and emits stable IDs,
offsets, lengths, hashes and ordering metadata.  It never emits decoded source
text or raw table bytes.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from extract_strings import DEFAULT_RANGES, ROM_BASE, strict_records  # noqa: E402


EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF
EXPECTED_TITLE = b"TOWNARIKIRI3"
EXPECTED_GAME_CODE = b"B3TJ"
EXPECTED_MAKER_CODE = b"AF"

TABLE_START = 0x0DD1B84
ENTRY_COUNT = 12
TABLE_END = TABLE_START + ENTRY_COUNT * 4
EXPECTED_TARGETS = (
    0x146F10,
    0x146F08,
    0x146F00,
    0x146EF8,
    0x146EF0,
    0x146EE8,
    0x146EE0,
    0x146ED8,
    0x146ED0,
    0x146EC8,
    0x146EBC,
    0x146EB4,
)


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def verify_identity(data: bytes) -> dict[str, object]:
    crc32 = binascii.crc32(data) & 0xFFFFFFFF
    title = data[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = data[0xAC:0xB0]
    maker_code = data[0xB0:0xB2]
    result = {
        "size": len(data),
        "crc32": f"{crc32:08X}",
        "title_ascii": title.decode("ascii", errors="replace"),
        "game_code": game_code.decode("ascii", errors="replace"),
        "maker_code": maker_code.decode("ascii", errors="replace"),
    }
    if (
        len(data) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != EXPECTED_TITLE
        or game_code != EXPECTED_GAME_CODE
        or maker_code != EXPECTED_MAKER_CODE
    ):
        raise ValueError(f"ROM identity mismatch: {result}")
    return result


def parse_table_targets(data: bytes, *, table_start: int = TABLE_START, count: int = ENTRY_COUNT) -> list[int]:
    if count <= 0 or table_start < 0 or table_start + count * 4 > len(data):
        raise ValueError("direct record table is outside ROM")
    targets: list[int] = []
    for index in range(count):
        value = struct.unpack_from("<I", data, table_start + index * 4)[0]
        if not ROM_BASE <= value < ROM_BASE + len(data):
            raise ValueError("table contains a non-ROM pointer")
        targets.append(value - ROM_BASE)
    return targets


def summarize_targets(targets: list[int], records: dict[int, object]) -> dict[str, object]:
    if not targets:
        raise ValueError("table has no targets")
    missing = [target for target in targets if target not in records]
    if missing:
        raise ValueError(f"table target is not a strict record: {missing!r}")
    deltas = [targets[index] - targets[index + 1] for index in range(len(targets) - 1)]
    rows = []
    for target in targets:
        row = records[target]
        rows.append(
            {
                "string_id": f"sjis:0x{target:06X}",
                "file_offset": _hex(target, 6),
                "gba_address": _hex(ROM_BASE + target),
                "region": str(row.region),
                "raw_length": int(row.raw_length),
                "end_offset_exclusive": _hex(row.end, 6),
                "newline_units": int(row.newline_units),
                "control_units": int(row.control_units),
            }
        )
    return {
        "entry_count": len(targets),
        "strict_target_count": len(rows),
        "direct_absolute": True,
        "target_order": "descending-file-offset",
        "target_offsets": [_hex(target, 6) for target in targets],
        "target_delta_counts": {
            _hex(delta, 4): deltas.count(delta) for delta in sorted(set(deltas))
        },
        "target_order_sha256": hashlib.sha256(
            struct.pack(f"<{len(targets)}I", *targets)
        ).hexdigest(),
        "records": rows,
    }


def analyze(data: bytes) -> dict[str, object]:
    identity = verify_identity(data)
    targets = parse_table_targets(data)
    if tuple(targets) != EXPECTED_TARGETS:
        raise ValueError("reviewed direct-record table targets changed")
    records = {row.start: row for row in strict_records(data, DEFAULT_RANGES)}
    table_bytes = data[TABLE_START:TABLE_END]
    summary = summarize_targets(targets, records)
    return {
        "identity": identity,
        "bounded_table": {
            "file_start": _hex(TABLE_START, 6),
            "file_end_exclusive": _hex(TABLE_END, 6),
            "gba_start": _hex(ROM_BASE + TABLE_START),
            "gba_end_exclusive": _hex(ROM_BASE + TABLE_END),
            "table_byte_length": len(table_bytes),
            "table_sha256": hashlib.sha256(table_bytes).hexdigest(),
            "summary": summary,
        },
        "classification": {
            "direct_pointer_provenance": "confirmed-static",
            "strict_record_targets": "confirmed-static",
            "record_category": "unclassified-text-pool-subtable",
            "capacity_and_slot_size": "unconfirmed",
            "pointer_rewrite_rule": "unconfirmed",
            "runtime_consumer": "unconfirmed",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze(args.rom.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(text, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
