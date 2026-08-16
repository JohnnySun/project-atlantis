#!/usr/bin/env python3
"""Bounded parser/caller probe for B3TJ's reviewed text-render chain.

This probe is intended to run after normal navigation on an existing GDB
connection.  It observes only the fixed parser entry ``0x080025CC``, the
fixed IWRAM cursor global ``0x03001588`` and the reviewed intermediate writer
``0x08001DBC``.  The parser's ``r1`` is classified against exact strict
record starts; only such a value receives a source read-watchpoint.  A RAM
``r0`` receives one bounded output-write watchpoint.

It emits registers, caller/stop addresses, classifications, hashes/counts and
pointer metadata only.  It never emits source/output bytes, scans pointers,
writes state/object/save/ROM, or treats a parser hit without strict source
membership as a text-record proof.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from consumer_probe import (  # noqa: E402
    destination_candidates,
    key_value,
    register_snapshot,
)
from font_record_runtime_probe import classify_source_pointer  # noqa: E402


ROM_BASE = 0x08000000
PARSER_ENTRY = 0x080025CC
PARSER_WRITER_ENTRY = 0x08001DBC
PARSER_CURSOR_GLOBAL = 0x03001588
KEYINPUT_ADDRESS = 0x04000130
RAM_RANGES = (
    (0x02000000, 0x02040000),
    (0x03000000, 0x03008000),
)
PARSER_CALLSITES = tuple(
    ROM_BASE + offset for offset in (0x164C, 0x1D92, 0x1E26, 0x281C)
)


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def normalized_pc(registers: dict[str, int]) -> int:
    return registers.get("pc", 0) & ~1


def parser_callsite_from_lr(lr: int) -> int | None:
    callsite = (lr & ~1) - 4
    return callsite if callsite in PARSER_CALLSITES else None


def is_ram_pointer(value: int) -> bool:
    return any(start <= value < end for start, end in RAM_RANGES)


def classify_parser_pointer(
    value: int, records: dict[int, dict[str, object]], *, role: str
) -> dict[str, object]:
    """Classify one fixed parser argument without retaining pointed-to bytes."""

    strict = classify_source_pointer(value, records)
    if strict.get("status") in {
        "strict-record-start",
        "strict-window-nonstrict-offset",
    }:
        return {"role": role, "value": _hex(value), **strict}
    if is_ram_pointer(value):
        return {"role": role, "value": _hex(value), "status": "ram-pointer"}
    if ROM_BASE <= value < ROM_BASE + 0x02000000:
        return {
            "role": role,
            "value": _hex(value),
            "status": "rom-pointer-outside-strict-record-start",
        }
    return {"role": role, "value": _hex(value), "status": "non-pointer"}


def _stop_row(
    stop: str,
    kind: str | None,
    address: int | None,
    registers: dict[str, int],
) -> dict[str, object]:
    return {
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else _hex(address),
        "pc": _hex(registers.get("pc", 0)),
        "lr": _hex(registers.get("lr", 0)),
        "registers": register_snapshot(registers),
    }


def _remove_breakpoint(client: GdbClient, address: int) -> None:
    try:
        client.remove_breakpoint(address, kind=2)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def _remove_watchpoint(
    client: GdbClient, address: int, kind: int, watch_type: int
) -> None:
    try:
        client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def _write_key(client: GdbClient, value: int) -> dict[str, object]:
    try:
        client.write_register(1, value)
    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        return {"status": "write-error", "error_type": type(exc).__name__}
    return {"status": "write-ok", "register": "r1", "value": _hex(value, 4)}


def _cursor_metadata(client: GdbClient) -> dict[str, object]:
    try:
        raw = client.read_memory(PARSER_CURSOR_GLOBAL, 4)
    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        return {
            "address": _hex(PARSER_CURSOR_GLOBAL),
            "status": "read-error",
            "error_type": type(exc).__name__,
        }
    value = int.from_bytes(raw, "little")
    return {
        "address": _hex(PARSER_CURSOR_GLOBAL),
        "status": "metadata-read",
        "value": _hex(value),
        "is_ram_pointer": is_ram_pointer(value),
    }


def trace_after_navigation(
    client: GdbClient,
    records: dict[int, dict[str, object]],
    *,
    sequence: list[tuple[str, int]],
    max_events: int,
    max_stops: int,
    max_parser_hits: int,
    per_event_timeout: float,
) -> dict[str, object]:
    """Trace the fixed parser edge on an already-connected session."""

    bounded_sequence: list[tuple[str, int]] = []
    remaining = max_events
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded_sequence.append((name, take))
        remaining -= take

    result: dict[str, object] = {
        "mode": "parser-record-post-navigation",
        "fixed_entries": {
            "parser": _hex(PARSER_ENTRY),
            "cursor_global": _hex(PARSER_CURSOR_GLOBAL),
            "writer": _hex(PARSER_WRITER_ENTRY),
        },
        "sequence": [
            {"key": name, "events": count}
            for name, count in bounded_sequence
        ],
        "max_events": max_events,
        "max_stops": max_stops,
        "max_parser_hits": max_parser_hits,
        "parser_hits": [],
        "source_read_hits": [],
        "output_write_hits": [],
        "writer_hits": [],
        "key_events": [],
        "classification": {
            "parser_entry": "unconfirmed-until-runtime-breakpoint-hit",
            "strict_source_read": "unconfirmed-until-exact-watch-hit",
            "ram_output_write": "unconfirmed-until-runtime-watch-hit",
            "iwram_writer": "unconfirmed-until-runtime-breakpoint-hit",
            "glyph_identity": "unconfirmed",
            "source_to_vram": "unconfirmed",
        },
    }
    parser_breakpoint = False
    writer_breakpoint = False
    key_watch = False
    source_watch = False
    source_address: int | None = None
    output_watch = False
    output_address: int | None = None
    stop_count = 0
    event_index = 0
    try:
        try:
            client.set_breakpoint(PARSER_ENTRY, kind=2)
            parser_breakpoint = True
            client.set_breakpoint(PARSER_WRITER_ENTRY, kind=2)
            writer_breakpoint = True
            client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            key_watch = True
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            result["termination"] = "setup-error"
            result["error_type"] = type(exc).__name__
            result["error_message"] = str(exc)
            return result

        for phase_name, phase_count in bounded_sequence:
            desired = key_value(phase_name)
            for _ in range(phase_count):
                if stop_count >= max_stops:
                    result["termination"] = "stop-limit"
                    return result
                try:
                    stop = client.continue_until_stop(per_event_timeout)
                    registers = client.read_registers()
                except TimeoutError:
                    result["termination"] = "per-event-timeout"
                    try:
                        result["interrupt_stop"] = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        result["interrupt_stop"] = None
                    return result
                except (RuntimeError, OSError, ConnectionError) as exc:
                    result["termination"] = "stop-error"
                    result["error_type"] = type(exc).__name__
                    result["error_message"] = str(exc)
                    return result
                stop_count += 1
                kind, stop_address = parse_stop_watch(stop)
                pc = normalized_pc(registers)

                if parser_breakpoint and pc == PARSER_ENTRY:
                    r0 = registers.get("r0", 0)
                    r1 = registers.get("r1", 0)
                    parser_row: dict[str, object] = {
                        "entry": _stop_row(stop, kind, stop_address, registers),
                        "caller_lr": _hex(registers.get("lr", 0)),
                        "caller_callsite": (
                            None
                            if parser_callsite_from_lr(registers.get("lr", 0)) is None
                            else _hex(parser_callsite_from_lr(registers["lr"]) or 0)
                        ),
                        "r0_destination": classify_parser_pointer(
                            r0, records, role="r0"
                        ),
                        "r1_input": classify_parser_pointer(r1, records, role="r1"),
                        "r0_ram_candidates": destination_candidates(registers),
                        "cursor": _cursor_metadata(client),
                    }
                    result["parser_hits"].append(parser_row)
                    if (
                        source_address is None
                        and classify_source_pointer(r1, records).get("status")
                        == "strict-record-start"
                    ):
                        try:
                            client.set_watchpoint(r1, kind=1, watch_type=3)
                            source_address = r1
                            source_watch = True
                            result["source_watch"] = {
                                "status": "installed",
                                "address": _hex(r1),
                                "kind": 1,
                                "watch_type": 3,
                            }
                        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                            result["source_watch"] = {
                                "status": "install-error",
                                "error_type": type(exc).__name__,
                            }
                    if output_address is None and is_ram_pointer(r0):
                        try:
                            client.set_watchpoint(r0, kind=1, watch_type=2)
                            output_address = r0
                            output_watch = True
                            result["output_watch"] = {
                                "status": "installed",
                                "address": _hex(r0),
                                "kind": 1,
                                "watch_type": 2,
                            }
                        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                            result["output_watch"] = {
                                "status": "install-error",
                                "error_type": type(exc).__name__,
                            }
                    if len(result["parser_hits"]) >= max_parser_hits:
                        _remove_breakpoint(client, PARSER_ENTRY)
                        parser_breakpoint = False
                    continue

                if source_watch and source_address is not None and stop_address is not None and (
                    source_address <= stop_address < source_address + 2
                ):
                    result["source_read_hits"].append(
                        {
                            "stop": _stop_row(stop, kind, stop_address, registers),
                            "status": "confirmed-runtime-strict-record-source-read",
                            "source_address": _hex(source_address),
                            "destination_candidates": destination_candidates(registers),
                        }
                    )
                    _remove_watchpoint(client, source_address, 1, 3)
                    source_watch = False
                    continue

                if output_watch and output_address is not None and stop_address is not None and (
                    output_address <= stop_address < output_address + 1
                ):
                    result["output_write_hits"].append(
                        {
                            "stop": _stop_row(stop, kind, stop_address, registers),
                            "status": "confirmed-runtime-parser-output-write-candidate",
                            "output_address": _hex(output_address),
                        }
                    )
                    _remove_watchpoint(client, output_address, 1, 2)
                    output_watch = False
                    continue

                if writer_breakpoint and pc == PARSER_WRITER_ENTRY:
                    result["writer_hits"].append(
                        {
                            "entry": _stop_row(stop, kind, stop_address, registers),
                            "status": "confirmed-runtime-iwram-writer-entry",
                            "caller_lr": _hex(registers.get("lr", 0)),
                            "ram_register_candidates": destination_candidates(registers),
                        }
                    )
                    continue

                if stop_address is not None and KEYINPUT_ADDRESS <= stop_address < KEYINPUT_ADDRESS + 2:
                    event = _stop_row(stop, kind, stop_address, registers)
                    event.update(
                        {
                            "index": event_index,
                            "phase": phase_name,
                            "requested_keyinput": _hex(desired, 4),
                            "write": _write_key(client, desired),
                        }
                    )
                    result["key_events"].append(event)
                    event_index += 1
                    continue

                result["unexpected_stop"] = _stop_row(stop, kind, stop_address, registers)
                result["termination"] = "unexpected-stop"
                return result
        result["termination"] = "sequence-exhausted-without-parser-strict-record-hit"
        return result
    finally:
        result["stop_count"] = stop_count
        if source_watch and source_address is not None:
            _remove_watchpoint(client, source_address, 1, 3)
        if output_watch and output_address is not None:
            _remove_watchpoint(client, output_address, 1, 2)
        if key_watch:
            _remove_watchpoint(client, KEYINPUT_ADDRESS, 2, 3)
        if parser_breakpoint:
            _remove_breakpoint(client, PARSER_ENTRY)
        if writer_breakpoint:
            _remove_breakpoint(client, PARSER_WRITER_ENTRY)
