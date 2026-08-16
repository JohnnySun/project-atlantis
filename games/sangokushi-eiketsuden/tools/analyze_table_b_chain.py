#!/usr/bin/env python3
"""Analyze the B3EJ table-B boundary and static consumer chain.

Only metadata, offsets, disassembly summaries, hashes and control-byte
frequencies are printed.  The complete source records are intentionally left
to the ignored extractor output, never to this report or Git.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from table_b_common import analyze_rom


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze_rom(args.rom.read_bytes())
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
