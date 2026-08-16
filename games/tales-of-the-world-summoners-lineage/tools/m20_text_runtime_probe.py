#!/usr/bin/env python3
"""Bounded runtime probe for the A9PJ null-terminated text consumer.

Only one GDB breakpoint cohort is installed: either the already identified
``0x080063E0`` text-stream entry or the fixed-count ``0x080063B6`` ``ldrh``
read site.  At each stop the probe records register metadata and a hash/count
summary of the pointed-to bounded halfword window.  Optional navigation uses
the already observed KEYINPUT path and writes only the authorized input
register; it does not write game RAM and never prints the window's code units
or decoded source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m15_navigate_probe import (  # noqa: E402
    parse_sequence,
    press_button,
)
from m16_name_entry_probe import read_display_maps  # noqa: E402

from m20_text_record_probe import (  # noqa: E402
    DECODER_VERSION,
    EXPECTED_ROM_SHA256,
    LINE_ADVANCE_CODE_UNIT,
    NULL_CODE_UNIT,
    code_unit_class,
)


TEXT_STREAM_NULL_ENTRY = 0x080063E0
TEXT_STREAM_FIXED_READ = 0x080063B6
ROM_BASE = 0x08000000
ROM_END = 0x0A000000
EWRAM_BASE = 0x02000000
EWRAM_END = 0x03000000
IWRAM_BASE = 0x03000000
IWRAM_END = 0x04000000
VRAM_BASE = 0x06000000
VRAM_END = 0x06018000
REGISTER_NAMES = (
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: hex32(registers[name])
        for name in REGISTER_NAMES
        if name in registers
    }


def memory_region(address: int) -> str:
    if ROM_BASE <= address < ROM_END:
        return "rom-bus"
    if EWRAM_BASE <= address < EWRAM_END:
        return "ewram"
    if IWRAM_BASE <= address < IWRAM_END:
        return "iwram"
    if VRAM_BASE <= address < VRAM_END:
        return "vram"
    return "other"


def summarize_window(data: bytes) -> dict[str, object]:
    """Return bounded stream facts without returning unit values."""

    units = len(data) // 2
    terminated = False
    control_count = 0
    font_index_count = 0
    min_index: int | None = None
    max_index: int | None = None
    classes: dict[str, int] = {}
    for index in range(units):
        code_unit = int.from_bytes(data[index * 2:index * 2 + 2], "little")
        kind = code_unit_class(code_unit)
        classes[kind] = classes.get(kind, 0) + 1
        if code_unit == NULL_CODE_UNIT:
            terminated = True
            break
        if code_unit == LINE_ADVANCE_CODE_UNIT:
            control_count += 1
            continue
        font_index_count += 1
        min_index = code_unit if min_index is None else min(min_index, code_unit)
        max_index = code_unit if max_index is None else max(max_index, code_unit)
    consumed_bytes = (index + 1) * 2 if units else 0
    return {
        "window_bytes": len(data),
        "window_sha256": digest(data),
        "consumed_bytes_before_cap": consumed_bytes,
        "unit_count_including_terminator": index + 1 if units else 0,
        "terminated_by_0000": terminated,
        "capped_or_short": not terminated,
        "control_candidate_count": control_count,
        "font_record_index_count": font_index_count,
        "font_record_index_min": None if min_index is None else f"0x{min_index:04X}",
        "font_record_index_max": None if max_index is None else f"0x{max_index:04X}",
        "class_counts": dict(sorted(classes.items())),
        "source_text_emitted": False,
    }


def stream_candidate_id(pointer: int, summary: dict[str, object]) -> str:
    identity = (
        f"a9pj:{DECODER_VERSION}:runtime-pointer={pointer:08x}:"
        f"window={summary['window_sha256']}:bytes={summary['window_bytes']}"
    )
    return hashlib.sha256(identity.encode("ascii")).hexdigest()[:24]


def screen_gate_metadata(client: GdbClient) -> dict[str, object]:
    display, _bg0, _bg1 = read_display_maps(client)
    layout = display["keyboard_layout"]
    return {
        "dispcnt": display["dispcnt"],
        "bgcnt": display["bgcnt"],
        "bg0_screenblock_sha256": display["bg0_screenblock_sha256"],
        "bg1_screenblock_sha256": display["bg1_screenblock_sha256"],
        "keyboard_position_match_count": layout["position_match_count"],
        "keyboard_gate": layout["confirmed"],
    }


def read_stream_window(client: GdbClient, pointer: int, window_bytes: int) -> tuple[bytes, str]:
    if pointer & 1:
        raise ValueError("unaligned text stream pointer")
    if pointer < 0 or pointer >= 0x100000000:
        raise ValueError("invalid 32-bit text stream pointer")
    region = memory_region(pointer)
    if region == "other":
        raise ValueError("text stream pointer is outside readable GBA regions")
    data = client.read_memory(pointer, window_bytes, chunk_size=0x40)
    return data, region


def capture(args: argparse.Namespace) -> dict[str, object]:
    entry_address = (
        TEXT_STREAM_FIXED_READ
        if args.entry == "fixed-read"
        else TEXT_STREAM_NULL_ENTRY
    )
    pointer_register = "r5" if args.entry == "fixed-read" else "r2"
    report: dict[str, object] = {
        "probe_version": "m20-text-runtime-probe-20260816.v1",
        "decoder_version": DECODER_VERSION,
        "rom_sha256_expected": EXPECTED_ROM_SHA256,
        "breakpoint": {
            "address": hex32(entry_address),
            "cohort_count": 1,
            "entry_mode": args.entry,
            "pointer_register": pointer_register,
            "purpose": (
                "fixed-count ldrh consumer read site"
                if args.entry == "fixed-read"
                else "null-terminated text-stream entry"
            ),
        },
        "protocol": {
            "packet_delay_seconds": args.packet_delay,
            "timeout_seconds": args.timeout,
            "single_connection": True,
            "register_writes": 0,
            "memory_writes": 0,
        },
        "navigation": {
            "enabled": bool(args.navigate_sequence),
            "sequence": args.navigate_sequence or [],
            "gate": False,
            "steps": [],
        },
        "initial_stop": None,
        "hits": [],
        "termination": None,
    }
    client = GdbClient(
        args.host,
        args.port,
        timeout=args.timeout,
        packet_delay=args.packet_delay,
    )
    with client:
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        if args.navigate_sequence:
            for button in args.navigate_sequence:
                step = press_button(
                    client,
                    button,
                    input_register=args.input_register,
                    hold_events=args.hold_events,
                    release_events=args.release_events,
                    event_timeout=args.event_timeout,
                )
                report["protocol"]["register_writes"] += sum(
                    1
                    for event in step["events"]
                    if event.get("stop_address") == "0x04000130"
                )
                client.continue_and_interrupt(args.step_settle_seconds)
                try:
                    screen = screen_gate_metadata(client)
                except (RuntimeError, ValueError, ConnectionError, OSError) as exc:
                    screen = {
                        "keyboard_gate": False,
                        "screen_read_status": "failed",
                        "screen_read_error": type(exc).__name__,
                    }
                step["screen"] = screen
                report["navigation"]["steps"].append(step)
                if screen.get("keyboard_gate"):
                    report["navigation"]["gate"] = True
                    break
            if not report["navigation"]["gate"]:
                report["termination"] = {
                    "status": "navigation-gate-failed",
                    "hit_count": 0,
                }
                return report

        client.set_breakpoint(entry_address)
        try:
            for hit_index in range(args.max_hits):
                try:
                    stop = client.continue_until_stop(args.event_timeout)
                except TimeoutError as exc:
                    report["termination"] = {
                        "status": "bounded-timeout",
                        "hit_count": len(report["hits"]),
                        "error": str(exc),
                    }
                    try:
                        report["interrupt_stop"] = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError) as interrupt_exc:
                        report["interrupt_error"] = type(interrupt_exc).__name__
                    break
                registers = client.read_registers()
                pointer = registers[pointer_register] & 0xFFFFFFFF
                hit: dict[str, object] = {
                    "hit_index": hit_index,
                    "stop_packet_kind": parse_stop_watch(stop)[0],
                    "pc": hex32(registers["pc"]),
                    "lr": hex32(registers["lr"]),
                    "registers": register_snapshot(registers),
                    "stream_pointer": hex32(pointer),
                    "stream_region": memory_region(pointer),
                    "context": "unknown-until-screen-correlation",
                }
                try:
                    data, region = read_stream_window(client, pointer, args.window_bytes)
                    summary = summarize_window(data)
                    hit["stream_region"] = region
                    hit["stream"] = summary
                    hit["candidate_id"] = stream_candidate_id(pointer, summary)
                    hit["role"] = "runtime-consumer-candidate"
                except (RuntimeError, ValueError, ConnectionError, OSError) as exc:
                    hit["stream_read_status"] = "bounded-read-failed"
                    hit["stream_read_error"] = type(exc).__name__
                    hit["role"] = "runtime-consumer-pointer-unreadable"
                report["hits"].append(hit)
            else:
                report["termination"] = {
                    "status": "bounded-hit-count",
                    "hit_count": len(report["hits"]),
                }
        finally:
            try:
                client.remove_breakpoint(entry_address)
            except (RuntimeError, OSError, ConnectionError):
                report["breakpoint_remove_status"] = "failed-after-capture"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--entry",
        choices=("null-entry", "fixed-read"),
        default="null-entry",
        help="null-entry=0x080063E0; fixed-read=0x080063B6 with stream pointer in r5",
    )
    parser.add_argument("--navigate-sequence", type=str)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--step-settle-seconds", type=float, default=0.25)
    parser.add_argument("--max-hits", type=int, default=8)
    parser.add_argument("--window-bytes", type=lambda value: int(value, 0), default=0x80)
    parser.add_argument("--event-timeout", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.12)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_hits <= 0:
        parser.error("--max-hits must be positive")
    if args.window_bytes <= 0 or args.window_bytes % 2:
        parser.error("--window-bytes must be a positive even number")
    try:
        if args.navigate_sequence:
            args.navigate_sequence = parse_sequence(args.navigate_sequence)
        if not 0 <= args.input_register <= 12:
            raise ValueError("input register must be r0..r12")
        if args.hold_events <= 0 or args.release_events < 0:
            raise ValueError("hold/release event counts are invalid")
        report = capture(args)
    except (ConnectionError, OSError, socket.timeout, TimeoutError) as exc:
        report = {
            "probe_version": "m20-text-runtime-probe-20260816.v1",
            "decoder_version": DECODER_VERSION,
            "breakpoint": {
                "address": hex32(
                    TEXT_STREAM_FIXED_READ
                    if args.entry == "fixed-read"
                    else TEXT_STREAM_NULL_ENTRY
                ),
                "cohort_count": 1,
            },
            "termination": {"status": "connection-failed", "error": type(exc).__name__},
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
