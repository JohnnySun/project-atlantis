#!/usr/bin/env python3
"""Bounded live probe for B3TJ's fixed font-map consumer.

The probe observes only the already reviewed ``0x08001414`` font-map entry.
At the first bounded hit it derives the candidate asset address from the
static ``0x080DDCC4 + r2*0x20`` contract, installs one read watchpoint for
that exact slot, and records the transform entry and a bounded write to the
IWRAM scratch base ``0x03000560`` when available.  KEYINPUT is intercepted
only to keep a short normal navigation sequence moving.

It never scans pointers, reads or emits source/glyph bytes, writes target
memory, changes state/save data, or treats a font hit as proof of a strict
Japanese source record.  All output is metadata: registers, stop packets,
addresses, hashes are intentionally absent, and bounded counts/statuses.
The shared ``core/gba/gdbstub_client.py`` is the only transport.
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
from consumer_probe import b3tj_identity, key_value, parse_sequence, register_snapshot  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

FONT_MAP_ENTRY = 0x08001414
FONT_MAP_CALLSITES = (0x08001556, 0x080015F8)
GLYPH_TRANSFORM_EVEN = 0x080011A8
GLYPH_TRANSFORM_ODD = 0x080012E0
FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
FONT_SCRATCH_BASE = 0x03000560

KEYINPUT_ADDRESS = 0x04000130
NO_KEY = 0x03FF


def normalized_pc(registers: dict[str, int]) -> int:
    return registers.get("pc", 0) & ~1


def font_asset_address(codepoint_index: int, rom_size: int = EXPECTED_SIZE) -> int:
    """Derive one guarded ROM asset address without reading the slot."""

    if codepoint_index < 0:
        raise ValueError("codepoint index must be non-negative")
    address = FONT_ASSET_BASE + codepoint_index * FONT_ASSET_STRIDE
    if not ROM_BASE <= address < ROM_BASE + rom_size:
        raise ValueError("derived font asset is outside the B3TJ ROM")
    if address + FONT_ASSET_STRIDE > ROM_BASE + rom_size:
        raise ValueError("derived font asset slot exceeds the B3TJ ROM")
    return address


def callsite_from_lr(lr: int) -> int | None:
    """Map a Thumb BL return LR to the immediately preceding BL address."""

    return_site = lr & ~1
    callsite = return_site - 4
    return callsite if callsite in FONT_MAP_CALLSITES else None


def _hex(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


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


def _write_key(client: GdbClient, value: int) -> dict[str, object]:
    """Write only the observed KEYINPUT destination register r1."""

    try:
        client.write_register(1, value)
    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        return {
            "status": "write-error",
            "register": "r1",
            "value": _hex(value, 4),
            "error_type": type(exc).__name__,
        }
    return {
        "status": "write-ok",
        "register": "r1",
        "value": _hex(value, 4),
    }


def _remove_breakpoint(client: GdbClient, address: int) -> None:
    try:
        client.remove_breakpoint(address, kind=2)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def _remove_watchpoint(client: GdbClient, address: int, kind: int, watch_type: int) -> None:
    try:
        client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def trace_font_hit(
    client: GdbClient,
    entry_stop: str,
    entry_registers: dict[str, int],
    *,
    rom_size: int,
    stage_timeout: float,
    max_stage_stops: int,
) -> dict[str, object]:
    """Trace one fixed font-map hit with bounded dynamic points."""

    index = entry_registers.get("r2", 0)
    result: dict[str, object] = {
        "entry": _stop_row(
            entry_stop,
            "breakpoint",
            FONT_MAP_ENTRY,
            entry_registers,
        ),
        "codepoint_index_r2": _hex(index),
        "caller_callsite": (
            None if callsite_from_lr(entry_registers.get("lr", 0)) is None
            else _hex(callsite_from_lr(entry_registers["lr"]) or 0)
        ),
        "caller_status": (
            "format-loop-direct-caller"
            if callsite_from_lr(entry_registers.get("lr", 0)) is not None
            else "caller-not-one-of-reviewed-format-sites"
        ),
        "pipeline_stops": [],
        "asset_watch": None,
        "scratch_watch": None,
    }
    try:
        asset = font_asset_address(index, rom_size)
    except ValueError as exc:
        result["asset_status"] = "derived-address-out-of-bounds"
        result["asset_error_type"] = type(exc).__name__
        return result

    result["asset_address"] = _hex(asset)
    result["asset_slot_bytes"] = FONT_ASSET_STRIDE
    result["asset_formula"] = "0x080DDCC4 + r2*0x20"

    asset_watch = False
    transform_points: list[int] = []
    scratch_watch = False
    try:
        try:
            client.set_watchpoint(asset, kind=4, watch_type=3)
            asset_watch = True
            result["asset_watch"] = {"status": "installed", "kind": 4, "watch_type": 3}
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            result["asset_watch"] = {
                "status": "install-error",
                "error_type": type(exc).__name__,
            }
            return result

        for transform in (GLYPH_TRANSFORM_EVEN, GLYPH_TRANSFORM_ODD):
            try:
                client.set_breakpoint(transform, kind=2)
                transform_points.append(transform)
            except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                result.setdefault("transform_breakpoint_errors", []).append(
                    {"entry": _hex(transform), "error_type": type(exc).__name__}
                )

        for _ in range(max_stage_stops):
            try:
                stop = client.continue_until_stop(stage_timeout)
                registers = client.read_registers()
            except TimeoutError:
                result["pipeline_status"] = "stage-timeout"
                result["pipeline_interrupt"] = "attempted"
                try:
                    result["interrupt_stop"] = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    result["interrupt_stop"] = None
                return result
            except (RuntimeError, OSError, ConnectionError) as exc:
                result["pipeline_status"] = "stage-error"
                result["error_type"] = type(exc).__name__
                return result

            kind, address = parse_stop_watch(stop)
            row = _stop_row(stop, kind, address, registers)
            pipeline_stops = result["pipeline_stops"]
            assert isinstance(pipeline_stops, list)
            pipeline_stops.append(row)
            pc = normalized_pc(registers)

            if pc in {GLYPH_TRANSFORM_EVEN, GLYPH_TRANSFORM_ODD}:
                row["stage"] = "transform-entry"
                row["transform_entry"] = _hex(pc)
                for transform in tuple(transform_points):
                    _remove_breakpoint(client, transform)
                transform_points.clear()
                continue

            if address is not None and asset <= address < asset + FONT_ASSET_STRIDE:
                row["stage"] = "asset-read"
                result["source_watch_status"] = "confirmed-runtime-asset-read-candidate"
                _remove_watchpoint(client, asset, 4, 3)
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

            if (
                scratch_watch
                and address is not None
                and FONT_SCRATCH_BASE <= address < FONT_SCRATCH_BASE + 4
            ):
                row["stage"] = "scratch-write"
                result["scratch_status"] = "confirmed-runtime-scratch-write-candidate"
                result["pipeline_status"] = "asset-read-and-scratch-write-observed"
                return result

            if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                row["stage"] = "keyinput-interleave"
                result.setdefault("interleaved_key_writes", 0)
                result["interleaved_key_writes"] += 1
                continue

            row["stage"] = "unexpected-stop"
            result["pipeline_status"] = "unexpected-stop"
            return result

        result["pipeline_status"] = "stage-stop-limit"
        return result
    finally:
        if asset_watch:
            _remove_watchpoint(client, asset, 4, 3)
        if scratch_watch:
            _remove_watchpoint(client, FONT_SCRATCH_BASE, 4, 2)
        for transform in transform_points:
            _remove_breakpoint(client, transform)


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[tuple[str, int]],
    per_stop_timeout: float,
    stage_timeout: float,
    max_events: int,
    max_font_hits: int,
    max_stage_stops: int,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    bounded_sequence: list[tuple[str, int]] = []
    remaining = max_events
    for name, count in sequence:
        if remaining <= 0:
            break
        take = min(count, remaining)
        bounded_sequence.append((name, take))
        remaining -= take

    report: dict[str, object] = {
        "mode": "fixed-font-map-live-consumer",
        "rom": str(rom_path),
        "identity": identity,
        "fixed_entries": {
            "font_map": _hex(FONT_MAP_ENTRY),
            "even_transform": _hex(GLYPH_TRANSFORM_EVEN),
            "odd_transform": _hex(GLYPH_TRANSFORM_ODD),
            "font_asset_base": _hex(FONT_ASSET_BASE),
            "font_scratch": _hex(FONT_SCRATCH_BASE),
        },
        "sequence": [{"key": name, "events": count} for name, count in bounded_sequence],
        "limits": {
            "max_events": max_events,
            "max_font_hits": max_font_hits,
            "max_stage_stops": max_stage_stops,
        },
        "key_events": [],
        "font_hits": [],
        "classification": {
            "font_map_runtime_edge": "unconfirmed-until-hit",
            "strict_record_source_edge": "unconfirmed-by-design",
            "glyph_identity": "unconfirmed",
            "scratch_to_vram": "unconfirmed",
        },
    }

    client = GdbClient(host, port, timeout=8.0)
    entry_breakpoint = False
    key_watch = False
    event_index = 0
    stop_count = 0
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        client.set_breakpoint(FONT_MAP_ENTRY, kind=2)
        entry_breakpoint = True
        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        key_watch = True

        for phase_name, phase_count in bounded_sequence:
            desired = key_value(phase_name)
            for _ in range(phase_count):
                if len(report["font_hits"]) >= max_font_hits:
                    report["termination"] = "font-hit-limit"
                    break
                try:
                    stop = client.continue_until_stop(per_stop_timeout)
                    registers = client.read_registers()
                except TimeoutError:
                    report["termination"] = "per-stop-timeout"
                    try:
                        report["interrupt_stop"] = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        report["interrupt_stop"] = None
                    break
                except (RuntimeError, OSError, ConnectionError) as exc:
                    report["termination"] = "stop-error"
                    report["error_type"] = type(exc).__name__
                    break
                stop_count += 1
                kind, address = parse_stop_watch(stop)
                pc = normalized_pc(registers)

                if pc == FONT_MAP_ENTRY:
                    hit = trace_font_hit(
                        client,
                        stop,
                        registers,
                        rom_size=len(rom),
                        stage_timeout=stage_timeout,
                        max_stage_stops=max_stage_stops,
                    )
                    hit["index"] = len(report["font_hits"])
                    report["font_hits"].append(hit)
                    event_index += 1
                    report["termination"] = "font-hit-observed"
                    break

                if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                    event = _stop_row(stop, kind, address, registers)
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

                report["unexpected_stop"] = _stop_row(stop, kind, address, registers)
                report["termination"] = "unexpected-stop"
                break
            if report.get("termination") in {
                "font-hit-limit",
                "font-hit-observed",
                "per-stop-timeout",
                "stop-error",
                "unexpected-stop",
            }:
                break
        if "termination" not in report:
            report["termination"] = "sequence-exhausted-without-font-hit"
        report["stop_count"] = stop_count
    finally:
        if entry_breakpoint:
            _remove_breakpoint(client, FONT_MAP_ENTRY)
        if key_watch:
            _remove_watchpoint(client, KEYINPUT_ADDRESS, 2, 3)
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--sequence", default="start:8,none:12,a:8,none:12")
    parser.add_argument("--per-stop-timeout", type=float, default=5.0)
    parser.add_argument("--stage-timeout", type=float, default=3.0)
    parser.add_argument("--max-events", type=int, default=64)
    parser.add_argument("--max-font-hits", type=int, default=1)
    parser.add_argument("--max-stage-stops", type=int, default=8)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_events < 1 or args.max_font_hits < 1 or args.max_stage_stops < 1:
        parser.error("max-events, max-font-hits and max-stage-stops must be positive")
    try:
        sequence = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    result = run_probe(
        args.rom,
        host=args.host,
        port=args.port,
        sequence=sequence,
        per_stop_timeout=args.per_stop_timeout,
        stage_timeout=args.stage_timeout,
        max_events=args.max_events,
        max_font_hits=args.max_font_hits,
        max_stage_stops=args.max_stage_stops,
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
