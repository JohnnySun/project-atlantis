#!/usr/bin/env python3
"""Bounded natural A5TJ OBJ-consumer runtime trace.

M1.12 observes only the twelve known ``0x06010000`` literal-load sites and
the DMA3 source/destination/control registers.  It drives a short natural
resource-transition key sequence; the only runtime register writes are the
active-low KEYINPUT values needed for navigation.  Output is limited to
addresses, PC/LR/register metadata, source classifications, bounded hashes,
lengths, and counts.  No raw RAM/VRAM/ROM bytes are emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m17_descriptor_probe import KEY_VALUES, _parse_key_sequence  # noqa: E402
from m16_queue_probe import ROM_BASE, ROM_LIMIT, address_metadata, hex_address, sha256  # noqa: E402


SCHEMA = "smt2.m1.12.obj-runtime.v1"
KEYINPUT = 0x04000130
DMA3_SAD = 0x040000D4
DMA3_DAD = 0x040000D8
DMA3_CNT = 0x040000DC
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
OAM_BASE = 0x07000000
OAM_LENGTH = 0x400

# These are the literal-load PCs established by M1.11.  They are kept as a
# bounded cohort instead of scanning all OBJ/ROM code at runtime.
OBJ_VRAM_LITERAL_LOADS = (
    0x080ABD80,
    0x080AC1B0,
    0x080BD136,
    0x080C1350,
    0x080D1DFC,
    0x080D5514,
    0x080D5E6E,
    0x080D5F8E,
    0x080D61F2,
    0x080D9A3E,
    0x080DC6AA,
    0x0813EFCE,
)

DMA_WATCHES = {
    "sad": DMA3_SAD,
    "dad": DMA3_DAD,
    "cnt": DMA3_CNT,
}


def region(address: int) -> str:
    if ROM_BASE <= address < ROM_LIMIT:
        return "rom"
    if 0x02000000 <= address < 0x02040000:
        return "ewram"
    if 0x03000000 <= address < 0x03008000:
        return "iwram"
    if 0x06010000 <= address < 0x06018000:
        return "obj_vram"
    if 0x06000000 <= address < 0x06010000:
        return "bg_vram"
    if 0x07000000 <= address < 0x07000400:
        return "oam"
    if 0x05000000 <= address < 0x05000400:
        return "palette"
    if 0x04000000 <= address < 0x04000400:
        return "io"
    return "other"


def register_metadata(registers: dict[str, int]) -> dict[str, str]:
    names = [f"r{number}" for number in range(8)] + ["r12", "sp", "lr", "pc"]
    return {name: hex_address(registers[name]) for name in names}


def store_metadata(rom: bytes, pc: int) -> dict[str, object] | None:
    """Decode only the register/width/offset of a Thumb store before PC."""
    if not ROM_BASE + 2 <= pc < ROM_LIMIT:
        return None
    offset = pc - ROM_BASE - 2
    if offset < 0 or offset + 2 > len(rom):
        return None
    instruction = int.from_bytes(rom[offset : offset + 2], "little")
    if instruction & 0xF800 == 0x6000:
        return {
            "form": "str_word_imm",
            "source_register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 4,
            "width": 4,
        }
    if instruction & 0xF800 == 0x8000:
        return {
            "form": "str_halfword_imm",
            "source_register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 2,
            "width": 2,
        }
    if instruction & 0xF000 == 0x9000 and not instruction & 0x0800:
        return {
            "form": "str_word_sp_relative",
            "source_register": (instruction >> 8) & 7,
            "base_register": 13,
            "offset": (instruction & 0xFF) * 4,
            "width": 4,
        }
    return None


def _safe_read(client: GdbClient, address: int, length: int) -> bytes:
    try:
        return client.read_memory(address, length)
    except (ConnectionError, RuntimeError, TimeoutError):
        return b""


def source_metadata(client: GdbClient, rom: bytes, address: int, *, sample_length: int = 0x40) -> dict[str, object]:
    item: dict[str, object] = {
        "address": address_metadata(address, len(rom)),
        "source_region": region(address),
        "sample_length": 0,
        "sample_hash": None,
    }
    if ROM_BASE <= address < ROM_BASE + len(rom):
        raw = rom[address - ROM_BASE : min(len(rom), address - ROM_BASE + sample_length)]
    elif region(address) in {"ewram", "iwram", "obj_vram", "bg_vram", "oam", "palette"}:
        raw = _safe_read(client, address, sample_length)
    else:
        raw = b""
    item["sample_length"] = len(raw)
    item["sample_hash"] = sha256(raw) if raw else None
    return item


def screen_metadata(client: GdbClient) -> dict[str, object]:
    vram = _safe_read(client, VRAM_BASE, VRAM_LENGTH)
    oam = _safe_read(client, OAM_BASE, OAM_LENGTH)
    return {
        "vram": {"length": len(vram), "hash": sha256(vram) if vram else None},
        "oam": {"length": len(oam), "hash": sha256(oam) if oam else None},
    }


class KeyScheduler:
    def __init__(self, names: list[str], idle_reads: int, hold_reads: int, gap_reads: int) -> None:
        self.names = names
        self.idle_reads = idle_reads
        self.hold_reads = hold_reads
        self.gap_reads = gap_reads
        self.reads = 0
        self.sent: list[str] = []

    def next_value(self) -> tuple[int, str | None]:
        self.reads += 1
        if self.reads <= self.idle_reads:
            return KEY_VALUES["none"], None
        phase = self.reads - self.idle_reads - 1
        cycle = self.hold_reads + self.gap_reads
        index = phase // cycle
        if index >= len(self.names):
            return KEY_VALUES["none"], None
        within = phase % cycle
        if within < self.hold_reads:
            name = self.names[index]
            if within == 0:
                self.sent.append(name)
                return KEY_VALUES[name], f"sent:{name}"
            return KEY_VALUES[name], None
        return KEY_VALUES["none"], None


def trace(
    *,
    port: int,
    rom: bytes,
    key_sequence: list[str],
    max_stops: int,
    record_limit: int,
    timeout: float,
    wall_seconds: float,
    idle_key_reads: int,
    hold_key_reads: int,
    gap_key_reads: int,
) -> dict[str, object]:
    client = GdbClient(port=port, timeout=max(timeout, 1.0), packet_delay=0.05)
    scheduler = KeyScheduler(key_sequence, idle_key_reads, hold_key_reads, gap_key_reads)
    events: list[dict[str, object]] = []
    site_counts: Counter[str] = Counter()
    watch_counts: Counter[str] = Counter()
    install_failures: list[dict[str, object]] = []
    installed_breakpoints: list[int] = []
    installed_watchpoints: list[tuple[int, int, int]] = []
    dma_values: dict[str, int | None] = {name: None for name in DMA_WATCHES}
    started = time.monotonic()
    stop_count = 0
    stopped_reason = "limit"
    screen_snapshot: dict[str, object] | None = None

    def add_event(item: dict[str, object]) -> None:
        if len(events) < record_limit:
            item.setdefault("elapsed_ms", round((time.monotonic() - started) * 1000, 1))
            events.append(item)

    def install_breakpoint(address: int) -> None:
        try:
            client.set_breakpoint(address, kind=2, point_type=1)
            installed_breakpoints.append(address)
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "breakpoint", "address": hex_address(address), "error": type(exc).__name__})

    def install_watchpoint(address: int, kind: int, watch_type: int, name: str) -> None:
        try:
            client.set_watchpoint(address, kind=kind, watch_type=watch_type)
            installed_watchpoints.append((address, kind, watch_type))
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "watchpoint", "address": hex_address(address), "name": name, "error": type(exc).__name__})

    client.connect()
    try:
        for address in OBJ_VRAM_LITERAL_LOADS:
            install_breakpoint(address)
        for name, address in DMA_WATCHES.items():
            install_watchpoint(address, 4, 2, name)
        install_watchpoint(KEYINPUT, 2, 3, "keyinput")

        while stop_count < max_stops and time.monotonic() - started < wall_seconds:
            try:
                stop = client.continue_until_stop(timeout=timeout)
            except TimeoutError:
                stopped_reason = "timeout"
                try:
                    client.interrupt(timeout=1.0)
                except (ConnectionError, RuntimeError, TimeoutError):
                    pass
                break
            stop_count += 1
            watch_kind, watch_address = parse_stop_watch(stop)
            if watch_kind == "rwatch" and watch_address == KEYINPUT:
                value, phase = scheduler.next_value()
                if phase is not None:
                    add_event({"kind": "input", "site": "keyinput_scheduler", "phase": phase, "key_reads": scheduler.reads})
                client.write_register(0, value)
                continue

            registers = client.read_registers()
            if watch_kind in {"watch", "awatch"} and watch_address is not None:
                name = next((item for item, address in DMA_WATCHES.items() if address == watch_address), "other_watchpoint")
                watch_counts[name] += 1
                store = store_metadata(rom, registers["pc"])
                stored_value = None
                if store is not None:
                    stored_value = registers[f"r{int(store['source_register'])}"]
                    dma_values[name] = stored_value
                item: dict[str, object] = {
                    "kind": "watchpoint",
                    "site": name,
                    "pc": hex_address(registers["pc"]),
                    "lr": hex_address(registers["lr"]),
                    "watch_address": hex_address(watch_address),
                    "registers": register_metadata(registers),
                    "store": store,
                    "stored_value": None if stored_value is None else hex_address(stored_value),
                    "stored_value_region": None if stored_value is None else region(stored_value),
                }
                if name == "cnt" and stored_value is not None:
                    item["transfer_units"] = stored_value & 0xFFFF
                    item["dma_control"] = hex_address(stored_value)
                if name == "sad" and stored_value is not None:
                    item["source"] = source_metadata(client, rom, stored_value)
                if name == "dad" and stored_value is not None:
                    item["destination"] = {"address": hex_address(stored_value), "region": region(stored_value)}
                if dma_values["sad"] is not None and dma_values["dad"] is not None:
                    item["dma_edge"] = {
                        "source": source_metadata(client, rom, dma_values["sad"]),
                        "destination": {"address": hex_address(dma_values["dad"]), "region": region(dma_values["dad"])},
                    }
                add_event(item)
                continue

            if "T05" not in stop and not stop.startswith("S"):
                stopped_reason = "unexpected-stop"
                break
            if registers["pc"] in OBJ_VRAM_LITERAL_LOADS:
                site_counts[hex_address(registers["pc"])] += 1
                add_event(
                    {
                        "kind": "breakpoint",
                        "site": "obj_vram_literal_consumer",
                        "pc": hex_address(registers["pc"]),
                        "lr": hex_address(registers["lr"]),
                        "registers": register_metadata(registers),
                        "literal_value": hex_address(0x06010000),
                        "destination_family": "obj_vram_base_candidate",
                        "dma_state": {
                            name: None if value is None else hex_address(value)
                            for name, value in dma_values.items()
                        },
                    }
                )
            else:
                stopped_reason = "unexpected-breakpoint"
                break
        else:
            stopped_reason = "event-or-wall-limit"
    finally:
        try:
            screen_snapshot = screen_metadata(client)
        except (ConnectionError, RuntimeError, TimeoutError):
            screen_snapshot = None
        for address in reversed(installed_breakpoints):
            try:
                client.remove_breakpoint(address, kind=2, point_type=1)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        for address, kind, watch_type in reversed(installed_watchpoints):
            try:
                client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        client.close()

    return {
        "schema": SCHEMA,
        "port": port,
        "rom": {"size": len(rom), "sha256": sha256(rom)},
        "bounds": {
            "max_stops": max_stops,
            "record_limit": record_limit,
            "timeout_seconds": timeout,
            "wall_seconds": wall_seconds,
            "key_sequence": key_sequence,
            "idle_key_reads": idle_key_reads,
            "hold_key_reads": hold_key_reads,
            "gap_key_reads": gap_key_reads,
        },
        "natural_transition": True,
        "same_reset_start_negative_repeated": False,
        "stopped_reason": stopped_reason,
        "stop_count": stop_count,
        "keyinput_read_hits": scheduler.reads,
        "keys_sent": scheduler.sent,
        "breakpoint_counts": dict(sorted(site_counts.items())),
        "watchpoint_counts": dict(sorted(watch_counts.items())),
        "install_failures": install_failures,
        "screen": screen_snapshot,
        "events": events,
        "consumer_cohort": {
            "literal_value": hex_address(0x06010000),
            "literal_load_count": len(OBJ_VRAM_LITERAL_LOADS),
            "literal_loads": [hex_address(value) for value in OBJ_VRAM_LITERAL_LOADS],
        },
        "conclusions": {
            "source_pointer_or_code_unit": "not_recovered_in_this_window",
            "glyph_chain": "not_established",
            "translation_ledger": "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=2367)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--key-sequence", default="a,start,a,b,down,a,right,a")
    parser.add_argument("--max-stops", type=int, default=512)
    parser.add_argument("--record-limit", type=int, default=160)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=35.0)
    parser.add_argument("--idle-key-reads", type=int, default=40)
    parser.add_argument("--hold-key-reads", type=int, default=2)
    parser.add_argument("--gap-key-reads", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.max_stops, args.record_limit, args.timeout, args.wall_seconds) <= 0:
        parser.error("bounds must be positive")
    try:
        key_sequence = _parse_key_sequence(args.key_sequence)
    except ValueError as exc:
        parser.error(str(exc))
    report = trace(
        port=args.port,
        rom=args.rom.read_bytes(),
        key_sequence=key_sequence,
        max_stops=args.max_stops,
        record_limit=args.record_limit,
        timeout=args.timeout,
        wall_seconds=args.wall_seconds,
        idle_key_reads=args.idle_key_reads,
        hold_key_reads=args.hold_key_reads,
        gap_key_reads=args.gap_key_reads,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
