#!/usr/bin/env python3
"""Extract B3EJ table-B records to the ignored local source table.

The output follows the project's local source-table shape and may contain the
original Japanese text, so the default path is
``research/sangokushi-eiketsuden-decoded.jsonl`` and is gitignored.  Standard
output contains only a metadata summary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from table_b_common import analyze_rom, extract_records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("games/sangokushi-eiketsuden/research/sangokushi-eiketsuden-decoded.jsonl"),
    )
    args = parser.parse_args()
    data = args.rom.read_bytes()
    # Run the metadata contract before writing the local source table.
    report = analyze_rom(data)
    records = extract_records(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "output": str(args.output),
        "entry_count": report["table_records"]["entry_count"],
        "unique_target_count": report["table_records"]["unique_target_count"],
        "shift_jis_valid_count": report["table_records"]["shift_jis_valid_count"],
        "payload_length_counts": report["table_records"]["payload_length_counts"],
        "format_counts": report["table_records"]["format_counts"],
        "unknown_format_counts": report["table_records"]["unknown_format_counts"],
        "opaque_control_byte_counts": report["table_records"]["opaque_control_byte_counts"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
