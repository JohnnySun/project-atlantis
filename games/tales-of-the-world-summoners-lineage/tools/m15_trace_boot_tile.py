#!/usr/bin/env python3
"""Trace the candidate name-entry glyph during bounded A9PJ boot.

The navigation capture already established that BG0 tile ``0x125`` is visible
on the first interactive kana/name-entry screen and that its 32-byte cell has
an exact clean-ROM graphics match at file offset ``0x163184``.  The previous
transition trace watched the same VRAM byte only while injecting the second
START and did not stop.  This probe arms the same one-byte write watchpoint at
the initial GDB stop, then allows at most one bounded runtime interval.  It
does not recapture the startup logo or emit tile/source bytes.

A stop records the CPU PC/LR/registers at the memory consumer.  A timeout is
an explicit negative result: the watchpoint was armed from reset and no CPU
store to the selected cell occurred during the interval.  Raw captures, if
requested, belong only in ignored work or ``/private/tmp``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from m15_navigate_probe import (  # noqa: E402
    capture,
    identity,
    register_snapshot,
)
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


VRAM = 0x06000000
TRACE_TILE_ID = 0x125
TRACE_TILE_X = 1
TRACE_TILE_Y = 17
TRACE_TILE_ADDRESS = VRAM + TRACE_TILE_ID * 32
TRACE_ROM_OFFSET = 0x163184
TRACE_ROM_ADDRESS = 0x08000000 + TRACE_ROM_OFFSET


def trace_boot_tile(
    client: GdbClient,
    *,
    event_timeout: float,
    max_hits: int,
) -> dict[str, object]:
    """Watch one candidate glyph cell for one bounded boot interval."""

    hits: list[dict[str, object]] = []
    termination = "completed-without-hit"
    terminal_stop: dict[str, object] | None = None
    unexpected_stop: dict[str, object] | None = None
    client.set_watchpoint(TRACE_TILE_ADDRESS, kind=1, watch_type=2)
    try:
        for index in range(max_hits):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                termination = "watchpoint-timeout"
                try:
                    stop = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    termination = "watchpoint-timeout-interrupt-failed"
                    break
                kind, address = parse_stop_watch(stop)
                terminal_stop = {
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                    "registers": register_snapshot(client.read_registers()),
                }
                break

            kind, address = parse_stop_watch(stop)
            snapshot = {
                "index": index,
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "registers": register_snapshot(client.read_registers()),
            }
            if address != TRACE_TILE_ADDRESS:
                termination = "unexpected-stop"
                unexpected_stop = snapshot
                break

            hits.append(snapshot)
            termination = "tile-write-hit"
            break
    finally:
        client.remove_watchpoint(TRACE_TILE_ADDRESS, kind=1, watch_type=2)

    return {
        "termination": termination,
        "tile_hits": hits,
        "terminal_stop": terminal_stop,
        "unexpected_stop": unexpected_stop,
        "tile_hit_count": sum(
            1 for hit in hits if hit.get("stop_address") == f"0x{TRACE_TILE_ADDRESS:08X}"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--event-timeout", type=float, default=8.0)
    parser.add_argument("--max-hits", type=int, default=1)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_hits < 1:
        parser.error("max-hits must be positive")

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "scope": {
            "watch_from": "initial GDB stop before runtime continue",
            "continue_budget_seconds": args.event_timeout,
            "max_hits": args.max_hits,
        },
        "trace_target": {
            "tile_id": f"0x{TRACE_TILE_ID:03X}",
            "tilemap_xy": [TRACE_TILE_X, TRACE_TILE_Y],
            "vram_address": f"0x{TRACE_TILE_ADDRESS:08X}",
            "watchpoint": "1-byte VRAM write",
            "rom_file_offset_candidate": f"0x{TRACE_ROM_OFFSET:06X}",
            "rom_bus_address_candidate": f"0x{TRACE_ROM_ADDRESS:08X}",
        },
    }

    client = GdbClient("127.0.0.1", args.port, timeout=8.0)
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["boot_trace"] = trace_boot_tile(
            client,
            event_timeout=args.event_timeout,
            max_hits=args.max_hits,
        )
        report["final_capture"] = capture(
            client,
            run_seconds=0.05,
            breakpoint=None,
            breakpoint_timeout=1.0,
            watchpoint=None,
            watch_length=4,
            watch_type=2,
            watch_timeout=1.0,
            dump_dir=args.dump_dir,
        )
    finally:
        client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
