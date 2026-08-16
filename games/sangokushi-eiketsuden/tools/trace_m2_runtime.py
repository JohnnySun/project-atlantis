#!/usr/bin/env python3
"""Bounded B3EJ M2 pointer/record/runtime-glyph trace.

This game-specific harness names one reviewed short record from the
``menu_battle_candidate_a`` pool.  GDB packet transport, register access and
watchpoints come from ``core/gba/gdbstub_client.py``.  The report contains
addresses, stop packets, register snapshots, hashes and VRAM-delta counts;
it never prints or writes original source text, ROM bytes, or rendered images.

The harness expects an already-running B3EJ mGBA GDB session on a caller-owned
port.  It keeps one client connection, intercepts active-low KEYINPUT reads to
send a bounded START sequence, watches the selected pointer-table entry and
record, then summarizes the post-sequence VRAM change.  Use the shared
``core/gba/render_vram.py`` separately on ignored captures when a visual
check is required.  When enabled, the static-chain wrapper breakpoint at
``0x0800D8F0`` records the actual ``r0`` source pointer before the byte reader;
it does not claim that the downstream glyph writer has been found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_GAME_CODE = "B3EJ"
KEYINPUT_ADDRESS = 0x04000130
NO_KEY = 0x03FF
KEY_BITS = {"a": 0, "b": 1, "select": 2, "start": 3, "right": 4, "left": 5,
            "up": 6, "down": 7, "r": 8, "l": 9}

# Table B in the research ledger: one short, valid-SJIS battle-effect record.
CANDIDATE = {
    "label": "menu_battle_candidate_a",
    "table_file_offset": 0x0D1FFC,
    "entry": 0,
    "record_file_offset": 0x078528,
    "record_payload_length": 14,
    "record_payload_sha256": "c7ac47044e9576475f854841981b18ae20eca25ad41df403164ee6307b1aecca",
}

STATIC_RECORD_WRAPPER_ADDRESS = 0x0800D8F0
RECORD_POOL_START = 0x08078528
RECORD_POOL_END_EXCLUSIVE = 0x0807870B

M22_BREAKPOINTS = {
    "consumer_entry": 0x08026054,
    "consumer_index_setup": 0x080262F8,
    "record_wrapper": 0x0800D8F0,
    "formatter": 0x0800D3FC,
    "output_writer": 0x0800CAD8,
    "sjis_renderer": 0x08008D18,
    "codepage_lookup": 0x080650A4,
    "glyph_expand": 0x080650DC,
    "vram_copy": 0x080656D4,
    "tilemap_writer": 0x08008914,
}
M22_SENTINEL_CODES = {0x9594: "U+90E8", 0x82C9: "U+306B", 0x97CD: "U+529B"}
M22_RAM_RANGES = (
    (0x02000000, 0x02040000),
    (0x03000000, 0x03008000),
)


def parse_sequence(spec: str) -> list[tuple[str, int]]:
    """Parse ``none:5,start:4,none:12`` into key phases."""

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


def expand_sequence(phases: Iterable[tuple[str, int]]) -> list[str]:
    expanded: list[str] = []
    for name, count in phases:
        expanded.extend([name] * count)
    return expanded


def key_value(name: str) -> int:
    if name == "none":
        return NO_KEY
    return NO_KEY & ~(1 << KEY_BITS[name])


def candidate_addresses() -> dict[str, object]:
    table_address = ROM_BASE + CANDIDATE["table_file_offset"]
    record_address = ROM_BASE + CANDIDATE["record_file_offset"]
    return {
        **CANDIDATE,
        "table_gba_address": table_address,
        "record_gba_address": record_address,
        "pointer_watch_length": 4,
        "record_watch_length": 1,
    }


def static_candidate_metadata(rom_path: Path) -> dict[str, object]:
    """Verify the reviewed pointer/record metadata without emitting bytes."""

    data = rom_path.read_bytes()
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    table_offset = int(CANDIDATE["table_file_offset"])
    entry = int(CANDIDATE["entry"])
    pointer_offset = table_offset + entry * 4
    pointer = int.from_bytes(data[pointer_offset:pointer_offset + 4], "little")
    record_offset = pointer - ROM_BASE
    terminator = data.find(b"\0", record_offset)
    if terminator < 0:
        terminator = len(data)
    payload = data[record_offset:terminator]
    metadata = {
        "game_code": game_code,
        "table_file_offset": f"0x{table_offset:06X}",
        "entry": entry,
        "pointer_value": f"0x{pointer:08X}",
        "record_file_offset": f"0x{record_offset:06X}",
        "record_payload_length": len(payload),
        "record_payload_sha256": hashlib.sha256(payload).hexdigest(),
        "sjis_decodable": _sjis_decodable(payload),
    }
    expected = candidate_addresses()
    if game_code != EXPECTED_GAME_CODE:
        raise ValueError(f"unexpected game code: {metadata}")
    if pointer != ROM_BASE + int(expected["record_file_offset"]):
        raise ValueError(f"reviewed pointer changed: {metadata}")
    if metadata["record_payload_length"] != CANDIDATE["record_payload_length"]:
        raise ValueError(f"reviewed record length changed: {metadata}")
    if metadata["record_payload_sha256"] != CANDIDATE["record_payload_sha256"]:
        raise ValueError(f"reviewed record hash changed: {metadata}")
    return metadata


def _sjis_decodable(payload: bytes) -> bool:
    try:
        payload.decode("shift_jis")
    except UnicodeDecodeError:
        return False
    return True


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    names = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "sp", "lr", "pc", "cpsr"}
    return {name: f"0x{value:08X}" for name, value in registers.items() if name in names}


def matching_registers(registers: dict[str, int], value: int) -> list[str]:
    return [name for name, actual in registers.items() if actual == value]


def io_values(client: GdbClient) -> dict[str, str]:
    names = {
        "DISPCNT": 0x04000000,
        "BG0CNT": 0x04000008,
        "BG1CNT": 0x0400000A,
        "BG2CNT": 0x0400000C,
        "BG3CNT": 0x0400000E,
    }
    return {
        name: f"0x{int.from_bytes(client.read_memory(address, 2), 'little'):04X}"
        for name, address in names.items()
    }


def vram_summary(before: bytes, after: bytes) -> dict[str, object]:
    changed_offsets = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
    changed_tiles = sorted({index // 32 for index in changed_offsets})
    changed_halfwords = sorted({index // 2 for index in changed_offsets})
    return {
        "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "length": len(after),
        "changed_bytes": len(changed_offsets),
        "changed_4bpp_tile_count": len(changed_tiles),
        "first_changed_4bpp_tiles": [f"0x{tile:04X}" for tile in changed_tiles[:32]],
        "changed_halfword_count": len(changed_halfwords),
    }


def _in_runtime_ram(address: int) -> bool:
    return any(start <= address < end for start, end in M22_RAM_RANGES)


def _u16_from(client: GdbClient, address: int) -> int | None:
    if not _in_runtime_ram(address):
        return None
    try:
        return int.from_bytes(client.read_memory(address, 2), "little")
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _u16_any(client: GdbClient, address: int) -> int | None:
    try:
        return int.from_bytes(client.read_memory(address, 2), "little")
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _r6_metadata(client: GdbClient, registers: dict[str, int], *, entry_pc: bool) -> dict[str, object]:
    """Record structure fields and index evidence without dumping source bytes."""

    base = registers["r0"] if entry_pc else registers["r6"]
    result: dict[str, object] = {
        "r6_base": f"0x{base:08X}",
        "caller_lr": f"0x{registers['lr']:08X}",
        "r6_base_is_runtime_ram": _in_runtime_ram(base),
    }
    fields: dict[str, int | None] = {}
    for offset in (0x00, 0x02, 0x04, 0x06, 0x08, 0x1C, 0x24):
        fields[f"0x{offset:02X}"] = _u16_from(client, base + offset) if offset != 0x1C else None
    if _in_runtime_ram(base + 0x1C):
        try:
            fields["0x1C"] = int.from_bytes(client.read_memory(base + 0x1C, 4), "little")
        except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
            fields["0x1C"] = None
    result["r6_fields_u16_or_pointer"] = fields
    record_base = fields.get("0x1C")
    if isinstance(record_base, int):
        result["record_byte_base"] = f"0x{record_base:08X}"
    if not entry_pc and isinstance(record_base, int):
        event_array_index = registers["r7"] - record_base
        result["event_array_index"] = event_array_index
        result["event_byte_pointer"] = f"0x{registers['r7']:08X}"
        try:
            event_byte_value: int | None = client.read_memory(registers["r7"], 1)[0]
        except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
            event_byte_value = None
        result["event_byte_value"] = event_byte_value
        length = fields.get("0x02")
        result["event_array_index_less_than_local_length"] = (
            isinstance(length, int) and 0 <= event_array_index < length
        )
        if event_byte_value is not None:
            table_index = event_byte_value & 0x7F
            result["actual_index"] = table_index
            result["masked_table_index"] = table_index
            result["index_less_than_table_b_count"] = 0 <= table_index < 44
    result["bound_status"] = "runtime-observed-only; not-static-proof"
    return result


def _pipeline_hit_metadata(
    client: GdbClient,
    name: str,
    registers: dict[str, int],
) -> dict[str, object]:
    pc = registers["pc"] & ~1
    result: dict[str, object] = {
        "hit": name,
        "pc": f"0x{pc:08X}",
        "lr": f"0x{registers['lr']:08X}",
        "registers": register_snapshot(registers),
    }
    if name == "consumer_entry":
        result["index_metadata"] = _r6_metadata(client, registers, entry_pc=True)
    elif name == "consumer_index_setup":
        result["index_metadata"] = _r6_metadata(client, registers, entry_pc=False)
    elif name == "codepage_lookup":
        code = registers["r1"] & 0xFFFF
        result["code_unit"] = f"0x{code:04X}"
        result["unicode_identity"] = M22_SENTINEL_CODES.get(code, "unmapped")
    elif name == "glyph_expand":
        codepage_index = registers["r1"] & 0xFFFF
        result["codepage_index"] = codepage_index
        result["codepage_table_address"] = f"0x{0x0824110C + codepage_index * 2:08X}"
        code = _u16_any(client, 0x0824110C + codepage_index * 2)
        if code is not None:
            result["code_unit"] = f"0x{code:04X}"
            result["unicode_identity"] = M22_SENTINEL_CODES.get(code, "unmapped")
        else:
            result["unicode_identity"] = "unmapped"
    elif name == "record_wrapper":
        result["record_pointer"] = f"0x{registers['r0']:08X}"
        result["record_pointer_is_B0"] = registers["r0"] == ROM_BASE + CANDIDATE["record_file_offset"]
    elif name == "formatter":
        result["source_pointer"] = f"0x{registers['r0']:08X}"
        result["formatter_output_arg"] = f"0x{registers['r2']:08X}"
    elif name == "output_writer":
        result["formatted_buffer_pointer"] = f"0x{registers['r0']:08X}"
    elif name == "vram_copy":
        result["destination"] = f"0x{registers['r0']:08X}"
        result["source"] = f"0x{registers['r1']:08X}"
        result["copy_length_units"] = registers["r2"]
        result["copy_length_bytes"] = registers["r2"] * 0x20
    elif name == "tilemap_writer":
        result["tilemap_x"] = registers["r0"] & 0xFFFF
        result["tilemap_y"] = registers["r1"] & 0xFFFF
        result["tilemap_value_base"] = registers["r2"] & 0xFFFF
    return result


def _pipeline_breakpoint_name(pc: int) -> str | None:
    normalized = pc & ~1
    for name, address in M22_BREAKPOINTS.items():
        if normalized == address:
            return name
    return None


def _collect_pipeline_events(
    client: GdbClient,
    report: dict[str, object],
    *,
    sequence: list[str],
    max_events: int,
    event_timeout: float,
    mode: str,
) -> bool:
    """Collect natural or controlled stops; return whether target is stopped."""

    target_stopped = True
    events = report["events"]
    for index in range(max_events):
        desired = sequence[index] if index < len(sequence) else "none"
        target_stopped = False
        try:
            stop = client.continue_until_stop(event_timeout)
        except TimeoutError:
            report["negative"].append({
                "mode": mode,
                "event_index": index,
                "kind": "event-timeout",
                "message": "no breakpoint/watchpoint stop in bounded interval",
            })
            return False
        target_stopped = True
        kind, address = parse_stop_watch(stop)
        registers = client.read_registers()
        hit = _pipeline_breakpoint_name(registers["pc"])
        event: dict[str, object] = {
            "mode": mode,
            "index": index,
            "requested_key": desired,
            "stop": stop,
            "stop_kind": kind,
            "stop_address": None if address is None else f"0x{address:08X}",
            "pc": f"0x{registers['pc'] & ~1:08X}",
            "lr": f"0x{registers['lr']:08X}",
        }
        if hit is not None:
            event.update(_pipeline_hit_metadata(client, hit, registers))
            events.append(event)
            # GDB stops before the breakpoint instruction. Single-step exactly
            # that instruction so the next continue cannot retrigger it.
            if (registers["pc"] & ~1) == M22_BREAKPOINTS[hit]:
                report.setdefault("breakpoint_steps", []).append({
                    "mode": mode,
                    "hit": hit,
                    "response": client.request("s"),
                })
            continue

        if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
            event["watch"] = "KEYINPUT"
            event["requested_keyinput"] = f"0x{key_value(desired):04X}"
            events.append(event)
            client.write_register(0, key_value(desired))
            continue

        event["watch"] = "unclassified"
        events.append(event)
    return target_stopped


def run_pipeline_trace(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[str],
    natural_events: int,
    controlled_events: int,
    event_timeout: float,
    settle_seconds: float,
    controlled_record: bool,
) -> dict[str, object]:
    """Trace natural reachability, then optionally inject B[0] at the wrapper.

    Register writes are an explicitly labelled controlled experiment.  They
    do not turn a controlled hit into evidence that the game naturally chose
    table-B entry 0.
    """

    static = static_candidate_metadata(rom_path)
    report: dict[str, object] = {
        "read_only": True,
        "harness": "M2.2-pipeline",
        "candidate": candidate_addresses(),
        "static_candidate": static,
        "breakpoints": {name: f"0x{address:08X}" for name, address in M22_BREAKPOINTS.items()},
        "events": [],
        "breakpoint_steps": [],
        "negative": [],
        "natural_reachability": "not-observed",
        "controlled_reachability": "not-requested",
    }
    client = GdbClient(host, port, timeout=max(5.0, event_timeout), packet_delay=0.08)
    breakpoint_set: list[tuple[str, int]] = []
    watch_set = False
    target_stopped = True
    before_vram: bytes | None = None
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        target_stopped = True
        before_vram = client.read_memory(0x06000000, 0x18000)
        for name, address in M22_BREAKPOINTS.items():
            client.set_breakpoint(address)
            breakpoint_set.append((name, address))
        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        watch_set = True

        target_stopped = _collect_pipeline_events(
            client,
            report,
            sequence=sequence,
            max_events=natural_events,
            event_timeout=event_timeout,
            mode="natural",
        )
        natural_hits = [
            event for event in report["events"]
            if event.get("mode") == "natural" and event.get("hit") in {
                "consumer_entry", "consumer_index_setup", "record_wrapper", "formatter",
            }
        ]
        report["natural_reachability"] = "observed" if natural_hits else "not-observed"

        if controlled_record and not natural_hits:
            report["controlled_reachability"] = "requested"
            if not target_stopped:
                report["interrupt_before_controlled"] = client.interrupt(timeout=2.0)
                target_stopped = True
            current = client.read_registers()
            record_address = ROM_BASE + CANDIDATE["record_file_offset"]
            client.write_register(0, record_address)
            client.write_register(15, STATIC_RECORD_WRAPPER_ADDRESS)
            report["controlled_injection"] = {
                "mode": "controlled-consumer-call-hijack",
                "entry": f"0x{STATIC_RECORD_WRAPPER_ADDRESS:08X}",
                "r0_record_pointer": f"0x{record_address:08X}",
                "previous_pc": f"0x{current['pc']:08X}",
                "previous_lr": f"0x{current['lr']:08X}",
                "natural_reachability_preserved": True,
            }
            target_stopped = _collect_pipeline_events(
                client,
                report,
                sequence=[],
                max_events=controlled_events,
                event_timeout=event_timeout,
                mode="controlled",
            )
            controlled_hits = [
                event for event in report["events"]
                if event.get("mode") == "controlled" and event.get("hit") in {
                    "record_wrapper", "formatter", "output_writer", "sjis_renderer",
                    "codepage_lookup", "glyph_expand", "vram_copy", "tilemap_writer",
                }
            ]
            report["controlled_reachability"] = "observed" if controlled_hits else "not-observed"
        elif controlled_record:
            report["controlled_reachability"] = "skipped-natural-hit"

        if not target_stopped:
            report["final_interrupt"] = client.interrupt(timeout=2.0)
            target_stopped = True
        after_vram = client.read_memory(0x06000000, 0x18000)
        report["vram_delta"] = vram_summary(before_vram, after_vram)
        report["natural_index_evidence"] = [
            event["index_metadata"]
            for event in report["events"]
            if event.get("mode") == "natural" and "index_metadata" in event
        ]
    finally:
        if watch_set:
            try:
                client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        for _name, address in reversed(breakpoint_set):
            try:
                client.remove_breakpoint(address)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        client.close()
    return report


def run_trace(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[str],
    max_events: int,
    event_timeout: float,
    settle_seconds: float,
    post_seconds: float,
    wrapper_breakpoint: bool = True,
) -> dict[str, object]:
    static = static_candidate_metadata(rom_path)
    addresses = candidate_addresses()
    pointer_address = int(addresses["table_gba_address"])
    record_address = int(addresses["record_gba_address"])
    report: dict[str, object] = {
        "read_only": True,
        "candidate": {
            **{key: value for key, value in addresses.items() if key != "record_payload_sha256"},
            "record_payload_sha256": CANDIDATE["record_payload_sha256"],
        },
        "static_candidate": static,
        "sequence": sequence,
        "events": [],
        "pointer_hits": [],
        "record_hits": [],
        "wrapper_hits": [],
        "negative": [],
    }
    client = GdbClient(host, port, timeout=max(5.0, event_timeout), packet_delay=0.08)
    watches: list[tuple[int, int, int]] = []
    breakpoint_set = False
    before_vram: bytes | None = None
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = io_values(client)
        before_vram = client.read_memory(0x06000000, 0x18000)

        if wrapper_breakpoint:
            client.set_breakpoint(STATIC_RECORD_WRAPPER_ADDRESS)
            breakpoint_set = True
            report["static_wrapper_breakpoint"] = f"0x{STATIC_RECORD_WRAPPER_ADDRESS:08X}"

        for address, length in (
            (KEYINPUT_ADDRESS, 2),
            (pointer_address, 4),
            (record_address, 1),
        ):
            client.set_watchpoint(address, kind=length, watch_type=3)
            watches.append((address, length, 3))

        for index, desired in enumerate(sequence[:max_events]):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                report["negative"].append({
                    "kind": "event-timeout",
                    "event_index": index,
                    "message": "no watched read occurred before the bounded timeout",
                })
                break
            kind, address = parse_stop_watch(stop)
            registers = client.read_registers()
            event = {
                "index": index,
                "requested_key": desired,
                "requested_keyinput": f"0x{key_value(desired):04X}",
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "registers": register_snapshot(registers),
            }
            report["events"].append(event)
            pc_without_thumb_bit = registers["pc"] & ~1
            if pc_without_thumb_bit == STATIC_RECORD_WRAPPER_ADDRESS:
                report["wrapper_hits"].append({
                    "event_index": index,
                    "stop": stop,
                    "pc": f"0x{registers['pc']:08X}",
                    "lr": f"0x{registers['lr']:08X}",
                    "r0": f"0x{registers['r0']:08X}",
                    "r0_is_candidate_record": registers["r0"] == record_address,
                    "r0_in_table_b_record_pool": RECORD_POOL_START <= registers["r0"] < RECORD_POOL_END_EXCLUSIVE,
                    "registers": register_snapshot(registers),
                })
            elif address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                client.write_register(0, key_value(desired))
            elif address is not None and pointer_address <= address < pointer_address + 4:
                report["pointer_hits"].append({
                    "event_index": index,
                    "stop": stop,
                    "stop_address": f"0x{address:08X}",
                    "pc": f"0x{registers['pc']:08X}",
                    "lr": f"0x{registers['lr']:08X}",
                    "registers_matching_record_address": matching_registers(registers, record_address),
                    "registers": register_snapshot(registers),
                })
            elif address is not None and record_address <= address < record_address + 1:
                report["record_hits"].append({
                    "event_index": index,
                    "stop": stop,
                    "stop_address": f"0x{address:08X}",
                    "pc": f"0x{registers['pc']:08X}",
                    "lr": f"0x{registers['lr']:08X}",
                    "registers": register_snapshot(registers),
                })

        report["link_status"] = (
            "pointer-record-wrapper-runtime-observed"
            if report["pointer_hits"] and report["record_hits"] and report["wrapper_hits"]
            else "record-wrapper-runtime-observed"
            if report["wrapper_hits"]
            else "no-runtime-link-observed"
        )
        report["post_sequence_stop"] = client.continue_and_interrupt(post_seconds)
        after_vram = client.read_memory(0x06000000, 0x18000)
        report["post_sequence_io"] = io_values(client)
        report["vram_delta"] = vram_summary(before_vram, after_vram)
    finally:
        if breakpoint_set:
            try:
                client.remove_breakpoint(STATIC_RECORD_WRAPPER_ADDRESS)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        for address, length, watch_type in reversed(watches):
            try:
                client.remove_watchpoint(address, kind=length, watch_type=watch_type)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        client.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--sequence", default="none:5,start:4,none:12")
    parser.add_argument("--max-events", type=int, default=32)
    parser.add_argument("--event-timeout", type=float, default=5.0)
    parser.add_argument("--settle-seconds", type=float, default=0.25)
    parser.add_argument("--post-seconds", type=float, default=0.50)
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="trace the M2.2 formatter/codepage/glyph pipeline breakpoints",
    )
    parser.add_argument(
        "--controlled-record",
        action="store_true",
        help="after natural tracing, inject the reviewed B[0] pointer at the wrapper (controlled only)",
    )
    parser.add_argument("--natural-events", type=int, default=24)
    parser.add_argument("--controlled-events", type=int, default=96)
    parser.add_argument(
        "--disable-wrapper-breakpoint",
        action="store_true",
        help="skip the static-chain 0x0800D8F0 breakpoint",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_events < 1:
        parser.error("--max-events must be positive")
    if args.natural_events < 1:
        parser.error("--natural-events must be positive")
    if args.controlled_events < 1:
        parser.error("--controlled-events must be positive")
    if args.controlled_record and not args.pipeline:
        parser.error("--controlled-record requires --pipeline")
    try:
        sequence = expand_sequence(parse_sequence(args.sequence))
        if args.pipeline:
            report = run_pipeline_trace(
                args.rom,
                host=args.host,
                port=args.port,
                sequence=sequence,
                natural_events=args.natural_events,
                controlled_events=args.controlled_events,
                event_timeout=args.event_timeout,
                settle_seconds=args.settle_seconds,
                controlled_record=args.controlled_record,
            )
        else:
            report = run_trace(
                args.rom,
                host=args.host,
                port=args.port,
                sequence=sequence,
                max_events=args.max_events,
                event_timeout=args.event_timeout,
                settle_seconds=args.settle_seconds,
                post_seconds=args.post_seconds,
                wrapper_breakpoint=not args.disable_wrapper_breakpoint,
            )
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"trace_m2_runtime.py: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
