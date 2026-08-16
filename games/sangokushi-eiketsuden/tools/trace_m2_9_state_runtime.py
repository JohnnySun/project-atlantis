#!/usr/bin/env python3
"""Bounded natural state-machine receipt for B3EJ.

This harness reuses the shared GDB transport and records only runtime
metadata.  It observes the static title/menu dispatcher, the M2.4 state gate,
the normal KEYINPUT reader, and the reviewed Table-B consumer edges while a
fresh process follows one bounded input sequence.  It never writes game state,
descriptor fields, event buffers, ROM, save data, or renderer inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


TOOL_DIR = Path(__file__).resolve().parent
TRACE_PATH = TOOL_DIR / "trace_m2_runtime.py"
SPEC = importlib.util.spec_from_file_location("sangokushi_trace_m2_runtime", TRACE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load trace_m2_runtime.py")
TRACE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE)


ROM_BASE = 0x08000000
KEYINPUT_ADDRESS = TRACE.KEYINPUT_ADDRESS
STATE_BYTE_ADDRESS = 0x030042D1
STATE_DISPATCH_ADDRESS = 0x0805D2EC
TITLE_MENU_OWNER_ADDRESS = 0x0805D10C
NORMAL_INPUT_ADDRESS = 0x0800C61E
STATE_GATE_ADDRESS = 0x0801A738
CONSUMER_ENTRY_ADDRESS = 0x08026054
CONSUMER_INDEX_ADDRESS = 0x080262F8
MAX_STOPS = 512
MAX_STATE_HITS = 128
MAX_INDEX_HITS = 32

BREAKPOINTS = {
    "state_dispatch": STATE_DISPATCH_ADDRESS,
    "title_menu_owner": TITLE_MENU_OWNER_ADDRESS,
    "normal_event_input": NORMAL_INPUT_ADDRESS,
    "state_gate": STATE_GATE_ADDRESS,
    "consumer_entry": CONSUMER_ENTRY_ADDRESS,
    "consumer_index_setup": CONSUMER_INDEX_ADDRESS,
}


def normalize_pc(value: int) -> int:
    return value & ~1


def breakpoint_name(pc: int) -> str | None:
    normalized = normalize_pc(pc)
    for name, address in BREAKPOINTS.items():
        if normalized == address:
            return name
    return None


def _runtime_ram(address: int) -> bool:
    return (
        0x02000000 <= address < 0x02040000
        or 0x03000000 <= address < 0x03008000
    )


def _read_u8(client: GdbClient, address: int) -> int | None:
    if not _runtime_ram(address):
        return None
    try:
        return client.read_memory(address, 1)[0]
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _read_u16(client: GdbClient, address: int) -> int | None:
    if not _runtime_ram(address):
        return None
    try:
        return int.from_bytes(client.read_memory(address, 2), "little")
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _read_u32(client: GdbClient, address: int) -> int | None:
    if not _runtime_ram(address):
        return None
    try:
        return int.from_bytes(client.read_memory(address, 4), "little")
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    names = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "sp", "lr", "pc", "cpsr"}
    return {name: f"0x{value:08X}" for name, value in registers.items() if name in names}


def _index_metadata(client: GdbClient, registers: dict[str, int], *, entry: bool) -> dict[str, object]:
    """Record the reviewed r6 fields without retaining event-array bytes."""

    base = registers["r0"] if entry else registers["r6"]
    metadata: dict[str, object] = {
        "r6_base": f"0x{base:08X}",
        "caller_lr": f"0x{registers['lr']:08X}",
        "r6_base_is_runtime_ram": _runtime_ram(base),
        "bound_status": "runtime-observed-only; not-static-proof",
    }
    fields: dict[str, int | None] = {}
    for offset in (0x02, 0x1C):
        fields[f"0x{offset:02X}"] = _read_u32(client, base + offset) if offset == 0x1C else _read_u16(client, base + offset)
    metadata["r6_count_or_field_0x02"] = fields["0x02"]
    metadata["event_buffer_pointer"] = (
        f"0x{fields['0x1C']:08X}" if isinstance(fields["0x1C"], int) else None
    )
    if not entry and isinstance(fields["0x1C"], int):
        event_pointer = registers["r7"]
        event_byte = _read_u8(client, event_pointer)
        metadata["event_array_index"] = event_pointer - fields["0x1C"]
        metadata["event_byte_value"] = event_byte
        if event_byte is not None:
            actual_index = event_byte & 0x7F
            metadata["actual_index"] = actual_index
            metadata["index_less_than_table_b_count"] = actual_index < 44
            count = fields["0x02"]
            metadata["actual_index_less_than_local_count"] = (
                isinstance(count, int) and actual_index < count
            )
    return metadata


def _vram_hash(client: GdbClient) -> str:
    return hashlib.sha256(client.read_memory(0x06000000, 0x18000)).hexdigest()


def summarize_index_gate(cohort: list[dict[str, object]]) -> str:
    if not cohort:
        return "not-observed"
    if all(row.get("index_less_than_table_b_count") is True for row in cohort):
        return "bounded-observed-all-indexes-less-than-44"
    return "bounded-observed-unknown-or-out-of-range"


def run_state_trace(
    rom_path: Path,
    *,
    host: str,
    port: int,
    sequence: list[str],
    settle_seconds: float,
    event_timeout: float,
    post_seconds: float,
    max_stops: int = MAX_STOPS,
) -> dict[str, object]:
    if not sequence:
        raise ValueError("sequence must not be empty")
    if len(sequence) > 64:
        raise ValueError("sequence must be <= 64 input phases")
    if not 1 <= max_stops <= MAX_STOPS:
        raise ValueError(f"max_stops must be between 1 and {MAX_STOPS}")

    static = TRACE.static_candidate_metadata(rom_path)
    report: dict[str, object] = {
        "read_only": True,
        "harness": "M2.9-state-runtime",
        "navigation_path": {
            "sequence": sequence,
            "sequence_length": len(sequence),
            "settle_seconds": settle_seconds,
            "event_timeout_seconds": event_timeout,
            "max_stops": max_stops,
        },
        "static_candidate": static,
        "breakpoints": {name: f"0x{address:08X}" for name, address in BREAKPOINTS.items()},
        "state_byte_address": f"0x{STATE_BYTE_ADDRESS:08X}",
        "events": [],
        "state_hits": [],
        "index_cohort": [],
        "negative": [],
        "input_events": 0,
        "natural_index_gate_status": "not-observed",
    }
    client = GdbClient(host, port, timeout=max(5.0, event_timeout), packet_delay=0.08)
    installed: list[int] = []
    watch_installed = False
    input_index = 0
    stop_index = 0
    started = time.monotonic()
    target_stopped = True
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = _register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = TRACE.io_values(client)
        report["vram_before_sha256"] = _vram_hash(client)
        for address in BREAKPOINTS.values():
            client.set_breakpoint(address)
            installed.append(address)
        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        watch_installed = True

        while input_index < len(sequence) and stop_index < max_stops:
            desired = sequence[input_index]
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                report["negative"].append({
                    "kind": "bounded-stop-timeout",
                    "stop_index": stop_index,
                    "input_index": input_index,
                    "message": "no reviewed breakpoint/watchpoint stop within event timeout",
                })
                target_stopped = False
                break
            stop_index += 1
            target_stopped = True
            kind, address = parse_stop_watch(stop)
            registers = client.read_registers()
            pc = normalize_pc(registers["pc"])
            hit = breakpoint_name(registers["pc"])
            event: dict[str, object] = {
                "stop_index": stop_index - 1,
                "input_index": input_index,
                "requested_key": desired,
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "pc": f"0x{pc:08X}",
                "lr": f"0x{registers['lr']:08X}",
                "registers": _register_snapshot(registers),
            }
            if hit is not None:
                event["hit"] = hit
                if hit == "state_dispatch":
                    state_value = _read_u8(client, STATE_BYTE_ADDRESS)
                    event["state_value"] = state_value
                    state_hits = report["state_hits"]
                    if isinstance(state_hits, list) and len(state_hits) < MAX_STATE_HITS:
                        state_hits.append({
                            "stop_index": stop_index - 1,
                            "state_value": state_value,
                            "caller_lr": f"0x{registers['lr']:08X}",
                        })
                elif hit == "state_gate":
                    descriptor = registers["r0"]
                    event["descriptor"] = f"0x{descriptor:08X}"
                    event["state_field_0x14"] = _read_u32(client, descriptor + 0x14)
                elif hit == "consumer_entry":
                    event["index_metadata"] = _index_metadata(client, registers, entry=True)
                elif hit == "consumer_index_setup":
                    metadata = _index_metadata(client, registers, entry=False)
                    event["index_metadata"] = metadata
                    cohort = report["index_cohort"]
                    if isinstance(cohort, list) and len(cohort) < MAX_INDEX_HITS:
                        cohort.append({
                            "provenance": "natural-consumer-index-setup",
                            "stop_index": stop_index - 1,
                            "actual_index": metadata.get("actual_index"),
                            "event_byte_value": metadata.get("event_byte_value"),
                            "r6_base": metadata.get("r6_base"),
                            "caller_lr": metadata.get("caller_lr"),
                            "local_count": metadata.get("r6_count_or_field_0x02"),
                            "index_less_than_table_b_count": metadata.get(
                                "index_less_than_table_b_count"
                            ),
                            "actual_index_less_than_local_count": metadata.get(
                                "actual_index_less_than_local_count"
                            ),
                        })
                report["events"].append(event)
                # Breakpoints stop before the instruction. Step once while the
                # same breakpoint remains installed, then resume.
                event["step_response"] = client.request("s")
                continue

            if address is not None and KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2:
                register = TRACE.input_write_register(registers["pc"])
                event["watch"] = "KEYINPUT"
                event["input_write_register"] = f"r{register}"
                event["requested_keyinput"] = f"0x{TRACE.key_value(desired):04X}"
                event["requested_pressed_mask"] = f"0x{TRACE.pressed_mask(desired):04X}"
                client.write_register(register, TRACE.key_value(desired))
                input_index += 1
                report["input_events"] = input_index
                report["events"].append(event)
                continue

            event["watch"] = "unclassified"
            report["events"].append(event)

        report["input_sequence_completed"] = input_index == len(sequence)
        report["stop_budget_exhausted"] = stop_index >= max_stops and input_index < len(sequence)
        if not target_stopped:
            report["final_interrupt"] = client.interrupt(timeout=2.0)
            target_stopped = True
        # The final bounded input stop is already a valid halted GDB state.
        # Running again here can hit one of the same breakpoints before the
        # interrupt packet arrives; mGBA 0.10.5 may then leave a stop reply in
        # front of the next memory response.  Keep the receipt at this clean
        # stop instead of crossing an unbounded post-sequence window.
        report["post_sequence_stop"] = "not-run-after-final-bounded-stop"
        report["post_seconds_requested_but_not_run"] = post_seconds
        report["vram_after_sha256"] = _vram_hash(client)
        report["final_io"] = TRACE.io_values(client)
        cohort = report["index_cohort"]
        report["natural_index_gate_status"] = summarize_index_gate(cohort if isinstance(cohort, list) else [])
        state_hits = report["state_hits"]
        report["state_hit_count"] = len(state_hits) if isinstance(state_hits, list) else 0
        report["state_values_observed"] = sorted({
            row.get("state_value") for row in state_hits if isinstance(row, dict)
            and isinstance(row.get("state_value"), int)
        }) if isinstance(state_hits, list) else []
        report["vram_changed"] = report["vram_before_sha256"] != report["vram_after_sha256"]
        report["natural_consumer_hit_count"] = sum(
            event.get("hit") in {"consumer_entry", "consumer_index_setup"}
            for event in report["events"]
        )
        report["classification"] = {
            "confirmed": [
                "natural input watchpoint receipt",
                "state dispatcher hits and bounded state-byte values"
                if report["state_hit_count"] else "no state dispatcher hit in bounded window",
            ],
            "provisional": [
                "state values are dispatcher metadata, not individual menu/battle labels",
            ],
            "negative": [
                "controlled writes to state/r6/event buffer were not used",
                "natural Table-B index proof exists only if consumer_index_setup cohort is non-empty",
            ],
            "unknown": [
                "normal event-ready transition and story/battle pool identity unless corresponding breakpoint hits",
            ],
        }
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    finally:
        if watch_installed:
            try:
                client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        for address in reversed(installed):
            try:
                client.remove_breakpoint(address)
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        client.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--sequence", default="none:8,start:4,none:20")
    parser.add_argument("--settle-seconds", type=float, default=9.0)
    parser.add_argument("--event-timeout", type=float, default=2.0)
    parser.add_argument("--post-seconds", type=float, default=1.0)
    parser.add_argument("--max-stops", type=int, default=MAX_STOPS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        sequence = TRACE.expand_sequence(TRACE.parse_sequence(args.sequence))
        report = run_state_trace(
            args.rom,
            host=args.host,
            port=args.port,
            sequence=sequence,
            settle_seconds=args.settle_seconds,
            event_timeout=args.event_timeout,
            post_seconds=args.post_seconds,
            max_stops=args.max_stops,
        )
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"trace_m2_9_state_runtime.py: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
