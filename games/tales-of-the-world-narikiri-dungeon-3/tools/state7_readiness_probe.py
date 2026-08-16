#!/usr/bin/env python3
"""Bounded state-7 resource-readiness probe for B3TJ.

This is a narrow companion to ``m18_a1ac_probe.py``.  It first reproduces the
normal state-4 A1AC path, then uses the same GDB connection after the normal
state return.  The post-return phase installs only the fixed state-7 entry,
the fixed A82AC readiness-check entry, the reviewed parser/writer points, and
the KEYINPUT read watch.  At A82AC it reads one guarded byte at ``r0 + 0x28``
as metadata; it never emits pointed-to bytes and never writes game state.

The result is a bounded runtime receipt.  A82AC is a resource/readiness edge,
not a text-consumer claim: parser, strict source, output, and glyph results
remain independently classified by the delegated parser probe.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
import m18_a1ac_probe as m18  # noqa: E402
import parser_record_runtime_probe as parser_probe  # noqa: E402
from consumer_probe import parse_sequence  # noqa: E402


STATE7_ENTRY = parser_probe.STATE7_HANDLER_ENTRY
A82AC_ENTRY = 0x080A82AC
RESOURCE_STATUS_OFFSET = 0x28


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    per_stop_timeout: float,
    max_stops: int,
    max_edge_checks: int,
    release_reads: int,
    max_steps: int,
    post_sequence: list[tuple[str, int]],
    post_max_events: int,
    post_max_stops: int,
    post_max_hits: int,
    post_per_event_timeout: float,
) -> dict[str, object]:
    """Run the normal A1AC path and one fixed post-return readiness trace."""

    old_entries = parser_probe.STATE_HANDLER_ENTRIES
    old_fields = parser_probe.STATE_HANDLER_MEMORY_FIELDS
    parser_probe.STATE_HANDLER_ENTRIES = {
        "state7": STATE7_ENTRY,
        "a82ac": A82AC_ENTRY,
    }
    parser_probe.STATE_HANDLER_MEMORY_FIELDS = {
        "a82ac": ("r0", RESOURCE_STATUS_OFFSET),
    }
    try:
        return m18.run_probe(
            rom_path,
            host=host,
            port=port,
            per_stop_timeout=per_stop_timeout,
            max_stops=max_stops,
            max_edge_checks=max_edge_checks,
            release_reads=release_reads,
            max_steps=max_steps,
            trace_parser_after_return=True,
            parser_sequence=post_sequence,
            parser_max_events=post_max_events,
            parser_max_stops=post_max_stops,
            parser_max_hits=post_max_hits,
            parser_per_event_timeout=post_per_event_timeout,
        )
    finally:
        parser_probe.STATE_HANDLER_ENTRIES = old_entries
        parser_probe.STATE_HANDLER_MEMORY_FIELDS = old_fields


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--per-stop-timeout", type=float, default=30.0)
    parser.add_argument("--max-stops", type=int, default=64)
    parser.add_argument("--max-edge-checks", type=int, default=8)
    parser.add_argument("--release-reads", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--post-sequence", default="none:256")
    parser.add_argument("--post-max-events", type=int, default=256)
    parser.add_argument("--post-max-stops", type=int, default=300)
    parser.add_argument("--post-max-hits", type=int, default=8)
    parser.add_argument("--post-per-event-timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for name in (
        "max_stops",
        "max_edge_checks",
        "release_reads",
        "max_steps",
        "post_max_events",
        "post_max_stops",
        "post_max_hits",
    ):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    try:
        post_sequence = parse_sequence(args.post_sequence)
    except ValueError as exc:
        parser.error(str(exc))
    result = run_probe(
        args.rom,
        host=args.host,
        port=args.port,
        per_stop_timeout=args.per_stop_timeout,
        max_stops=args.max_stops,
        max_edge_checks=args.max_edge_checks,
        release_reads=args.release_reads,
        max_steps=args.max_steps,
        post_sequence=post_sequence,
        post_max_events=args.post_max_events,
        post_max_stops=args.post_max_stops,
        post_max_hits=args.post_max_hits,
        post_per_event_timeout=args.post_per_event_timeout,
    )
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
