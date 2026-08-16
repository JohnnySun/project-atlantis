#!/usr/bin/env python3
"""Bounded A5TJ BIOS-SWI consumer trace.

Connect to an already-running mGBA GDB stub and stop at the GBA SWI vector.
The report records only register metadata, ROM offsets, hashes, and bounded
counts.  It is intended to identify an earlier CpuSet/CpuFastSet consumer of
OBJ VRAM without saving a ROM, RAM dump, decompressed stream, or game text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


KEYINPUT = 0x04000130
SWI_VECTOR = 0x00000008
OBJ_VRAM_START = 0x06010000
OBJ_VRAM_END = 0x06018000
BG_VRAM_START = 0x06000000
BG_VRAM_END = 0x06010000
IWRAM_START = 0x03000000
IWRAM_END = 0x03008000
EWRAM_START = 0x02000000
EWRAM_END = 0x02040000


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def region(address: int) -> str:
    if OBJ_VRAM_START <= address < OBJ_VRAM_END:
        return "obj_vram"
    if BG_VRAM_START <= address < BG_VRAM_END:
        return "bg_vram"
    if IWRAM_START <= address < IWRAM_END:
        return "iwram"
    if EWRAM_START <= address < EWRAM_END:
        return "ewram"
    if 0x07000000 <= address < 0x07000400:
        return "oam"
    if 0x05000000 <= address < 0x05000400:
        return "palette"
    return "other"


def swi_number(rom: bytes | None, link_register: int) -> int | None:
    """Read an immediate from a Thumb SWI immediately before the return PC."""
    if rom is None or not 0x08000000 <= link_register < 0x0A000000:
        return None
    offset = link_register - 0x08000000 - 2
    if offset < 0 or offset + 1 >= len(rom):
        return None
    if rom[offset + 1] != 0xDF:
        return None
    return rom[offset]


def source_metadata(address: int, rom_size: int | None) -> dict[str, object]:
    item: dict[str, object] = {"address": f"0x{address:08x}", "region": region(address)}
    if 0x08000000 <= address < 0x0A000000:
        offset = address - 0x08000000
        item["rom_offset"] = f"0x{offset:x}"
        item["rom_offset_in_bounds"] = rom_size is None or offset < rom_size
    return item


def event_record(
    registers: dict[str, int],
    rom: bytes | None,
    *,
    stop_packet: str,
) -> dict[str, object]:
    r0 = registers["r0"]
    r1 = registers["r1"]
    r2 = registers["r2"]
    lr = registers["lr"]
    return {
        "pc": f"0x{registers['pc']:08x}",
        "lr": f"0x{lr:08x}",
        "swi": swi_number(rom, lr),
        "source": source_metadata(r0, None if rom is None else len(rom)),
        "destination": source_metadata(r1, None),
        "control": f"0x{r2:08x}",
        "destination_region": region(r1),
        "stop": stop_packet[:80],
    }


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
    all_events: list[dict[str, object]] = []
    obj_events: list[dict[str, object]] = []
    region_counts: dict[str, int] = {}
    swi_counts: dict[str, int] = {}
    vector_hits = 0
    key_hits = 0
    start_polls = 0
    start_sent = False
    started_at = time.monotonic()
    stopped_reason = "limit"
    client.connect()
    try:
        client.set_breakpoint(SWI_VECTOR, kind=2)
        if press_start:
            client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
        while vector_hits < max_events and time.monotonic() - started_at < wall_seconds:
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
            if "T05" not in stop and not stop.startswith("S"):
                stopped_reason = "unexpected-stop"
                break
            registers = client.read_registers()
            vector_hits += 1
            item = event_record(registers, rom, stop_packet=stop)
            destination_region = str(item["destination_region"])
            region_counts[destination_region] = region_counts.get(destination_region, 0) + 1
            swi_value = item["swi"]
            swi_key = "unknown" if swi_value is None else f"0x{int(swi_value):02x}"
            swi_counts[swi_key] = swi_counts.get(swi_key, 0) + 1
            if len(all_events) < record_limit:
                all_events.append(item)
            if destination_region == "obj_vram":
                obj_events.append(item)
                if len(obj_events) >= record_limit:
                    stopped_reason = "obj-record-limit"
                    break
        else:
            stopped_reason = "event-or-wall-limit"
    finally:
        for action, address, kind, point_type in (
            ("breakpoint", SWI_VECTOR, 2, 1),
            ("watchpoint", KEYINPUT, 2, 3),
        ):
            try:
                if action == "breakpoint":
                    client.remove_breakpoint(address, kind=kind, point_type=point_type)
                elif press_start:
                    client.remove_watchpoint(address, kind=kind, watch_type=point_type)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        client.close()
    return {
        "port": port,
        "rom": None if rom is None else {"size": len(rom), "sha256": sha256(rom)},
        "bounds": {
            "max_events": max_events,
            "record_limit": record_limit,
            "timeout_seconds": timeout,
            "wall_seconds": wall_seconds,
            "press_start": press_start,
        },
        "stopped_reason": stopped_reason,
        "vector_hits": vector_hits,
        "keyinput_read_hits": key_hits,
        "start_sent": start_sent,
        "destination_region_counts": region_counts,
        "swi_counts": swi_counts,
        "obj_vram_events": obj_events,
        "events": all_events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2367)
    parser.add_argument("--rom", type=Path, help="optional local ROM for hash and SWI opcode classification")
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
