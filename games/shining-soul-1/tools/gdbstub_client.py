#!/usr/bin/env python3
"""Minimal GDB remote serial protocol client for talking to mGBA's
built-in GDB stub (`mgba --gdb`, default port 2345). Read-only recon
tool: used to pause the emulator mid-run and inspect live memory
(VRAM/WRAM/EWRAM) rather than statically guessing at ROM offsets.

Not a general GDB client - only implements the handful of packet types
needed here: qSupported handshake, 'g' (read general registers),
'm addr,len' (read memory), 'c'/vCont continue, and interrupt (\\x03).
GBA target registers via this stub: r0-r12, sp, lr, pc, cpsr (16 x
32-bit words for 'g', per mGBA's ARM target description).

Usage as a library:
    from gdbstub_client import GdbClient
    c = GdbClient("127.0.0.1", 2345)
    c.connect()
    mem = c.read_mem(0x06000000, 256)   # VRAM
    regs = c.read_registers()
    c.close()
"""
import socket


def checksum(data: bytes) -> int:
    return sum(data) & 0xFF


class GdbClient:
    def __init__(self, host="127.0.0.1", port=2345, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.buf = b""

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def close(self):
        if self.sock:
            self.sock.close()

    def _send_packet(self, payload: bytes):
        pkt = b"$" + payload + b"#" + f"{checksum(payload):02x}".encode()
        self.sock.sendall(pkt)

    def _recv_raw(self, n=4096) -> bytes:
        try:
            return self.sock.recv(n)
        except socket.timeout:
            return b""

    def _fill_buf(self):
        chunk = self._recv_raw()
        if chunk:
            self.buf += chunk
        return chunk

    def _read_packet(self) -> bytes:
        # wait for a full $...#xx packet in self.buf, ack it, return payload
        while True:
            start = self.buf.find(b"$")
            end = self.buf.find(b"#", start) if start != -1 else -1
            if start != -1 and end != -1 and len(self.buf) >= end + 3:
                payload = self.buf[start + 1:end]
                self.buf = self.buf[end + 3:]
                self.sock.sendall(b"+")  # ack
                return payload
            if not self._fill_buf():
                raise TimeoutError("no complete packet received")

    def send(self, payload: str) -> str:
        # mGBA's gdb stub is flaky about packets sent back-to-back with no
        # gap (observed empirically: a send() immediately following a
        # previous response sometimes never gets a reply at all). A short
        # pre-send delay avoids this reliably; retry once on timeout as a
        # second line of defense.
        import time
        time.sleep(0.05)
        for attempt in range(2):
            self._send_packet(payload.encode())
            try:
                # consume leading +/- acks before the real packet
                while True:
                    if not self.buf:
                        self._fill_buf()
                    if self.buf[:1] in (b"+", b"-"):
                        self.buf = self.buf[1:]
                        continue
                    break
                return self._read_packet().decode(errors="replace")
            except TimeoutError:
                if attempt == 0:
                    time.sleep(0.3)
                    continue
                raise

    def read_registers(self):
        resp = self.send("g")
        # each reg is 4 bytes, little-endian, hex-encoded (8 hex chars)
        regs = []
        for i in range(0, len(resp), 8):
            word = resp[i:i + 8]
            if len(word) < 8:
                break
            b = bytes.fromhex(word)
            regs.append(int.from_bytes(b, "little"))
        return regs

    def read_mem(self, addr: int, length: int) -> bytes:
        out = b""
        chunk_size = 512  # keep packets modest
        off = 0
        while off < length:
            n = min(chunk_size, length - off)
            resp = self.send(f"m{addr + off:x},{n:x}")
            if resp.startswith("E"):
                raise RuntimeError(f"gdbstub error reading 0x{addr+off:x}: {resp}")
            out += bytes.fromhex(resp)
            off += n
        return out

    def write_mem(self, addr: int, data: bytes):
        payload = f"M{addr:x},{len(data):x}:" + data.hex()
        resp = self.send(payload)
        if resp != "OK":
            raise RuntimeError(f"write_mem failed at 0x{addr:x}: {resp}")

    def interrupt(self):
        self.sock.sendall(b"\x03")
        return self._read_packet().decode(errors="replace")

    def cont(self):
        self._send_packet(b"c")

    # --- Added in session 3: watchpoints, register write, blocking
    # continue-until-stop. Verified against mGBA 0.10.5's actual gdb-stub.c
    # source (src/debugger/gdb-stub.c) rather than assumed from the generic
    # GDB remote protocol spec, since mGBA's stub is a partial
    # implementation:
    #   - Z/z packet: "Z<type>,<addr-hex>,<kind-hex>" / "z<type>,...".
    #     type 0/1 = breakpoint, 2 = write watchpoint, 3 = read watchpoint,
    #     4 = read/write watchpoint. Reply "OK" on success, empty ('') on
    #     unsupported type - _send_packet's reply will just be "" in that
    #     case, not an error code, so callers must check for both.
    #   - P packet: "P<regno-hex>=<value>", value is the register's 4 raw
    #     bytes in target (little-endian, ARM) order hex-encoded - same
    #     convention as the 'g' packet's register dump, NOT a plain
    #     big-endian hex number of the value. regno follows the same
    #     r0..r12=0..12, sp=13, lr=14, pc=15 numbering as read_registers().
    #   - Continuing ('c') does not reply immediately; the stub sends an
    #     unsolicited stop-reply packet later, when a breakpoint/watchpoint
    #     fires: "T05<type>:<addr-hex>;" where <type> is "watch"/"rwatch"/
    #     "awatch" for data watchpoints. This still arrives as a normal
    #     $...#xx framed packet that _read_packet() can consume (any stray
    #     leading '+' ack byte before the '$' is naturally skipped by
    #     _read_packet's buffer-scan logic), it just may take much longer
    #     to arrive than a normal command reply, so it needs its own
    #     (longer, caller-supplied) socket timeout rather than self.timeout.

    def set_watchpoint(self, addr: int, kind: int = 4, wtype: int = 2):
        """wtype: 2=write, 3=read, 4=read/write. kind=byte length of the
        watched access (4 for a word). Raises if the stub rejects it."""
        resp = self.send(f"Z{wtype},{addr:x},{kind:x}")
        if resp != "OK":
            raise RuntimeError(
                f"set_watchpoint(type={wtype}) at 0x{addr:x} failed: {resp!r}"
            )

    def remove_watchpoint(self, addr: int, kind: int = 4, wtype: int = 2):
        resp = self.send(f"z{wtype},{addr:x},{kind:x}")
        if resp != "OK":
            raise RuntimeError(
                f"remove_watchpoint(type={wtype}) at 0x{addr:x} failed: {resp!r}"
            )

    def set_breakpoint(self, addr: int, kind: int = 2, wtype: int = 1):
        """wtype 0=software, 1=hardware breakpoint. kind=2 for a THUMB
        halfword instruction."""
        resp = self.send(f"Z{wtype},{addr:x},{kind:x}")
        if resp != "OK":
            raise RuntimeError(f"set_breakpoint at 0x{addr:x} failed: {resp!r}")

    def remove_breakpoint(self, addr: int, kind: int = 2, wtype: int = 1):
        resp = self.send(f"z{wtype},{addr:x},{kind:x}")
        if resp != "OK":
            raise RuntimeError(f"remove_breakpoint at 0x{addr:x} failed: {resp!r}")

    def write_register(self, regno: int, value: int):
        val_hex = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
        resp = self.send(f"P{regno:x}={val_hex}")
        if resp != "OK":
            raise RuntimeError(
                f"write_register(r{regno}=0x{value:x}) failed: {resp!r}"
            )

    def cont_and_wait(self, timeout: float = 30.0) -> str:
        """Send 'c' and block for the async stop-reply packet (breakpoint
        or watchpoint hit), with its own timeout distinct from self.timeout
        since execution may run for a while before stopping. Raises
        TimeoutError if nothing arrives in time - caller should then send
        \\x03 (interrupt()) to regain control, since the target is still
        running."""
        import time
        time.sleep(0.05)
        self._send_packet(b"c")
        old_to = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            return self._read_packet().decode(errors="replace")
        finally:
            self.sock.settimeout(old_to)


REG_NAMES = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
             "r10", "r11", "r12", "sp", "lr", "pc", "cpsr"]


def parse_stop_watch(stop_pkt: str):
    """Parse a 'T05watch:6010000;' style stop-reply into (kind, addr) or
    (None, None) if it's not a data watchpoint stop (e.g. plain 'T05;' for
    a breakpoint, or a swbreak/hwbreak marker)."""
    import re
    m = re.search(r"(watch|rwatch|awatch):([0-9a-fA-F]+);", stop_pkt)
    if not m:
        return None, None
    return m.group(1), int(m.group(2), 16)


if __name__ == "__main__":
    import sys
    c = GdbClient()
    c.connect()
    print("qSupported:", c.send("qSupported:multiprocess+"))
    print("?:", c.send("?"))
    regs = c.read_registers()
    names = ["r0","r1","r2","r3","r4","r5","r6","r7","r8","r9","r10","r11","r12","sp","lr","pc","cpsr"]
    for n, v in zip(names, regs):
        print(f"  {n} = 0x{v:08x}")
    c.close()
