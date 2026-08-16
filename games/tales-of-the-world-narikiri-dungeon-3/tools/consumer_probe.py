#!/usr/bin/env python3
"""Bounded B3TJ string-consumer probe using the shared ``core/gba`` client.

This tool is game-specific only where it names the B3TJ record, KEYINPUT
navigation point and post-hit VRAM observation.  GDB packet transport,
watchpoints, register access and standard GBA region capture come from
``core/gba/gdbstub_client.py``; no per-game transport or renderer is copied.

The normal run settles at the title screen, then emulates a short active-low
START/A sequence by intercepting the game's KEYINPUT read and overriding the
destination register.  It watches one concrete direct-pointer string record
(``sjis:0x146EE0``), removes the input/record watches on a hit, and watches
one bounded post-hit VRAM write slice.  The ``--resolver-only`` mode instead
breaks at the static relative-pointer resolver ``0x08003444``, steps to its
return site, and records only returned pointers which fall in the five
declared text windows.  ``--trace-offset`` adds a caller-return breakpoint
and a read watchpoint for one already selected concrete record.  Raw dumps
and optional rendered PPMs belong in ``/private/tmp`` or ignored
``games/<game>/work`` only.

No decoded source text is printed.  The JSON report contains offsets,
registers, stop packets, hashes and ROM-to-VRAM exact-match metadata.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from extract_strings import DEFAULT_RANGES, iter_parsed_strings  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

TARGET_RECORD_OFFSET = 0x146EE0
TARGET_RECORD_ADDRESS = ROM_BASE + TARGET_RECORD_OFFSET
KEYINPUT_ADDRESS = 0x04000130
VRAM_ADDRESS = 0x06000000
RESOLVER_ENTRY = 0x08003444
RESOLVER_RETURN = 0x0800345C

TEXT_WINDOWS = tuple(
    (spec.name, ROM_BASE + spec.start, ROM_BASE + spec.end)
    for spec in DEFAULT_RANGES
)

NO_KEY = 0x03FF
KEY_BITS = {"a": 0, "b": 1, "select": 2, "start": 3, "right": 4, "left": 5, "up": 6, "down": 7, "r": 8, "l": 9}

REGION_SIZES = {
    "vram": (VRAM_ADDRESS, 0x18000),
    "palette": (0x05000000, 0x400),
    "oam": (0x07000000, 0x400),
    "iwram": (0x03000000, 0x8000),
}


def strict_record_metadata(rom: bytes) -> dict[int, dict[str, object]]:
    """Index strict record boundaries without retaining source text in output."""

    return {
        row.start: {
            "string_id": f"sjis:0x{row.start:06X}",
            "file_offset": f"0x{row.start:06X}",
            "gba_address": f"0x{ROM_BASE + row.start:08X}",
            "region": row.region,
            "raw_length": row.raw_length,
        }
        for row in iter_parsed_strings(rom, DEFAULT_RANGES)
    }


def classify_resolved_pointer(
    resolved_address: int, records: dict[int, dict[str, object]]
) -> dict[str, object]:
    """Classify one live resolver result against only the five known windows."""

    result: dict[str, object] = {
        "resolved_r0": f"0x{resolved_address:08X}",
        "status": "outside-tested-text-windows",
    }
    if not (ROM_BASE <= resolved_address < ROM_BASE + EXPECTED_SIZE):
        if resolved_address == 0:
            result["status"] = "null-result"
        return result

    file_offset = resolved_address - ROM_BASE
    result["file_offset"] = f"0x{file_offset:06X}"
    for name, start, end in TEXT_WINDOWS:
        if start <= resolved_address < end:
            result["window"] = name
            result["window_range"] = f"0x{start - ROM_BASE:06X}-0x{end - ROM_BASE:06X}"
            record = records.get(file_offset)
            if record is None:
                result["status"] = "confirmed-window-nonstrict-offset"
            else:
                result["status"] = "confirmed-window-record"
                result["record"] = record
            return result
    return result


def destination_candidates(registers: dict[str, int]) -> dict[str, str]:
    """Report RAM-looking register values, without reading or emitting RAM."""

    candidates: dict[str, str] = {}
    for name in ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r12", "sp"):
        value = registers.get(name, 0)
        if (
            0x02000000 <= value < 0x02040000
            or 0x03000000 <= value < 0x03008000
        ):
            candidates[name] = f"0x{value:08X}"
    return candidates


def normalized_pc(registers: dict[str, int]) -> int:
    return registers.get("pc", 0) & ~1


def parse_sequence(spec: str) -> list[tuple[str, int]]:
    phases: list[tuple[str, int]] = []
    for item in spec.split(","):
        name, count_text = item.split(":", 1)
        name = name.strip().lower()
        if name not in KEY_BITS and name != "none":
            raise ValueError(f"unknown key phase: {name}")
        count = int(count_text, 0)
        if count < 1:
            raise ValueError("key phase counts must be positive")
        phases.append((name, count))
    if not phases:
        raise ValueError("sequence must contain at least one phase")
    return phases


def key_value(name: str) -> int:
    if name == "none":
        return NO_KEY
    return NO_KEY & ~(1 << KEY_BITS[name])


def b3tj_identity(rom: bytes) -> dict[str, object]:
    crc32 = binascii.crc32(rom) & 0xFFFFFFFF
    title = rom[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = rom[0xAC:0xB0]
    maker_code = rom[0xB0:0xB2]
    result = {
        "size": len(rom),
        "crc32": f"{crc32:08X}",
        "title_ascii": title.decode("ascii", errors="replace"),
        "game_code": game_code.decode("ascii", errors="replace"),
        "maker_code": maker_code.decode("ascii", errors="replace"),
    }
    if (
        len(rom) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != b"TOWNARIKIRI3"
        or game_code != b"B3TJ"
        or maker_code != b"AF"
    ):
        raise ValueError(f"ROM identity mismatch: {result}")
    return result


def io_value(client: GdbClient, address: int, length: int = 2) -> int:
    return int.from_bytes(client.read_memory(address, length), "little")


def render_parameters(dispcnt: int, bg1cnt: int) -> dict[str, object]:
    return {
        "dispcnt": f"0x{dispcnt:04X}",
        "bg1cnt": f"0x{bg1cnt:04X}",
        "bg1_charbase": ((bg1cnt >> 2) & 0x3) * 0x4000,
        "bg1_screenbase": ((bg1cnt >> 8) & 0x1F) * 0x800,
        "bg1_bpp": 8 if bg1cnt & 0x80 else 4,
        "obj_mapping": "1d" if dispcnt & 0x40 else "2d",
    }


def exact_tile_matches(rom: bytes, vram: bytes, *, tile_size: int = 32) -> list[dict[str, object]]:
    """Find exact ROM copies for nonzero, tile-aligned VRAM tiles."""

    matches: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for vram_offset in range(0, len(vram) - tile_size + 1, tile_size):
        tile = vram[vram_offset : vram_offset + tile_size]
        if not any(tile):
            continue
        first = rom.find(tile)
        if first < 0:
            continue
        count = 0
        offsets: list[int] = []
        cursor = first
        while cursor >= 0 and len(offsets) < 8:
            offsets.append(cursor)
            count += 1
            cursor = rom.find(tile, cursor + 1)
        key = (vram_offset, first)
        if key in seen:
            continue
        seen.add(key)
        matches.append(
            {
                "vram_offset": f"0x{vram_offset:05X}",
                "rom_offsets": [f"0x{offset:06X}" for offset in offsets],
                "rom_match_count_capped": count,
            }
        )
    return matches


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: f"0x{value:08X}"
        for name, value in registers.items()
        if name in {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "sp", "lr", "pc", "cpsr"}
    }


def read_regions(client: GdbClient, dump_dir: Path | None) -> tuple[dict[str, object], dict[str, bytes]]:
    data: dict[str, bytes] = {}
    summaries: dict[str, object] = {}
    for name, (address, length) in REGION_SIZES.items():
        raw = client.read_memory(address, length)
        data[name] = raw
        summaries[name] = {
            "address": f"0x{address:08X}",
            "length": length,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "nonzero_bytes": sum(value != 0 for value in raw),
        }
        if dump_dir is not None:
            dump_dir.mkdir(parents=True, exist_ok=True)
            (dump_dir / f"{name}.bin").write_bytes(raw)
    return summaries, data


def _snapshot_source_read(
    stop: str,
    kind: str | None,
    address: int | None,
    registers: dict[str, int],
    record: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else f"0x{address:08X}",
        "pc": f"0x{registers['pc']:08X}",
        "lr": f"0x{registers['lr']:08X}",
        "registers": register_snapshot(registers),
        "destination_register_candidates": destination_candidates(registers),
        "record": record,
    }


def run_resolver_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    settle_seconds: float,
    per_event_timeout: float,
    sequence: list[tuple[str, int]],
    trace_offset: int | None,
    trace_first_record: bool,
    max_resolver_hits: int,
) -> dict[str, object]:
    """Trace the resolver and, optionally, one concrete record consumer.

    The probe deliberately examines only the return value of the known
    resolver and the five strict extractor windows.  It never scans pointers
    during the runtime session and never emits source bytes.  A trace target
    can be supplied after a resolver-only run; ``trace_first_record`` is a
    bounded fallback for the first strict record actually returned by the
    resolver.
    """

    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    records = strict_record_metadata(rom)
    requested_record = None
    requested_address = None
    if trace_offset is not None:
        requested_address = ROM_BASE + trace_offset
        requested_record = records.get(trace_offset)

    client = GdbClient(host, port, timeout=8.0)
    entry_breakpoint = False
    key_watch = False
    return_breakpoint = False
    caller_breakpoint = False
    caller_breakpoint_address: int | None = None
    record_watch = False
    active_record_address: int | None = None
    caller_trace_done = False
    report: dict[str, object] = {
        "mode": "resolver-breakpoint-and-live-caller",
        "rom": str(rom_path),
        "identity": identity,
        "strict_record_count": len(records),
        "tested_text_windows": [
            {
                "name": name,
                "start": f"0x{start - ROM_BASE:06X}",
                "end": f"0x{end - ROM_BASE:06X}",
            }
            for name, start, end in TEXT_WINDOWS
        ],
        "resolver": {
            "entry": f"0x{RESOLVER_ENTRY:08X}",
            "return_site": f"0x{RESOLVER_RETURN:08X}",
            "max_hits": max_resolver_hits,
            "hits": [],
        },
        "trace_request": {
            "requested_file_offset": (
                None if trace_offset is None else f"0x{trace_offset:06X}"
            ),
            "requested_gba_address": (
                None if requested_address is None else f"0x{requested_address:08X}"
            ),
            "requested_record": requested_record,
            "trace_first_record": trace_first_record,
        },
        "sequence": [{"key": name, "events": count} for name, count in sequence],
        "key_events": [],
        "source_read_hits": [],
        "caller_returns": [],
    }

    def install_record_watch(address: int, record: dict[str, object] | None) -> None:
        nonlocal record_watch, active_record_address
        if record_watch:
            return
        client.set_watchpoint(address, kind=1, watch_type=3)
        record_watch = True
        active_record_address = address
        trace = report["trace_request"]
        assert isinstance(trace, dict)
        trace.setdefault("selected_record", record)
        trace["active_watch_address"] = f"0x{address:08X}"

    def remove_record_watch() -> None:
        nonlocal record_watch, active_record_address
        if record_watch and active_record_address is not None:
            try:
                client.remove_watchpoint(active_record_address, kind=1, watch_type=3)
            finally:
                record_watch = False
                active_record_address = None

    def safe_interrupt() -> str | None:
        try:
            return client.interrupt(timeout=2.0)
        except (TimeoutError, OSError, ConnectionError):
            return None

    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = {
            "dispcnt": f"0x{io_value(client, 0x04000000):04X}",
            "bg1cnt": f"0x{io_value(client, 0x0400000A):04X}",
        }

        client.set_breakpoint(RESOLVER_ENTRY, kind=2)
        entry_breakpoint = True
        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        key_watch = True
        if requested_address is not None:
            install_record_watch(requested_address, requested_record)

        event_index = 0
        stop_requested = False
        for phase, event_count in sequence:
            desired = key_value(phase)
            for _ in range(event_count):
                while True:
                    if len(report["resolver"]["hits"]) >= max_resolver_hits:
                        report["termination"] = "resolver-hit-limit"
                        stop_requested = True
                        break
                    try:
                        stop = client.continue_until_stop(per_event_timeout)
                    except TimeoutError:
                        report["termination"] = "input-watch-timeout"
                        report["interrupt_stop"] = safe_interrupt()
                        stop_requested = True
                        break
                    registers = client.read_registers()
                    kind, address = parse_stop_watch(stop)
                    pc = normalized_pc(registers)

                    if pc == RESOLVER_ENTRY:
                        entry_registers = registers
                        resolver_hit: dict[str, object] = {
                            "entry_stop": stop,
                            "entry_registers": register_snapshot(entry_registers),
                            "table_base_r0": f"0x{entry_registers['r0']:08X}",
                            "index_r1": f"0x{entry_registers['r1']:08X}",
                            "caller_lr": f"0x{entry_registers['lr']:08X}",
                            "caller_return_site": f"0x{entry_registers['lr'] & ~1:08X}",
                        }
                        return_stop = None
                        return_registers = None
                        try:
                            client.set_breakpoint(RESOLVER_RETURN, kind=2)
                            return_breakpoint = True
                            return_stop = client.continue_until_stop(per_event_timeout)
                            return_registers = client.read_registers()
                        except TimeoutError:
                            resolver_hit["status"] = "return-site-timeout"
                            resolver_hit["interrupt_stop"] = safe_interrupt()
                            report["resolver"]["hits"].append(resolver_hit)
                            report["termination"] = "resolver-return-timeout"
                            stop_requested = True
                        finally:
                            if return_breakpoint:
                                try:
                                    client.remove_breakpoint(RESOLVER_RETURN, kind=2)
                                finally:
                                    return_breakpoint = False

                        if stop_requested:
                            break
                        assert return_stop is not None
                        assert return_registers is not None
                        resolved_address = return_registers["r0"]
                        pointer = classify_resolved_pointer(resolved_address, records)
                        resolver_hit.update(
                            {
                                "return_stop": return_stop,
                                "return_registers": register_snapshot(return_registers),
                                "resolved_r0": f"0x{resolved_address:08X}",
                                "pointer": pointer,
                                "status": pointer["status"],
                            }
                        )
                        report["resolver"]["hits"].append(resolver_hit)

                        record = pointer.get("record")
                        if pointer.get("status") == "confirmed-window-record":
                            assert isinstance(record, dict)
                            if requested_address is None and trace_first_record:
                                install_record_watch(
                                    resolved_address, record
                                )
                            should_trace_caller = (
                                active_record_address == resolved_address
                                and not caller_trace_done
                            )
                            if should_trace_caller:
                                caller_site = entry_registers["lr"] & ~1
                                caller_breakpoint_address = caller_site
                                caller_trace: dict[str, object] = {
                                    "record": record,
                                    "breakpoint": f"0x{caller_site:08X}",
                                }
                                try:
                                    client.set_breakpoint(caller_site, kind=2)
                                    caller_breakpoint = True
                                    caller_stop = client.continue_until_stop(
                                        per_event_timeout
                                    )
                                    caller_registers = client.read_registers()
                                    caller_kind, caller_address = parse_stop_watch(
                                        caller_stop
                                    )
                                    caller_trace.update(
                                        {
                                            "stop": caller_stop,
                                            "stop_kind": caller_kind,
                                            "stop_address": (
                                                None
                                                if caller_address is None
                                                else f"0x{caller_address:08X}"
                                            ),
                                            "pc": f"0x{caller_registers['pc']:08X}",
                                            "lr": f"0x{caller_registers['lr']:08X}",
                                            "registers": register_snapshot(
                                                caller_registers
                                            ),
                                        }
                                    )
                                    report["caller_returns"].append(caller_trace)
                                    caller_trace_done = True
                                except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
                                    caller_trace["status"] = "caller-return-or-breakpoint-error"
                                    caller_trace["error_type"] = type(exc).__name__
                                    caller_trace["interrupt_stop"] = safe_interrupt()
                                    report["caller_returns"].append(caller_trace)
                                    caller_trace_done = True
                                finally:
                                    if caller_breakpoint:
                                        try:
                                            client.remove_breakpoint(caller_site, kind=2)
                                        finally:
                                            caller_breakpoint = False
                                            caller_breakpoint_address = None
                        # The target remains stopped at caller return (if that
                        # breakpoint was used), so the outer loop can resume
                        # and observe the read watchpoint or KEYINPUT next.
                        continue

                    if (
                        record_watch
                        and active_record_address is not None
                        and address is not None
                        and active_record_address <= address < active_record_address + 4
                    ):
                        trace = report["trace_request"]
                        assert isinstance(trace, dict)
                        record = trace.get("selected_record")
                        report["source_read_hits"].append(
                            _snapshot_source_read(
                                stop, kind, address, registers,
                                record if isinstance(record, dict) else None,
                            )
                        )
                        remove_record_watch()
                        continue

                    if (
                        address is not None
                        and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2
                    ):
                        report["key_events"].append(
                            {
                                "index": event_index,
                                "phase": phase,
                                "requested_keyinput": f"0x{desired:04X}",
                                "stop": stop,
                                "stop_kind": kind,
                                "stop_address": f"0x{address:08X}",
                                "registers": register_snapshot(registers),
                            }
                        )
                        event_index += 1
                        # B3TJ's observed polling load places the value in r1;
                        # override only that destination after the read stop.
                        client.write_register(1, desired)
                        break

                    report["unexpected_stop"] = {
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": (
                            None if address is None else f"0x{address:08X}"
                        ),
                        "pc": f"0x{registers['pc']:08X}",
                        "registers": register_snapshot(registers),
                    }
                    report["termination"] = "unexpected-stop"
                    stop_requested = True
                    break
                if stop_requested:
                    break
            if stop_requested:
                break

        if "termination" not in report:
            report["termination"] = "sequence-exhausted"
        resolver = report["resolver"]
        assert isinstance(resolver, dict)
        resolver["hit_count"] = len(resolver["hits"])
        report["source_read_count"] = len(report["source_read_hits"])
        report["caller_return_count"] = len(report["caller_returns"])
    finally:
        if caller_breakpoint:
            try:
                if caller_breakpoint_address is not None:
                    client.remove_breakpoint(caller_breakpoint_address, kind=2)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if return_breakpoint:
            try:
                client.remove_breakpoint(RESOLVER_RETURN, kind=2)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if entry_breakpoint:
            try:
                client.remove_breakpoint(RESOLVER_ENTRY, kind=2)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if key_watch:
            try:
                client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if record_watch:
            try:
                remove_record_watch()
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        client.close()
    return report


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    settle_seconds: float,
    per_event_timeout: float,
    post_hit_timeout: float,
    sequence: list[tuple[str, int]],
    dump_dir: Path | None,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    client = GdbClient(host, port, timeout=8.0)
    key_watch = False
    record_watch = False
    vram_watch = False
    report: dict[str, object] = {
        "rom": str(rom_path),
        "identity": identity,
        "target_record": {
            "string_id": f"sjis:0x{TARGET_RECORD_OFFSET:06X}",
            "file_offset": f"0x{TARGET_RECORD_OFFSET:06X}",
            "gba_address": f"0x{TARGET_RECORD_ADDRESS:08X}",
        },
        "sequence": [{"key": name, "events": count} for name, count in sequence],
        "key_events": [],
        "record_hit": None,
        "post_hit_vram": None,
    }

    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())

        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = {
            "dispcnt": f"0x{io_value(client, 0x04000000):04X}",
            "bg1cnt": f"0x{io_value(client, 0x0400000A):04X}",
        }

        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        key_watch = True
        client.set_watchpoint(TARGET_RECORD_ADDRESS, kind=1, watch_type=3)
        record_watch = True

        target_hit = False
        event_index = 0
        for phase, event_count in sequence:
            desired = key_value(phase)
            for _ in range(event_count):
                try:
                    stop = client.continue_until_stop(per_event_timeout)
                except TimeoutError:
                    report["termination"] = "input-watch-timeout"
                    break
                kind, address = parse_stop_watch(stop)
                registers = client.read_registers()
                event = {
                    "index": event_index,
                    "phase": phase,
                    "requested_keyinput": f"0x{desired:04X}",
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                    "registers": register_snapshot(registers),
                }
                report["key_events"].append(event)
                event_index += 1

                if address is not None and TARGET_RECORD_ADDRESS <= address < TARGET_RECORD_ADDRESS + 4:
                    report["record_hit"] = {
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": f"0x{address:08X}",
                        "registers": register_snapshot(registers),
                        "caller_lr": f"0x{registers['lr']:08X}",
                        "pc": f"0x{registers['pc']:08X}",
                        "stack_pointer": f"0x{registers['sp']:08X}",
                    }
                    target_hit = True
                    break

                if address is None or not (KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2):
                    report["termination"] = "unexpected-stop"
                    break

                # mGBA stops after the load. r1 is the destination register in
                # B3TJ's observed KEYINPUT polling instruction.
                client.write_register(1, desired)
            if target_hit or report.get("termination") in {"input-watch-timeout", "unexpected-stop"}:
                break

        if not target_hit and "termination" not in report:
            report["termination"] = "sequence-exhausted-without-record-hit"

        if key_watch:
            client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            key_watch = False
        if record_watch:
            client.remove_watchpoint(TARGET_RECORD_ADDRESS, kind=1, watch_type=3)
            record_watch = False

        if target_hit:
            # Observe the next bounded screen update separately.  If the text
            # consumer writes glyph data after reading this record, the VRAM
            # write stop gives a concrete second runtime edge; otherwise the
            # absence is retained as a negative result.
            client.set_watchpoint(VRAM_ADDRESS, kind=4, watch_type=2)
            vram_watch = True
            try:
                stop = client.continue_until_stop(post_hit_timeout)
                kind, address = parse_stop_watch(stop)
                regs = client.read_registers()
                report["post_hit_vram"] = {
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                    "registers": register_snapshot(regs),
                }
            except TimeoutError:
                report["post_hit_vram"] = {"result": "no-vram-write-before-timeout"}
                try:
                    client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    pass
            finally:
                client.remove_watchpoint(VRAM_ADDRESS, kind=4, watch_type=2)
                vram_watch = False

            report["post_hit_io"] = {
                "dispcnt": io_value(client, 0x04000000),
                "bg1cnt": io_value(client, 0x0400000A),
            }
            report["render_parameters"] = render_parameters(
                report["post_hit_io"]["dispcnt"], report["post_hit_io"]["bg1cnt"]
            )
            summaries, raw = read_regions(client, dump_dir)
            report["regions"] = summaries
            report["rom_to_vram_exact_tiles"] = exact_tile_matches(rom, raw["vram"])
            report["exact_tile_match_count"] = len(report["rom_to_vram_exact_tiles"])
    finally:
        for address, kind, watch_type, active in (
            (KEYINPUT_ADDRESS, 2, 3, key_watch),
            (TARGET_RECORD_ADDRESS, 1, 3, record_watch),
            (VRAM_ADDRESS, 4, 2, vram_watch),
        ):
            if active:
                try:
                    client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
                except (RuntimeError, TimeoutError, OSError, ConnectionError):
                    pass
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    parser.add_argument("--per-event-timeout", type=float, default=5.0)
    parser.add_argument("--post-hit-timeout", type=float, default=3.0)
    parser.add_argument(
        "--sequence",
        default="start:8,none:12,a:8,none:12",
        help="comma-separated key:event-count phases",
    )
    parser.add_argument(
        "--resolver-only",
        action="store_true",
        help="trace 0x08003444 entry/return values without a record watchpoint",
    )
    parser.add_argument(
        "--trace-offset",
        type=lambda value: int(value, 0),
        help="run resolver mode and read-watch one concrete file offset",
    )
    parser.add_argument(
        "--trace-first-record",
        action="store_true",
        help="run resolver mode and trace the first strict-window record returned",
    )
    parser.add_argument(
        "--max-resolver-hits",
        type=int,
        default=24,
        help="bounded maximum resolver calls to record (default: 24)",
    )
    parser.add_argument("--dump-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        sequence = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    resolver_mode = (
        args.resolver_only
        or args.trace_offset is not None
        or args.trace_first_record
    )
    if args.max_resolver_hits < 1:
        parser.error("--max-resolver-hits must be positive")
    if resolver_mode:
        result = run_resolver_probe(
            args.rom,
            host=args.host,
            port=args.port,
            settle_seconds=args.settle_seconds,
            per_event_timeout=args.per_event_timeout,
            sequence=sequence,
            trace_offset=None if args.resolver_only else args.trace_offset,
            trace_first_record=(
                False if args.resolver_only else args.trace_first_record
            ),
            max_resolver_hits=args.max_resolver_hits,
        )
    else:
        result = run_probe(
            args.rom,
            host=args.host,
            port=args.port,
            settle_seconds=args.settle_seconds,
            per_event_timeout=args.per_event_timeout,
            post_hit_timeout=args.post_hit_timeout,
            sequence=sequence,
            dump_dir=args.dump_dir,
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
