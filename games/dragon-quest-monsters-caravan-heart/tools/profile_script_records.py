#!/usr/bin/env python3
"""Profile clean A9HJ script spans without emitting source text.

``extract_text.py`` deliberately uses the next pointer as a conservative
candidate span.  This tool measures where the first ``FF`` control candidate
appears inside those spans and whether more bytes remain after it.  It does
not promote ``FF`` to a terminator, split records, or name any control code.
The report is aggregate-only and should be written outside Git (for example
under ``/private/tmp``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib
from collections import Counter
from pathlib import Path
from typing import Iterable


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
TERMINATOR_CANDIDATE = 0xFF


def validate_rom(data: bytes) -> dict[str, str | int]:
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")
    return {"size": len(data), "crc32": f"{crc32:08X}", "sha256": sha256}


def load_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if record.get("rom_sha256") != EXPECTED_SHA256:
                raise ValueError("decoded record has a non-clean or missing ROM hash")
            records.append(record)
    return records


def _token_size(token: dict[str, object]) -> int:
    return 2 if token.get("kind") in {"pair", "alt-glyph"} else 1


def profile(records: Iterable[dict[str, object]]) -> dict[str, object]:
    rows = list(records)
    boundary_counts = Counter(str(record.get("boundary", "unknown")) for record in rows)
    control_counts: Counter[str] = Counter()
    first_ff_offsets: Counter[str] = Counter()
    terminated = 0
    no_terminator = 0
    post_terminator_records = 0
    post_terminator_tokens = 0
    post_terminator_bytes = 0
    terminator_last_token = 0
    pair_tokens = 0
    alt_glyph_tokens = 0
    truncated_pairs = 0

    for record in rows:
        tokens = record.get("tokens")
        if not isinstance(tokens, list):
            raise ValueError("decoded record has no token list")
        ff_index: int | None = None
        for index, token in enumerate(tokens):
            if not isinstance(token, dict):
                raise ValueError("decoded record contains a non-object token")
            kind = token.get("kind")
            if kind == "pair":
                pair_tokens += 1
            elif kind == "alt-glyph":
                alt_glyph_tokens += 1
            elif kind == "pair-truncated":
                truncated_pairs += 1
            if kind == "control-candidate":
                value = int(token["value"])
                control_counts[f"{value:02X}"] += 1
                if value == TERMINATOR_CANDIDATE and ff_index is None:
                    ff_index = index
                    first_ff_offsets[str(int(token.get("offset", 0)))] += 1
        if ff_index is None:
            no_terminator += 1
            continue
        terminated += 1
        trailing = tokens[ff_index + 1 :]
        if trailing:
            post_terminator_records += 1
            post_terminator_tokens += len(trailing)
            post_terminator_bytes += sum(
                _token_size(token) for token in trailing if isinstance(token, dict)
            )
        else:
            terminator_last_token += 1

    return {
        "records": len(rows),
        "terminated_candidate": terminated,
        "no_terminator_candidate": no_terminator,
        "terminator_last_token": terminator_last_token,
        "post_terminator_records": post_terminator_records,
        "post_terminator_tokens": post_terminator_tokens,
        "post_terminator_bytes": post_terminator_bytes,
        "pair_tokens": pair_tokens,
        "alt_glyph_tokens": alt_glyph_tokens,
        "truncated_pairs": truncated_pairs,
        "boundary_candidates": dict(sorted(boundary_counts.items())),
        "control_counts": dict(sorted(control_counts.items())),
        "first_ff_offset_counts": dict(sorted(first_ff_offsets.items(), key=lambda item: int(item[0]))),
        "ff_is_boundary_proven": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("decoded", type=Path, help="ignored output from extract_text.py")
    parser.add_argument("--out", type=Path, required=True, help="aggregate JSON report outside Git")
    args = parser.parse_args()

    try:
        identity = validate_rom(args.rom.read_bytes())
        report = profile(load_records(args.decoded))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"profile_script_records: {error}", file=sys.stderr)
        return 2

    print("rom", identity)
    for key in (
        "records",
        "terminated_candidate",
        "no_terminator_candidate",
        "terminator_last_token",
        "post_terminator_records",
        "post_terminator_tokens",
        "post_terminator_bytes",
        "pair_tokens",
        "alt_glyph_tokens",
        "truncated_pairs",
    ):
        print(key, report[key])
    print("ff-is-boundary-proven", report["ff_is_boundary_proven"])
    print("report", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
