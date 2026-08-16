#!/usr/bin/env python3
"""Probe the first bounded natural caller of the verified text consumer.

This is intentionally smaller than a navigation harness: after the live font
initializer guard, it sets one breakpoint at the known consumer entry and
records only the first caller LR, register metadata, source-pointer class,
and timeout/stop status.  It does not rewrite arguments or dump memory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from core.gba.gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m19_runtime_qa import (  # noqa: E402
    PATCHED_ROM_SHA256,
    ROM_BASE,
    TARGET_OFFSET,
    _registers_metadata,
    address,
    sha256,
)
from probe_font_resource import CONSUMER, _assert_initialized, capture_initializer  # noqa: E402


class CallerProbeReject(ValueError):
    """A bounded caller probe invariant failed closed."""


def classify_entry(regs: Mapping[str, int], *, target_pointer: int) -> Dict[str, Any]:
    source_pointer = int(regs["r0"])
    lr = int(regs["lr"])
    return {
        "consumer_pc": address(int(regs["pc"])),
        "lr": address(lr),
        "caller_callsite": address(max(0, lr - 5)),
        "registers": _registers_metadata(regs),
        "source_pointer": address(source_pointer),
        "target_pointer": address(target_pointer),
        "source_pointer_region": (
            "rom" if ROM_BASE <= source_pointer < ROM_BASE + 0x0800000 else "ram_or_io"
        ),
        "target_pointer_match": source_pointer == target_pointer,
    }


def probe(client: GdbClient, rom: bytes, *, window_seconds: float) -> Dict[str, Any]:
    initializer = capture_initializer(client, rom, boot_seconds=1.0, stop_timeout=8.0)
    slots = _assert_initialized(client)
    target_pointer = ROM_BASE + TARGET_OFFSET
    client.set_breakpoint(CONSUMER)
    try:
        try:
            stop = client.continue_until_stop(max(0.25, window_seconds))
        except TimeoutError:
            try:
                stop = client.interrupt(timeout=2.0)
            except (OSError, TimeoutError) as exc:
                return {
                    "initializer": {
                        "slot_values": initializer["slot_values"],
                        "nonzero_base_guard": all(slots.values()),
                    },
                    "caller": {"status": "transport_negative", "error": str(exc)},
                }
            return {
                "initializer": {
                    "slot_values": initializer["slot_values"],
                    "nonzero_base_guard": all(slots.values()),
                },
                "caller": {"status": "window_timeout", "stop": stop},
            }
        kind, watched = parse_stop_watch(stop)
        regs = client.read_registers()
        if kind is not None:
            return {
                "initializer": {
                    "slot_values": initializer["slot_values"],
                    "nonzero_base_guard": all(slots.values()),
                },
                "caller": {
                    "status": "unexpected_watch_stop",
                    "watch_kind": kind,
                    "watched": address(watched or 0),
                },
            }
        if int(regs["pc"]) != CONSUMER:
            return {
                "initializer": {
                    "slot_values": initializer["slot_values"],
                    "nonzero_base_guard": all(slots.values()),
                },
                "caller": {"status": "unexpected_breakpoint_stop", "stop_pc": address(int(regs["pc"]))},
            }
        return {
            "initializer": {
                "slot_values": initializer["slot_values"],
                "nonzero_base_guard": all(slots.values()),
            },
            "caller": {"status": "consumer_entry_observed", **classify_entry(regs, target_pointer=target_pointer)},
        }
    finally:
        try:
            client.remove_breakpoint(CONSUMER)
        except Exception:
            pass


def build_report(rom: bytes, *, port: int, result: Mapping[str, Any], window_seconds: float) -> Dict[str, Any]:
    rom_hash = sha256(rom)
    if rom_hash != PATCHED_ROM_SHA256:
        raise CallerProbeReject("patched_rom_hash_mismatch")
    caller = result.get("caller")
    initializer = result.get("initializer")
    if not isinstance(caller, Mapping) or not isinstance(initializer, Mapping):
        raise CallerProbeReject("probe_result_shape_invalid")
    target_match = caller.get("target_pointer_match") is True
    return {
        "schema": "super-robot-taisen-d-m115-caller-probe-v1",
        "game_code": "A6SJ",
        "source_policy": {"source_text_emitted": False, "raw_memory_emitted": False},
        "rom": {"sha256": rom_hash, "expected_sha256": PATCHED_ROM_SHA256, "hash_match": True},
        "gdb": {"port": port, "single_connection": True, "fresh_process_required": True, "window_seconds": window_seconds},
        "initializer": dict(initializer),
        "caller": dict(caller),
        "gate": {
            "font_base_nonzero": initializer.get("nonzero_base_guard") is True,
            "consumer_entry_observed": caller.get("status") == "consumer_entry_observed",
            "target_pointer_match": target_match,
            "target_render_proven": False,
            "natural_screen_proven": False,
            "translation_status": "ai_draft",
        },
        "next_condition": (
            "capture codepage units and writer after target pointer match"
            if target_match
            else "obtain target caller/index or controlled callee-entry state before render proof"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--window-seconds", type=float, default=1.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rom = args.rom.read_bytes()
        with GdbClient(port=args.port, timeout=8.0) as client:
            result = probe(client, rom, window_seconds=args.window_seconds)
        report = build_report(rom, port=args.port, result=result, window_seconds=args.window_seconds)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, CallerProbeReject, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m115_caller_probe_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m115_caller_probe=accepted status={} target_match={}".format(
            report["caller"].get("status"), report["gate"]["target_pointer_match"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
