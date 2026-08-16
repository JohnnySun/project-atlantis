#!/usr/bin/env python3

import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gdbstub_client import GdbClient, make_packet, parse_stop_watch  # noqa: E402


class FakeSocket:
    def __init__(self, responses):
        self.responses = responses
        self.pending = b""
        self.timeout = 1.0
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)
        if data == b"\x03":
            self.pending += make_packet(b"S02")
        elif data.startswith(b"$"):
            payload = data[1:data.index(b"#")].decode("ascii")
            response = self.responses[payload]
            self.pending += b"+" + make_packet(response.encode("ascii"))

    def recv(self, _size):
        if not self.pending:
            raise socket.timeout()
        output, self.pending = self.pending, b""
        return output

    def settimeout(self, value):
        self.timeout = value

    def gettimeout(self):
        return self.timeout

    def close(self):
        pass


class GdbClientTest(unittest.TestCase):
    def make_client(self, responses):
        client = GdbClient(packet_delay=0, retry_delay=0)
        client.sock = FakeSocket(responses)
        return client

    def test_register_memory_and_point_operations(self):
        register_hex = "".join(
            value.to_bytes(4, "little").hex() for value in range(17)
        )
        client = self.make_client({
            "g": register_hex,
            "m6000000,4": "01020304",
            "Z1,80000c0,2": "OK",
            "z1,80000c0,2": "OK",
            "Z2,6000000,4": "OK",
            "z2,6000000,4": "OK",
            "P0=78563412": "OK",
            "M2000000,2:aabb": "OK",
        })
        self.assertEqual(client.read_registers()["pc"], 15)
        self.assertEqual(client.read_memory(0x06000000, 4), b"\x01\x02\x03\x04")
        client.set_breakpoint(0x080000C0)
        client.remove_breakpoint(0x080000C0)
        client.set_watchpoint(0x06000000)
        client.remove_watchpoint(0x06000000)
        client.write_register(0, 0x12345678)
        client.write_memory(0x02000000, b"\xaa\xbb")

    def test_interrupt_and_watch_stop_parser(self):
        client = self.make_client({})
        self.assertEqual(client.interrupt(), "S02")
        self.assertEqual(parse_stop_watch("T05rwatch:6001234;"), ("rwatch", 0x06001234))
        self.assertEqual(parse_stop_watch("T05hwbreak:;"), (None, None))


if __name__ == "__main__":
    unittest.main()
