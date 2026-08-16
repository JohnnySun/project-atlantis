#!/usr/bin/env python3
"""Bounded B3TJ runtime probe for mGBA's GDB stub.

This target-specific harness deliberately reuses the repository's mature,
game-agnostic GDB remote client at ``games/shining-soul-1/tools``.  The
reused client only transports GDB packets; no Shining Soul ROM offsets,
renderer, codepage or text assumptions are imported here.  The B3TJ-specific
addresses below were independently observed in this ROM's THUMB code.

The probe is read-only with respect to the ROM and does not write target
memory.  It installs four short-lived hardware breakpoints on the BIOS
decompression wrappers, records at most ``--max-calls`` calls, steps over the
hit and exits.  A per-hit timeout interrupts the emulator so a missing event
cannot leave an unattended mGBA process running.

Output is JSON metadata only: source file offsets, compression tags,
declared output sizes, destinations and stop packets.  It never emits
decoded game text.

Usage (with an independently started mGBA GDB session):
    python3 tools/runtime_probe.py ROM --port 24387 --max-calls 14
"""

from __future__ import annotations

import argparse
import binascii
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
GENERIC_TOOLS = REPO_ROOT / "games" / "shining-soul-1" / "tools"
sys.path.insert(0, str(GENERIC_TOOLS))

# This import is intentionally the generic transport only.  The target
# addresses and record interpretation in this file are B3TJ-specific.
from gdbstub_client import GdbClient  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

WRAPPERS = {
    0x080DD440: "LZ77-VRAM/swi12",
    0x080DD444: "Huffman-VRAM/swi11",
    0x080DD44C: "RL-VRAM/swi15",
    0x080DD450: "RL-WRAM/swi14",
}


def file_offset_for_gba(address: int, rom_size: int) -> int | None:
    offset = address - ROM_BASE
    if 0 <= offset < rom_size:
        return offset
    return None


def compression_header(rom: bytes, file_offset: int | None) -> dict[str, int | str] | None:
    if file_offset is None or file_offset + 4 > len(rom):
        return None
    tag = rom[file_offset]
    names = {0x10: "LZ77", 0x20: "Huffman", 0x24: "Huffman", 0x30: "RLE"}
    if tag not in names:
        return {"tag": tag, "name": "unknown"}
    size = int.from_bytes(rom[file_offset + 1 : file_offset + 4], "little")
    return {"tag": tag, "name": names[tag], "declared_output_size": size}


def stop_address(stop_packet: str) -> int | None:
    match = re.search(r"(?:hwbreak|swbreak):([0-9a-fA-F]+);", stop_packet)
    return int(match.group(1), 16) if match else None


def verify_b3tj(rom: bytes) -> None:
    if len(rom) != EXPECTED_SIZE or (binascii.crc32(rom) & 0xFFFFFFFF) != EXPECTED_CRC32:
        raise ValueError("ROM identity mismatch; this probe is restricted to B3TJ CRC32 1867CCEF")


def run_probe(
    rom_path: Path,
    host: str,
    port: int,
    max_calls: int,
    wait_timeout: float,
    command_timeout: float,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    verify_b3tj(rom)
    client = GdbClient(host, port, timeout=command_timeout)
    breakpoints = list(WRAPPERS)
    calls: list[dict[str, object]] = []
    termination = "max_calls"
    handshake = None
    initial_stop = None

    client.connect()
    try:
        handshake = client.send("qSupported:multiprocess+")
        initial_stop = client.send("?")
        for address in breakpoints:
            client.set_breakpoint(address, kind=2, wtype=1)

        for index in range(max_calls):
            try:
                stop = client.cont_and_wait(timeout=wait_timeout)
            except TimeoutError:
                termination = "per_hit_timeout"
                try:
                    client.interrupt()
                except (TimeoutError, OSError):
                    pass
                break

            regs = client.read_registers()
            if len(regs) < 16:
                termination = "short_register_dump"
                break
            pc = regs[15] & ~1
            hit = stop_address(stop)
            wrapper_address = hit if hit in WRAPPERS else pc
            source_gba = regs[0]
            source_offset = file_offset_for_gba(source_gba, len(rom))
            header = compression_header(rom, source_offset)
            row: dict[str, object] = {
                "index": index,
                "stop": stop,
                "pc": f"0x{pc:08X}",
                "wrapper": WRAPPERS.get(wrapper_address, "unknown"),
                "wrapper_address": f"0x{wrapper_address:08X}",
                "source_gba": f"0x{source_gba:08X}",
                "source_file_offset": (
                    f"0x{source_offset:06X}" if source_offset is not None else None
                ),
                "destination": f"0x{regs[1]:08X}",
                "lr": f"0x{regs[14]:08X}",
            }
            if header is not None:
                row["source_header"] = header
            calls.append(row)

            # The wrapper addresses are the SWI instructions themselves.  A
            # single step returns to ordinary game code before continuing.
            client.send("s")

        if len(calls) >= max_calls:
            termination = "max_calls"
    finally:
        for address in breakpoints:
            try:
                client.remove_breakpoint(address, kind=2, wtype=1)
            except (RuntimeError, TimeoutError, OSError):
                pass
        client.close()

    return {
        "rom": str(rom_path),
        "crc32": f"{binascii.crc32(rom) & 0xFFFFFFFF:08X}",
        "host": host,
        "port": port,
        "wrapper_count": len(WRAPPERS),
        "max_calls": max_calls,
        "wait_timeout_seconds": wait_timeout,
        "handshake": handshake,
        "initial_stop": initial_stop,
        "termination": termination,
        "calls": calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--max-calls", type=int, default=14)
    parser.add_argument("--wait-timeout", type=float, default=10.0)
    parser.add_argument("--command-timeout", type=float, default=8.0)
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("--max-calls must be positive")
    result = run_probe(
        args.rom,
        args.host,
        args.port,
        args.max_calls,
        args.wait_timeout,
        args.command_timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
