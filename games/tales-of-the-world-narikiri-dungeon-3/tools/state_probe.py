#!/usr/bin/env python3
"""Bounded B3TJ state-dispatcher and normal-input probe.

This probe is deliberately narrower than the resolver probe: it observes the
state dispatcher at ``0x08005ECC`` and its caller return at ``0x08005E12``,
then injects only active-low KEYINPUT read destinations.  It does not scan
ROM pointers, override state bytes, or emit RAM/VRAM contents.  The report is
metadata only: state bytes, dispatch-table addresses, registers, event
counts, and hashes of bounded screen regions when a state transition occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from consumer_probe import (  # noqa: E402
    KEYINPUT_ADDRESS,
    b3tj_identity,
    key_value,
    parse_sequence,
    register_snapshot,
)


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

STATE_DISPATCHER = 0x08005ECC
STATE_RETURN = 0x08005E12
STATE_TABLE_BASE = 0x08741D94
STATE_TABLE_ENTRIES = 32
STATE_NEXT = 0x02000000
STATE_CURRENT = 0x02000001
STATE_PREVIOUS = 0x02000002

NO_KEY = 0x03FF
SCREEN_REGIONS = {
    "vram": (0x06000000, 0x18000),
    "palette": (0x05000000, 0x400),
    "oam": (0x07000000, 0x400),
}


def signed_byte(value: int) -> int:
    """Interpret the dispatcher ldrsb state index as a signed byte."""

    return value - 0x100 if value & 0x80 else value


def state_metadata(state_bytes: bytes, table_base: int = STATE_TABLE_BASE) -> dict[str, object]:
    """Describe the three state bytes and one bounded dispatch-table entry."""

    if len(state_bytes) < 3:
        raise ValueError("state probe requires three state bytes")
    next_state = signed_byte(state_bytes[0])
    current_state = signed_byte(state_bytes[1])
    previous_state = signed_byte(state_bytes[2])
    result: dict[str, object] = {
        "next_state_byte": f"0x{state_bytes[0]:02X}",
        "current_state_byte": f"0x{state_bytes[1]:02X}",
        "previous_state_byte": f"0x{state_bytes[2]:02X}",
        "next_state": next_state,
        "current_state": current_state,
        "previous_state": previous_state,
        "dispatch_index_signed": next_state,
        "dispatch_table_base": f"0x{table_base:08X}",
    }
    if 0 <= next_state < STATE_TABLE_ENTRIES:
        result["dispatch_entry"] = f"0x{table_base + next_state * 4:08X}"
        result["dispatch_status"] = "bounded-entry"
    else:
        result["dispatch_status"] = "signed-index-out-of-bounds"
    return result


def screen_hash_metadata(client: GdbClient) -> dict[str, object]:
    """Hash only fixed GBA screen regions; never place their bytes in JSON."""

    result: dict[str, object] = {}
    for name, (address, length) in SCREEN_REGIONS.items():
        raw = client.read_memory(address, length)
        result[name] = {
            "address": f"0x{address:08X}",
            "length": length,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "nonzero_bytes": sum(value != 0 for value in raw),
        }
    return result


def _format_pointer(value: int) -> str:
    return f"0x{value:08X}"


def _sequence_events(sequence: list[tuple[str, int]], max_events: int) -> list[tuple[str, int]]:
    remaining = max_events
    bounded: list[tuple[str, int]] = []
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded.append((name, take))
        remaining -= take
    return bounded


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    per_stop_timeout: float,
    sequence: list[tuple[str, int]],
    max_events: int,
    max_stops: int,
    max_transitions: int,
) -> dict[str, object]:
    """Run one bounded state/KEYINPUT session on an already started mGBA."""

    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    bounded_sequence = _sequence_events(sequence, max_events)
    requested_events = sum(count for _, count in bounded_sequence)
    client = GdbClient(host, port, timeout=8.0)
    entry_breakpoint = False
    return_breakpoint = False
    key_watch = False
    pending_dispatch: dict[str, object] | None = None

    report: dict[str, object] = {
        "mode": "state-dispatcher-and-normal-keyinput",
        "rom": str(rom_path),
        "identity": identity,
        "dispatcher": {
            "entry": _format_pointer(STATE_DISPATCHER),
            "return_site": _format_pointer(STATE_RETURN),
            "table_base": _format_pointer(STATE_TABLE_BASE),
            "state_bytes": {
                "next": _format_pointer(STATE_NEXT),
                "current": _format_pointer(STATE_CURRENT),
                "previous": _format_pointer(STATE_PREVIOUS),
            },
        },
        "sequence": [{"key": name, "events": count} for name, count in bounded_sequence],
        "requested_event_count": requested_events,
        "limits": {
            "max_events": max_events,
            "max_stops": max_stops,
            "max_transitions": max_transitions,
        },
        "state_entries": [],
        "transitions": [],
        "key_events": [],
        "drain_key_reads": 0,
    }

    def read_state() -> bytes:
        return client.read_memory(STATE_NEXT, 3)

    def capture_dispatch_entry(registers: dict[str, int], stop: str) -> dict[str, object]:
        state_bytes = read_state()
        metadata = state_metadata(state_bytes)
        if "initial_screen_hashes" not in report:
            report["initial_screen_hashes"] = screen_hash_metadata(client)
        entry_text = metadata.get("dispatch_entry")
        if isinstance(entry_text, str):
            entry = int(entry_text, 16)
            function = int.from_bytes(client.read_memory(entry, 4), "little")
            metadata["resolved_function"] = _format_pointer(function)
            metadata["resolved_function_thumb"] = _format_pointer(function & ~1)
            metadata["resolved_function_status"] = (
                "rom-code-pointer"
                if ROM_BASE <= (function & ~1) < ROM_BASE + EXPECTED_SIZE
                else "non-rom-pointer"
            )
        return {
            "stop": stop,
            "registers": register_snapshot(registers),
            "pc": _format_pointer(registers["pc"]),
            "lr": _format_pointer(registers["lr"]),
            "state": metadata,
        }

    def finish_dispatch(return_stop: str, return_registers: dict[str, int]) -> None:
        nonlocal pending_dispatch
        if pending_dispatch is None:
            report["orphan_return_count"] = int(report.get("orphan_return_count", 0)) + 1
            return
        post_bytes = read_state()
        post = state_metadata(post_bytes)
        pending_dispatch["return"] = {
            "stop": return_stop,
            "registers": register_snapshot(return_registers),
            "pc": _format_pointer(return_registers["pc"]),
            "lr": _format_pointer(return_registers["lr"]),
            "state": post,
        }
        entry_state = pending_dispatch["entry"]["state"]
        assert isinstance(entry_state, dict)
        from_state = entry_state["current_state"]
        to_state = post["current_state"]
        changed = (
            from_state != to_state
            or entry_state["next_state_byte"] != post["next_state_byte"]
            or entry_state["previous_state_byte"] != post["previous_state_byte"]
        )
        report["dispatch_count"] = int(report.get("dispatch_count", 0)) + 1
        if changed:
            pending_dispatch["transition"] = {
                "from_current_state": from_state,
                "to_current_state": to_state,
                "requested_next_before": entry_state["next_state"],
                "requested_next_after": post["next_state"],
                "previous_before": entry_state["previous_state"],
                "previous_after": post["previous_state"],
            }
            transitions = report["transitions"]
            assert isinstance(transitions, list)
            if len(transitions) < max_transitions:
                pending_dispatch["screen_hashes"] = screen_hash_metadata(client)
                transitions.append(pending_dispatch)
            else:
                report["termination"] = "transition-limit"
        pending_dispatch = None

    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        # The dispatcher is only reached during the boot-to-state-4 handoff;
        # install all points while -g still holds the CPU at the reset stop.
        # A post-boot settle would miss that one-shot dispatcher entry and
        # leave only the state-4 input polling loop observable.
        report["boot_state"] = state_metadata(read_state())

        client.set_breakpoint(STATE_DISPATCHER, kind=2)
        entry_breakpoint = True
        client.set_breakpoint(STATE_RETURN, kind=2)
        return_breakpoint = True
        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        key_watch = True

        event_index = 0
        stop_count = 0
        sequence_index = 0
        phase_name = "none"
        phase_remaining = 0
        if bounded_sequence:
            phase_name, phase_remaining = bounded_sequence[0]

        while event_index < requested_events and stop_count < max_stops:
            if phase_remaining <= 0:
                sequence_index += 1
                if sequence_index >= len(bounded_sequence):
                    break
                phase_name, phase_remaining = bounded_sequence[sequence_index]
            desired = key_value(phase_name)
            try:
                stop = client.continue_until_stop(per_stop_timeout)
            except TimeoutError:
                report["termination"] = "per-stop-timeout"
                try:
                    report["interrupt_stop"] = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    report["interrupt_stop"] = None
                break
            stop_count += 1
            kind, address = parse_stop_watch(stop)

            # KEYINPUT is the high-frequency stop in state 4.  Its stop
            # packet and destination register are sufficient for the input
            # receipt; defer the expensive full register/state reads to the
            # dispatcher entry and return points.
            if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                key_events = report["key_events"]
                assert isinstance(key_events, list)
                key_events.append(
                    {
                        "index": event_index,
                        "phase": phase_name,
                        "requested_keyinput": _format_pointer(desired),
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": _format_pointer(address),
                        "destination_register": "r1",
                    }
                )
                client.write_register(1, desired)
                event_index += 1
                phase_remaining -= 1
                continue

            registers = client.read_registers()
            pc = registers["pc"] & ~1

            if pc == STATE_DISPATCHER:
                pending_dispatch = {
                    "entry": capture_dispatch_entry(registers, stop),
                }
                entries = report["state_entries"]
                assert isinstance(entries, list)
                entries.append(pending_dispatch["entry"])
                continue

            if pc == STATE_RETURN:
                finish_dispatch(stop, registers)
                if report.get("termination") == "transition-limit":
                    break
                continue

            report["unexpected_stop"] = {
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else _format_pointer(address),
                "registers": register_snapshot(registers),
            }
            report["termination"] = "unexpected-stop"
            break

        if "termination" not in report:
            report["termination"] = (
                "stop-limit" if stop_count >= max_stops else "sequence-exhausted"
            )
        # A dispatcher entry can be reached before its handler returns.  Keep
        # that open edge explicit so a bounded negative cannot be mistaken for
        # a completed state transition or a missing breakpoint hit.
        if pending_dispatch is not None:
            report["open_dispatch"] = {
                "return_observed": False,
                "entry": pending_dispatch["entry"],
            }
        report["event_count"] = event_index
        report["stop_count"] = stop_count
        report["dispatch_count"] = int(report.get("dispatch_count", 0))
        report["transition_count"] = len(report["transitions"])
    finally:
        if return_breakpoint:
            try:
                client.remove_breakpoint(STATE_RETURN, kind=2)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if entry_breakpoint:
            try:
                client.remove_breakpoint(STATE_DISPATCHER, kind=2)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if key_watch:
            try:
                client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--per-stop-timeout", type=float, default=5.0)
    parser.add_argument("--sequence", default="start:8,none:12,a:8,none:12")
    parser.add_argument("--max-events", type=int, default=128)
    parser.add_argument("--max-stops", type=int, default=2048)
    parser.add_argument("--max-transitions", type=int, default=32)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for name in ("max_events", "max_stops", "max_transitions"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    try:
        sequence = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    result = run_probe(
        args.rom,
        host=args.host,
        port=args.port,
        per_stop_timeout=args.per_stop_timeout,
        sequence=sequence,
        max_events=args.max_events,
        max_stops=args.max_stops,
        max_transitions=args.max_transitions,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
