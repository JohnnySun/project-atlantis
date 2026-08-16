#!/usr/bin/env python3
"""Bounded live A1AC input/edge/state-return probe for B3TJ.

The probe is intentionally a one-shot runtime harness, not a pointer scanner.
It starts with only fixed B3TJ code breakpoints installed at the reset stop.
When the live ``0x0800A1AC`` resource-update caller is reached, it installs a
single KEYINPUT read watch, writes active-low A to the observed destination
register ``r1``, and records the exact ``OK`` response from the shared GDB
client.  Subsequent watched reads are released with ``0x03FF`` at a finite
limit.  The edge flag, object ``+0x54``, A2C0 result, common dispatcher return,
and screen hashes are metadata only; no state, object, save, ROM, or raw
screen bytes are written or emitted.

The single-step slice is deliberately bounded to the static edge check
``0x0800A174`` through ``0x0800A180``.  A step failure is retained as an
explicit provisional/unknown result instead of being replaced with a state or
object write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402

GAME_TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(GAME_TOOLS))
from consumer_probe import b3tj_identity, key_value, register_snapshot  # noqa: E402
from state_probe import state_metadata  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

STATE_DISPATCHER = 0x08005ECC
STATE_RETURN = 0x08005E12
STATE_TABLE_BASE = 0x08741D94
STATE_NEXT = 0x02000000

A1AC_ENTRY = 0x0800A1AC
STATE4_A58C = 0x0800A58C
STATE4_A388 = 0x0800A388
STATE4_A030 = 0x0800A030
STATE4_A050 = 0x0800A050
A1AC_CALLSITE = 0x0800A3E6
EDGE_CHECK = 0x0800A174
EDGE_TRUE_PATH = 0x0800A180
POST_SLOT_STORE = 0x0800A18C
A2C0_ENTRY = 0x0800A2C0
A2C0_CALLER_AFTER = 0x0800A3F0

KEYINPUT_ADDRESS = 0x04000130
EDGE_ADDRESS = 0x030033F8
EDGE_A_BIT = 0x0001
NO_KEY = 0x03FF
START_KEY = key_value("start")
A_KEY = key_value("a")

RAM_RANGES = (
    (0x02000000, 0x02040000),
    (0x03000000, 0x03008000),
)
SCREEN_REGIONS = {
    "vram": (0x06000000, 0x18000),
    "palette": (0x05000000, 0x400),
    "oam": (0x07000000, 0x400),
}


def format_pointer(value: int) -> str:
    return f"0x{value:08X}"


def read_state_metadata(client: GdbClient) -> dict[str, object]:
    return state_metadata(client.read_memory(STATE_NEXT, 3))


def screen_hash_metadata(client: GdbClient) -> dict[str, object]:
    """Hash fixed screen regions with no raw screen output."""

    result: dict[str, object] = {}
    for name, (address, length) in SCREEN_REGIONS.items():
        # mGBA's GDB memory endpoint rejects larger VRAM packets on this
        # build; use the core client's known-safe bounded chunk size.
        raw = client.read_memory(address, length, chunk_size=0x200)
        result[name] = {
            "address": format_pointer(address),
            "length": length,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "nonzero_bytes": sum(value != 0 for value in raw),
        }
    return result


def is_ram_pointer(value: int) -> bool:
    return any(start <= value < end for start, end in RAM_RANGES)


def object_metadata(
    client: GdbClient,
    registers: dict[str, int],
    *,
    register_name: str,
    stage: str,
    slot_offset: int = 0x54,
) -> dict[str, object]:
    """Read one bounded object field from a guarded runtime RAM pointer."""

    value = registers.get(register_name, 0)
    result: dict[str, object] = {
        "stage": stage,
        "register": register_name,
        "pointer": format_pointer(value),
        "pointer_is_ram": is_ram_pointer(value),
        "slot_offset": f"0x{slot_offset:02X}",
    }
    if not is_ram_pointer(value) or not is_ram_pointer(value + slot_offset):
        result["slot_status"] = "guarded-outside-gba-ram"
        return result
    try:
        slot = int.from_bytes(client.read_memory(value + slot_offset, 4), "little")
    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        result["slot_status"] = "read-error"
        result["error_type"] = type(exc).__name__
        return result
    result["slot_status"] = "read"
    result["slot_value"] = format_pointer(slot)
    return result


def ram_register_candidates(registers: dict[str, int]) -> dict[str, str]:
    """Record plausible register provenance without selecting by address scan."""

    return {
        name: format_pointer(value)
        for name, value in registers.items()
        if name in {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r12", "sp"}
        and is_ram_pointer(value)
    }


def edge_metadata(client: GdbClient) -> dict[str, object]:
    value = int.from_bytes(client.read_memory(EDGE_ADDRESS, 2), "little")
    return {
        "address": format_pointer(EDGE_ADDRESS),
        "value": format_pointer(value),
        "bit0": bool(value & EDGE_A_BIT),
    }


def word_metadata(client: GdbClient, address: int, *, label: str) -> dict[str, object]:
    """Read one exact bounded word after a watchpoint stop."""

    result: dict[str, object] = {
        "label": label,
        "address": format_pointer(address),
        "length": 4,
    }
    try:
        value = int.from_bytes(client.read_memory(address, 4), "little")
    except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
        result["status"] = "read-error"
        result["error_type"] = type(exc).__name__
        return result
    result["status"] = "read"
    result["value"] = format_pointer(value)
    return result


def write_key_with_ack(client: GdbClient, value: int) -> dict[str, object]:
    """Write one GDB register and expose the core client's exact ``OK`` ACK."""

    raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
    receipt: dict[str, object] = {
        "register": "r1",
        "value": f"0x{value:04X}",
        "packet_delay_seconds": client.packet_delay,
        "timeout_retry_limit": 1,
        "response": None,
    }
    try:
        response = client.request(f"P1={raw}")
    except (TimeoutError, RuntimeError, OSError, ConnectionError) as exc:
        receipt["status"] = "failed"
        receipt["error_type"] = type(exc).__name__
        receipt["failure_boundary"] = "shared-client-delay-and-one-timeout-retry"
        return receipt
    receipt["response"] = response
    receipt["status"] = "ok" if response == "OK" else "unexpected-response"
    return receipt


