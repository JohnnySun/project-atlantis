#!/usr/bin/env python3
"""Small read-mostly client for mGBA's GBA GDB remote stub.

The client deliberately implements only the packets needed by this game's
read-only runtime reconnaissance. It assumes the mGBA 0.10.x target layout:
r0-r12, sp, lr, pc, cpsr. A GDB session is single-use: after disconnecting,
restart the matching mGBA process before reconnecting.
"""

from __future__ import annotations

import socket
import time


REG_NAMES = [
    "r0",
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "sp",
    "lr",
    "pc",
    "cpsr",
]


def make_packet(payload: bytes) -> bytes:
    checksum = sum(payload) & 0xFF
    return b"$" + payload + b"#" + f"{checksum:02x}".encode("ascii")


class GdbStubClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 2345, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.buffer = b""

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def __enter__(self) -> "GdbStubClient":
        self.connect()
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def _require_socket(self) -> socket.socket:
        if self.sock is None:
            raise RuntimeError("GDB client is not connected")
        return self.sock

    def _read_packet(self) -> bytes:
        sock = self._require_socket()
        while True:
            while self.buffer[:1] in (b"+", b"-"):
                self.buffer = self.buffer[1:]
            start = self.buffer.find(b"$")
            if start >= 0:
                if start:
                    self.buffer = self.buffer[start:]
                end = self.buffer.find(b"#", 1)
                if end >= 0 and len(self.buffer) >= end + 3:
                    payload = self.buffer[1:end]
                    self.buffer = self.buffer[end + 3 :]
                    sock.sendall(b"+")
                    return payload
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("GDB socket closed")
            self.buffer += chunk

    def request(self, payload: str) -> str:
        sock = self._require_socket()
        # mGBA's stub can miss a packet sent immediately after a response.
        time.sleep(0.05)
        sock.sendall(make_packet(payload.encode("ascii")))
        return self._read_packet().decode("ascii", errors="replace")

    def read_registers(self) -> dict[str, int]:
        response = self.request("g")
        if len(response) % 8 != 0:
            raise RuntimeError(f"malformed register response: {response!r}")
        values = []
        for index in range(0, len(response), 8):
            values.append(int.from_bytes(bytes.fromhex(response[index : index + 8]), "little"))
        if len(values) != len(REG_NAMES):
            raise RuntimeError(f"expected {len(REG_NAMES)} registers, got {len(values)}")
        return dict(zip(REG_NAMES, values))

    def read_memory(self, address: int, length: int) -> bytes:
        output = bytearray()
        offset = 0
        while offset < length:
            size = min(0x200, length - offset)
            response = self.request(f"m{address + offset:x},{size:x}")
            if response.startswith("E"):
                raise RuntimeError(f"memory read failed at 0x{address + offset:x}: {response}")
            chunk = bytes.fromhex(response)
            if len(chunk) != size:
                raise RuntimeError(
                    f"short memory read at 0x{address + offset:x}: {len(chunk)} != {size}"
                )
            output.extend(chunk)
            offset += size
        return bytes(output)

    def set_breakpoint(self, address: int, kind: int = 2, breakpoint_type: int = 1) -> None:
        response = self.request(f"Z{breakpoint_type},{address:x},{kind:x}")
        if response != "OK":
            raise RuntimeError(f"breakpoint failed at 0x{address:x}: {response!r}")

    def remove_breakpoint(self, address: int, kind: int = 2, breakpoint_type: int = 1) -> None:
        response = self.request(f"z{breakpoint_type},{address:x},{kind:x}")
        if response != "OK":
            raise RuntimeError(f"breakpoint removal failed at 0x{address:x}: {response!r}")

    def set_watchpoint(self, address: int, kind: int = 4, watchpoint_type: int = 2) -> None:
        response = self.request(f"Z{watchpoint_type},{address:x},{kind:x}")
        if response != "OK":
            raise RuntimeError(f"watchpoint failed at 0x{address:x}: {response!r}")

    def remove_watchpoint(self, address: int, kind: int = 4, watchpoint_type: int = 2) -> None:
        response = self.request(f"z{watchpoint_type},{address:x},{kind:x}")
        if response != "OK":
            raise RuntimeError(f"watchpoint removal failed at 0x{address:x}: {response!r}")

    def continue_and_interrupt(self, seconds: float = 0.5) -> str:
        sock = self._require_socket()
        time.sleep(0.05)
        sock.sendall(make_packet(b"c"))
        time.sleep(seconds)
        sock.sendall(b"\x03")
        return self._read_packet().decode("ascii", errors="replace")

    def continue_until_stop(self, timeout: float = 30.0) -> str:
        sock = self._require_socket()
        time.sleep(0.05)
        old_timeout = sock.gettimeout()
        sock.settimeout(timeout)
        try:
            sock.sendall(make_packet(b"c"))
            return self._read_packet().decode("ascii", errors="replace")
        finally:
            sock.settimeout(old_timeout)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--run-seconds", type=float, default=0.5)
    args = parser.parse_args()

    with GdbStubClient(port=args.port) as client:
        print(f"initial_stop={client.request('?')}")
        stop = client.continue_and_interrupt(args.run_seconds)
        print(f"runtime_stop={stop}")
        for name, value in client.read_registers().items():
            print(f"{name}=0x{value:08x}")
