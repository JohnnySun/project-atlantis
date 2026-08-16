#!/usr/bin/env python3
"""Bounded A5TJ DMA destination trace.

This observes writes to the four GBA DMA destination registers while an
already-running mGBA session advances.  It records source/destination/control
metadata only, so the result can identify a VRAM transfer without preserving
raw ROM, RAM, or tile data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


KEYINPUT = 0x04000130
DMA_DESTINATIONS = {
    0: (0x040000B4, 0x040000B0),
    1: (0x040000C0, 0x040000BC),
    2: (0x040000CC, 0x040000C8),
    3: (0x040000D8, 0x040000D4),
}


def region(address: int) -> str:
    if 0x06010000 <= address < 0x06018000:
        return "obj_vram"
    if 0x06000000 <= address < 0x06010000:
        return "bg_vram"
    if 0x07000000 <= address < 0x07000400:
        return "oam"
    if 0x05000000 <= address < 0x05000400:
        return "palette"
    if 0x02000000 <= address < 0x02040000:
        return "ewram"
    if 0x03000000 <= address < 0x03008000:
        return "iwram"
    return "other"


def hex_address(value: int) -> str:
    return f"0x{value:08x}"


def thumb_store_info(rom: bytes | None, pc: int) -> dict[str, object] | None:
    """Decode the simple Thumb store immediately before a watchpoint stop."""
    if rom is None or not 0x08000002 <= pc < 0x0A000000:
        return None
    offset = pc - 0x08000000 - 2
    if offset < 0 or offset + 2 > len(rom):
        return None
    instruction = int.from_bytes(rom[offset : offset + 2], "little")
    if instruction & 0xF800 == 0x6000:  # STR word, immediate offset
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_imm",
            "register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 4,
        }
    if instruction & 0xF800 == 0x8000:  # STRH, immediate offset
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_halfword_imm",
            "register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 2,
        }
    if instruction & 0xF000 == 0x9000:  # STR word, SP-relative
        if instruction & 0x0800:
            return None
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_sp_relative",
            "register": (instruction >> 8) & 7,
            "base_register": 13,
            "offset": (instruction & 0xFF) * 4,
        }
    return None


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    names = [f"r{number}" for number in range(8)] + ["r12", "sp", "lr", "pc"]
    return {name: hex_address(registers[name]) for name in names}


def trace(
    *,
    port: int,
    rom: bytes | None,
    max_events: int,
    record_limit: int,
    timeout: float,
    wall_seconds: float,
    press_start: bool,
) -> dict[str, object]:
    client = GdbClient(port=port, timeout=max(timeout, 1.0), packet_delay=0.05)
    events: list[dict[str, object]] = []
    region_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    key_hits = 0
    start_sent = False
    start_polls = 0
    stopped_reason = "limit"
    started_at = time.monotonic()
    last_source: dict[int, int | None] = {channel: None for channel in DMA_DESTINATIONS}
    last_destination: dict[int, int | None] = {channel: None for channel in DMA_DESTINATIONS}
    client.connect()
    try:
        for _channel, (destination_register, source_register) in DMA_DESTINATIONS.items():
            client.set_watchpoint(destination_register, kind=4, watch_type=2)
            client.set_watchpoint(source_register, kind=4, watch_type=2)
        if press_start:
            client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
        while len(events) < max_events and time.monotonic() - started_at < wall_seconds:
            try:
                stop = client.continue_until_stop(timeout=timeout)
            except TimeoutError:
                stopped_reason = "timeout"
                try:
                    client.interrupt(timeout=1.0)
                except (TimeoutError, ConnectionError):
                    pass
                break
            watch_kind, watch_address = parse_stop_watch(stop)
            if watch_kind == "rwatch" and watch_address == KEYINPUT:
                key_hits += 1
                if not start_sent:
                    client.write_register(0, 0x3F7)
                    start_sent = True
                    start_polls = 1
                elif start_polls < 6:
                    client.write_register(0, 0x3F7)
                    start_polls += 1
                else:
                    client.write_register(0, 0x3FF)
                continue
            if watch_kind not in {"watch", "awatch"} or watch_address is None:
                stopped_reason = "unexpected-stop"
                break
            register_kind = next(
                (
                    (number, "destination")
                    for number, (dest, _source) in DMA_DESTINATIONS.items()
                    if dest == watch_address
                ),
                None,
            ) or next(
                (
                    (number, "source")
                    for number, (_dest, source) in DMA_DESTINATIONS.items()
                    if source == watch_address
                ),
                None,
            )
            if register_kind is None:
                stopped_reason = "unexpected-watchpoint"
                break
            channel, register_name = register_kind
            registers = client.read_registers()
            store = thumb_store_info(rom, registers["pc"])
            stored_value = None
            if store is not None:
                register_number = int(store["register"])
                stored_value = registers[f"r{register_number}"]
            if stored_value is not None and register_name == "source":
                last_source[channel] = stored_value
            if stored_value is not None and register_name == "destination":
                last_destination[channel] = stored_value
            source = last_source[channel]
            destination = last_destination[channel]
            item = {
                "channel": channel,
                "register_kind": register_name,
                "pc": hex_address(registers["pc"]),
                "watch_address": hex_address(watch_address),
                "store": store,
                "stored_value": None if stored_value is None else hex_address(stored_value),
                "stored_value_region": None if stored_value is None else region(stored_value),
                "source": None if source is None else hex_address(source),
                "source_region": None if source is None else region(source),
                "destination": None if destination is None else hex_address(destination),
                "destination_region": None if destination is None else region(destination),
                "registers": register_snapshot(registers),
                "stop": stop[:80],
            }
            events.append(item)
            if register_name == "destination" and destination is not None:
                destination_region = region(destination)
                region_counts[destination_region] = region_counts.get(destination_region, 0) + 1
            channel_key = str(channel)
            channel_counts[channel_key] = channel_counts.get(channel_key, 0) + 1
        else:
            stopped_reason = "event-or-wall-limit"
    finally:
        for _channel, (destination_register, source_register) in DMA_DESTINATIONS.items():
            try:
                client.remove_watchpoint(destination_register, kind=4, watch_type=2)
                client.remove_watchpoint(source_register, kind=4, watch_type=2)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        if press_start:
            try:
                client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        client.close()
    return {
        "port": port,
        "rom": None if rom is None else {"size": len(rom)},
        "bounds": {
            "max_events": max_events,
            "record_limit": record_limit,
            "timeout_seconds": timeout,
            "wall_seconds": wall_seconds,
            "press_start": press_start,
        },
        "stopped_reason": stopped_reason,
        "keyinput_read_hits": key_hits,
        "start_sent": start_sent,
        "destination_region_counts": region_counts,
        "channel_counts": channel_counts,
        "events": events[:record_limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2367)
    parser.add_argument("--rom", type=Path, help="optional ROM for Thumb store decoding")
    parser.add_argument("--max-events", type=int, default=256)
    parser.add_argument("--record-limit", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=30.0)
    parser.add_argument("--press-start", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_events <= 0 or args.record_limit <= 0 or args.timeout <= 0 or args.wall_seconds <= 0:
        parser.error("bounds must be positive")
    rom = None if args.rom is None else args.rom.read_bytes()
    report = trace(
        port=args.port,
        rom=rom,
        max_events=args.max_events,
        record_limit=args.record_limit,
        timeout=args.timeout,
        wall_seconds=args.wall_seconds,
        press_start=args.press_start,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