def single_step_to_edge_true_path(
    client: GdbClient,
    *,
    max_steps: int,
) -> dict[str, object]:
    """Single-step from the edge-load entry until A180 or a bounded failure."""

    result: dict[str, object] = {
        "start_pc": format_pointer(EDGE_CHECK),
        "target_pc": format_pointer(EDGE_TRUE_PATH),
        "max_steps": max_steps,
        "steps": [],
    }
    for index in range(max_steps):
        try:
            stop = client.request("s")
            registers = client.read_registers()
        except (TimeoutError, RuntimeError, OSError, ConnectionError) as exc:
            result["status"] = "step-error"
            result["error_type"] = type(exc).__name__
            return result
        pc = registers["pc"] & ~1
        steps = result["steps"]
        assert isinstance(steps, list)
        steps.append(
            {
                "index": index,
                "stop": stop,
                "pc": format_pointer(pc),
                "lr": format_pointer(registers["lr"]),
                "registers": register_snapshot(registers),
            }
        )
        if pc == EDGE_TRUE_PATH:
            result["status"] = "reached-edge-true-path"
            return result
        if pc in {0x0800A110, A1AC_ENTRY}:
            result["status"] = "left-edge-path-before-target"
            return result
    result["status"] = "step-limit"
    return result


def safe_interrupt(client: GdbClient) -> str | None:
    try:
        return client.interrupt(timeout=2.0)
    except (TimeoutError, OSError, ConnectionError):
        return None


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    per_stop_timeout: float,
    max_stops: int,
    max_edge_checks: int,
    release_reads: int,
    max_steps: int,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    client = GdbClient(host, port, timeout=8.0, packet_delay=0.05, retry_delay=0.25)
    breakpoints = {
        "dispatcher": False,
        "state_return": False,
        "a1ac": False,
        "state4_a58c": False,
        "state4_a388": False,
        "state4_a030": False,
        "state4_a050": False,
        "a1ac_callsite": False,
        "edge_check": False,
        "post_slot_store": False,
        "a2c0": False,
        "a2c0_caller_after": False,
    }
    key_watch = False
    completion_watch = False
    completion_watch_address: int | None = None
    report: dict[str, object] = {
        "mode": "m1.8-live-a1ac-single-pulse",
        "rom": str(rom_path),
        "identity": identity,
        "fixed_addresses": {
            "dispatcher": format_pointer(STATE_DISPATCHER),
            "state_return": format_pointer(STATE_RETURN),
            "a1ac_entry": format_pointer(A1AC_ENTRY),
            "state4_a58c": format_pointer(STATE4_A58C),
            "state4_a388": format_pointer(STATE4_A388),
            "state4_a030": format_pointer(STATE4_A030),
            "a1ac_callsite": format_pointer(A1AC_CALLSITE),
            "edge_check": format_pointer(EDGE_CHECK),
            "edge_true_path": format_pointer(EDGE_TRUE_PATH),
            "post_slot_store": format_pointer(POST_SLOT_STORE),
            "a2c0_entry": format_pointer(A2C0_ENTRY),
            "a2c0_caller_after": format_pointer(A2C0_CALLER_AFTER),
            "keyinput": format_pointer(KEYINPUT_ADDRESS),
            "edge_iwram": format_pointer(EDGE_ADDRESS),
        },
        "policy": {
            "one_live_a1ac_hit": True,
            "pre_a1ac_start_keyinput": f"0x{START_KEY:04X}",
            "a_keyinput": f"0x{A_KEY:04X}",
            "release_keyinput": f"0x{NO_KEY:04X}",
            "pre_a1ac_release_reads_limit": 3,
            "release_reads_limit": release_reads,
            "packet_delay_seconds": 0.05,
            "timeout_retry_limit": 1,
            "writes_state": False,
            "writes_object": False,
            "writes_save": False,
        },
        "limits": {
            "max_stops": max_stops,
            "max_edge_checks": max_edge_checks,
            "max_steps": max_steps,
            "per_stop_timeout": per_stop_timeout,
        },
        "dispatcher_entries": [],
        "state4_setup_entries": [],
        "a030_completion_writes": [],
        "a1ac_callsite_hits": [],
        "a1ac_hits": [],
        "keyinput_events": [],
        "edge_checks": [],
        "single_step": None,
        "object_slot_reads": [],
        "a2c0": [],
        "state_returns": [],
    }

    def append_limited(name: str, row: dict[str, object], limit: int) -> None:
        values = report[name]
        assert isinstance(values, list)
        if len(values) < limit:
            values.append(row)

    def capture_dispatch(registers: dict[str, int], stop: str) -> dict[str, object]:
        state = read_state_metadata(client)
        row: dict[str, object] = {
            "stop": stop,
            "pc": format_pointer(registers["pc"] & ~1),
            "lr": format_pointer(registers["lr"]),
            "registers": register_snapshot(registers),
            "state": state,
        }
        entry_text = state.get("dispatch_entry")
        if isinstance(entry_text, str):
            entry = int(entry_text, 16)
            function = int.from_bytes(client.read_memory(entry, 4), "little")
            row["dispatch_entry_value"] = format_pointer(function)
            row["resolved_function_thumb"] = format_pointer(function & ~1)
        return row

    try:
        try:
            client.connect()
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            report["termination"] = "setup-error"
            report["error_type"] = type(exc).__name__
            report["error_message"] = str(exc)
            return report
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["boot_state"] = read_state_metadata(client)

        client.set_breakpoint(STATE_DISPATCHER, kind=2)
        breakpoints["dispatcher"] = True
        client.set_breakpoint(STATE_RETURN, kind=2)
        breakpoints["state_return"] = True
        client.set_breakpoint(A1AC_ENTRY, kind=2)
        breakpoints["a1ac"] = True
        client.set_breakpoint(STATE4_A58C, kind=2)
        breakpoints["state4_a58c"] = True
        client.set_breakpoint(STATE4_A388, kind=2)
        breakpoints["state4_a388"] = True
        client.set_breakpoint(STATE4_A030, kind=2)
        breakpoints["state4_a030"] = True
        client.set_breakpoint(STATE4_A050, kind=2)
        breakpoints["state4_a050"] = True
        client.set_breakpoint(A1AC_CALLSITE, kind=2)
        breakpoints["a1ac_callsite"] = True
        client.set_breakpoint(EDGE_CHECK, kind=2)
        breakpoints["edge_check"] = True
        client.set_breakpoint(POST_SLOT_STORE, kind=2)
        breakpoints["post_slot_store"] = True
        client.set_breakpoint(A2C0_ENTRY, kind=2)
        breakpoints["a2c0"] = True
        client.set_breakpoint(A2C0_CALLER_AFTER, kind=2)
        breakpoints["a2c0_caller_after"] = True

        a1ac_seen = False
        pre_start_done = False
        pre_release_remaining = 3
        a_write_done = False
        release_remaining = release_reads
        edge_check_count = 0
        stop_count = 0
        normal_return = False
        stop_reason = "stop-limit"

        while stop_count < max_stops:
            try:
                stop = client.continue_until_stop(per_stop_timeout)
            except TimeoutError:
                stop_reason = "per-stop-timeout"
                report["interrupt_stop"] = safe_interrupt(client)
                break
            stop_count += 1
            kind, address = parse_stop_watch(stop)
            registers = client.read_registers()
            pc = registers["pc"] & ~1

            if (
                completion_watch
                and completion_watch_address is not None
                and address is not None
                and completion_watch_address <= address < completion_watch_address + 4
            ):
                append_limited(
                    "a030_completion_writes",
                    {
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": format_pointer(address),
                        "pc": format_pointer(pc),
                        "lr": format_pointer(registers["lr"]),
                        "registers": register_snapshot(registers),
                        "edge": edge_metadata(client),
                        "watched_object_completion": word_metadata(
                            client,
                            completion_watch_address,
                            label="runtime-object-plus-0x44-after-writer",
                        ),
                        "writer_context_r4": format_pointer(registers["r4"]),
                    },
                    4,
                )
                try:
                    client.remove_watchpoint(
                        completion_watch_address, kind=4, watch_type=2
                    )
                except (RuntimeError, TimeoutError, OSError, ConnectionError):
                    pass
                completion_watch = False
                completion_watch_address = None
                continue

            if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                event: dict[str, object] = {
                    "index": len(report["keyinput_events"]),
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": format_pointer(address),
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers_before_write": register_snapshot(registers),
                }
                if not a1ac_seen and not pre_start_done:
                    ack = write_key_with_ack(client, START_KEY)
                    event["phase"] = "pre-a1ac-start"
                    event["write_ack"] = ack
                    if ack.get("status") != "ok":
                        report["termination"] = "pre-a1ac-start-ack-failed"
                        stop_reason = "pre-a1ac-start-ack-failed"
                        append_limited("keyinput_events", event, release_reads + 6)
                        break
                    pre_start_done = True
                    event["registers_after_write"] = register_snapshot(client.read_registers())
                elif not a1ac_seen and pre_release_remaining > 0:
                    ack = write_key_with_ack(client, NO_KEY)
                    event["phase"] = "pre-a1ac-release"
                    event["write_ack"] = ack
                    pre_release_remaining -= 1
                    if ack.get("status") != "ok":
                        report["termination"] = "pre-a1ac-release-ack-failed"
                        stop_reason = "pre-a1ac-release-ack-failed"
                        append_limited("keyinput_events", event, release_reads + 6)
                        break
                    event["registers_after_write"] = register_snapshot(client.read_registers())
                elif not a1ac_seen:
                    event["phase"] = "pre-a1ac-release-limit-reached"
                    key_watch = False
                    try:
                        client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
                    except (RuntimeError, TimeoutError, OSError, ConnectionError):
                        pass
                elif not a_write_done:
                    ack = write_key_with_ack(client, A_KEY)
                    event["phase"] = "a-pulse"
                    event["write_ack"] = ack
                    if ack.get("status") != "ok":
                        report["termination"] = "register-write-ack-failed"
                        stop_reason = "register-write-ack-failed"
                        append_limited("keyinput_events", event, release_reads + 6)
                        break
                    a_write_done = True
                    event["registers_after_write"] = register_snapshot(client.read_registers())
                elif release_remaining > 0:
                    ack = write_key_with_ack(client, NO_KEY)
                    event["phase"] = "release"
                    event["write_ack"] = ack
                    release_remaining -= 1
                    if ack.get("status") != "ok":
                        report["termination"] = "release-write-ack-failed"
                        stop_reason = "release-write-ack-failed"
                        append_limited("keyinput_events", event, release_reads + 6)
                        break
                    event["registers_after_write"] = register_snapshot(client.read_registers())
                else:
                    event["phase"] = "release-limit-reached"
                    key_watch = False
                    try:
                        client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
                    except (RuntimeError, TimeoutError, OSError, ConnectionError):
                        pass
                append_limited("keyinput_events", event, release_reads + 6)
                continue

            if pc == STATE_DISPATCHER:
                append_limited("dispatcher_entries", capture_dispatch(registers, stop), 4)
                continue

            if pc in {STATE4_A58C, STATE4_A388, STATE4_A030}:
                append_limited(
                    "state4_setup_entries",
                    {
                        "function": format_pointer(pc),
                        "stop": stop,
                        "lr": format_pointer(registers["lr"]),
                        "registers": register_snapshot(registers),
                        "edge": edge_metadata(client),
                    },
                    8,
                )
                continue

            if pc == STATE4_A050:
                object_pointer = registers.get("r4", 0)
                if not completion_watch and is_ram_pointer(object_pointer + 0x44):
                    completion_watch_address = object_pointer + 0x44
                    client.set_watchpoint(
                        completion_watch_address, kind=4, watch_type=2
                    )
                    completion_watch = True
                if not key_watch:
                    client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
                    key_watch = True
                append_limited(
                    "state4_setup_entries",
                    {
                        "function": format_pointer(pc),
                        "stop": stop,
                        "lr": format_pointer(registers["lr"]),
                        "registers": register_snapshot(registers),
                        "edge": edge_metadata(client),
                        "object_completion_watch": (
                            None
                            if completion_watch_address is None
                            else format_pointer(completion_watch_address)
                        ),
                        "object_completion": object_metadata(
                            client,
                            registers,
                            register_name="r4",
                            stage="a030-loop-slot54",
                        ),
                        "object_completion_flag": object_metadata(
                            client,
                            registers,
                            register_name="r4",
                            stage="a030-loop-completion-flag",
                            slot_offset=0x44,
                        ),
                    },
                    8,
                )
                if breakpoints["state4_a050"]:
                    try:
                        client.remove_breakpoint(STATE4_A050, kind=2)
                    except (RuntimeError, TimeoutError, OSError, ConnectionError):
                        pass
                    breakpoints["state4_a050"] = False
                continue

            if pc == A1AC_CALLSITE:
                append_limited(
                    "a1ac_callsite_hits",
                    {
                        "stop": stop,
                        "pc": format_pointer(pc),
                        "lr": format_pointer(registers["lr"]),
                        "registers": register_snapshot(registers),
                        "object_argument_r0": object_metadata(
                            client, registers, register_name="r0", stage="a1ac-callsite"
                        ),
                    },
                    4,
                )
                continue

            if pc == A1AC_ENTRY:
                row = {
                    "stop": stop,
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "ram_register_candidates": ram_register_candidates(registers),
                    "edge_before": edge_metadata(client),
                    "object_candidate_r7": object_metadata(
                        client, registers, register_name="r7", stage="a1ac-entry-candidate"
                    ),
                }
                append_limited("a1ac_hits", row, 2)
                if not a1ac_seen:
                    a1ac_seen = True
                    if not key_watch:
                        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
                        key_watch = True
                    client.remove_breakpoint(A1AC_ENTRY, kind=2)
                    breakpoints["a1ac"] = False
                continue

            if pc == EDGE_CHECK:
                edge_check_count += 1
                row = {
                    "index": edge_check_count,
                    "stop": stop,
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "edge": edge_metadata(client),
                    "object_candidate_r7": object_metadata(
                        client, registers, register_name="r7", stage="edge-check-candidate"
                    ),
                }
                append_limited("edge_checks", row, max_edge_checks)
                if edge_check_count > max_edge_checks:
                    report["termination"] = "edge-check-limit"
                    stop_reason = "edge-check-limit"
                    break
                if row["edge"]["bit0"] is True:
                    step = single_step_to_edge_true_path(client, max_steps=max_steps)
                    report["single_step"] = step
                    if step.get("status") == "reached-edge-true-path":
                        steps = step.get("steps")
                        last_registers = registers
                        if isinstance(steps, list) and steps:
                            last = steps[-1]
                            if isinstance(last, dict):
                                last_registers = {
                                    name: int(value, 16)
                                    for name, value in last.get("registers", {}).items()
                                    if isinstance(value, str) and value.startswith("0x")
                                }
                                last_registers.setdefault("r7", registers.get("r7", 0))
                                last_registers.setdefault("pc", EDGE_TRUE_PATH)
                                last_registers.setdefault("lr", registers.get("lr", 0))
                        append_limited(
                            "object_slot_reads",
                            object_metadata(
                                client,
                                last_registers,
                                register_name="r7",
                                stage="edge-true-path-before-slot-store",
                            ),
                            8,
                        )
                    else:
                        report["termination"] = "single-step-edge-path-failed"
                        stop_reason = "single-step-edge-path-failed"
                        break
                continue

            if pc == POST_SLOT_STORE:
                append_limited(
                    "object_slot_reads",
                    object_metadata(
                        client,
                        registers,
                        register_name="r7",
                        stage="post-slot-store",
                    ),
                    8,
                )
                if key_watch:
                    try:
                        client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
                    except (RuntimeError, TimeoutError, OSError, ConnectionError):
                        pass
                    key_watch = False
                continue

            if pc == A2C0_ENTRY:
                row = {
                    "stop": stop,
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "object_argument_r0": object_metadata(
                        client, registers, register_name="r0", stage="a2c0-entry"
                    ),
                    "edge": edge_metadata(client),
                }
                append_limited("a2c0", row, 4)
                continue

            if pc == A2C0_CALLER_AFTER:
                row = {
                    "stop": stop,
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "return_r0": format_pointer(registers["r0"]),
                    "success": registers["r0"] == 1,
                }
                append_limited("a2c0", row, 4)
                continue

            if pc == STATE_RETURN:
                normal_return = True
                state = read_state_metadata(client)
                row = {
                    "stop": stop,
                    "pc": format_pointer(pc),
                    "lr": format_pointer(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "state": state,
                    "screen_hashes": screen_hash_metadata(client),
                    "a2c0_success_seen": any(
                        isinstance(item, dict) and item.get("success") is True
                        for item in report["a2c0"]
                    ),
                }
                append_limited("state_returns", row, 2)
                stop_reason = "normal-state-return"
                break

            report["unexpected_stop"] = {
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else format_pointer(address),
                "pc": format_pointer(pc),
                "lr": format_pointer(registers["lr"]),
                "registers": register_snapshot(registers),
            }
            stop_reason = "unexpected-stop"
            break

        report["stop_count"] = stop_count
        report["a1ac_seen"] = a1ac_seen
        report["pre_start_done"] = pre_start_done
        report["pre_release_reads_observed"] = sum(
            item.get("phase") == "pre-a1ac-release"
            for item in report["keyinput_events"]
            if isinstance(item, dict)
        )
        report["a_write_done"] = a_write_done
        report["release_reads_observed"] = sum(
            item.get("phase") == "release"
            for item in report["keyinput_events"]
            if isinstance(item, dict)
        )
        report["edge_check_count"] = edge_check_count
        report["normal_state_return"] = normal_return
        report["termination"] = report.get("termination", stop_reason)
        report["confirmed_runtime"] = {
            "pre_a1ac_start_ack_ok": any(
                isinstance(item, dict)
                and isinstance(item.get("write_ack"), dict)
                and item["write_ack"].get("status") == "ok"
                and item.get("phase") == "pre-a1ac-start"
                for item in report["keyinput_events"]
            ),
            "a1ac_entry_hit": a1ac_seen,
            "a_register_write_ack_ok": any(
                isinstance(item, dict)
                and isinstance(item.get("write_ack"), dict)
                and item["write_ack"].get("status") == "ok"
                and item.get("phase") == "a-pulse"
                for item in report["keyinput_events"]
            ),
            "edge_bit0_observed": any(
                isinstance(item, dict)
                and isinstance(item.get("edge"), dict)
                and item["edge"].get("bit0") is True
                for item in report["edge_checks"]
            ),
            "a2c0_entry_hit": any(
                isinstance(item, dict) and item.get("pc") == format_pointer(A2C0_ENTRY)
                for item in report["a2c0"]
            ),
            "a2c0_success": any(
                isinstance(item, dict) and item.get("success") is True
                for item in report["a2c0"]
            ),
            "state_return_hit": normal_return,
        }
    finally:
        if completion_watch and completion_watch_address is not None:
            try:
                client.remove_watchpoint(
                    completion_watch_address, kind=4, watch_type=2
                )
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        if key_watch:
            try:
                client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            except (RuntimeError, TimeoutError, OSError, ConnectionError):
                pass
        for name, address in (
            ("a2c0_caller_after", A2C0_CALLER_AFTER),
            ("a2c0", A2C0_ENTRY),
            ("post_slot_store", POST_SLOT_STORE),
            ("edge_check", EDGE_CHECK),
            ("state4_a388", STATE4_A388),
            ("state4_a58c", STATE4_A58C),
            ("state4_a030", STATE4_A030),
            ("state4_a050", STATE4_A050),
            ("a1ac_callsite", A1AC_CALLSITE),
            ("a1ac", A1AC_ENTRY),
            ("state_return", STATE_RETURN),
            ("dispatcher", STATE_DISPATCHER),
        ):
            if breakpoints[name]:
                try:
                    client.remove_breakpoint(address, kind=2)
                except (RuntimeError, TimeoutError, OSError, ConnectionError):
                    pass
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--per-stop-timeout", type=float, default=12.0)
    parser.add_argument("--max-stops", type=int, default=64)
    parser.add_argument("--max-edge-checks", type=int, default=8)
    parser.add_argument("--release-reads", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for name in ("max_stops", "max_edge_checks", "release_reads", "max_steps"):
        if getattr(args, name) < 1:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    result = run_probe(
        args.rom,
        host=args.host,
        port=args.port,
        per_stop_timeout=args.per_stop_timeout,
        max_stops=args.max_stops,
        max_edge_checks=args.max_edge_checks,
        release_reads=args.release_reads,
        max_steps=args.max_steps,
    )
    output = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(output, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
