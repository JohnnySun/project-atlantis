#!/usr/bin/env python3
"""Trace FE6 callback-gate provenance with one bounded GDB session.

M1.12 follows the static callback candidates from ``analyze_m111_gates.py``.
It uses a fresh AFEJ mGBA process and only active-low KEYINPUT reads for
natural navigation.  Breakpoints at the candidate callback entries and
read-watchpoints at their aligned ROM function-pointer words are kept as
separate receipts.  The report stores registers, pointer values, hashes and
addresses only; it never emits raw RAM, ROM bytes or decoded Japanese text.

The small request wrappers tolerate stale stop/memory packets observed in the
reviewed mGBA GDB stub.  They are bounded and do not retry a connection or
silently turn a failed runtime capture into a positive result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import summarize  # noqa: E402
from gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch  # noqa: E402
from analyze_m111_gates import build_report as static_gate_report  # noqa: E402
from trace_m18_callers import (  # noqa: E402
    BUFFER,
    BUFFER_SIZE,
    CALLER_INDEX_TABLE,
    COPY_WRAPPER,
    EXPECTED_GAME_CODE,
    EXPECTED_SHA256,
    HIGH_CALLER,
    HIGH_CALLSITE,
    KEYINPUT,
    LOADER_BL,
    LOADER_ENTRY,
    LOADER_RETURN,
    NO_KEY,
    POINTER_TABLE,
    POINTER_TABLE_END,
    ROM_BASE,
    ROM_SIZE,
    WORKER,
    buffer_summary,
    hex32,
    identity,
    loader_caller_from_lr,
    _function_for_call,
    prologue_addresses,
    return_addresses,
    scan_direct_calls,
    snapshot,
    table_provenance,
    u32,
)


CALLBACKS = {
    0x08098340: {
        "role": "alternate_callback_candidate",
        "stored_pointer": 0x08098341,
        "pointer_word": 0x08691230,
    },
    0x080984A8: {
        "role": "primary_high_group_callback_candidate",
        "stored_pointer": 0x080984A9,
        "pointer_word": 0x08691358,
    },
}

CANDIDATE_ENTRY = 0x080985D8
CANDIDATE_DIRECT_CALL = 0x080985EC
CANDIDATE_ALT_ENTRY = 0x08098624
CANDIDATE_ALT_CALLS = (0x0809867A, 0x08098694)
NATURAL_GENERIC_CALLSITE = 0x08009252
CONSUMER_ENTRY = 0x08098C00
CONSUMER_BYTE_READ = 0x08098C24
CONSUMER_CONTROL_BRANCH = 0x08098C78

DISPLAY_IO = {
    "DISPCNT": 0x04000000,
    "BG0CNT": 0x04000008,
    "BG1CNT": 0x0400000A,
    "BG2CNT": 0x0400000C,
    "BG3CNT": 0x0400000E,
}

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


def _compact_registers(regs: dict[str, int]) -> dict[str, str]:
    names = {"pc", "lr", "sp", "cpsr", "r0", "r1", "r2", "r3", "r7"}
    return {name: hex32(value) for name, value in regs.items() if name in names}


def _packet_is_registers(response: str) -> bool:
    return len(response) == len(REG_NAMES) * 8


def _request_ok(client: GdbClient, payload: str) -> None:
    """Boundedly drain stale packets until the point command acknowledges."""

    for _ in range(8):
        response = client.request(payload)
        if response == "OK":
            return
        if response.startswith("E"):
            raise RuntimeError(f"GDB request failed for {payload!r}: {response!r}")
        # mGBA can leave T/S, register, or short memory responses queued.
    raise RuntimeError(f"no OK response for {payload!r}")


def _read_registers(client: GdbClient) -> dict[str, int]:
    for _ in range(8):
        response = client.request("g")
        if response.startswith("E"):
            raise RuntimeError(f"register read failed: {response!r}")
        if response.startswith(("T", "S")) or not _packet_is_registers(response):
            continue
        try:
            values = [
                int.from_bytes(bytes.fromhex(response[index:index + 8]), "little")
                for index in range(0, len(response), 8)
            ]
        except ValueError:
            continue
        if len(values) == len(REG_NAMES):
            return dict(zip(REG_NAMES, values))
    raise RuntimeError("no complete register response after stop")


def _write_register(client: GdbClient, register_number: int, value: int) -> None:
    raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
    _request_ok(client, f"P{register_number:x}={raw}")


def _read_memory(client: GdbClient, address: int, length: int) -> bytes:
    output = bytearray()
    for offset in range(0, length, 0x200):
        size = min(0x200, length - offset)
        payload = f"m{address + offset:x},{size:x}"
        for _ in range(8):
            response = client.request(payload)
            if response.startswith("E"):
                raise RuntimeError(f"memory read failed at 0x{address + offset:x}")
            if response in {"OK"} or response.startswith(("T", "S")):
                continue
            try:
                data = bytes.fromhex(response)
            except ValueError:
                continue
            if len(data) == size:
                output.extend(data)
                break
        else:
            raise RuntimeError(f"no bounded memory response for 0x{address + offset:x}")
    return bytes(output)


def _continue_until_stop(client: GdbClient, timeout: float) -> str:
    """Continue once, draining stale packets until a real stop arrives."""

    sock = client._require_socket()
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        client.continue_running()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = client._read_packet().decode("ascii", errors="replace")
            if response.startswith(("T", "S")) or parse_stop_watch(response)[0]:
                return response
        raise TimeoutError("target did not stop before timeout")
    except socket.timeout as exc:
        raise TimeoutError("target did not stop before timeout") from exc
    finally:
        sock.settimeout(old_timeout)


def _interrupt(client: GdbClient) -> str:
    try:
        return client.interrupt(timeout=2.0)
    except (ConnectionError, OSError, TimeoutError):
        return "S02"


def _display_io(client: GdbClient) -> dict[str, str]:
    return {
        name: hex32(int.from_bytes(_read_memory(client, address, 2), "little"))
        for name, address in DISPLAY_IO.items()
    }


def _valid_rom_or_ram(address: int, length: int) -> bool:
    return (
        ROM_BASE <= address and address + length <= ROM_BASE + ROM_SIZE
        or 0x02000000 <= address and address + length <= 0x02040000
        or 0x03000000 <= address and address + length <= 0x03008000
        or 0x06000000 <= address and address + length <= 0x06018000
    )


def _source_hash(client: GdbClient, source: int) -> Optional[dict[str, object]]:
    # Some table entries expose an odd ROM pointer while the loader consumes
    # the surrounding packed stream. Keep the requested pointer for
    # provenance, but align only the bounded hash window for the GDB read.
    read_address = source & ~1
    if not _valid_rom_or_ram(read_address, 0x40):
        return None
    try:
        summary = summarize(_read_memory(client, read_address, 0x40), read_address)
        summary["requested_source_pointer"] = hex32(source)
        return summary
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _generic_loader_gate(rom: bytes) -> dict[str, object]:
    prologues = prologue_addresses(rom)
    returns = return_addresses(rom, ROM_BASE, ROM_BASE + len(rom))
    bounds = _function_for_call(NATURAL_GENERIC_CALLSITE, prologues, returns)
    return {
        "callsite": hex32(NATURAL_GENERIC_CALLSITE),
        "direct_loader_callsite": NATURAL_GENERIC_CALLSITE in scan_direct_calls(rom, LOADER_ENTRY),
        "function_start": bounds["function_start"],
        "function_return": bounds["function_return"],
        "function_boundary_confidence": bounds["function_boundary_confidence"],
        "role": "natural_route_generic_loader_candidate",
    }


def _route_report(
    *,
    args: argparse.Namespace,
    rom: bytes,
    sequence: list[str],
) -> dict[str, object]:
    static = static_gate_report(args.rom)
    report: dict[str, object] = {
        "schema": "afej-m112-dispatch-runtime-v1",
        "rom": identity(args.rom),
        "route": {
            "name": args.route_name,
            "sequence": sequence,
            "natural_reachability": True,
            "controlled_actions": [],
            "input_model": "KEYINPUT active-low read watchpoint; only r1 KEYINPUT value is supplied",
            "time_window_seconds": {
                "initial": args.initial_seconds,
                "per_step": args.step_seconds,
                "final": args.final_seconds,
            },
        },
        "static_gate": {
            "schema": static["schema"],
            "loader_direct_callsite_count": static["loader"]["direct_callsite_count"],
            "callback_pointer_candidates": [
                {
                    "callback_entry": hex32(address),
                    "stored_thumb_pointer": hex32(info["stored_pointer"]),
                    "pointer_word": hex32(info["pointer_word"]),
                    "role": info["role"],
                }
                for address, info in CALLBACKS.items()
            ],
            "generic_loader_candidate": _generic_loader_gate(rom),
        },
        "runtime": {
            "single_gdb_connection": True,
            "fresh_mgba_expected": True,
            "port": args.port,
            "events": [],
            "callback_pointer_reads": [],
            "callback_entries": [],
            "loader_records": [],
            "hit_counts": {},
            "display_io": {},
        },
    }
    runtime = report["runtime"]
    client = GdbClient(port=args.port, timeout=args.gdb_timeout, packet_delay=args.packet_delay)
    breakpoints = tuple(CALLBACKS) + (
        CANDIDATE_ENTRY,
        CANDIDATE_DIRECT_CALL,
        CANDIDATE_ALT_ENTRY,
        *CANDIDATE_ALT_CALLS,
        NATURAL_GENERIC_CALLSITE,
        HIGH_CALLER,
        HIGH_CALLSITE,
        LOADER_ENTRY,
        LOADER_BL,
        LOADER_RETURN,
        CONSUMER_ENTRY,
        CONSUMER_BYTE_READ,
        CONSUMER_CONTROL_BRANCH,
    )
    watchpoints = (KEYINPUT, *(info["pointer_word"] for info in CALLBACKS.values()))
    counts = {hex32(address): 0 for address in breakpoints}
    pointer_counts = {hex32(address): 0 for address in watchpoints[1:]}
    started = time.monotonic()
    installed_breakpoints: list[int] = []
    installed_watchpoints: list[int] = []

    def record_stop(packet: str) -> tuple[Optional[str], Optional[int], dict[str, int]]:
        stop_kind, stop_address = parse_stop_watch(packet)
        regs = _read_registers(client)
        pc = regs["pc"] & 0xFFFFFFFF
        if pc in breakpoints:
            counts[hex32(pc)] += 1
        event: dict[str, object] = {
            "stop": packet.split(";", 1)[0],
            "pc": hex32(pc),
            "stop_kind": stop_kind,
            "stop_address": None if stop_address is None else hex32(stop_address),
            "registers": _compact_registers(regs),
        }
        if stop_address == KEYINPUT:
            event["kind"] = "keyinput_poll"
        elif stop_address in pointer_counts:
            pointer_key = hex32(stop_address)
            pointer_counts[pointer_key] += 1
            value = int.from_bytes(_read_memory(client, stop_address, 4), "little")
            event.update({
                "kind": "callback_pointer_read_watch",
                "pointer_word": pointer_key,
                "stored_thumb_pointer": hex32(value),
                "read_pc_after_access": hex32(pc),
            })
            runtime["callback_pointer_reads"].append(event.copy())
        elif pc in CALLBACKS:
            info = CALLBACKS[pc]
            value = int.from_bytes(_read_memory(client, info["pointer_word"], 4), "little")
            event.update({
                "kind": "callback_entry",
                "callback_entry": hex32(pc),
                "role": info["role"],
                "stored_thumb_pointer": hex32(value),
                "callback_lr": hex32(regs["lr"]),
                "pointer_word": hex32(info["pointer_word"]),
            })
            runtime["callback_entries"].append(event.copy())
        elif pc in (CANDIDATE_DIRECT_CALL, *CANDIDATE_ALT_CALLS, HIGH_CALLSITE, NATURAL_GENERIC_CALLSITE):
            index = regs["r0"]
            event.update({
                "kind": "loader_direct_callsite",
                "callsite": hex32(pc),
                "caller_lr": hex32(regs["lr"]),
                "loader_index": index,
                "provenance": table_provenance(rom, index),
            })
        elif pc == LOADER_ENTRY:
            event.update({
                "kind": "loader_entry",
                "loader_index": regs["r0"],
                "caller_lr": hex32(regs["lr"]),
                "derived_callsite": loader_caller_from_lr(regs["lr"]),
                "provenance": table_provenance(rom, regs["r0"]),
            })
        elif pc == LOADER_BL:
            index = None
            try:
                index = int.from_bytes(_read_memory(client, regs["r7"], 4), "little")
            except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
                pass
            event.update({
                "kind": "loader_copy_callsite",
                "loader_index": index,
                "copy_wrapper": hex32(COPY_WRAPPER),
                "worker": hex32(WORKER),
                "copy_wrapper_lr": hex32(regs["lr"]),
                "source_pointer": hex32(regs["r0"]),
                "destination": hex32(regs["r1"]),
                "source_hash_window": _source_hash(client, regs["r0"]),
                "provenance": table_provenance(rom, index) if isinstance(index, int) else None,
            })
        elif pc == LOADER_RETURN:
            event.update({
                "kind": "loader_return",
                "buffer": buffer_summary(_read_memory(client, BUFFER, BUFFER_SIZE)),
            })
            runtime["loader_records"].append(event.copy())
        elif pc in (CONSUMER_ENTRY, CONSUMER_BYTE_READ, CONSUMER_CONTROL_BRANCH):
            event["kind"] = "text_consumer"
        else:
            event["kind"] = "other_breakpoint"
        runtime["events"].append(event)
        return stop_kind, stop_address, regs

    def continue_for(seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                packet = _continue_until_stop(client, min(args.stop_timeout, max(0.25, deadline - time.monotonic())))
            except TimeoutError:
                record_stop(_interrupt(client))
                return
            record_stop(packet)

    def press_button(button: str) -> dict[str, object]:
        desired = NO_KEY & ~(1 << BUTTON_BITS[button])
        rows: list[dict[str, object]] = []
        _request_ok(client, f"z3,{KEYINPUT:x},2")
        _request_ok(client, f"Z3,{KEYINPUT:x},2")
        try:
            deadline = time.monotonic() + args.event_timeout * (args.hold_events + args.release_events) * 4
            while len(rows) < args.hold_events + args.release_events and time.monotonic() < deadline:
                try:
                    packet = _continue_until_stop(client, args.event_timeout)
                except TimeoutError:
                    record_stop(_interrupt(client))
                    break
                stop_kind, stop_address = parse_stop_watch(packet)
                if stop_address != KEYINPUT:
                    record_stop(packet)
                    continue
                regs = _read_registers(client)
                value = desired if len(rows) < args.hold_events else NO_KEY
                _write_register(client, 1, value)
                rows.append({
                    "sequence_index": len(rows),
                    "stop_kind": stop_kind,
                    "stop_address": hex32(KEYINPUT),
                    "requested_keyinput": hex32(value),
                    "registers": _compact_registers(regs),
                })
        finally:
            _request_ok(client, f"z3,{KEYINPUT:x},2")
        return {"button": button, "key_event_count": len(rows), "key_events": rows}

    try:
        connect_client(client, args.source_port)
        runtime["supported"] = client.request("qSupported:multiprocess+")
        runtime["initial_stop"] = client.request("?").split(";", 1)[0]
        runtime["initial_registers"] = _compact_registers(_read_registers(client))
        for address in breakpoints:
            _request_ok(client, f"Z1,{address:x},2")
            installed_breakpoints.append(address)
        _request_ok(client, f"Z3,{KEYINPUT:x},2")
        installed_watchpoints.append(KEYINPUT)
        for address in watchpoints[1:]:
            try:
                _request_ok(client, f"Z3,{address:x},4")
                installed_watchpoints.append(address)
            except RuntimeError as exc:
                runtime.setdefault("watchpoint_errors", []).append({
                    "address": hex32(address),
                    "error": type(exc).__name__,
                })
        continue_for(args.initial_seconds)
        route_steps: list[dict[str, object]] = []
        for index, button in enumerate(sequence):
            step = press_button(button)
            before = len(runtime["events"])
            continue_for(args.step_seconds)
            step.update({
                "step_index": index,
                "events_after_input": len(runtime["events"]) - before,
                "display_io": _display_io(client),
            })
            route_steps.append(step)
            if len(runtime["callback_entries"]) >= args.max_callbacks:
                break
        continue_for(args.final_seconds)
        runtime["steps"] = route_steps
        runtime["hit_counts"] = counts
        runtime["pointer_watch_hit_counts"] = pointer_counts
        runtime["display_io"] = _display_io(client)
        runtime["natural_callback_hit"] = bool(runtime["callback_entries"])
        runtime["natural_non_selector_loader_hit"] = any(
            event.get("kind") == "loader_direct_callsite"
            and event.get("callsite") != hex32(HIGH_CALLSITE)
            for event in runtime["events"]
        )
    finally:
        for address in reversed(installed_watchpoints):
            try:
                _request_ok(client, f"z3,{address:x},{2 if address == KEYINPUT else 4}")
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        for address in reversed(installed_breakpoints):
            try:
                _request_ok(client, f"z1,{address:x},2")
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        client.close()
    runtime["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return report


def parse_sequence(value: str) -> list[str]:
    sequence = [part.strip().lower() for part in value.split(",") if part.strip()]
    if not sequence or any(part not in BUTTON_BITS for part in sequence):
        raise ValueError(f"sequence must contain known buttons: {sorted(BUTTON_BITS)}")
    return sequence


def connect_client(client: GdbClient, source_port: Optional[int]) -> None:
    if source_port is None:
        client.connect()
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(client.timeout)
    try:
        sock.bind(("127.0.0.1", source_port))
        sock.connect((client.host, client.port))
        client.sock = sock
        client.buffer = b""
    except BaseException:
        sock.close()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--source-port", type=int)
    parser.add_argument("--route-name", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initial-seconds", type=float, default=2.0)
    parser.add_argument("--step-seconds", type=float, default=0.8)
    parser.add_argument("--final-seconds", type=float, default=1.5)
    parser.add_argument("--event-timeout", type=float, default=1.0)
    parser.add_argument("--stop-timeout", type=float, default=1.0)
    parser.add_argument("--gdb-timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.05)
    parser.add_argument("--hold-events", type=int, default=6)
    parser.add_argument("--release-events", type=int, default=3)
    parser.add_argument("--max-callbacks", type=int, default=32)
    args = parser.parse_args()
    if not 1 <= args.max_callbacks <= 32:
        parser.error("max-callbacks must be between 1 and 32")
    sequence = parse_sequence(args.sequence)
    rom = args.rom.read_bytes()
    identity(args.rom)
    report = _route_report(args=args, rom=rom, sequence=sequence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    runtime = report["runtime"]
    print(f"output={args.output}")
    print(f"callback_entries={len(runtime['callback_entries'])}")
    print(f"loader_records={len(runtime['loader_records'])}")
    print(f"pointer_watch_hits={runtime.get('pointer_watch_hit_counts', {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
