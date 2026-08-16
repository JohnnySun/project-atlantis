#!/usr/bin/env python3
"""Bounded A5TJ queue, staging, and DMA3 probe.

The runtime mode connects to an already-running, session-owned mGBA GDB stub.
It records only addresses, PC/LR, selected argument registers, lengths, hashes,
and counts.  It never writes a ROM or emits RAM/VRAM/OAM bytes.

The static mode verifies the eight known fixed OBJ-DMA copies and the small
resource-queue contract.  It intentionally does not perform a font-pattern or
full-ROM glyph scan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


ROM_BASE = 0x08000000
ROM_LIMIT = 0x0A000000
KEYINPUT = 0x04000130
STAGING_BASE = 0x02001000
QUEUE_BASE = 0x02009004
QUEUE_ENTRY_STRIDE = 0x64
QUEUE_ENTRY_COUNT = 64
QUEUE_CALLBACK_TABLE = 0x0815EEEC
QUEUE_PRODUCER = 0x080AD0FC
QUEUE_DRAIN = 0x080AD01C
QUEUE_DISPATCH_SITES = (0x080AD070, 0x080AD0A2, 0x080AD0BE)
LZ77_WRAM_WRAPPER = 0x0815CB00

DMA3_REGISTERS = {
    "sad": 0x040000D4,
    "dad": 0x040000D8,
    "cnt": 0x040000DC,
}

# The five sites that were previously named in M1.5 are the first STR inside
# the routine.  Keep both the true entry and that store PC explicit.
FIXED_DMA_CANDIDATES = (
    {"name": "obj_dma_0baecc", "entry": 0x080BAECC},
    {"name": "obj_dma_0bb318", "entry": 0x080BB318},
    {"name": "obj_dma_0bb61c", "entry": 0x080BB61C},
    {"name": "obj_dma_0bbcdc", "entry": 0x080BBCD8},
    {"name": "obj_dma_0bc588", "entry": 0x080BC584},
    {"name": "obj_dma_0bc97c", "entry": 0x080BC978},
    {"name": "obj_dma_0d8d84", "entry": 0x080D8D80},
    {"name": "obj_dma_0d944c", "entry": 0x080D9448},
)

FIXED_DMA_INSTRUCTIONS = (
    0x4904,
    0x4805,
    0x6008,
    0x4805,
    0x6048,
    0x4805,
    0x6088,
    0x6888,
    0x4770,
)

# Queue entries observed in the reset -> Start run.  The first entry is the
# slot-base watch; the other two are the live entries carrying the observed
# resource pointers.  No separate monotonic head/tail variable was found in
# the bounded drain/producer disassembly; the entry flag is the queue state
# transition actually consumed by this code path.
QUEUE_WATCHES = {
    "entry0_flag": QUEUE_BASE,
    "observed_entry_1": QUEUE_BASE + QUEUE_ENTRY_STRIDE,
    "observed_entry_2": QUEUE_BASE + 2 * QUEUE_ENTRY_STRIDE,
}


def hex_address(value: int) -> str:
    return f"0x{value:08x}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    if 0x04000000 <= address < 0x04000400:
        return "io"
    if ROM_BASE <= address < ROM_LIMIT:
        return "rom"
    return "other"


def address_metadata(address: int, rom_size: int | None = None) -> dict[str, object]:
    item: dict[str, object] = {
        "address": hex_address(address),
        "region": region(address),
    }
    if ROM_BASE <= address < ROM_LIMIT:
        offset = address - ROM_BASE
        item["rom_offset"] = hex_address(offset)
        item["rom_offset_in_bounds"] = rom_size is None or offset < rom_size
    return item


def read_u16(data: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 2 > len(data):
        raise ValueError(f"address outside ROM: {hex_address(address)}")
    return int.from_bytes(data[offset : offset + 2], "little")


def read_u32(data: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"address outside ROM: {hex_address(address)}")
    return int.from_bytes(data[offset : offset + 4], "little")


def thumb_literal_load(data: bytes, instruction_address: int) -> dict[str, object]:
    """Decode a Thumb LDR Rt,[PC,#imm] and its literal value."""
    instruction = read_u16(data, instruction_address)
    if instruction & 0xF800 != 0x4800:
        raise ValueError(
            f"not a Thumb literal LDR at {hex_address(instruction_address)}"
        )
    pc_base = (instruction_address + 4) & ~3
    literal_address = pc_base + ((instruction & 0xFF) * 4)
    return {
        "instruction": f"0x{instruction:04x}",
        "register": (instruction >> 8) & 7,
        "literal_address": hex_address(literal_address),
        "value": hex_address(read_u32(data, literal_address)),
    }


def decode_fixed_dma(data: bytes, entry: int) -> dict[str, object]:
    """Verify one fixed 9-instruction DMA3 setup and return metadata only."""
    instructions = [read_u16(data, entry + offset) for offset in range(0, 0x12, 2)]
    valid = tuple(instructions) == FIXED_DMA_INSTRUCTIONS
    result: dict[str, object] = {
        "entry": hex_address(entry),
        "source_store_pc": hex_address(entry + 4),
        "instruction_end": hex_address(entry + 0x12),
        "literal_pool": {
            "start": hex_address(entry + 0x14),
            "end": hex_address(entry + 0x24),
        },
        "instruction_hash": sha256(
            data[entry - ROM_BASE : entry - ROM_BASE + 0x12]
        ),
        "instruction_pattern_valid": valid,
    }
    if not valid:
        result["decoded"] = None
        return result
    dma_register = thumb_literal_load(data, entry)
    source = thumb_literal_load(data, entry + 2)
    destination = thumb_literal_load(data, entry + 6)
    control = thumb_literal_load(data, entry + 10)
    result["decoded"] = {
        "dma_register": dma_register,
        "source": source,
        "destination": destination,
        "control": control,
        "transfer_units": int(str(control["value"]), 16) & 0xFFFF,
    }
    return result


def find_exact_u32(data: bytes, value: int, *, limit: int = 20) -> list[int]:
    needle = value.to_bytes(4, "little")
    offsets: list[int] = []
    start = 0
    while len(offsets) < limit:
        found = data.find(needle, start)
        if found < 0:
            break
        offsets.append(found)
        start = found + 1
    return offsets


def thumb_bl_target(data: bytes, instruction_address: int) -> int | None:
    """Decode a Thumb-2 BL pair, returning an untagged target address."""
    first = read_u16(data, instruction_address)
    second = read_u16(data, instruction_address + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    imm11 = second & 0x07FF
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    offset = (sign << 24) | (i1 << 23) | (i2 << 22)
    offset |= imm10 << 12
    offset |= imm11 << 1
    if offset & (1 << 24):
        offset -= 1 << 25
    return (instruction_address + 4 + offset) & ~1


def direct_bl_callers(data: bytes, target: int, *, limit: int = 20) -> list[str]:
    callers: list[str] = []
    for offset in range(0, max(0, len(data) - 3), 2):
        address = ROM_BASE + offset
        try:
            decoded = thumb_bl_target(data, address)
        except ValueError:
            break
        if decoded == target:
            callers.append(hex_address(address))
            if len(callers) >= limit:
                break
    return callers


def queue_contract() -> dict[str, object]:
    return {
        "drain": hex_address(QUEUE_DRAIN),
        "producer": hex_address(QUEUE_PRODUCER),
        "entry_base": hex_address(QUEUE_BASE),
        "entry_stride": hex_address(QUEUE_ENTRY_STRIDE),
        "entry_count": QUEUE_ENTRY_COUNT,
        "callback_table": hex_address(QUEUE_CALLBACK_TABLE),
        "dispatch_sites": [hex_address(site) for site in QUEUE_DISPATCH_SITES],
        "entry_fields": {
            "state": "0x00",
            "type": "0x02",
            "argument": "0x04",
            "source_pointer": "0x14",
            "progress": "0x10",
            "sentinel_check": "0x20",
        },
        "head_tail_finding": "no separate head/tail slot in bounded drain/producer disassembly; entry state is consumed",
    }


def build_static_report(data: bytes) -> dict[str, object]:
    fixed: list[dict[str, object]] = []
    for spec in FIXED_DMA_CANDIDATES:
        entry = int(spec["entry"])
        item = decode_fixed_dma(data, entry)
        item["name"] = spec["name"]
        item["thumb_pointer_refs"] = [
            hex_address(offset) for offset in find_exact_u32(data, entry + 1)
        ]
        item["direct_bl_callers"] = direct_bl_callers(data, entry)
        fixed.append(item)
    staging_entry = 0x080BAEF0
    staging_window = data[staging_entry - ROM_BASE : staging_entry - ROM_BASE + 0x78]
    return {
        "schema": "smt2.m1.6.static.v1",
        "rom": {"size": len(data), "sha256": sha256(data)},
        "fixed_dma_candidates": fixed,
        "fixed_dma_count": len(fixed),
        "staging_writer_candidate": {
            "entry": hex_address(staging_entry),
            "instruction_window_length": len(staging_window),
            "instruction_window_hash": sha256(staging_window),
            "staging_bases": [hex_address(STAGING_BASE), hex_address(STAGING_BASE + 0x1000)],
            "lz77_wrapper": hex_address(LZ77_WRAM_WRAPPER),
            "runtime_status": "not_hit_in_reset_to_start_window",
        },
        "queue": queue_contract(),
    }


def register_metadata(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: hex_address(registers[name])
        for name in ("r0", "r1", "r2", "r3", "lr", "pc")
    }


def thumb_store_info(data: bytes | None, pc: int) -> dict[str, object] | None:
    """Decode the simple Thumb store immediately before a watchpoint stop."""
    if data is None or not ROM_BASE + 2 <= pc < ROM_LIMIT:
        return None
    instruction_address = pc - 2
    instruction = read_u16(data, instruction_address)
    if instruction & 0xF800 == 0x6000:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_imm",
            "register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 4,
        }
    if instruction & 0xF800 == 0x8000:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_halfword_imm",
            "register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 2,
        }
    if instruction & 0xF000 == 0x9000 and not instruction & 0x0800:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_sp_relative",
            "register": (instruction >> 8) & 7,
            "base_register": 13,
            "offset": (instruction & 0xFF) * 4,
        }
    return None


