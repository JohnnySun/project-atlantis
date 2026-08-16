#!/usr/bin/env python3
"""Bounded A9PJ M1.5 navigation probe using the shared GBA runtime core.

The game-specific part is limited to A9PJ identity, the observed KEYINPUT
poll destination (r1), and an active-low button sequence.  GDB transport and
the standard RAM/VRAM/palette/OAM capture come from ``core/gba``.  Reports
contain hashes, registers, display parameters, and stop packets only; raw
regions belong in ignored ``work/`` or ``/private/tmp``.

The probe settles past the startup sequence, injects one bounded button at a
time by stopping on the KEYINPUT read and overwriting r1, and stops after the
first step whose display/VRAM state changes.  The changed state is a candidate
interactive screen and must still be checked with the shared BG/OAM renderer;
this tool does not claim that a changed screen contains text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from capture_runtime import capture  # noqa: E402
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


EXPECTED_SIZE = 8 * 1024 * 1024
EXPECTED_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"
KEYINPUT = 0x04000130
DISPCNT = 0x04000000
BG0CNT = 0x04000008
VRAM = 0x06000000

NO_KEY = 0x03FF
BUTTON_BITS = {
    "a": 0,
    "b": 1,
    "select": 2,
    "start": 3,
    "right": 4,
    "left": 5,
    "up": 6,
    "down": 7,
    "r": 8,
    "l": 9,
}


def parse_sequence(value: str) -> list[str]:
    sequence = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not sequence or any(item not in BUTTON_BITS for item in sequence):
        raise ValueError(f"sequence must contain known buttons: {sorted(BUTTON_BITS)}")
    return sequence


def button_value(button: str) -> int:
    return NO_KEY & ~(1 << BUTTON_BITS[button])


def identity(rom_path: Path) -> dict[str, object]:
    data = rom_path.read_bytes()
    result = {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "title": data[0xA0:0xAC].rstrip(b"\0").decode("ascii", errors="replace"),
        "game_code": data[0xAC:0xB0].decode("ascii", errors="replace"),
        "maker_code": data[0xB0:0xB2].decode("ascii", errors="replace"),
    }
    if result["size"] != EXPECTED_SIZE or result["sha256"] != EXPECTED_SHA256:
        raise ValueError(f"A9PJ ROM identity mismatch: {result}")
    return result


def display_state(client: GdbClient) -> dict[str, object]:
    dispcnt = int.from_bytes(client.read_memory(DISPCNT, 2), "little")
    bgcnt = [
        int.from_bytes(client.read_memory(BG0CNT + index * 2, 2), "little")
        for index in range(4)
    ]
    vram = client.read_memory(VRAM, 0x18000)
    return {
        "dispcnt": f"0x{dispcnt:04X}",
        "bgcnt": [f"0x{value:04X}" for value in bgcnt],
        "vram_sha256": hashlib.sha256(vram).hexdigest(),
        "vram_nonzero_bytes": sum(value != 0 for value in vram),
    }


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    names = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "sp", "lr", "pc", "cpsr"}
    return {name: f"0x{value:08X}" for name, value in registers.items() if name in names}


def press_button(
    client: GdbClient,
    button: str,
    *,
    input_register: int,
    hold_events: int,
    release_events: int,
    event_timeout: float,
) -> dict[str, object]:
    """Inject one active-low press using the observed KEYINPUT read path."""

    desired = button_value(button)
    events: list[dict[str, object]] = []
    termination = "completed"
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    try:
        for index in range(hold_events + release_events):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                termination = "keyinput-watch-timeout"
                try:
                    client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    termination = "keyinput-watch-timeout-interrupt-failed"
                break
            kind, address = parse_stop_watch(stop)
            registers = client.read_registers()
            event = {
                "index": index,
                "requested_keyinput": f"0x{(desired if index < hold_events else NO_KEY):04X}",
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "registers": register_snapshot(registers),
            }
            events.append(event)
            if address != KEYINPUT:
                termination = "unexpected-watch-stop"
                break
            client.write_register(input_register, desired if index < hold_events else NO_KEY)
    finally:
        client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
    return {
        "button": button,
        "hold_events": hold_events,
        "release_events": release_events,
        "termination": termination,
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=1.0)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--sequence", default="start,a,b")
    parser.add_argument("--stop-after-changes", type=int, default=1)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        sequence = parse_sequence(args.sequence)
        if not 0 <= args.input_register <= 12:
            raise ValueError("input register must be r0..r12")
        if args.stop_after_changes < 1:
            raise ValueError("stop-after-changes must be positive")
    except ValueError as exc:
        parser.error(str(exc))

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "port": args.port,
        "keyinput": {
            "address": f"0x{KEYINPUT:08X}",
            "observed_destination_register": f"r{args.input_register}",
            "active_low_idle": f"0x{NO_KEY:04X}",
        },
        "sequence": sequence,
        "stop_after_changes": args.stop_after_changes,
        "screens": [],
        "termination": "sequence-exhausted-without-display-change",
    }

    client = GdbClient(args.host, args.port, timeout=8.0)
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(args.settle_seconds)
        previous = display_state(client)
        report["pre_input_display"] = previous
        display_changes = 0

        for button in sequence:
            step = press_button(
                client,
                button,
                input_register=args.input_register,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
            )
            client.continue_and_interrupt(args.step_settle_seconds)
            current = display_state(client)
            step["display"] = current
            step["display_changed"] = (
                current["dispcnt"] != previous["dispcnt"]
                or current["bgcnt"] != previous["bgcnt"]
                or current["vram_sha256"] != previous["vram_sha256"]
            )
            report["screens"].append(step)
            if step["display_changed"]:
                display_changes += 1
                step["display_change_index"] = display_changes
            if step["display_changed"] and display_changes >= args.stop_after_changes:
                # Use the shared standard capture in the changed state.  It
                # writes only hashes to this JSON and raw regions to dump_dir.
                report["changed_screen_capture"] = capture(
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
                report["termination"] = f"display-change-{display_changes}-captured"
                break
            previous = current
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
