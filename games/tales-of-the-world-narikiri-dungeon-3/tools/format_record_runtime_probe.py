#!/usr/bin/env python3
"""Bounded live probe for B3TJ's format-loop record consumer.

The probe breaks only at the reviewed ``0x080014F4`` format entry.  It
classifies that invocation's ``r0`` against the five strict extractor windows;
only an exact requested record (or the first strict record with the explicit
fallback flag) gets a source read-watch.  The same invocation is then traced
for at most one codepoint lookup, one font-map asset slot and one scratch
write.  It emits registers, addresses, hashes/counts and stop metadata only.

It does not scan pointers, read source/glyph bytes, write state/object/save or
pretend a static record-to-asset result is live evidence.  The shared
``core/gba/gdbstub_client.py`` remains the only transport.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from consumer_probe import (  # noqa: E402
    b3tj_identity,
    destination_candidates,
    key_value,
    parse_sequence,
    register_snapshot,
    strict_record_metadata,
)
from font_record_runtime_probe import (  # noqa: E402
    classify_asset_pointer,
    classify_source_pointer,
)


ROM_BASE = 0x08000000
FORMAT_ENTRY = 0x080014F4
FORMAT_CALLSITES = tuple(ROM_BASE + offset for offset in (0x1652, 0x8E16, 0x167A6, 0xA778E, 0xBAC58, 0xC6184))
CODEPOINT_LOOKUP_ENTRY = 0x08004D90
FONT_MAP_ENTRY = 0x08001414
GLYPH_TRANSFORM_ENTRIES = (0x080011A8, 0x080012E0)
FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
FONT_SCRATCH_BASE = 0x03000560
KEYINPUT_ADDRESS = 0x04000130


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def normalized_pc(registers: dict[str, int]) -> int:
    return registers.get("pc", 0) & ~1


def format_callsite_from_lr(lr: int) -> int | None:
    callsite = (lr & ~1) - 4
    return callsite if callsite in FORMAT_CALLSITES else None


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


def trace_record_format_hit(
    client: GdbClient,
    entry_stop: str,
    entry_registers: dict[str, int],
    records: dict[int, dict[str, object]],
    *,
    desired_key: int,
    rom_size: int,
    stage_timeout: float,
    max_stage_stops: int,
) -> dict[str, object]:
    """Trace one exact strict source-shaped format invocation."""

    source_pointer = entry_registers.get("r0", 0)
    source = classify_source_pointer(source_pointer, records)
    result: dict[str, object] = {
        "entry": _stop_row(entry_stop, "breakpoint", FORMAT_ENTRY, entry_registers),
        "caller_lr": _hex(entry_registers.get("lr", 0)),
        "caller_callsite": (
            None
            if format_callsite_from_lr(entry_registers.get("lr", 0)) is None
            else _hex(format_callsite_from_lr(entry_registers["lr"]) or 0)
        ),
        "source": source,
        "stage_stops": [],
        "source_watch": None,
        "lookup": None,
        "font_map": None,
        "asset_watch": None,
        "scratch_watch": None,
    }
    if source.get("status") != "strict-record-start":
        result["pipeline_status"] = "not-an-exact-strict-record"
        return result

    source_watch = False
    lookup_breakpoint = False
    font_map_breakpoint = False
    transform_breakpoints: list[int] = []
    asset_watch = False
    scratch_watch = False
    asset_address: int | None = None
    try:
        client.set_watchpoint(source_pointer, kind=1, watch_type=3)
        source_watch = True
        result["source_watch"] = {
            "status": "installed",
            "address": _hex(source_pointer),
            "kind": 1,
            "watch_type": 3,
        }
        for address in (CODEPOINT_LOOKUP_ENTRY, FONT_MAP_ENTRY):
            client.set_breakpoint(address, kind=2)
        lookup_breakpoint = True
        font_map_breakpoint = True

        for _ in range(max_stage_stops):
            try:
                stop = client.continue_until_stop(stage_timeout)
                registers = client.read_registers()
            except TimeoutError:
                result["pipeline_status"] = "stage-timeout"
                try:
                    result["interrupt_stop"] = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    result["interrupt_stop"] = None
                return result
            except (RuntimeError, OSError, ConnectionError) as exc:
                result["pipeline_status"] = "stage-error"
                result["error_type"] = type(exc).__name__
                return result

            kind, stop_address = parse_stop_watch(stop)
            row = _stop_row(stop, kind, stop_address, registers)
            result["stage_stops"].append(row)
            pc = normalized_pc(registers)

            if source_watch and stop_address is not None and (
                source_pointer <= stop_address < source_pointer + 2
            ):
                row["stage"] = "source-read"
                result["source_read_status"] = "confirmed-runtime-strict-record-source-read"
                result["source_read_pc"] = _hex(pc)
                result["source_read_lr"] = _hex(registers.get("lr", 0))
                result["source_destination_candidates"] = destination_candidates(registers)
                _remove_watchpoint(client, source_pointer, 1, 3)
                source_watch = False
                continue

            if lookup_breakpoint and pc == CODEPOINT_LOOKUP_ENTRY:
                row["stage"] = "codepoint-lookup-entry"
                result["lookup"] = {
                    "status": "confirmed-runtime-codepoint-lookup-entry",
                    "pc": _hex(pc),
                    "r0_source_cursor": _hex(registers.get("r0", 0)),
                    "lookup_flag_r1": _hex(registers.get("r1", 0)),
                    "registers": register_snapshot(registers),
                }
                _remove_breakpoint(client, CODEPOINT_LOOKUP_ENTRY)
                lookup_breakpoint = False
                continue

            if font_map_breakpoint and pc == FONT_MAP_ENTRY:
                row["stage"] = "font-map-entry"
                index = registers.get("r2", 0)
                try:
                    asset_address = FONT_ASSET_BASE + index * FONT_ASSET_STRIDE
                    asset_class = classify_asset_pointer(asset_address)
                    if asset_address < FONT_ASSET_BASE or asset_address + FONT_ASSET_STRIDE > ROM_BASE + rom_size:
                        raise ValueError("asset outside ROM")
                except (ValueError, OverflowError) as exc:
                    result["font_map"] = {
                        "status": "derived-address-error",
                        "error_type": type(exc).__name__,
                        "r2_index": _hex(index),
                    }
                    return result
                result["font_map"] = {
                    "status": "confirmed-runtime-font-map-entry",
                    "pc": _hex(pc),
                    "r2_index": _hex(index),
                    "asset": asset_class,
                    "caller_lr": _hex(registers.get("lr", 0)),
                    "registers": register_snapshot(registers),
                }
                _remove_breakpoint(client, FONT_MAP_ENTRY)
                font_map_breakpoint = False
                try:
                    client.set_watchpoint(asset_address, kind=4, watch_type=3)
                    asset_watch = True
                    result["asset_watch"] = {
                        "status": "installed",
                        "address": _hex(asset_address),
                        "kind": 4,
                        "watch_type": 3,
                    }
                except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                    result["asset_watch"] = {
                        "status": "install-error",
                        "error_type": type(exc).__name__,
                    }
                    return result
                for transform in GLYPH_TRANSFORM_ENTRIES:
                    try:
                        client.set_breakpoint(transform, kind=2)
                        transform_breakpoints.append(transform)
                    except (RuntimeError, TimeoutError, OSError, ConnectionError):
                        pass
                continue

            if asset_watch and asset_address is not None and stop_address is not None and (
                asset_address <= stop_address < asset_address + FONT_ASSET_STRIDE
            ):
                row["stage"] = "asset-read"
                result["asset_read_status"] = "confirmed-runtime-asset-read-candidate"
                _remove_watchpoint(client, asset_address, 4, 3)
                asset_watch = False
                try:
                    client.set_watchpoint(FONT_SCRATCH_BASE, kind=4, watch_type=2)
                    scratch_watch = True
                    result["scratch_watch"] = {
                        "status": "installed",
                        "address": _hex(FONT_SCRATCH_BASE),
                        "kind": 4,
                        "watch_type": 2,
                    }
                except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                    result["scratch_watch"] = {
                        "status": "install-error",
                        "error_type": type(exc).__name__,
                    }
                    result["pipeline_status"] = "asset-read-no-scratch-watch"
                    return result
                continue

            if scratch_watch and stop_address is not None and (
                FONT_SCRATCH_BASE <= stop_address < FONT_SCRATCH_BASE + 4
            ):
                row["stage"] = "scratch-write"
                result["scratch_status"] = "confirmed-runtime-scratch-write-candidate"
                result["pipeline_status"] = "source-lookup-font-map-asset-scratch-observed"
                return result

            if stop_address is not None and KEYINPUT_ADDRESS <= stop_address < KEYINPUT_ADDRESS + 2:
                row["stage"] = "keyinput-interleave"
                result.setdefault("key_writes", []).append(_write_key(client, desired_key))
                continue

            if pc in GLYPH_TRANSFORM_ENTRIES:
                row["stage"] = "glyph-transform-entry"
                result.setdefault("transform_entries", []).append(_hex(pc))
                for transform in tuple(transform_breakpoints):
                    _remove_breakpoint(client, transform)
                transform_breakpoints.clear()
                continue

            row["stage"] = "unexpected-stop"
            result["pipeline_status"] = "unexpected-stop"
            return result

        result["pipeline_status"] = "stage-stop-limit"
        return result
    finally:
        if source_watch:
            _remove_watchpoint(client, source_pointer, 1, 3)
        if lookup_breakpoint:
            _remove_breakpoint(client, CODEPOINT_LOOKUP_ENTRY)
        if font_map_breakpoint:
            _remove_breakpoint(client, FONT_MAP_ENTRY)
        if asset_watch and asset_address is not None:
            _remove_watchpoint(client, asset_address, 4, 3)
        if scratch_watch:
            _remove_watchpoint(client, FONT_SCRATCH_BASE, 4, 2)
        for transform in transform_breakpoints:
            _remove_breakpoint(client, transform)


def trace_after_navigation(
    client: GdbClient,
    records: dict[int, dict[str, object]],
    *,
    rom_size: int,
    sequence: list[tuple[str, int]],
    per_event_timeout: float,
    stage_timeout: float,
    max_events: int,
    max_format_hits: int,
    max_stage_stops: int,
    trace_record_offset: int | None,
    trace_first_strict: bool,
) -> dict[str, object]:
    """Trace formatter consumption on an already-connected post-navigation session."""

    bounded_sequence: list[tuple[str, int]] = []
    remaining = max_events
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded_sequence.append((name, take))
        remaining -= take

    result: dict[str, object] = {
        "mode": "format-loop-strict-record-post-navigation",
        "trace_request": {
            "record_offset": None
            if trace_record_offset is None
            else _hex(trace_record_offset, 6),
            "trace_first_strict": trace_first_strict,
        },
        "sequence": [
            {"key": name, "events": count}
            for name, count in bounded_sequence
        ],
        "format_hits": [],
        "key_events": [],
        "classification": {
            "format_entry": "unconfirmed-until-runtime-breakpoint-hit",
            "strict_record_source_read": "unconfirmed-until-exact-watch-hit",
            "codepoint_lookup": "unconfirmed-until-runtime-breakpoint-hit",
            "font_map_asset": "unconfirmed-until-runtime-breakpoint-hit",
            "glyph_identity": "unconfirmed",
            "scratch_to_vram": "unconfirmed",
        },
    }
    format_breakpoint = False
    key_watch = False
    event_index = 0
    try:
        try:
            client.set_breakpoint(FORMAT_ENTRY, kind=2)
            format_breakpoint = True
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
                if len(result["format_hits"]) >= max_format_hits:
                    result["termination"] = "format-hit-limit"
                    break
                try:
                    stop = client.continue_until_stop(per_event_timeout)
                    registers = client.read_registers()
                except TimeoutError:
                    result["termination"] = "per-event-timeout"
                    try:
                        result["interrupt_stop"] = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        result["interrupt_stop"] = None
                    break
                except (RuntimeError, OSError, ConnectionError) as exc:
                    result["termination"] = "stop-error"
                    result["error_type"] = type(exc).__name__
                    result["error_message"] = str(exc)
                    break

                kind, stop_address = parse_stop_watch(stop)
                pc = normalized_pc(registers)
                if pc == FORMAT_ENTRY:
                    source = classify_source_pointer(registers.get("r0", 0), records)
                    hit: dict[str, object] = {
                        "entry": _stop_row(stop, kind, stop_address, registers),
                        "source": source,
                        "caller_lr": _hex(registers.get("lr", 0)),
                        "caller_callsite": (
                            None
                            if format_callsite_from_lr(registers.get("lr", 0)) is None
                            else _hex(format_callsite_from_lr(registers["lr"]) or 0)
                        ),
                    }
                    result["format_hits"].append(hit)
                    is_target = source.get("status") == "strict-record-start" and (
                        trace_record_offset is None
                        or source.get("record", {}).get("file_offset")
                        == _hex(trace_record_offset, 6)
                        or trace_first_strict
                    )
                    if is_target:
                        hit["pipeline"] = trace_record_format_hit(
                            client,
                            stop,
                            registers,
                            records,
                            desired_key=desired,
                            rom_size=rom_size,
                            stage_timeout=stage_timeout,
                            max_stage_stops=max_stage_stops,
                        )
                        result["termination"] = "strict-record-format-hit"
                        return result
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
            if result.get("termination") in {
                "format-hit-limit",
                "strict-record-format-hit",
                "per-event-timeout",
                "stop-error",
                "unexpected-stop",
            }:
                break
        if "termination" not in result:
            result["termination"] = "sequence-exhausted-without-strict-record-format-hit"
        return result
    finally:
        if format_breakpoint:
            _remove_breakpoint(client, FORMAT_ENTRY)
        if key_watch:
            _remove_watchpoint(client, KEYINPUT_ADDRESS, 2, 3)


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[tuple[str, int]],
    per_event_timeout: float,
    stage_timeout: float,
    max_events: int,
    max_format_hits: int,
    max_stage_stops: int,
    trace_record_offset: int | None,
    trace_first_strict: bool,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    records = strict_record_metadata(rom)
    requested_record = records.get(trace_record_offset) if trace_record_offset is not None else None
    if trace_record_offset is not None and requested_record is None:
        raise ValueError("trace-record-offset must name an exact strict record start")

    bounded_sequence: list[tuple[str, int]] = []
    remaining = max_events
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded_sequence.append((name, take))
        remaining -= take

    report: dict[str, object] = {
        "mode": "format-loop-strict-record-live-consumer",
        "rom": str(rom_path),
        "identity": identity,
        "strict_record_count": len(records),
        "fixed_entries": {
            "format_entry": _hex(FORMAT_ENTRY),
            "codepoint_lookup": _hex(CODEPOINT_LOOKUP_ENTRY),
            "font_map": _hex(FONT_MAP_ENTRY),
            "font_asset_base": _hex(FONT_ASSET_BASE),
            "font_scratch": _hex(FONT_SCRATCH_BASE),
        },
        "trace_request": {
            "record_offset": None if trace_record_offset is None else _hex(trace_record_offset, 6),
            "record": requested_record,
            "trace_first_strict": trace_first_strict,
        },
        "sequence": [{"key": name, "events": count} for name, count in bounded_sequence],
        "format_hits": [],
        "key_events": [],
        "classification": {
            "format_entry": "unconfirmed-until-runtime-breakpoint-hit",
            "strict_record_source_read": "unconfirmed-until-exact-watch-hit",
            "codepoint_lookup": "unconfirmed-until-runtime-breakpoint-hit",
            "font_map_asset": "unconfirmed-until-runtime-breakpoint-hit",
            "glyph_identity": "unconfirmed",
            "scratch_to_vram": "unconfirmed",
        },
    }

    client = GdbClient(host, port, timeout=8.0)
    format_breakpoint = False
    key_watch = False
    event_index = 0
    try:
        try:
            client.connect()
            report["supported"] = client.request("qSupported:multiprocess+")
            report["initial_stop"] = client.request("?")
            report["initial_registers"] = register_snapshot(client.read_registers())
            client.set_breakpoint(FORMAT_ENTRY, kind=2)
            format_breakpoint = True
            client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            key_watch = True
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            report["termination"] = "setup-error"
            report["error_type"] = type(exc).__name__
            report["error_message"] = str(exc)
            return report

        for phase_name, phase_count in bounded_sequence:
            desired = key_value(phase_name)
            for _ in range(phase_count):
                if len(report["format_hits"]) >= max_format_hits:
                    report["termination"] = "format-hit-limit"
                    break
                try:
                    stop = client.continue_until_stop(per_event_timeout)
                    registers = client.read_registers()
                except TimeoutError:
                    report["termination"] = "per-event-timeout"
                    try:
                        report["interrupt_stop"] = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        report["interrupt_stop"] = None
                    break
                except (RuntimeError, OSError, ConnectionError) as exc:
                    report["termination"] = "stop-error"
                    report["error_type"] = type(exc).__name__
                    report["error_message"] = str(exc)
                    break

                kind, stop_address = parse_stop_watch(stop)
                pc = normalized_pc(registers)
                if pc == FORMAT_ENTRY:
                    source = classify_source_pointer(registers.get("r0", 0), records)
                    hit: dict[str, object] = {
                        "entry": _stop_row(stop, kind, stop_address, registers),
                        "source": source,
                        "caller_lr": _hex(registers.get("lr", 0)),
                        "caller_callsite": (
                            None
                            if format_callsite_from_lr(registers.get("lr", 0)) is None
                            else _hex(format_callsite_from_lr(registers["lr"]) or 0)
                        ),
                    }
                    report["format_hits"].append(hit)
                    is_target = source.get("status") == "strict-record-start" and (
                        trace_record_offset is None
                        or source.get("record", {}).get("file_offset") == _hex(trace_record_offset, 6)
                        or trace_first_strict
                    )
                    if is_target:
                        traced = trace_record_format_hit(
                            client,
                            stop,
                            registers,
                            records,
                            desired_key=desired,
                            rom_size=len(rom),
                            stage_timeout=stage_timeout,
                            max_stage_stops=max_stage_stops,
                        )
                        hit["pipeline"] = traced
                        report["termination"] = "strict-record-format-hit"
                        break
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
                    report["key_events"].append(event)
                    event_index += 1
                    continue

                report["unexpected_stop"] = _stop_row(stop, kind, stop_address, registers)
                report["termination"] = "unexpected-stop"
                break
            if report.get("termination") in {
                "format-hit-limit",
                "strict-record-format-hit",
                "per-event-timeout",
                "stop-error",
                "unexpected-stop",
            }:
                break
        if "termination" not in report:
            report["termination"] = "sequence-exhausted-without-strict-record-format-hit"
        return report
    finally:
        if format_breakpoint:
            _remove_breakpoint(client, FORMAT_ENTRY)
        if key_watch:
            _remove_watchpoint(client, KEYINPUT_ADDRESS, 2, 3)
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--sequence", default="start:8,none:12,a:8,none:12")
    parser.add_argument("--per-event-timeout", type=float, default=5.0)
    parser.add_argument("--stage-timeout", type=float, default=3.0)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--max-format-hits", type=int, default=8)
    parser.add_argument("--max-stage-stops", type=int, default=12)
    parser.add_argument(
        "--trace-record-offset",
        type=lambda value: int(value, 0),
        default=0x146EE0,
        help="exact strict record file offset to trace (default 0x146EE0)",
    )
    parser.add_argument(
        "--trace-first-strict",
        action="store_true",
        help="trace the first strict record format hit instead of only the requested offset",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_events < 1 or args.max_format_hits < 1 or args.max_stage_stops < 1:
        parser.error("max-events, max-format-hits and max-stage-stops must be positive")
    try:
        sequence = parse_sequence(args.sequence)
        result = run_probe(
            args.rom,
            host=args.host,
            port=args.port,
            sequence=sequence,
            per_event_timeout=args.per_event_timeout,
            stage_timeout=args.stage_timeout,
            max_events=args.max_events,
            max_format_hits=args.max_format_hits,
            max_stage_stops=args.max_stage_stops,
            trace_record_offset=args.trace_record_offset,
            trace_first_strict=args.trace_first_strict,
        )
    except ValueError as exc:
        parser.error(str(exc))
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
