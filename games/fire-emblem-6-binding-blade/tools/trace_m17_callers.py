#!/usr/bin/env python3
"""Trace FE6 M1.7 high-level text callers and one bounded scene transition.

This is a game-specific layer over ``core/gba/gdbstub_client.py``.  It
records static Thumb call evidence, selector/index/source provenance, return
LR/callsite registers, output hashes, marker offsets, and display hashes.  It
never writes the ROM and never serializes source or raw RAM bytes.

The loader breakpoint must be placed at the first halfword of the Thumb BL
(``0x08013b02``), not at ``0x08013b04``.  The latter is the second halfword of
that instruction and produces a misleading stop/LR pair.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


ROM_BASE = 0x08000000
ROM_SIZE = 8 * 1024 * 1024
EXPECTED_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)
EXPECTED_GAME_CODE = "AFEJ"

POINTER_TABLE = 0x080F635C
POINTER_TABLE_END = 3342
CALLER_INDEX_TABLE = 0x08691738
BUFFER = 0x02029404
BUFFER_SIZE = 0x400
RENDER_SINK = 0x06014000

HIGH_CALLER = 0x08098AFC
HIGH_CALLSITE = 0x08098B10
LOADER_ENTRY = 0x08013AD0
LOADER_BL = 0x08013B02
LOADER_RETURN = 0x08013B08
OLD_PROVENANCE = 0x08002B06
COPY_WRAPPER = 0x0800384C
WORKER = 0x0300323C

KEYINPUT = 0x04000130
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

TRACE_POINTS = (HIGH_CALLER, HIGH_CALLSITE, LOADER_ENTRY, LOADER_BL, LOADER_RETURN)


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def snapshot(regs: dict[str, int]) -> dict[str, str]:
    names = {"pc", "lr", "sp", "cpsr", "r0", "r1", "r2", "r7"}
    return {name: hex32(value) for name, value in regs.items() if name in names}


def u16(data: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(data[offset:offset + 2], "little")


def u32(data: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(data[offset:offset + 4], "little")


def is_rom_pointer(value: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + ROM_SIZE


def thumb_bl_target(first: int, second: int, address: int) -> int:
    """Decode a Thumb-2 BL pair and return its absolute target."""

    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    imm11 = second & 0x07FF
    offset = (sign << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if sign:
        offset -= 1 << 25
    return (address + 4 + offset) & 0xFFFFFFFF


def static_proof(rom: bytes) -> dict[str, object]:
    """Return static facts needed to interpret the runtime receipts."""

    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    if rom[0xAC:0xB0].decode("ascii", errors="replace") != EXPECTED_GAME_CODE:
        raise ValueError("ROM game code is not AFEJ")
    digest = hashlib.sha256(rom).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("ROM SHA-256 is not the reviewed AFEJ revision")

    caller_first = u16(rom, HIGH_CALLSITE)
    caller_second = u16(rom, HIGH_CALLSITE + 2)
    loader_first = u16(rom, LOADER_BL)
    loader_second = u16(rom, LOADER_BL + 2)
    table_end = 0
    while is_rom_pointer(u32(rom, POINTER_TABLE + table_end * 4)):
        table_end += 1
        if table_end > 10000:
            raise ValueError("pointer-table scan exceeded safety bound")

    selector_values = [u32(rom, CALLER_INDEX_TABLE + index * 4) for index in range(8)]
    return {
        "rom_sha256": digest,
        "high_caller": hex32(HIGH_CALLER),
        "high_callsite": hex32(HIGH_CALLSITE),
        "high_callsite_halfwords": [hex(caller_first), hex(caller_second)],
        "high_callsite_bl_target": hex32(
            thumb_bl_target(caller_first, caller_second, HIGH_CALLSITE)
        ),
        "loader_entry": hex32(LOADER_ENTRY),
        "loader_bl": hex32(LOADER_BL),
        "loader_bl_halfwords": [hex(loader_first), hex(loader_second)],
        "loader_bl_target": hex32(thumb_bl_target(loader_first, loader_second, LOADER_BL)),
        "loader_return": hex32(LOADER_RETURN),
        "old_provenance": hex32(OLD_PROVENANCE),
        "old_provenance_halfwords": [hex(u16(rom, OLD_PROVENANCE)), hex(u16(rom, OLD_PROVENANCE + 2))],
        "pointer_table": hex32(POINTER_TABLE),
        "pointer_table_domain": [0, table_end],
        "pointer_table_first_nonpointer": {
            "index": table_end,
            "entry": hex32(POINTER_TABLE + table_end * 4),
            "value": hex32(u32(rom, POINTER_TABLE + table_end * 4)),
        },
        "caller_index_table": hex32(CALLER_INDEX_TABLE),
        "caller_index_table_values_0_7": selector_values,
    }


def table_provenance(rom: bytes, index: int) -> dict[str, object]:
    if not 0 <= index < POINTER_TABLE_END:
        return {"table_index": index, "within_proven_table": False}
    entry_address = POINTER_TABLE + index * 4
    source = u32(rom, entry_address)
    return {
        "table_index": index,
        "within_proven_table": True,
        "table_entry": hex32(entry_address),
        "source_pointer": hex32(source),
    }


def buffer_summary(data: bytes) -> dict[str, object]:
    digest = hashlib.sha256(data).hexdigest()
    terminator = data.find(b"\x00")
    if terminator < 0:
        terminator = None
    scan_end = len(data) if terminator is None else terminator + 1
    marker_bytes = (0x00, 0x01, 0x04, 0xFF)
    markers = {
        f"0x{value:02x}": [
            index for index, byte in enumerate(data[:scan_end]) if byte == value
        ]
        for value in marker_bytes
    }
    return {
        "address": hex32(BUFFER),
        "buffer_length": len(data),
        "buffer_sha256": digest,
        "logical_terminator_offset": terminator,
        "control_marker_offsets": markers,
    }


def display_state(client: GdbClient) -> dict[str, object]:
    vram = client.read_memory(0x06000000, 0x18000)
    dispcnt = int.from_bytes(client.read_memory(0x04000000, 2), "little")
    bgcnt = [
        int.from_bytes(client.read_memory(0x04000008 + index * 2, 2), "little")
        for index in range(4)
    ]
    return {
        "dispcnt": hex(dispcnt),
        "bgcnt": [hex(value) for value in bgcnt],
        "vram_sha256": hashlib.sha256(vram).hexdigest(),
        "vram_nonzero_bytes": sum(byte != 0 for byte in vram),
    }


def loader_caller_from_lr(lr: int) -> Optional[str]:
    """Convert a valid Thumb BL return LR to its callsite when recognizable."""

    if not (lr & 1):
        return None
    return hex32((lr & ~1) - 4)


class Trace:
    def __init__(self, client: GdbClient, rom: bytes, max_records: int) -> None:
        self.client = client
        self.rom = rom
        self.max_records = max_records
        self.events: list[dict[str, object]] = []
        self.loader_records: list[dict[str, object]] = []
        self._last_loader: Optional[dict[str, object]] = None

    def install(self) -> None:
        for address in TRACE_POINTS:
            self.client.set_breakpoint(address)

    def uninstall(self) -> None:
        for address in TRACE_POINTS:
            try:
                self.client.remove_breakpoint(address)
            except (ConnectionError, OSError, RuntimeError):
                pass

    def handle_stop(self, stop: str) -> dict[str, object]:
        regs = self.client.read_registers()
        pc = regs["pc"] & 0xFFFFFFFF
        stop_kind, stop_address = parse_stop_watch(stop)
        row: dict[str, object] = {
            "stop": stop,
            "pc": hex32(pc),
            "registers": snapshot(regs),
        }
        if stop_kind is not None:
            row["stop_kind"] = stop_kind
            row["stop_address"] = None if stop_address is None else hex32(stop_address)
        if stop_address == BUFFER:
            row["kind"] = "ewram_buffer_write_watch"
        elif stop_address == RENDER_SINK:
            row["kind"] = "renderer_vram_write_watch"
        elif pc == HIGH_CALLER:
            row["kind"] = "high_caller_entry"
            row["selector_argument"] = regs["r0"]
        elif pc == HIGH_CALLSITE:
            selector = regs["r7"]
            index = regs["r0"]
            row["kind"] = "high_caller_loader_callsite"
            row["selector"] = selector
            row["mapped_loader_index"] = index
            row["caller_table_entry"] = hex32(CALLER_INDEX_TABLE + selector * 4)
            row["provenance"] = table_provenance(self.rom, index)
        elif pc == LOADER_ENTRY:
            index = regs["r0"]
            row["kind"] = "loader_entry"
            row["loader_index"] = index
            row["provenance"] = table_provenance(self.rom, index)
            row["return_lr_callsite"] = loader_caller_from_lr(regs["lr"])
        elif pc == LOADER_BL:
            index = int.from_bytes(self.client.read_memory(regs["r7"], 4), "little")
            row["kind"] = "loader_copy_bl_callsite"
            row["loader_index"] = index
            row["source_pointer_register"] = hex32(regs["r0"])
            row["destination_register"] = hex32(regs["r1"])
            row["copy_wrapper"] = hex32(COPY_WRAPPER)
            row["worker"] = hex32(WORKER)
            row["provenance"] = table_provenance(self.rom, index)
            row["return_lr_callsite"] = loader_caller_from_lr(regs["lr"])
            self._last_loader = row
        elif pc == LOADER_RETURN:
            row["kind"] = "loader_return"
            if self._last_loader is not None:
                row["loader_index"] = self._last_loader.get("loader_index")
                row["return_lr_callsite"] = self._last_loader.get("return_lr_callsite")
            row.update(buffer_summary(self.client.read_memory(BUFFER, BUFFER_SIZE)))
            if self._last_loader is not None:
                record = {
                    "loader_index": self._last_loader.get("loader_index"),
                    "provenance": self._last_loader.get("provenance"),
                    "source_pointer_register": self._last_loader.get("source_pointer_register"),
                    "copy_callsite": self._last_loader.get("return_lr_callsite"),
                    "buffer": {key: value for key, value in row.items() if key in {
                        "address", "buffer_length", "buffer_sha256",
                        "logical_terminator_offset", "control_marker_offsets",
                    }},
                }
                if len(self.loader_records) < self.max_records:
                    self.loader_records.append(record)
        self.events.append(row)
        return row

    def continue_for(self, seconds: float, *, stop_on_max_records: bool = False) -> dict[str, object]:
        deadline = time.monotonic() + seconds
        timeouts = 0
        while time.monotonic() < deadline:
            remaining = max(0.25, deadline - time.monotonic())
            try:
                stop = self.client.continue_until_stop(min(remaining, 5.0))
            except TimeoutError:
                timeouts += 1
                try:
                    stop = self.client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    break
            self.handle_stop(stop)
            if stop_on_max_records and len(self.loader_records) >= self.max_records:
                break
        return {"timeouts": timeouts, "event_count": len(self.events)}

    def continue_to_input(
        self,
        button: str,
        *,
        hold_events: int,
        release_events: int,
        event_timeout: float,
        input_register: int,
    ) -> dict[str, object]:
        desired = NO_KEY & ~(1 << BUTTON_BITS[button])
        key_events: list[dict[str, object]] = []
        termination = "completed"
        self.client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
        try:
            total = hold_events + release_events
            stop_count = 0
            while len(key_events) < total and stop_count < total * 8:
                stop_count += 1
                try:
                    stop = self.client.continue_until_stop(event_timeout)
                except TimeoutError:
                    termination = "keyinput-watch-timeout"
                    try:
                        self.client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        termination = "keyinput-watch-timeout-interrupt-failed"
                    break
                kind, address = parse_stop_watch(stop)
                regs = self.client.read_registers()
                index = len(key_events)
                if address == KEYINPUT:
                    value = desired if index < hold_events else NO_KEY
                    self.client.write_register(input_register, value)
                    key_events.append({
                        "index": index,
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": hex32(address),
                        "requested_keyinput": hex(value),
                        "registers": snapshot(regs),
                    })
                else:
                    self.handle_stop(stop)
                    key_events.append({
                        "index": index,
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": None if address is None else hex32(address),
                        "interleaved_trace_stop": True,
                        "registers": snapshot(regs),
                    })
                    # This iteration did not consume a KEYINPUT read.  Do not
                    # advance the desired value; the loop count above is only a
                    # safety bound and the requested value is based on the
                    # number of actual KEYINPUT reads below.
                    key_events.pop()
                    continue
        finally:
            self.client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
        if len(key_events) < total and termination == "completed":
            termination = "input-stop-limit"
        return {
            "button": button,
            "hold_events": hold_events,
            "release_events": release_events,
            "termination": termination,
            "key_events": key_events,
        }


def parse_sequence(value: str) -> list[str]:
    sequence = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not sequence or any(item not in BUTTON_BITS for item in sequence):
        raise ValueError(f"sequence must contain known buttons: {sorted(BUTTON_BITS)}")
    return sequence


def identity(rom_path: Path) -> dict[str, object]:
    data = rom_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE or digest != EXPECTED_SHA256:
        raise ValueError("ROM identity mismatch; expected the reviewed AFEJ revision")
    return {
        "size": len(data),
        "sha256": digest,
        "game_code": data[0xAC:0xB0].decode("ascii", errors="replace"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--initial-seconds", type=float, default=3.0)
    parser.add_argument("--step-seconds", type=float, default=1.0)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--sequence", default="start,a,b")
    parser.add_argument("--max-records", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sequence = parse_sequence(args.sequence)
    if not 0 <= args.input_register <= 12:
        parser.error("input register must be r0..r12")
    if not 1 <= args.max_records <= 32:
        parser.error("max-records must be between 1 and 32")

    rom = args.rom.read_bytes()
    report: dict[str, object] = {
        "rom": identity(args.rom),
        "static": static_proof(rom),
        "runtime": {
            "port": args.port,
            "trace_points": [hex32(address) for address in TRACE_POINTS],
            "input": {
                "keyinput": hex32(KEYINPUT),
                "input_register": f"r{args.input_register}",
                "active_low_idle": hex(NO_KEY),
            },
            "sequence": sequence,
            "events": [],
            "loader_records": [],
            "screens": [],
        },
    }

    client = GdbClient(port=args.port, timeout=args.timeout)
    trace = Trace(client, rom, args.max_records)
    try:
        client.connect()
        runtime = report["runtime"]
        assert isinstance(runtime, dict)
        runtime["supported"] = client.request("qSupported:multiprocess+")
        runtime["initial_stop"] = client.request("?")
        runtime["initial_registers"] = snapshot(client.read_registers())
        trace.install()
        initial = trace.continue_for(args.initial_seconds, stop_on_max_records=True)
        runtime["initial_collection"] = initial
        runtime["pre_input_display"] = display_state(client)

        previous = runtime["pre_input_display"]
        assert isinstance(previous, dict)
        for button in sequence:
            step = trace.continue_to_input(
                button,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
                input_register=args.input_register,
            )
            settle_event_start = len(trace.events)
            client.set_watchpoint(BUFFER, kind=4, watch_type=2)
            try:
                trace.continue_for(args.step_seconds)
            finally:
                client.remove_watchpoint(BUFFER, kind=4, watch_type=2)
            settle_events = trace.events[settle_event_start:]
            step["buffer_write_watch_count"] = sum(
                event.get("kind") == "ewram_buffer_write_watch"
                for event in settle_events
            )
            current = display_state(client)
            step["display"] = current
            step["display_changed"] = (
                current["dispcnt"] != previous["dispcnt"]
                or current["bgcnt"] != previous["bgcnt"]
                or current["vram_sha256"] != previous["vram_sha256"]
            )
            runtime["screens"].append(step)
            previous = current
        runtime["events"] = trace.events
        runtime["loader_records"] = trace.loader_records
    finally:
        trace.uninstall()
        client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
