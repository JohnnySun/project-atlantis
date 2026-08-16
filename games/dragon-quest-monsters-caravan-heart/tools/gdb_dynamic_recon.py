#!/usr/bin/env python3
"""Read-only mGBA GDB reconnaissance for the A9HJ candidate ROM.

The tool deliberately emits hashes and address/register metadata rather than
decoded text.  Optional binary dumps belong in a caller-selected temporary
directory and must not be committed.

The Qt mGBA build used by this project starts GDB on its compiled-in port, so
the session uses a private patched mGBA copy and passes the port explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import time
from pathlib import Path
from typing import Optional


REG_NAMES = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
]


def checksum(payload: bytes) -> int:
    return sum(payload) & 0xFF


class GdbClient:
    """Small GDB remote client covering the mGBA operations used here."""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.buffer = b""

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _send_frame(self, payload: bytes) -> None:
        assert self.sock is not None
        frame = b"$" + payload + b"#" + f"{checksum(payload):02x}".encode()
        self.sock.sendall(frame)

    def _read_packet(self, timeout: Optional[float] = None) -> str:
        assert self.sock is not None
        old_timeout = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while True:
                start = self.buffer.find(b"$")
                if start >= 0:
                    end = self.buffer.find(b"#", start)
                    if end >= 0 and len(self.buffer) >= end + 3:
                        payload = self.buffer[start + 1:end]
                        self.buffer = self.buffer[end + 3:]
                        self.sock.sendall(b"+")
                        return payload.decode(errors="replace")
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise ConnectionError("mGBA GDB connection closed")
                self.buffer += chunk
        finally:
            if timeout is not None:
                self.sock.settimeout(old_timeout)

    def command(self, payload: str, timeout: Optional[float] = None) -> str:
        time.sleep(0.05)
        self._send_frame(payload.encode())
        return self._read_packet(timeout)

    def continue_run(self) -> None:
        time.sleep(0.05)
        self._send_frame(b"c")

    def continue_until_stop(self, timeout: float) -> str:
        self.continue_run()
        return self._read_packet(timeout)

    def interrupt(self, timeout: float = 10.0) -> str:
        assert self.sock is not None
        self.sock.sendall(b"\x03")
        return self._read_packet(timeout)

    def registers(self) -> dict[str, int]:
        response = self.command("g")
        values = []
        for offset in range(0, len(response), 8):
            word = response[offset:offset + 8]
            if len(word) < 8:
                break
            values.append(int.from_bytes(bytes.fromhex(word), "little"))
        return {name: value for name, value in zip(REG_NAMES, values)}

    def read_memory(self, address: int, length: int) -> bytes:
        result = bytearray()
        for offset in range(0, length, 512):
            amount = min(512, length - offset)
            response = self.command(f"m{address + offset:x},{amount:x}")
            if response.startswith("E"):
                raise RuntimeError(f"mGBA memory read failed at 0x{address + offset:x}: {response}")
            result.extend(bytes.fromhex(response))
        return bytes(result)


def nonzero_spans(data: bytes, limit: int = 32) -> list[list[int]]:
    spans: list[list[int]] = []
    start = None
    for index, value in enumerate(data):
        if value and start is None:
            start = index
        elif not value and start is not None:
            spans.append([start, index])
            start = None
            if len(spans) >= limit:
                return spans
    if start is not None and len(spans) < limit:
        spans.append([start, len(data)])
    return spans


def summarize_region(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08X}",
        "length": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "nonzero_bytes": sum(value != 0 for value in data),
        "nonzero_spans": nonzero_spans(data),
    }


def save_dump(dump_dir: Optional[Path], name: str, data: bytes) -> Optional[str]:
    if dump_dir is None:
        return None
    dump_dir.mkdir(parents=True, exist_ok=True)
    path = dump_dir / f"{name}.bin"
    path.write_bytes(data)
    return str(path)


def capture(args: argparse.Namespace) -> dict[str, object]:
    client = GdbClient(args.host, args.port, timeout=args.command_timeout)
    client.connect()
    try:
        supported = client.command("qSupported:multiprocess+")
        initial_stop = client.command("?")
        entry_breakpoint = client.command("Z0,80000c0,4")
        entry_stop = client.continue_until_stop(args.entry_timeout)
        entry_registers = client.registers()
        clear_breakpoint = client.command("z0,80000c0,4")

        watch_stop = None
        watch_registers = None
        watch_address = None
        watch_reply = None
        if args.watch_address is not None:
            watch_address = args.watch_address
            watch_reply = client.command(f"Z2,{watch_address:x},{args.watch_length:x}")
            watch_stop = client.continue_until_stop(args.watch_timeout)
            watch_registers = client.registers()
            client.command(f"z2,{watch_address:x},{args.watch_length:x}")

        client.continue_run()
        time.sleep(args.duration)
        manual_stop = client.interrupt(args.interrupt_timeout)
        after_registers = client.registers()

        io_specs = {
            "dispcnt": (0x04000000, 2),
            "vcount": (0x04000006, 2),
            "bg0cnt": (0x04000008, 2),
            "bg1cnt": (0x0400000A, 2),
            "bg2cnt": (0x0400000C, 2),
            "bg3cnt": (0x0400000E, 2),
            "keyinput": (0x04000130, 2),
        }
        io_values = {
            name: {
                "address": f"0x{address:08X}",
                "value_le": int.from_bytes(client.read_memory(address, length), "little"),
            }
            for name, (address, length) in io_specs.items()
        }

        region_specs = {
            "ewram_head": (0x02000000, 0x1000),
            "iwram": (0x03000000, 0x8000),
            "palette": (0x05000000, 0x400),
            "vram": (0x06000000, 0x18000),
            "oam": (0x07000000, 0x400),
        }
        region_data = {
            name: client.read_memory(address, length)
            for name, (address, length) in region_specs.items()
        }
        regions = {
            name: summarize_region(data, region_specs[name][0])
            for name, data in region_data.items()
        }
        dump_paths = {
            name: save_dump(args.dump_dir, name, data)
            for name, data in region_data.items()
        }

        return {
            "tool": "gdb_dynamic_recon",
            "gdb": {"host": args.host, "port": args.port, "supported": supported},
            "entry": {
                "breakpoint_reply": entry_breakpoint,
                "stop": entry_stop,
                "registers": entry_registers,
                "clear_reply": clear_breakpoint,
            },
            "watch": {
                "address": None if watch_address is None else f"0x{watch_address:08X}",
                "length": args.watch_length if watch_address is not None else None,
                "set_reply": watch_reply,
                "stop": watch_stop,
                "registers": watch_registers,
            },
            "after_duration": {
                "seconds": args.duration,
                "stop": manual_stop,
                "registers": after_registers,
            },
            "io": io_values,
            "regions": regions,
            "dump_paths": dump_paths,
        }
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2387)
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--entry-timeout", type=float, default=20.0)
    parser.add_argument("--interrupt-timeout", type=float, default=10.0)
    parser.add_argument("--command-timeout", type=float, default=5.0)
    parser.add_argument("--watch-address", type=lambda value: int(value, 0))
    parser.add_argument("--watch-length", type=lambda value: int(value, 0), default=4)
    parser.add_argument("--watch-timeout", type=float, default=20.0)
    parser.add_argument("--dump-dir", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(capture(parse_args()), ensure_ascii=False, indent=2, sort_keys=True))
