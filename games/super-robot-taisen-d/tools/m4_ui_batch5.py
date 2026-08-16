#!/usr/bin/env python3
"""Run the reusable batch-4 source-safe audit for one narrow UI prompt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m4_ui_batch4 import (  # noqa: E402
    Batch4Reject,
    build_report,
    m18,
    read_index,
    validate_selection,
)


SELECTION = {516324: "是否要儲存資料？"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-rom", type=Path, required=True)
    parser.add_argument("--patched-rom", type=Path, required=True)
    parser.add_argument("--bps", type=Path, required=True)
    parser.add_argument("--bps-applied-rom", type=Path, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--reinsert-report", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        base_rom = args.base_rom.read_bytes()
        selected = validate_selection(
            base_rom,
            m18.read_source_records(args.source_table),
            read_index(args.ledger),
            SELECTION,
        )
        report = build_report(
            base_rom,
            args.patched_rom.read_bytes(),
            selected,
            read_index(args.ledger),
            json.loads(args.reinsert_report.read_text(encoding="utf-8")),
            json.loads(args.roundtrip.read_text(encoding="utf-8")),
            args.bps.read_bytes(),
            args.bps_applied_rom.read_bytes(),
            SELECTION,
        )
        report["schema"] = "super-robot-taisen-d-m4-ui-batch5-v1"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, m18.M17Error) as exc:
        print(f"m4_batch5_rejected={exc}", file=sys.stderr)
        return 2
    print(f"m4_batch5=accepted records={report['selection']['record_count']} combined={report['static_reinsert']['combined_records']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
