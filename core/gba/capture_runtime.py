#!/usr/bin/env python3
"""Capture a bounded, game-agnostic GBA runtime baseline through mGBA GDB.

The report contains registers, selected I/O values, hashes, and non-zero byte
counts.  Optional raw dumps may contain copyrighted game data and therefore
must stay under an ignored games/<game>/work/ directory or /private/tmp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional

from gdbstub_client import GdbClient, parse_stop_watch


REGIONS = {
    "ewram_head": (0x02000000, 0x1000),
    "iwram": (0x03000000, 0x8000),
    "palette": (0x05000000, 0x400),
    "vram": (0x06000000, 0x18000),
    "oam": (0x07000000, 0x400),
}

IO_REGISTERS = {
    "DISPCNT": (0x04000000, 2),
    "VCOUNT": (0x04000006, 2),
    "BG0CNT": (0x04000008, 2),
    "BG1CNT": (0x0400000A, 2),
    "BG2CNT": (0x0400000C, 2),
    "BG3CNT": (0x0400000E, 2),
    "KEYINPUT": (0x04000130, 2),
}


def summarize(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08X}",
        "length": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "nonzero_bytes": sum(value != 0 for value in data),
    }


def capture(
    client: GdbClient,
    *,
    run_seconds: float,
    breakpoint: Optional[int],
    breakpoint_timeout: float,
    watchpoint: Optional[int],
    watch_length: int,
    watch_type: int,
    watch_timeout: float,
    dump_dir: Optional[Path],
) -> dict[str, object]:
    report: dict[str, object] = {
        "supported": client.request("qSupported:multiprocess+"),
        "initial_stop": client.request("?"),
        "initial_registers": client.read_registers(),
    }

    if breakpoint is not None:
        client.set_breakpoint(breakpoint)
        try:
            stop = client.continue_until_stop(breakpoint_timeout)
            report["breakpoint"] = {
                "address": f"0x{breakpoint:08X}",
                "stop": stop,
                "registers": client.read_registers(),
            }
        finally:
            client.remove_breakpoint(breakpoint)

    if watchpoint is not None:
        client.set_watchpoint(watchpoint, watch_length, watch_type)
        try:
            stop = client.continue_until_stop(watch_timeout)
            kind, address = parse_stop_watch(stop)
            report["watchpoint"] = {
                "requested_address": f"0x{watchpoint:08X}",
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else f"0x{address:08X}",
                "registers": client.read_registers(),
            }
        finally:
            client.remove_watchpoint(watchpoint, watch_length, watch_type)

    report["runtime_stop"] = client.continue_and_interrupt(run_seconds)
    report["runtime_registers"] = client.read_registers()
    report["io"] = {
        name: {
            "address": f"0x{address:08X}",
            "value": int.from_bytes(client.read_memory(address, length), "little"),
        }
        for name, (address, length) in IO_REGISTERS.items()
    }

    region_data = {
        name: client.read_memory(address, length)
        for name, (address, length) in REGIONS.items()
    }
    report["regions"] = {
        name: summarize(data, REGIONS[name][0])
        for name, data in region_data.items()
    }
    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)
        for name, data in region_data.items():
            (dump_dir / f"{name}.bin").write_bytes(data)
        report["dump_dir"] = str(dump_dir)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-seconds", type=float, default=1.0)
    parser.add_argument("--breakpoint", type=lambda value: int(value, 0))
    parser.add_argument("--breakpoint-timeout", type=float, default=20.0)
    parser.add_argument("--watchpoint", type=lambda value: int(value, 0))
    parser.add_argument("--watch-length", type=lambda value: int(value, 0), default=4)
    parser.add_argument(
        "--watch-type",
        type=int,
        choices=(2, 3, 4),
        default=2,
        help="2=write, 3=read, 4=read/write",
    )
    parser.add_argument("--watch-timeout", type=float, default=20.0)
    parser.add_argument("--dump-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with GdbClient(args.host, args.port) as client:
        result = capture(
            client,
            run_seconds=args.run_seconds,
            breakpoint=args.breakpoint,
            breakpoint_timeout=args.breakpoint_timeout,
            watchpoint=args.watchpoint,
            watch_length=args.watch_length,
            watch_type=args.watch_type,
            watch_timeout=args.watch_timeout,
            dump_dir=args.dump_dir,
        )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
