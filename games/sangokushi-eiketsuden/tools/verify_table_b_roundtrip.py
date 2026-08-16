#!/usr/bin/env python3
"""Verify table-B Shift-JIS decode/encode no-op invariants.

The command emits only record counts, offsets, hashes, lengths and control
statistics.  It never prints the decoded source text or raw record bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from table_b_common import parse_table_b_boundary, record_structure, table_b_records


def verify_table_b(data: bytes) -> dict[str, object]:
    boundary = parse_table_b_boundary(data)
    records = table_b_records(data, boundary)
    hash_accumulator = hashlib.sha256()
    length_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    opaque_counts: Counter[str] = Counter()
    byte_identical_count = 0
    hash_identical_count = 0
    control_invariant_count = 0
    entries = []

    for record in records:
        payload = record["payload"]
        structure = record_structure(payload)
        encoded = str(structure["text"]).encode("shift_jis")
        source_hash = hashlib.sha256(payload).hexdigest()
        encoded_hash = hashlib.sha256(encoded).hexdigest()
        byte_identical = encoded == payload
        encoded_structure = record_structure(encoded)
        control_invariant = all(
            structure[key] == encoded_structure[key]
            for key in (
                "payload_length",
                "line_feed_count",
                "format_counts",
                "unknown_format_counts",
                "opaque_control_byte_counts",
            )
        )
        byte_identical_count += byte_identical
        hash_identical_count += source_hash == encoded_hash
        control_invariant_count += control_invariant
        length_counts[str(len(payload))] += 1
        format_counts.update(structure["format_counts"])
        opaque_counts.update(structure["opaque_control_byte_counts"])
        hash_accumulator.update(bytes.fromhex(source_hash))
        entries.append({
            "entry": record["entry"],
            "record_file_offset": record["record_file_offset"],
            "payload_length": len(payload),
            "source_sha256": source_hash,
            "encoded_sha256": encoded_hash,
            "byte_identical": byte_identical,
            "control_invariant": control_invariant,
        })

    return {
        "read_only": True,
        "table_file_offset": boundary["table_file_offset"],
        "entry_count": len(records),
        "byte_identical_count": byte_identical_count,
        "hash_identical_count": hash_identical_count,
        "control_invariant_count": control_invariant_count,
        "payload_length_counts": dict(sorted(length_counts.items(), key=lambda pair: int(pair[0]))),
        "format_counts": dict(sorted(format_counts.items())),
        "opaque_control_byte_counts": dict(sorted(opaque_counts.items())),
        "record_hashes_sha256": hash_accumulator.hexdigest(),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_table_b(args.rom.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
