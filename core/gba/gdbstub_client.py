#!/usr/bin/env python3
"""Small, dependency-free client for mGBA's GBA GDB remote stub.

The API intentionally covers only Project Atlantis runtime-recon needs:
register and memory access, breakpoints/watchpoints, continue/interrupt, and
single-register writes.  It does not read or modify a ROM file.
"""

from __future__ import annotations

import re
import socket
import time
from typing import Optional


REG_NAMES = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
]


def checksum(payload: bytes) -> int:
    return sum(payload) & 0xFF


def make_packet(payload: bytes) -> bytes:
    return b"$" + payload + b"#" + f"{checksum(payload):02x}".encode("ascii")


class GdbClient:
    """Minimal mGBA 0.10.x remote client.

    Keep one client connected for the entire capture.  mGBA 0.10.5 commonly
    fails to accept a second connection after the first client disconnects;
    restart only the matching emulator process before reconnecting.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 2345,
        timeout: float = 5.0,
        packet_delay: float = 0.05,
        retry_delay: float = 0.25,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.packet_delay = packet_delay
        self.retry_delay = retry_delay
        self.sock: Optional[socket.socket] = None
        self.buffer = b""

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        self.buffer = b""

    def __enter__(self) -> "GdbClient":
        self.connect()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _require_socket(self) -> socket.socket:
        if self.sock is None:
            raise RuntimeError("GDB client is not connected")
        return self.sock

    def _send_packet(self, payload: bytes) -> None:
        self._require_socket().sendall(make_packet(payload))

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
                    received = self.buffer[end + 1:end + 3]
                    self.buffer = self.buffer[end + 3:]
                    try:
                        valid = int(received, 16) == checksum(payload)
                    except ValueError:
                        valid = False
                    sock.sendall(b"+" if valid else b"-")
                    if not valid:
                        raise RuntimeError("invalid GDB packet checksum")
                    return payload
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("mGBA GDB stub closed the connection")
            self.buffer += chunk

    def request(self, payload: str) -> str:
        """Send one request and return its response, retrying one timeout.

        The short pre-send delay is deliberate: mGBA 0.10.5 can drop a packet
        sent immediately after the preceding response.
        """
        sock = self._require_socket()
        time.sleep(self.packet_delay)
        for attempt in range(2):
            self._send_packet(payload.encode("ascii"))
            try:
                return self._read_packet().decode("ascii", errors="replace")
            except socket.timeout:
                if attempt:
                    raise TimeoutError(f"mGBA did not answer {payload!r}")
                time.sleep(self.retry_delay)
                self.buffer = b""
                sock.settimeout(self.timeout)
        raise AssertionError("unreachable")

    send = request

    def read_registers(self) -> dict[str, int]:
        response = self.request("g")
        if len(response) % 8:
            raise RuntimeError(f"malformed register response: {response!r}")
        values = [
            int.from_bytes(bytes.fromhex(response[i:i + 8]), "little")
            for i in range(0, len(response), 8)
        ]
        if len(values) != len(REG_NAMES):
            raise RuntimeError(
                f"expected {len(REG_NAMES)} registers, got {len(values)}"
            )
        return dict(zip(REG_NAMES, values))

    def read_register_values(self) -> list[int]:
        regs = self.read_registers()
        return [regs[name] for name in REG_NAMES]

    def read_memory(self, address: int, length: int, chunk_size: int = 0x200) -> bytes:
        output = bytearray()
        for offset in range(0, length, chunk_size):
            size = min(chunk_size, length - offset)
            response = self.request(f"m{address + offset:x},{size:x}")
            if response.startswith("E"):
                raise RuntimeError(
                    f"memory read failed at 0x{address + offset:x}: {response}"
                )
            chunk = bytes.fromhex(response)
            if len(chunk) != size:
                raise RuntimeError(
                    f"short memory read at 0x{address + offset:x}: "
                    f"{len(chunk)} != {size}"
                )
            output.extend(chunk)
        return bytes(output)

    read_mem = read_memory

    def write_memory(self, address: int, data: bytes) -> None:
        response = self.request(f"M{address:x},{len(data):x}:{data.hex()}")
        if response != "OK":
            raise RuntimeError(f"memory write failed at 0x{address:x}: {response!r}")

    write_mem = write_memory

    def write_register(self, register_number: int, value: int) -> None:
        raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
        response = self.request(f"P{register_number:x}={raw}")
        if response != "OK":
            raise RuntimeError(f"register write failed: {response!r}")

    def _change_point(
        self, action: str, point_type: int, address: int, kind: int, label: str
    ) -> None:
        response = self.request(f"{action}{point_type},{address:x},{kind:x}")
        if response != "OK":
            raise RuntimeError(f"{label} failed at 0x{address:x}: {response!r}")

    def set_breakpoint(self, address: int, kind: int = 2, point_type: int = 1) -> None:
        self._change_point("Z", point_type, address, kind, "breakpoint")

    def remove_breakpoint(self, address: int, kind: int = 2, point_type: int = 1) -> None:
        self._change_point("z", point_type, address, kind, "breakpoint removal")

    clear_breakpoint = remove_breakpoint

    def set_watchpoint(self, address: int, kind: int = 4, watch_type: int = 2) -> None:
        self._change_point("Z", watch_type, address, kind, "watchpoint")

    def remove_watchpoint(self, address: int, kind: int = 4, watch_type: int = 2) -> None:
        self._change_point("z", watch_type, address, kind, "watchpoint removal")

    clear_watchpoint = remove_watchpoint

    def continue_running(self) -> None:
        time.sleep(self.packet_delay)
        self._send_packet(b"c")

    cont = continue_running

    def interrupt(self, timeout: Optional[float] = None) -> str:
        sock = self._require_socket()
        old_timeout = sock.gettimeout()
        if timeout is not None:
            sock.settimeout(timeout)
        try:
            sock.sendall(b"\x03")
            return self._read_packet().decode("ascii", errors="replace")
        finally:
            sock.settimeout(old_timeout)

    def continue_until_stop(self, timeout: float = 30.0) -> str:
        sock = self._require_socket()
        old_timeout = sock.gettimeout()
        sock.settimeout(timeout)
        try:
            self.continue_running()
            return self._read_packet().decode("ascii", errors="replace")
        except socket.timeout as exc:
            raise TimeoutError("target did not stop before timeout") from exc
        finally:
            sock.settimeout(old_timeout)

    cont_and_wait = continue_until_stop

    def continue_and_interrupt(self, seconds: float = 0.5) -> str:
        self.continue_running()
        time.sleep(seconds)
        return self.interrupt()


def parse_stop_watch(packet: str) -> tuple[Optional[str], Optional[int]]:
    match = re.search(r"(watch|rwatch|awatch):([0-9a-fA-F]+);", packet)
    if not match:
        return None, None
    return match.group(1), int(match.group(2), 16)


parse_watch_stop = parse_stop_watch


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--run-seconds", type=float, default=0.0)
    args = parser.parse_args()

    with GdbClient(args.host, args.port) as client:
        print(f"supported={client.request('qSupported:multiprocess+')}")
        print(f"initial_stop={client.request('?')}")
        if args.run_seconds:
            print(f"runtime_stop={client.continue_and_interrupt(args.run_seconds)}")
        for name, value in client.read_registers().items():
            print(f"{name}=0x{value:08x}")
