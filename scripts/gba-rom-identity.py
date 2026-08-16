#!/usr/bin/env python3
"""Inspect or verify a local GBA ROM without emitting copyrighted payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.gba.rom_identity import RomIdentityError, report  # noqa: E402


def _write(value: dict[str, object], output: Path | None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"wrote {output} status={value['status']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--expect-size", type=int)
    parser.add_argument("--expect-crc32")
    parser.add_argument("--expect-sha256")
    parser.add_argument("--expect-title")
    parser.add_argument("--expect-game-code")
    parser.add_argument("--expect-maker-code")
    parser.add_argument("--expect-software-version", type=lambda value: int(value, 0))
    parser.add_argument("--allow-invalid-header", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    expected = {
        key.removeprefix("expect_"): value
        for key, value in vars(args).items()
        if key.startswith("expect_") and value is not None
    }
    try:
        value = report(args.rom, expected, require_valid_header=not args.allow_invalid_header)
    except (OSError, RomIdentityError) as exc:
        value = {
            "format": "project-atlantis-gba-rom-identity-v1",
            "status": "unknown",
            "rom": None,
            "diagnostics": [
                {"check": "rom_read", "status": "unknown", "message": str(exc)}
            ],
        }
    _write(value, args.output)
    return 0 if value["status"] == "pass" else 1 if value["status"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
