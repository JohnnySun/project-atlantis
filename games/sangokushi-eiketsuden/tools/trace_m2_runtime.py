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
check is required.
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
        "negative": [],
    }
    client = GdbClient(host, port, timeout=max(5.0, event_timeout), packet_delay=0.08)
    watches: list[tuple[int, int, int]] = []
    before_vram: bytes | None = None
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = io_values(client)
        before_vram = client.read_memory(0x06000000, 0x18000)

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
            if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
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
            "pointer-and-record-runtime-read-observed"
            if report["pointer_hits"] and report["record_hits"]
            else "no-runtime-link-observed"
        )
        report["post_sequence_stop"] = client.continue_and_interrupt(post_seconds)
        after_vram = client.read_memory(0x06000000, 0x18000)
        report["post_sequence_io"] = io_values(client)
        report["vram_delta"] = vram_summary(before_vram, after_vram)
    finally:
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_events < 1:
        parser.error("--max-events must be positive")
    try:
        sequence = expand_sequence(parse_sequence(args.sequence))
        report = run_trace(
            args.rom,
            host=args.host,
            port=args.port,
            sequence=sequence,
            max_events=args.max_events,
            event_timeout=args.event_timeout,
            settle_seconds=args.settle_seconds,
            post_seconds=args.post_seconds,
        )
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
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