def queue_entry_metadata(data: bytes, address: int) -> dict[str, object] | None:
    if address < 0x02000000 or address >= 0x02040000:
        return None
    if len(data) < 0x24:
        return None
    return {
        "address": hex_address(address),
        "length": len(data),
        "hash": sha256(data),
        "state": hex_address(int.from_bytes(data[0:2], "little")),
        "type": hex_address(int.from_bytes(data[2:4], "little")),
        "argument": hex_address(int.from_bytes(data[4:6], "little")),
        "progress": hex_address(int.from_bytes(data[0x10:0x14], "little")),
        "source": address_metadata(int.from_bytes(data[0x14:0x18], "little")),
        "sentinel": hex_address(int.from_bytes(data[0x20:0x24], "little")),
    }


def event_base(site: str, registers: dict[str, int]) -> dict[str, object]:
    return {
        "site": site,
        "pc": hex_address(registers["pc"]),
        "lr": hex_address(registers["lr"]),
        "registers": register_metadata(registers),
    }


def runtime_summary(report: dict[str, object]) -> dict[str, object]:
    """Reduce a probe report to counts and metadata for research notes."""
    events = report.get("events", [])
    if not isinstance(events, list):
        events = []
    site_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    for event in events:
        if not isinstance(event, dict):
            continue
        site = event.get("site")
        kind = event.get("kind")
        if isinstance(site, str):
            site_counts[site] += 1
        if isinstance(kind, str):
            kind_counts[kind] += 1
    return {
        "schema": "smt2.m1.6.runtime-summary.v1",
        "stopped_reason": report.get("stopped_reason"),
        "keyinput_read_hits": report.get("keyinput_read_hits", 0),
        "start_sent": report.get("start_sent", False),
        "event_count": len(events),
        "site_counts": dict(sorted(site_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
        "watchpoint_counts": report.get("watchpoint_counts", {}),
        "queue_source_count": len(report.get("queue_sources", []))
        if isinstance(report.get("queue_sources", []), list)
        else 0,
        "obj_dma_hits": sum(
            count
            for name, count in site_counts.items()
            if name.startswith("obj_dma_")
        ),
        "staging_write_hits": site_counts.get("staging_buffer", 0),
    }


def _rom_length_field(data: bytes, address: int) -> int | None:
    if not ROM_BASE <= address < ROM_LIMIT:
        return None
    offset = address - ROM_BASE
    if offset + 4 > len(data):
        return None
    header = int.from_bytes(data[offset : offset + 4], "little")
    if header & 0xFF != 0x10:
        return None
    return (header >> 8) & 0xFFFFFF


def _append_bounded(events: list[dict[str, object]], item: dict[str, object], limit: int) -> None:
    if len(events) < limit:
        events.append(item)


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
    """Run one bounded trace against a live, already-started mGBA session."""
    client = GdbClient(port=port, timeout=max(timeout, 1.0), packet_delay=0.05)
    events: list[dict[str, object]] = []
    queue_sources: list[dict[str, object]] = []
    watchpoint_counts: Counter[str] = Counter()
    watchpoint_samples: Counter[str] = Counter()
    site_counts: Counter[str] = Counter()
    installed_breakpoints: list[int] = []
    installed_watchpoints: list[tuple[int, int, int]] = []
    key_hits = 0
    start_sent = False
    start_polls = 0
    stopped_reason = "limit"
    started_at = time.monotonic()
    site_by_pc: dict[int, str] = {
        QUEUE_PRODUCER: "queue_producer",
        **{site: "queue_dispatch" for site in QUEUE_DISPATCH_SITES},
        0x080BAEF0: "staging_writer_candidate",
        LZ77_WRAM_WRAPPER: "lz77_wrapper",
    }
    for spec in FIXED_DMA_CANDIDATES:
        entry = int(spec["entry"])
        site_by_pc[entry] = str(spec["name"])
        site_by_pc[entry + 4] = str(spec["name"])

    def record(site: str, registers: dict[str, int], **extra: object) -> None:
        item = {"kind": "breakpoint", **event_base(site, registers)}
        item.update(extra)
        site_counts[site] += 1
        _append_bounded(events, item, record_limit)

    client.connect()
    try:
        for address in sorted(site_by_pc):
            client.set_breakpoint(address, kind=2, point_type=1)
            installed_breakpoints.append(address)
        client.set_watchpoint(STAGING_BASE, kind=4, watch_type=2)
        installed_watchpoints.append((STAGING_BASE, 4, 2))
        for name, address in QUEUE_WATCHES.items():
            client.set_watchpoint(address, kind=4, watch_type=2)
            installed_watchpoints.append((address, 4, 2))
        for name, address in DMA3_REGISTERS.items():
            client.set_watchpoint(address, kind=4, watch_type=2)
            installed_watchpoints.append((address, 4, 2))
        if press_start:
            client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
            installed_watchpoints.append((KEYINPUT, 2, 3))

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
            registers = client.read_registers()
            if watch_kind in {"watch", "awatch"} and watch_address is not None:
                watch_name = next(
                    (name for name, address in QUEUE_WATCHES.items() if address == watch_address),
                    None,
                )
                if watch_name is None:
                    watch_name = next(
                        (name for name, address in DMA3_REGISTERS.items() if address == watch_address),
                        None,
                    )
                if watch_address == STAGING_BASE:
                    watch_name = "staging_buffer"
                watch_name = watch_name or "other_watchpoint"
                watchpoint_counts[watch_name] += 1
                item = {
                    "kind": "watchpoint",
                    "site": watch_name,
                    "pc": hex_address(registers["pc"]),
                    "lr": hex_address(registers["lr"]),
                    "watch_address": hex_address(watch_address),
                    "registers": register_metadata(registers),
                    "length": 4,
                }
                if watch_name in DMA3_REGISTERS:
                    store = thumb_store_info(rom, registers["pc"])
                    value = None
                    if store is not None:
                        value = registers[f"r{int(store['register'])}"]
                    item["store"] = store
                    item["value"] = None if value is None else hex_address(value)
                    if watch_name == "cnt" and value is not None:
                        item["transfer_units"] = value & 0xFFFF
                elif watch_name == "staging_buffer":
                    try:
                        sample = client.read_memory(STAGING_BASE, 0x40)
                    except (RuntimeError, TimeoutError, ConnectionError):
                        sample = b""
                    item["sample_length"] = len(sample)
                    item["sample_hash"] = sha256(sample) if sample else None
                elif watch_name in QUEUE_WATCHES:
                    try:
                        entry_bytes = client.read_memory(watch_address, 0x24)
                    except (RuntimeError, TimeoutError, ConnectionError):
                        entry_bytes = b""
                    item["entry"] = queue_entry_metadata(entry_bytes, watch_address)
                # DMA register stores can be frequent.  Keep a small sample
                # per watchpoint while retaining complete counts, so the
                # record budget still reaches queue and candidate breakpoints.
                if watchpoint_samples[watch_name] < 4:
                    _append_bounded(events, item, record_limit)
                    watchpoint_samples[watch_name] += 1
                continue
            if "T05" not in stop and not stop.startswith("S"):
                stopped_reason = "unexpected-stop"
                break
            site = site_by_pc.get(registers["pc"])
            if site is None:
                stopped_reason = "unexpected-breakpoint"
                break
            if site == "queue_producer":
                source = registers["r0"]
                source_item = {
                    **address_metadata(source, None if rom is None else len(rom)),
                    "count": 1,
                }
                queue_sources.append(source_item)
                record(
                    site,
                    registers,
                    source=source_item,
                    argument=hex_address(registers["r1"]),
                )
            elif site == "queue_dispatch":
                entry_address = registers["r0"]
                try:
                    entry_bytes = client.read_memory(entry_address, 0x24)
                except (RuntimeError, TimeoutError, ConnectionError):
                    entry_bytes = b""
                record(
                    site,
                    registers,
                    entry=queue_entry_metadata(entry_bytes, entry_address),
                    callback_target=address_metadata(registers["r1"]),
                )
            elif site == "lz77_wrapper":
                length = _rom_length_field(rom or b"", registers["r0"])
                record(
                    site,
                    registers,
                    source=address_metadata(registers["r0"], None if rom is None else len(rom)),
                    destination=address_metadata(registers["r1"]),
                    length=length,
                )
            else:
                record(site, registers, length=None)
        else:
            stopped_reason = "event-or-wall-limit"
    finally:
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
        "schema": "smt2.m1.6.runtime.v1",
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
        "keyinput_read_hits": key_hits,
        "start_sent": start_sent,
        "breakpoint_counts": dict(sorted(site_counts.items())),
        "watchpoint_counts": dict(sorted(watchpoint_counts.items())),
        "watchpoint_sample_counts": dict(sorted(watchpoint_samples.items())),
        "queue_sources": queue_sources[:record_limit],
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="local A5TJ ROM; never copied to output")
    parser.add_argument("--static-only", action="store_true", help="verify fixed DMA and queue metadata without GDB")
    parser.add_argument("--summary", action="store_true", help="write only a metadata summary of --input-report")
    parser.add_argument("--input-report", type=Path, help="existing runtime JSON for --summary")
    parser.add_argument("--port", type=int, default=2367)
    parser.add_argument("--max-events", type=int, default=256)
    parser.add_argument("--record-limit", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=35.0)
    parser.add_argument("--press-start", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_events <= 0 or args.record_limit <= 0 or args.timeout <= 0 or args.wall_seconds <= 0:
        parser.error("bounds must be positive")
    rom = args.rom.read_bytes()
    if args.summary:
        if args.input_report is None:
            parser.error("--summary requires --input-report")
        report = runtime_summary(json.loads(args.input_report.read_text(encoding="utf-8")))
    elif args.static_only:
        report = build_static_report(rom)
    else:
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
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
