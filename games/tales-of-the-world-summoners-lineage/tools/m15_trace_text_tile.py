#!/usr/bin/env python3
"""Trace one A9PJ name-entry tile during the bounded title transition.

This uses the target's ``m15_navigate_probe`` helpers and the shared
``core/gba`` GDB client/capture.  The selected BG0 tile is game-specific:
tile 0x125 appears at the first character position of the lower category
label on the captured name-entry screen, and its final 32-byte cell matches
clean-ROM file offset 0x163184.  The probe watches one byte of the VRAM cell
while injecting the second START press.  It records the stop PC/LR/registers
but never writes the ROM or emits source text.

The raw regions from the final screen belong only in ignored work or
``/private/tmp``.  A missing tile stop is a valid bounded negative result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
from m15_navigate_probe import (  # noqa: E402
    KEYINPUT,
    NO_KEY,
    capture,
    display_state,
    identity,
    parse_stop_watch,
    press_button,
    register_snapshot,
)
from gdbstub_client import GdbClient  # noqa: E402


VRAM = 0x06000000
TRACE_TILE_ID = 0x125
TRACE_TILE_X = 1
TRACE_TILE_Y = 17
TRACE_TILE_ADDRESS = VRAM + TRACE_TILE_ID * 32
TRACE_ROM_OFFSET = 0x163184
TRACE_ROM_ADDRESS = 0x08000000 + TRACE_ROM_OFFSET


def trace_second_start(
    client: GdbClient,
    *,
    input_register: int,
    hold_events: int,
    release_events: int,
    event_timeout: float,
    max_tile_hits: int,
) -> dict[str, object]:
    """Press START while a bounded write watchpoint observes one tile cell."""

    hits: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    termination = "completed"
    key_events_seen = 0
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    client.set_watchpoint(TRACE_TILE_ADDRESS, kind=1, watch_type=2)
    try:
        for index in range(hold_events + release_events):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                termination = "watchpoint-timeout"
                try:
                    client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    termination = "watchpoint-timeout-interrupt-failed"
                break

            kind, address = parse_stop_watch(stop)
            registers = client.read_registers()
            snapshot = {
                "index": index,
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "registers": register_snapshot(registers),
            }
            if address == TRACE_TILE_ADDRESS:
                hits.append(snapshot)
                if len(hits) >= max_tile_hits:
                    termination = "tile-hit-cap-reached"
                    break
                # The watchpoint stops after the store.  Step one instruction
                # so the same store cannot be reported repeatedly.
                client.request("s")
            elif address == KEYINPUT:
                desired = 0x03F7 if key_events_seen < hold_events else NO_KEY
                snapshot["requested_keyinput"] = f"0x{desired:04X}"
                events.append(snapshot)
                client.write_register(input_register, desired)
                key_events_seen += 1
            else:
                events.append(snapshot)
                termination = "unexpected-stop"
                break
    finally:
        client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
        client.remove_watchpoint(TRACE_TILE_ADDRESS, kind=1, watch_type=2)
    return {
        "termination": termination,
        "tile_hits": hits,
        "key_events": events,
        "tile_hit_count": len(hits),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=1.0)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--max-tile-hits", type=int, default=8)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "trace_target": {
            "tile_id": f"0x{TRACE_TILE_ID:03X}",
            "tilemap_xy": [TRACE_TILE_X, TRACE_TILE_Y],
            "vram_address": f"0x{TRACE_TILE_ADDRESS:08X}",
            "watchpoint": "1-byte VRAM write",
            "rom_file_offset_candidate": f"0x{TRACE_ROM_OFFSET:06X}",
            "rom_bus_address_candidate": f"0x{TRACE_ROM_ADDRESS:08X}",
        },
        "keyinput": {
            "address": f"0x{KEYINPUT:08X}",
            "destination_register": f"r{args.input_register}",
            "active_low_idle": f"0x{NO_KEY:04X}",
        },
    }

    client = GdbClient("127.0.0.1", args.port, timeout=8.0)
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(args.settle_seconds)

        # First START reaches the already identified title-logo state.  Do
        # not capture it; it is only the navigation anchor for the trace.
        report["pre_title_display"] = display_state(client)
        report["first_start"] = press_button(
            client,
            "start",
            input_register=args.input_register,
            hold_events=args.hold_events,
            release_events=args.release_events,
            event_timeout=args.event_timeout,
        )
        report["title_settle_stop"] = client.continue_and_interrupt(args.step_settle_seconds)
        report["title_display"] = display_state(client)

        report["transition_trace"] = trace_second_start(
            client,
            input_register=args.input_register,
            hold_events=args.hold_events,
            release_events=args.release_events,
            event_timeout=args.event_timeout,
            max_tile_hits=args.max_tile_hits,
        )
        client.continue_and_interrupt(args.step_settle_seconds)
        report["post_trace_display"] = display_state(client)
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
