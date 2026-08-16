#!/usr/bin/env python3
"""Capture a bounded, source-free runtime memory baseline from mGBA.

The matching mGBA process must already be running with the private GDB port.
This probe prints only stop state, registers, hashes, and nonzero counts; it
does not write ROM/save data or reproduce Japanese source text.
"""

from __future__ import annotations

import argparse
import hashlib

from gdbstub_client import GdbStubClient


REGION_SPECS = (
    ("iwram", 0x03000000, 0x8000),
    ("palette", 0x05000000, 0x400),
    ("vram", 0x06000000, 0x18000),
    ("oam", 0x07000000, 0x400),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--run-seconds", type=float, default=1.0)
    args = parser.parse_args()

    with GdbStubClient(port=args.port, timeout=5.0) as client:
        print(f"initial_stop={client.request('?')}", flush=True)
        print(f"runtime_stop={client.continue_and_interrupt(args.run_seconds)}", flush=True)
        registers = client.read_registers()
        print(
            "registers="
            + ",".join(f"{name}=0x{value:08x}" for name, value in registers.items()),
            flush=True,
        )
        for name, address, length in REGION_SPECS:
            data = client.read_memory(address, length)
            print(
                f"region={name} address=0x{address:08x} length=0x{length:x} "
                f"sha256={hashlib.sha256(data).hexdigest()} nonzero={sum(byte != 0 for byte in data)}",
                flush=True,
            )


if __name__ == "__main__":
    main()
