#!/usr/bin/env python3
"""Bounded live trace for B3TJ's source-shaped font loader.

This probe starts from the fixed ``0x080021A8`` loader entry discovered by
the static M2 pass.  It installs one read watchpoint for that invocation's
``r1`` input, then observes the fixed post-address-calculation point
``0x080021DA`` and, when the computed ``r8`` is a guarded ROM address, one
read watchpoint for that exact asset slot.

The navigation sequence is deliberately short and uses only the normal
active-low KEYINPUT read destination.  No state, object, save, ROM, RAM or
VRAM bytes are written or read by this tool.  Reports contain only registers,
addresses, strict-record metadata, stop metadata and bounded counts; source
and glyph bytes are never emitted.  The shared ``core/gba/gdbstub_client.py``
is the only transport.
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
    TEXT_WINDOWS,
)


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024

FONT_LOADER_ENTRY = 0x080021A8
FONT_ASSET_READY = 0x080021DA
FONT_LOADER_CALLSITE = 0x08015C26
FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20

KEYINPUT_ADDRESS = 0x04000130
NO_KEY = 0x03FF


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def normalized_pc(registers: dict[str, int]) -> int:
    return registers.get("pc", 0) & ~1


def is_watchable_address(address: int, length: int = 1) -> bool:
    """Allow only ROM/EWRAM/IWRAM ranges for a byte watchpoint."""

    if length < 1:
        return False
    end = address + length
    ranges = (
        (0x02000000, 0x02040000),
        (0x03000000, 0x03008000),
        (ROM_BASE, ROM_BASE + EXPECTED_SIZE),
    )
    return any(start <= address and end <= limit for start, limit in ranges)


def classify_source_pointer(
    address: int, records: dict[int, dict[str, object]]
) -> dict[str, object]:
    """Classify one loader input pointer without retaining source bytes."""

    result: dict[str, object] = {"pointer": _hex(address)}
    if ROM_BASE <= address < ROM_BASE + EXPECTED_SIZE:
        file_offset = address - ROM_BASE
        result["file_offset"] = _hex(file_offset, 6)
        for name, start, end in TEXT_WINDOWS:
            if start <= address < end:
                result["window"] = name
                result["window_range"] = (
                    f"0x{start - ROM_BASE:06X}-0x{end - ROM_BASE:06X}"
                )
                record = records.get(file_offset)
                if record is None:
                    result["status"] = "strict-window-nonstrict-offset"
                else:
                    result["status"] = "strict-record-start"
                    result["record"] = record
                return result
        result["status"] = "rom-outside-tested-text-windows"
        return result

    if 0x02000000 <= address < 0x02040000 or 0x03000000 <= address < 0x03008000:
        result["status"] = "runtime-ram-input"
    elif is_watchable_address(address):
        result["status"] = "watchable-nontext-address"
    else:
        result["status"] = "unwatchable-input-address"
    return result


def classify_asset_pointer(address: int) -> dict[str, object]:
    """Classify the computed r8 slot, without reading the slot."""

    result: dict[str, object] = {
        "pointer": _hex(address),
        "slot_bytes": FONT_ASSET_STRIDE,
        "formula": "0x080DDCC4 + index*0x20",
    }
    if not is_watchable_address(address, FONT_ASSET_STRIDE):
        result["status"] = "asset-slot-out-of-bounds"
        return result
    if address < FONT_ASSET_BASE:
        result["status"] = "before-static-asset-base"
        return result
    relative = address - FONT_ASSET_BASE
    if relative % FONT_ASSET_STRIDE:
        result["status"] = "asset-slot-unaligned"
        return result
    result["index"] = _hex(relative // FONT_ASSET_STRIDE)
    result["status"] = "asset-slot-address-shaped"
    return result


def callsite_from_lr(lr: int) -> int | None:
    return_site = lr & ~1
    callsite = return_site - 4
    return callsite if callsite == FONT_LOADER_CALLSITE else None


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


def _safe_remove_breakpoint(client: GdbClient, address: int) -> None:
    try:
        client.remove_breakpoint(address, kind=2)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def _safe_remove_watchpoint(
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
        return {
            "status": "write-error",
            "register": "r1",
            "value": _hex(value, 4),
            "error_type": type(exc).__name__,
        }
    return {"status": "write-ok", "register": "r1", "value": _hex(value, 4)}


def trace_loader_hit(
    client: GdbClient,
    entry_stop: str,
    entry_registers: dict[str, int],
    records: dict[int, dict[str, object]],
    *,
    desired_key: int,
    stage_timeout: float,
    max_stage_stops: int,
    injected_source_address: int | None = None,
) -> dict[str, object]:
    """Trace one loader invocation with at most two dynamic read watches."""

    original_source_pointer = entry_registers.get("r1", 0)
    source_pointer = original_source_pointer
    observed_registers = entry_registers
    source_injection: dict[str, object] | None = None
    if injected_source_address is not None:
        try:
            client.write_register(1, injected_source_address)
            observed_registers = client.read_registers()
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            return {
                "entry": _stop_row(
                    entry_stop, "breakpoint", FONT_LOADER_ENTRY, entry_registers
                ),
                "source_injection": {
                    "status": "write-error",
                    "error_type": type(exc).__name__,
                },
                "pipeline_status": "source-injection-error",
            }
        source_pointer = observed_registers.get("r1", injected_source_address)
        source_injection = {
            "status": "register-write-ok",
            "register": "r1",
            "original_pointer": _hex(original_source_pointer),
            "injected_pointer": _hex(source_pointer),
            "provenance": "runtime-argument-injected",
        }
    source_class = classify_source_pointer(source_pointer, records)
    result: dict[str, object] = {
        "entry": _stop_row(
            entry_stop, "breakpoint", FONT_LOADER_ENTRY, entry_registers
        ),
        "caller_lr": _hex(entry_registers.get("lr", 0)),
        "caller_callsite": (
            None
            if callsite_from_lr(entry_registers.get("lr", 0)) is None
            else _hex(FONT_LOADER_CALLSITE, 6)
        ),
        "source_injection": source_injection,
        "source": source_class,
        "source_watch": None,
        "asset_ready": None,
        "asset_watch": None,
        "stage_stops": [],
        "destination_candidates_at_entry": destination_candidates(observed_registers),
    }
    if injected_source_address is not None:
        result["entry_after_source_injection"] = _stop_row(
            entry_stop, "breakpoint", FONT_LOADER_ENTRY, observed_registers
        )
    source_watch = False
    asset_ready_breakpoint = False
    asset_watch = False
    asset_address: int | None = None

    try:
        if is_watchable_address(source_pointer):
            try:
                client.set_watchpoint(source_pointer, kind=1, watch_type=3)
                source_watch = True
                result["source_watch"] = {
                    "status": "installed",
                    "address": _hex(source_pointer),
                    "kind": 1,
                    "watch_type": 3,
                }
            except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                result["source_watch"] = {
                    "status": "install-error",
                    "error_type": type(exc).__name__,
                }
        else:
            result["source_watch"] = {
                "status": "not-installed-unwatchable-input"
            }

        try:
            client.set_breakpoint(FONT_ASSET_READY, kind=2)
            asset_ready_breakpoint = True
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            result["asset_ready"] = {
                "status": "breakpoint-install-error",
                "error_type": type(exc).__name__,
            }

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
            rows = result["stage_stops"]
            assert isinstance(rows, list)
            rows.append(row)
            pc = normalized_pc(registers)

            if source_watch and stop_address is not None and (
                source_pointer <= stop_address < source_pointer + 2
            ):
                row["stage"] = "source-read"
                if source_class.get("status") == "strict-record-start":
                    result["source_read_status"] = (
                        "confirmed-runtime-injected-strict-record-source-read"
                        if injected_source_address is not None
                        else "confirmed-runtime-strict-record-source-read"
                    )
                else:
                    result["source_read_status"] = "confirmed-runtime-nonstrict-input-read"
                result["source_read_pc"] = _hex(pc)
                result["source_read_lr"] = _hex(registers.get("lr", 0))
                result["source_destination_candidates"] = destination_candidates(
                    registers
                )
                _safe_remove_watchpoint(client, source_pointer, 1, 3)
                source_watch = False
                continue

            if asset_ready_breakpoint and pc == FONT_ASSET_READY:
                row["stage"] = "asset-address-ready"
                asset_address = registers.get("r8", 0)
                result["asset_ready"] = {
                    "status": "confirmed-runtime-address-calculation-point",
                    "pc": _hex(pc),
                    "r8_asset": classify_asset_pointer(asset_address),
                    "registers": register_snapshot(registers),
                }
                _safe_remove_breakpoint(client, FONT_ASSET_READY)
                asset_ready_breakpoint = False
                if is_watchable_address(asset_address):
                    try:
                        client.set_watchpoint(asset_address, kind=1, watch_type=3)
                        asset_watch = True
                        result["asset_watch"] = {
                            "status": "installed",
                            "address": _hex(asset_address),
                            "kind": 1,
                            "watch_type": 3,
                        }
                    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                        result["asset_watch"] = {
                            "status": "install-error",
                            "error_type": type(exc).__name__,
                        }
                else:
                    result["asset_watch"] = {
                        "status": "not-installed-unwatchable-asset"
                    }
                continue

            if asset_watch and asset_address is not None and stop_address == asset_address:
                row["stage"] = "asset-read"
                result["asset_read_status"] = (
                    "confirmed-runtime-asset-read-candidate"
                )
                result["asset_read_pc"] = _hex(pc)
                _safe_remove_watchpoint(client, asset_address, 1, 3)
                asset_watch = False
                result["pipeline_status"] = "source-and-asset-read-observed"
                return result

            if stop_address is not None and KEYINPUT_ADDRESS <= stop_address < KEYINPUT_ADDRESS + 2:
                row["stage"] = "keyinput-interleave"
                result.setdefault("interleaved_key_writes", 0)
                result["interleaved_key_writes"] += 1
                result.setdefault("key_writes", []).append(_write_key(client, desired_key))
                continue

            row["stage"] = "unexpected-stop"
            result["pipeline_status"] = "unexpected-stop"
            return result

        result["pipeline_status"] = "stage-stop-limit"
        return result
    finally:
        if source_watch:
            _safe_remove_watchpoint(client, source_pointer, 1, 3)
        if asset_ready_breakpoint:
            _safe_remove_breakpoint(client, FONT_ASSET_READY)
        if asset_watch and asset_address is not None:
            _safe_remove_watchpoint(client, asset_address, 1, 3)


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[tuple[str, int]],
    per_event_timeout: float,
    stage_timeout: float,
    max_events: int,
    max_loader_hits: int,
    max_stage_stops: int,
    injected_record_offset: int | None = None,
) -> dict[str, object]:
    """Run one bounded loader-entry session and return metadata only."""

    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    records = strict_record_metadata(rom)
    injected_source_address: int | None = None
    if injected_record_offset is not None:
        if injected_record_offset not in records:
            raise ValueError(
                "--inject-record-offset must name an exact strict record start"
            )
        injected_source_address = ROM_BASE + injected_record_offset
    bounded_sequence: list[tuple[str, int]] = []
    remaining = max_events
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded_sequence.append((name, take))
        remaining -= take

    report: dict[str, object] = {
        "mode": "font-record-loader-live-consumer",
        "rom": str(rom_path),
        "identity": identity,
        "strict_record_count": len(records),
        "fixed_entries": {
            "font_loader": _hex(FONT_LOADER_ENTRY),
            "font_asset_ready": _hex(FONT_ASSET_READY),
            "font_loader_callsite": _hex(FONT_LOADER_CALLSITE),
            "font_asset_base": _hex(FONT_ASSET_BASE),
            "font_asset_stride": FONT_ASSET_STRIDE,
        },
        "source_injection": (
            {
                "status": "requested-strict-record-start",
                "file_offset": _hex(injected_record_offset, 6),
                "gba_address": _hex(injected_source_address),
            }
            if injected_record_offset is not None
            else {"status": "disabled"}
        ),
        "limits": {
            "max_events": max_events,
            "max_loader_hits": max_loader_hits,
            "max_stage_stops": max_stage_stops,
        },
        "sequence": [
            {"key": name, "events": count} for name, count in bounded_sequence
        ],
        "loader_hits": [],
        "key_events": [],
        "classification": {
            "loader_entry": "unconfirmed-until-runtime-breakpoint-hit",
            "strict_record_source_read": (
                "injected-source-pipeline-only"
                if injected_source_address is not None
                else "unconfirmed-until-exact-watch-hit"
            ),
            "asset_read": "unconfirmed-until-exact-watch-hit",
            "glyph_identity": "unconfirmed",
            "decoder_output_or_vram": "unconfirmed",
        },
    }

    client = GdbClient(host, port, timeout=8.0)
    entry_breakpoint = False
    key_watch = False
    event_index = 0
    stop_count = 0
    try:
        try:
            client.connect()
            report["supported"] = client.request("qSupported:multiprocess+")
            report["initial_stop"] = client.request("?")
            report["initial_registers"] = register_snapshot(client.read_registers())
            client.set_breakpoint(FONT_LOADER_ENTRY, kind=2)
            entry_breakpoint = True
            client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            key_watch = True
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            report["termination"] = "setup-error"
            report["error_type"] = type(exc).__name__
            report["error_message"] = str(exc)
            return report

        for phase_name, phase_count in bounded_sequence:
            desired_key = key_value(phase_name)
            for _ in range(phase_count):
                if len(report["loader_hits"]) >= max_loader_hits:
                    report["termination"] = "loader-hit-limit"
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

                stop_count += 1
                kind, stop_address = parse_stop_watch(stop)
                pc = normalized_pc(registers)
                if pc == FONT_LOADER_ENTRY:
                    hit = trace_loader_hit(
                        client,
                        stop,
                        registers,
                        records,
                        desired_key=desired_key,
                        stage_timeout=stage_timeout,
                        max_stage_stops=max_stage_stops,
                        injected_source_address=injected_source_address,
                    )
                    hit["index"] = len(report["loader_hits"])
                    report["loader_hits"].append(hit)
                    report["termination"] = "loader-hit-observed"
                    break

                if stop_address is not None and KEYINPUT_ADDRESS <= stop_address < KEYINPUT_ADDRESS + 2:
                    event = _stop_row(stop, kind, stop_address, registers)
                    event.update(
                        {
                            "index": event_index,
                            "phase": phase_name,
                            "requested_keyinput": _hex(desired_key, 4),
                            "write": _write_key(client, desired_key),
                        }
                    )
                    report["key_events"].append(event)
                    event_index += 1
                    continue

                report["unexpected_stop"] = _stop_row(
                    stop, kind, stop_address, registers
                )
                report["termination"] = "unexpected-stop"
                break
            if report.get("termination") in {
                "loader-hit-limit",
                "loader-hit-observed",
                "per-event-timeout",
                "stop-error",
                "unexpected-stop",
            }:
                break
        if "termination" not in report:
            report["termination"] = "sequence-exhausted-without-loader-hit"
        report["stop_count"] = stop_count
        return report
    finally:
        if entry_breakpoint:
            _safe_remove_breakpoint(client, FONT_LOADER_ENTRY)
        if key_watch:
            _safe_remove_watchpoint(client, KEYINPUT_ADDRESS, 2, 3)
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--sequence", default="start:1,none:300,a:1,none:300")
    parser.add_argument("--per-event-timeout", type=float, default=5.0)
    parser.add_argument("--stage-timeout", type=float, default=3.0)
    parser.add_argument("--max-events", type=int, default=602)
    parser.add_argument("--max-loader-hits", type=int, default=1)
    parser.add_argument("--max-stage-stops", type=int, default=12)
    parser.add_argument(
        "--inject-record-offset",
        type=lambda value: int(value, 0),
        help="optional exact strict record offset; labels the run as injected-source only",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_events < 1 or args.max_loader_hits < 1 or args.max_stage_stops < 1:
        parser.error("max-events, max-loader-hits and max-stage-stops must be positive")
    try:
        sequence = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        result = run_probe(
            args.rom,
            host=args.host,
            port=args.port,
            sequence=sequence,
            per_event_timeout=args.per_event_timeout,
            stage_timeout=args.stage_timeout,
            max_events=args.max_events,
            max_loader_hits=args.max_loader_hits,
            max_stage_stops=args.max_stage_stops,
            injected_record_offset=args.inject_record_offset,
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
