#!/usr/bin/env python3
"""Trace the clean A9HJ asset decoder without emitting source-bearing data.

The addresses in this file are game-specific observations from the verified
clean ROM.  It records dispatch/helper/return metadata, output hashes and
coarse byte statistics.  ``--inject-a`` changes only the emulator's r0 for
one input poll; it never writes the ROM or a save file.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = __file__
for _ in range(4):
    REPO_ROOT = os.path.dirname(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "core", "gba"))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


DISPATCH = 0x08000528
RETURN = 0x08011D28
INPUT_AFTER_READ = 0x08011D3C
HELPERS = (0x080006CC, 0x080006EC, 0x08000762, 0x080007B4, 0x08000864)
HELPER_NAMES = {
    0x080006CC: "a",
    0x080006EC: "b",
    0x08000762: "c",
    0x080007B4: "d",
    0x08000864: "e",
}
TRACE_POINTS = (DISPATCH, *HELPERS, RETURN)
TEXT_POINTS = (
    0x08012500,
    0x0801266C,
    0x08012728,
    0x08013738,
    0x0801375E,
    0x08013E00,
    0x08013E4C,
)
ALL_POINTS = (*TRACE_POINTS, *TEXT_POINTS)


def fmt(value: int) -> str:
    return f"0x{value:08X}"


def region(value: int) -> str:
    for lower, upper, name in (
        (0x02000000, 0x02040000, "EWRAM"),
        (0x03000000, 0x03008000, "IWRAM"),
        (0x05000000, 0x05000400, "PAL"),
        (0x06000000, 0x06018000, "VRAM"),
        (0x07000000, 0x07000400, "OAM"),
        (0x08000000, 0x0A000000, "ROM"),
    ):
        if lower <= value < upper:
            return name
    return "other"


def byte_stats(data: bytes) -> dict[str, Any]:
    sjis_pairs = 0
    sjis_offsets: list[int] = []
    controls = 0
    high = 0
    index = 0
    while index < len(data):
        value = data[index]
        high += value >= 0x80
        controls += value in {
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
            0x1B, 0xFE, 0xFF,
        }
        if (
            index + 1 < len(data)
            and (0x81 <= value <= 0x9F or 0xE0 <= value <= 0xEF)
            and 0x40 <= data[index + 1] <= 0xFC
            and data[index + 1] != 0x7F
        ):
            sjis_pairs += 1
            if len(sjis_offsets) < 4:
                sjis_offsets.append(index)
            index += 2
        else:
            index += 1
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "nonzero": sum(bool(value) for value in data),
        "high": high,
        "sjis_pairs": sjis_pairs,
        "sjis_offsets": [fmt(value) for value in sjis_offsets],
        "control_like": controls,
    }


def observe(client: GdbClient, state: dict[str, Any], stop: str) -> int:
    registers = client.read_registers()
    pc = registers["pc"] & ~1
    watch_kind, watch_address = parse_stop_watch(stop)
    if watch_kind is not None:
        print(
            "watch-stop",
            watch_kind,
            fmt(watch_address or 0),
            "pc",
            fmt(registers["pc"]),
            "lr",
            fmt(registers["lr"]),
            "r0-r3",
            [fmt(registers[name]) for name in ("r0", "r1", "r2", "r3")],
        )
    if pc == DISPATCH:
        state["sequence"] += 1
        state["pending"] = {"sequence": state["sequence"], "source": registers["r0"], "destination": registers["r1"]}
        state["helper"] = None
        pending = state["pending"]
        print(
            "dispatch",
            pending["sequence"],
            "source",
            fmt(pending["source"]),
            region(pending["source"]),
            "destination",
            fmt(pending["destination"]),
            region(pending["destination"]),
        )
    elif pc in HELPERS:
        state["helper"] = {"pc": pc, "end": registers["r8"]}
        sequence = state["pending"]["sequence"] if state["pending"] else None
        print(
            "helper",
            sequence,
            HELPER_NAMES[pc],
            "input",
            fmt(registers["r1"]),
            "end",
            fmt(registers["r8"]),
        )
    elif pc == RETURN:
        pending = state["pending"]
        helper = state["helper"]
        if pending and helper:
            destination = pending["destination"]
            length = helper["end"] - destination if helper["end"] >= destination else 0
            if 0 < length <= 0x40000:
                summary = byte_stats(client.read_memory(destination, length))
            else:
                summary = {"invalid_length": length}
            print(
                "complete",
                pending["sequence"],
                HELPER_NAMES[helper["pc"]],
                fmt(destination),
                region(destination),
                "length",
                length,
                summary,
            )
        state["pending"] = None
        state["helper"] = None
    elif pc == INPUT_AFTER_READ:
        print("input-poll", fmt(registers["r0"]))
    elif pc == 0x08012500:
        state["text_parser_calls"] += 1
        print("text-parser", state["text_parser_calls"], "r0", fmt(registers["r0"]), "r1", fmt(registers["r1"]))
    elif pc == 0x0801266C:
        state["text_char_calls"] += 1
        if state["text_char_calls"] <= 16:
            print("text-char-handler", state["text_char_calls"], "r0-r3", [fmt(registers[name]) for name in ("r0", "r1", "r2", "r3")])
    elif pc == 0x08012728:
        state["text_source_calls"] += 1
        if state["text_source_calls"] <= 32:
            source = registers["r2"]
            source_hash = None
            if 0x02000000 <= source < 0x0A000000:
                source_hash = hashlib.sha256(client.read_memory(source, 32)).hexdigest()[:16]
            print("text-source", state["text_source_calls"], "ptr", fmt(source), region(source), "byte", fmt(registers["r4"] & 0xFF), "sha", source_hash)
    elif pc == 0x08013738:
        pair = (registers["r0"] & 0xFF, registers["r1"] & 0xFF)
        state["glyph_pairs"].append(pair)
        if len(state["glyph_pairs"]) <= 64:
            print("glyph-pair", len(state["glyph_pairs"]), f"0x{pair[0]:02X}", f"0x{pair[1]:02X}", "r2-r3", [fmt(registers[name]) for name in ("r2", "r3")])
    elif pc in (0x08013E00, 0x08013E4C):
        state["layout_calls"] += 1
        if state["layout_calls"] <= 16:
            print("layout", fmt(pc), state["layout_calls"], "r0-r3", [fmt(registers[name]) for name in ("r0", "r1", "r2", "r3")])
    elif pc == 0x0801375E:
        state["glyph_table_calls"] += 1
        if state["glyph_table_calls"] <= 8:
            print("glyph-table", state["glyph_table_calls"], "state", fmt(registers["r6"]), "table", fmt(registers["r1"]), "computed", fmt(registers["r5"]))
    elif not stop.startswith("S02"):
        print("other-stop", stop, "pc", fmt(registers["pc"]))
    return pc


def pump(client: GdbClient, state: dict[str, Any], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        timeout = max(0.2, min(2.0, deadline - time.monotonic()))
        try:
            stop = client.continue_until_stop(timeout)
        except TimeoutError:
            print("timer-stop", client.interrupt(timeout=2.0))
            return
        observe(client, state, stop)


def inject_a(client: GdbClient, state: dict[str, Any], label: int, timeout: float) -> None:
    client.set_breakpoint(INPUT_AFTER_READ)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            try:
                stop = client.continue_until_stop(min(2.0, deadline - time.monotonic()))
            except TimeoutError:
                stop = client.interrupt(timeout=2.0)
            if observe(client, state, stop) == INPUT_AFTER_READ:
                registers = client.read_registers()
                client.write_register(0, 0x03FE)
                print("inject-a", label, "before", fmt(registers["r0"]), "after", fmt(0x03FE))
                return
        raise TimeoutError("clean input breakpoint did not fire")
    finally:
        try:
            client.remove_breakpoint(INPUT_AFTER_READ)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--baseline-seconds", type=float, default=3.0)
    parser.add_argument("--between-seconds", type=float, default=1.5)
    parser.add_argument("--inject-a", type=int, default=0, metavar="COUNT")
    parser.add_argument("--input-timeout", type=float, default=5.0)
    parser.add_argument("--mgba", type=__import__("pathlib").Path)
    parser.add_argument("--rom", type=__import__("pathlib").Path)
    parser.add_argument("--dump-dir", type=Path)
    parser.add_argument("--watch-address", type=lambda value: int(value, 0), action="append")
    parser.add_argument("--watch-length", type=lambda value: int(value, 0), default=2)
    args = parser.parse_args()

    state: dict[str, Any] = {
        "pending": None,
        "helper": None,
        "sequence": 0,
        "text_parser_calls": 0,
        "text_char_calls": 0,
        "text_source_calls": 0,
        "glyph_table_calls": 0,
        "layout_calls": 0,
        "glyph_pairs": [],
    }
    emulator = None
    if args.mgba is not None:
        if args.rom is None:
            parser.error("--rom is required with --mgba")
        emulator = subprocess.Popen(
            [
                str(args.mgba),
                "-C",
                f"ports.qt.gdbPort={args.port}",
                "-g",
                str(args.rom),
            ],
            cwd=REPO_ROOT,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)

    client = GdbClient(port=args.port, timeout=2.0)
    try:
        for attempt in range(20):
            try:
                client.connect()
                break
            except OSError:
                if attempt == 19:
                    raise
                time.sleep(0.25)
        print("initial", client.request("?"))
        for address in TRACE_POINTS:
            client.set_breakpoint(address)
        watch_addresses: list[int] = []
        text_addresses: list[int] = []
        try:
            pump(client, state, args.baseline_seconds)
            for label in range(1, args.inject_a + 1):
                inject_a(client, state, label, args.input_timeout)
                if args.watch_address and label == args.inject_a:
                    for address in args.watch_address:
                        client.set_watchpoint(address, args.watch_length, 2)
                        watch_addresses.append(address)
                if label == args.inject_a:
                    for address in TEXT_POINTS:
                        client.set_breakpoint(address)
                        text_addresses.append(address)
                pump(client, state, args.between_seconds)
                io = {
                    name: int.from_bytes(client.read_memory(address, 2), "little")
                    for name, address in (
                        ("DISPCNT", 0x04000000),
                        ("BG0CNT", 0x04000008),
                        ("BG1CNT", 0x0400000A),
                        ("BG2CNT", 0x0400000C),
                        ("BG3CNT", 0x0400000E),
                        ("KEYINPUT", 0x04000130),
                    )
                }
                print("io", label, {name: fmt(value) for name, value in io.items()})
                if args.dump_dir is not None:
                    args.dump_dir.mkdir(parents=True, exist_ok=True)
                    for name, address, length in (
                        ("vram", 0x06000000, 0x18000),
                        ("palette", 0x05000000, 0x400),
                        ("oam", 0x07000000, 0x400),
                        ("iwram", 0x03000000, 0x8000),
                    ):
                        data = client.read_memory(address, length)
                        (args.dump_dir / f"{name}.bin").write_bytes(data)
                        print("dump", label, name, hashlib.sha256(data).hexdigest())
        finally:
            for address in reversed(watch_addresses):
                try:
                    client.remove_watchpoint(address, args.watch_length, 2)
                except Exception:
                    pass
            for address in reversed((*TRACE_POINTS, *text_addresses)):
                try:
                    client.remove_breakpoint(address)
                except Exception:
                    pass
    finally:
        client.close()
        if emulator is not None:
            emulator.terminate()
            try:
                emulator.wait(timeout=3)
            except subprocess.TimeoutExpired:
                emulator.kill()
                emulator.wait()


if __name__ == "__main__":
    main()
