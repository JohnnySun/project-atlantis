#!/usr/bin/env python3
"""Bounded B3TJ parser-to-glyph runtime probe.

This game-specific probe reuses ``core/gba/gdbstub_client.py`` for all GDB
transport and register/watchpoint operations.  It expects an owned mGBA
listener already running the B3TJ navigation harness.  The first two parser
entries are observed without changing game state; on the second entry only,
the selected *strict record start* is written once to ``r1``.  An ``OK`` ACK is
required before source, formatter, glyph-asset and fixed glyph-store evidence
is accepted as argument-injected evidence.

Reports contain addresses, registers, hashes, classifications and counts only.
They never print or write source/output bytes.  Keep report files in
``/private/tmp`` or an ignored ``games/<game>/work`` directory.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from extract_strings import (  # noqa: E402
    DEFAULT_RANGES,
    EXPECTED_CRC32,
    EXPECTED_SIZE,
    ROM_BASE,
    iter_parsed_strings,
    verify_b3tj,
)


PARSER_ENTRY = 0x080025CC
FORMATTER_CALLSITE = 0x08001652
FORMATTER_ENTRY = 0x080014F4
GLYPH_ENTRY = 0x08001414
CODEPOINT_LOOKUP = 0x08004D90
WRITER_ENTRY = 0x08001DBC
FONT_ASSET_BASE = 0x080DDCC4
FONT_ASSET_STRIDE = 0x20
GLYPH_STORE_POINTS = {
    0x080011F6: "glyph_store_011F6",
    0x08001236: "glyph_store_01236",
    0x08001278: "glyph_store_01278",
    0x080012BE: "glyph_store_012BE",
}
DEFAULT_RECORD_OFFSET = 0x140D68
RAM_RANGES = ((0x02000000, 0x02040000), (0x03000000, 0x03008000))


def hx(value: int, width: int = 8) -> str:
    return f"0x{value:0{width}X}"


def is_ram_pointer(value: int) -> bool:
    return any(start <= value < end for start, end in RAM_RANGES)


def register_metadata(registers: dict[str, int]) -> dict[str, str]:
    names = (
        "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r12",
        "sp", "lr", "pc",
    )
    return {name: hx(registers.get(name, 0)) for name in names}


def strict_record_metadata(rom: bytes) -> dict[int, dict[str, object]]:
    """Index strict boundaries while retaining no decoded source text."""

    return {
        row.start: {
            "string_id": f"sjis:0x{row.start:06X}",
            "file_offset": hx(row.start, 6),
            "gba_address": hx(ROM_BASE + row.start),
            "region": row.region,
            "raw_length": row.raw_length,
            "allocated_length": row.raw_length + 1,
            "source_span_sha256": hashlib.sha256(
                rom[row.start : row.end + 1]
            ).hexdigest(),
        }
        for row in iter_parsed_strings(rom, DEFAULT_RANGES)
    }


def _window_for(value: int) -> tuple[str, int, int] | None:
    for spec in DEFAULT_RANGES:
        start = ROM_BASE + spec.start
        end = ROM_BASE + spec.end
        if start <= value < end:
            return spec.name, start, end
    return None


def classify_pointer(
    value: int, rom: bytes, records: dict[int, dict[str, object]]
) -> dict[str, object]:
    """Classify a live pointer against the five reviewed windows only."""

    result: dict[str, object] = {"pointer": hx(value), "status": "non-pointer"}
    if not (ROM_BASE <= value < ROM_BASE + EXPECTED_SIZE):
        result["status"] = "ram-pointer" if is_ram_pointer(value) else "non-pointer"
        return result

    offset = value - ROM_BASE
    result["file_offset"] = hx(offset, 6)
    window = _window_for(value)
    if window is None:
        result["status"] = "rom-outside-tested-text-windows"
        return result

    name, start, end = window
    result["window"] = name
    result["window_range"] = f"{hx(start - ROM_BASE, 6)}-{hx(end - ROM_BASE, 6)}"
    record = records.get(offset)
    if record is not None:
        result["status"] = "strict-record-start"
        result["record"] = record
    else:
        result["status"] = "strict-window-nonstrict-offset"
        previous_nul = rom.rfind(b"\0", 0, offset)
        next_nul = rom.find(b"\0", offset)
        if previous_nul >= 0 and next_nul >= previous_nul:
            span_start = previous_nul + 1
            span = rom[span_start : next_nul + 1]
            result["nearest_nul_span"] = {
                "start": hx(span_start, 6),
                "end": hx(next_nul, 6),
                "length": len(span),
                "sha256": hashlib.sha256(span).hexdigest(),
            }
    return result


def stop_metadata(
    stop: str,
    kind: str | None,
    address: int | None,
    registers: dict[str, int],
) -> dict[str, object]:
    return {
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else hx(address),
        "registers": register_metadata(registers),
        "ram_registers": {
            name: hx(value)
            for name, value in registers.items()
            if name in {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r12", "sp"}
            and is_ram_pointer(value)
        },
    }


def _set_breakpoint(client: GdbClient, address: int) -> None:
    # Use the shared client with the same software-breakpoint point type as
    # the already validated B3TJ runtime probe.
    client.set_breakpoint(address, kind=2, point_type=0)


def _remove_breakpoint(client: GdbClient, address: int) -> None:
    try:
        client.remove_breakpoint(address, kind=2, point_type=0)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def _set_watchpoint(client: GdbClient, address: int, length: int, watch_type: int) -> None:
    client.set_watchpoint(address, kind=length, watch_type=watch_type)


def _remove_watchpoint(
    client: GdbClient, address: int, length: int, watch_type: int
) -> None:
    try:
        client.remove_watchpoint(address, kind=length, watch_type=watch_type)
    except (RuntimeError, TimeoutError, OSError, ConnectionError):
        pass


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    record_offset: int,
    max_stops: int,
    per_stop_timeout: float,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    verify_b3tj(rom)
    records = strict_record_metadata(rom)
    selected = records.get(record_offset)
    if selected is None:
        raise ValueError(
            f"record offset {hx(record_offset, 6)} is not an exact strict record start"
        )
    target_address = ROM_BASE + record_offset

    fixed_entries = {
        "parser": hx(PARSER_ENTRY),
        "formatter_callsite": hx(FORMATTER_CALLSITE),
        "formatter": hx(FORMATTER_ENTRY),
        "glyph_candidate": hx(GLYPH_ENTRY),
        "codepoint_lookup": hx(CODEPOINT_LOOKUP),
        "writer_candidate": hx(WRITER_ENTRY),
        **{name: hx(address) for address, name in GLYPH_STORE_POINTS.items()},
    }
    report: dict[str, object] = {
        "mode": "bounded-live-parser-consumer",
        "rom": {"path": str(rom_path)},
        "identity": {
            "size": len(rom),
            "crc32": f"{binascii.crc32(rom) & 0xFFFFFFFF:08X}",
            "sha256": hashlib.sha256(rom).hexdigest(),
            "expected_size": EXPECTED_SIZE,
            "expected_crc32": f"{EXPECTED_CRC32:08X}",
        },
        "strict_record_count": len(records),
        "selected_record": selected,
        "selected_record_offset": hx(record_offset, 6),
        "selected_record_address": hx(target_address),
        "fixed_entries": fixed_entries,
        "provenance": {
            "natural_flow": "state7/parser entries are observed before injection; no strict source read is claimed from them",
            "argument_injected": "r1 is written once at parser hit 2 and only an OK ACK promotes the strict pipeline edge",
            "writes_state": False,
            "writes_object": False,
            "writes_save": False,
            "writes_rom": False,
        },
        "events": [],
        "counters": {
            "stops": 0,
            "parser_hits": 0,
            "source_read_hits": 0,
            "output_write_hits": 0,
            "output_read_hits": 0,
            "glyph_asset_read_hits": 0,
            "glyph_store_hits": 0,
        },
        "termination": "not-started",
    }
    events = report["events"]
    counters = report["counters"]
    assert isinstance(events, list)
    assert isinstance(counters, dict)

    client = GdbClient(host, port, timeout=max(6.0, per_stop_timeout))
    installed_breakpoints: set[int] = set()
    source_watch_address: int | None = None
    output_watch_address: int | None = None
    output_read_watch_address: int | None = None
    asset_watch_address: int | None = None
    injected = False
    try:
        client.connect()
        events.append({"event": "GDB_INITIAL", "stop": client.request("?")})
        initial_breakpoints = (
            (PARSER_ENTRY, "parser"),
            (FORMATTER_CALLSITE, "formatter_callsite"),
            (FORMATTER_ENTRY, "formatter"),
            (GLYPH_ENTRY, "glyph_candidate"),
            (CODEPOINT_LOOKUP, "codepoint_lookup"),
            (WRITER_ENTRY, "writer_candidate"),
        )
        for address, name in initial_breakpoints:
            _set_breakpoint(client, address)
            installed_breakpoints.add(address)
            events.append({"event": "BREAKPOINT_INSTALL", "name": name, "address": hx(address)})

        for _ in range(max_stops):
            stop = client.continue_until_stop(per_stop_timeout)
            registers = client.read_registers()
            kind, address = parse_stop_watch(stop)
            pc = registers.get("pc", 0) & ~1
            counters["stops"] = int(counters["stops"]) + 1

            if (
                source_watch_address is not None
                and kind == "rwatch"
                and address is not None
                and source_watch_address <= address < source_watch_address + 2
            ):
                counters["source_read_hits"] = int(counters["source_read_hits"]) + 1
                events.append(
                    {
                        "event": "SOURCE_READ",
                        "status": "confirmed-runtime-strict-record-source-read" if injected else "unexpected-preinject-source-read",
                        "source": classify_pointer(source_watch_address, rom, records),
                        "reader_pc": hx(registers.get("pc", 0)),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                _remove_watchpoint(client, source_watch_address, 1, 3)
                source_watch_address = None
                continue

            if (
                output_read_watch_address is not None
                and kind == "rwatch"
                and address is not None
                and output_read_watch_address <= address < output_read_watch_address + 1
            ):
                counters["output_read_hits"] = int(counters["output_read_hits"]) + 1
                events.append(
                    {
                        "event": "OUTPUT_READ",
                        "status": "confirmed-runtime-formatted-buffer-read",
                        "output_address": hx(output_read_watch_address),
                        "reader_pc": hx(registers.get("pc", 0)),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                _remove_watchpoint(client, output_read_watch_address, 1, 3)
                output_read_watch_address = None
                continue

            if (
                asset_watch_address is not None
                and kind == "rwatch"
                and address is not None
                and asset_watch_address <= address < asset_watch_address + FONT_ASSET_STRIDE
            ):
                counters["glyph_asset_read_hits"] = int(counters["glyph_asset_read_hits"]) + 1
                events.append(
                    {
                        "event": "GLYPH_ASSET_READ",
                        "status": "confirmed-runtime-glyph-asset-read",
                        "asset_address": hx(asset_watch_address),
                        "reader_pc": hx(registers.get("pc", 0)),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                _remove_watchpoint(client, asset_watch_address, FONT_ASSET_STRIDE, 3)
                asset_watch_address = None
                continue

            if (
                output_watch_address is not None
                and kind == "watch"
                and address is not None
                and output_watch_address <= address < output_watch_address + 1
            ):
                counters["output_write_hits"] = int(counters["output_write_hits"]) + 1
                events.append(
                    {
                        "event": "OUTPUT_WRITE",
                        "status": "confirmed-runtime-parser-output-write",
                        "output_address": hx(output_watch_address),
                        "writer_pc": hx(registers.get("pc", 0)),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                _remove_watchpoint(client, output_watch_address, 1, 2)
                if output_read_watch_address is None:
                    _set_watchpoint(client, output_watch_address, 1, 3)
                    output_read_watch_address = output_watch_address
                output_watch_address = None
                continue

            if pc in GLYPH_STORE_POINTS:
                store_name = GLYPH_STORE_POINTS[pc]
                if injected:
                    counters["glyph_store_hits"] = int(counters["glyph_store_hits"]) + 1
                    events.append(
                        {
                            "event": "GLYPH_STORE",
                            "status": "confirmed-runtime-glyph-destination-store",
                            "evidence_level": "argument-injected",
                            "instruction": store_name,
                            "destination_address": hx(registers.get("r1", 0)),
                            "value_register": "r4",
                            "caller_lr": hx(registers.get("lr", 0)),
                            "stop": stop_metadata(stop, kind, address, registers),
                        }
                    )
                    report["termination"] = "first-glyph-fixed-store"
                    break
                events.append(
                    {
                        "event": "GLYPH_STORE_PREINJECT",
                        "status": "observed-before-strict-record-injection",
                        "instruction": store_name,
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                continue

            if pc == PARSER_ENTRY:
                counters["parser_hits"] = int(counters["parser_hits"]) + 1
                ordinal = int(counters["parser_hits"])
                r0 = registers.get("r0", 0)
                r1 = registers.get("r1", 0)
                events.append(
                    {
                        "event": "PARSER",
                        "ordinal": ordinal,
                        "evidence_level": "natural-flow" if not injected else "argument-injected",
                        "r0_destination": classify_pointer(r0, rom, records),
                        "r1_source": classify_pointer(r1, rom, records),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                if ordinal == 2 and not injected:
                    register_value = target_address.to_bytes(4, "little").hex()
                    ack = client.request(f"P1={register_value}")
                    injected = ack == "OK"
                    events.append(
                        {
                            "event": "REGISTER_INJECT",
                            "register": "r1",
                            "value": hx(target_address),
                            "ack": ack,
                            "status": "argument-injected-parser-source" if injected else "register-injection-not-acknowledged",
                            "source": classify_pointer(target_address, rom, records),
                        }
                    )
                    if injected:
                        _set_watchpoint(client, target_address, 1, 3)
                        source_watch_address = target_address
                        if is_ram_pointer(r0):
                            _set_watchpoint(client, r0, 1, 2)
                            output_watch_address = r0
                        for glyph_address, name in GLYPH_STORE_POINTS.items():
                            _set_breakpoint(client, glyph_address)
                            installed_breakpoints.add(glyph_address)
                            events.append(
                                {
                                    "event": "BREAKPOINT_INSTALL",
                                    "name": name,
                                    "address": hx(glyph_address),
                                    "phase": "after-strict-injection",
                                }
                            )
                continue

            if pc == FORMATTER_CALLSITE:
                events.append(
                    {
                        "event": "FORMATTER_CALLSITE",
                        "status": "confirmed-runtime-formatter-callsite",
                        "evidence_level": "argument-injected" if injected else "natural-flow",
                        "stop": stop_metadata(stop, kind, address, registers),
                        "caller_lr": hx(registers.get("lr", 0)),
                    }
                )
                continue

            if pc == FORMATTER_ENTRY:
                events.append(
                    {
                        "event": "FORMATTER_ENTRY",
                        "status": "confirmed-runtime-formatted-buffer-consumer-entry",
                        "evidence_level": "argument-injected" if injected else "natural-flow",
                        "r0": classify_pointer(registers.get("r0", 0), rom, records),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                continue

            if pc == GLYPH_ENTRY:
                index = registers.get("r2", 0)
                asset = FONT_ASSET_BASE + index * FONT_ASSET_STRIDE
                event: dict[str, Any] = {
                    "event": "GLYPH_ENTRY",
                    "status": "confirmed-runtime-glyph-lookup-candidate",
                    "evidence_level": "argument-injected" if injected else "natural-flow",
                    "codepoint_index": hx(index),
                    "asset_formula": "0x080DDCC4 + r2*0x20",
                    "asset_address": hx(asset),
                    "caller_lr": hx(registers.get("lr", 0)),
                    "stop": stop_metadata(stop, kind, address, registers),
                }
                events.append(event)
                if injected and asset_watch_address is None and ROM_BASE <= asset < ROM_BASE + EXPECTED_SIZE:
                    _set_watchpoint(client, asset, FONT_ASSET_STRIDE, 3)
                    asset_watch_address = asset
                continue

            if pc == CODEPOINT_LOOKUP:
                events.append(
                    {
                        "event": "CODEPOINT_LOOKUP",
                        "status": "confirmed-runtime-codepoint-lookup-entry",
                        "evidence_level": "argument-injected" if injected else "natural-flow",
                        "r2": hx(registers.get("r2", 0)),
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                continue

            if pc == WRITER_ENTRY:
                events.append(
                    {
                        "event": "WRITER_ENTRY",
                        "status": "confirmed-runtime-iwram-writer-candidate",
                        "evidence_level": "argument-injected" if injected else "natural-flow",
                        "caller_lr": hx(registers.get("lr", 0)),
                        "stop": stop_metadata(stop, kind, address, registers),
                    }
                )
                continue

            report["termination"] = "unexpected-stop"
            events.append(
                {
                    "event": "UNEXPECTED_STOP",
                    "stop": stop_metadata(stop, kind, address, registers),
                }
            )
            break
        else:
            report["termination"] = "stop-limit"
    except (RuntimeError, TimeoutError, OSError, ConnectionError, ValueError) as exc:
        report["termination"] = "runtime-error"
        report["error_type"] = type(exc).__name__
        report["error_message"] = str(exc)
    finally:
        # mGBA 0.11 can hang while enumerating/removing a breakpoint list after
        # a fixed Thumb store stop.  The process is explicitly caller-owned;
        # close this one connection and let the caller terminate that exact
        # emulator PID before any rerun.  This keeps the probe bounded and
        # avoids pretending cleanup success is runtime evidence.
        report["cleanup"] = {
            "mode": "connection-close-only",
            "breakpoints_removed": False,
            "watchpoints_removed": False,
            "reason": "owned-mGBA-process-must-be-restarted-before-rerun",
        }
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--record-offset",
        type=lambda value: int(value, 0),
        default=DEFAULT_RECORD_OFFSET,
        help="exact strict file offset to inject at parser hit 2 (default: 0x140D68)",
    )
    parser.add_argument("--max-stops", type=int, default=64)
    parser.add_argument("--per-stop-timeout", type=float, default=8.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_stops < 1:
        parser.error("--max-stops must be positive")
    if args.per_stop_timeout <= 0:
        parser.error("--per-stop-timeout must be positive")
    try:
        report = run_probe(
            args.rom,
            host=args.host,
            port=args.port,
            record_offset=args.record_offset,
            max_stops=args.max_stops,
            per_stop_timeout=args.per_stop_timeout,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
