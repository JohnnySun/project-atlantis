#!/usr/bin/env python3
"""Capture a bounded AFEJ glyph-map to VRAM writer receipt.

This is an M1.19 follow-up to the earlier natural-route tracer.  It keeps the
source/output boundary strict: reports contain addresses, opaque code-unit
tokens, hashes, lengths and hit counts, but never a complete decoded string,
ROM image or RAM dump.  Navigation only supplies active-low KEYINPUT values;
the tracer never writes a selector, index, PC or game state.

The runtime path is intentionally structural:

    EWRAM text buffer -> 0x080992dc two-byte map lookup
      -> 0x08098c62 glyph-field write -> 0x080995b0 composer
      -> 0x08099580 kernel -> 0x080995a6 str r1,[r2] -> VRAM

The stop loop drains stale mGBA packets before accepting a stop response.  The
shared core GDB client still owns packet framing; this file only supplies the
game-specific bounded observation points and receipt schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import summarize  # noqa: E402
from gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch  # noqa: E402
from trace_m19_natural import (  # noqa: E402
    BUFFER,
    BUFFER_SIZE,
    BUTTON_BITS,
    CONSUMER_BYTE_READ,
    CONSUMER_CONTROL_BRANCH,
    COPY_WRAPPER,
    HIGH_CALLSITE,
    KEYINPUT,
    LOADER_BL,
    LOADER_ENTRY,
    LOADER_RETURN,
    NO_KEY,
    ROM_BASE,
    ROM_SIZE,
    WORKER,
    _capstone_instructions,
    _opaque_byte_branch_target,
    buffer_summary,
    hex32,
    identity,
    loader_caller_from_lr,
    parse_sequence,
    snapshot,
    table_provenance,
)


MAP_LOOKUP_ENTRY = 0x080992DC
MAP_LOOKUP_FIRST_BYTE = 0x080992E2
MAP_LOOKUP_MATCH = 0x080992F6
MAP_LOOKUP_FALLBACK = 0x0809930A
MAP_LOOKUP_WRAPPER = 0x08099314
MAP_BASE = 0x08691644

GLYPH_FIELD_WRITE = 0x08098C62
GLYPH_READER_ENTRY = 0x08098F68
GLYPH_FIELD_READ = 0x08098F78
COMPOSER_ENTRY = 0x08099424
# 0x08099460 is ``movs r2,#0``; the actual BL instruction is 0x08099462.
COMPOSER_CALL = 0x08099462
RENDERER_ENTRY = 0x080995B0
RENDERER_KERNEL = 0x08099580
RENDERER_WRITE = 0x080995A6
RENDERER_WRITE_AFTER = 0x080995A8

EWRAM_START = 0x02000000
EWRAM_END = 0x02040000
IWRAM_START = 0x03000000
IWRAM_END = 0x03008000
VRAM_START = 0x06000000
VRAM_END = 0x06018000

DISPLAY_IO = {
    "DISPCNT": 0x04000000,
    "BG0CNT": 0x04000008,
    "BG1CNT": 0x0400000A,
    "BG2CNT": 0x0400000C,
    "BG3CNT": 0x0400000E,
}

BREAKPOINTS = (
    LOADER_ENTRY,
    LOADER_BL,
    LOADER_RETURN,
    CONSUMER_BYTE_READ,
    CONSUMER_CONTROL_BRANCH,
    MAP_LOOKUP_ENTRY,
    MAP_LOOKUP_FIRST_BYTE,
    MAP_LOOKUP_MATCH,
    MAP_LOOKUP_FALLBACK,
    MAP_LOOKUP_WRAPPER,
    GLYPH_FIELD_WRITE,
    GLYPH_READER_ENTRY,
    GLYPH_FIELD_READ,
    COMPOSER_ENTRY,
    COMPOSER_CALL,
    RENDERER_ENTRY,
    RENDERER_KERNEL,
    RENDERER_WRITE,
)


def _is_stop(response: str) -> bool:
    return response.startswith(("T", "S")) or parse_stop_watch(response)[0] is not None


def _request_ok(client: GdbClient, payload: str) -> None:
    """Boundedly drain stale packets until a point/register write is OK."""

    expected_register_length = len(REG_NAMES) * 8
    for _ in range(12):
        response = client.request(payload)
        if response == "OK":
            return
        if response.startswith("E"):
            raise RuntimeError(f"GDB request failed for {payload!r}: {response!r}")
        if len(response) == expected_register_length:
            continue
        if _is_stop(response):
            continue
    raise RuntimeError(f"no OK response for {payload!r}")


def _read_registers(client: GdbClient) -> dict[str, int]:
    expected_length = len(REG_NAMES) * 8
    for _ in range(16):
        response = client.request("g")
        if response.startswith("E") or len(response) != expected_length:
            continue
        try:
            values = [
                int.from_bytes(bytes.fromhex(response[index:index + 8]), "little")
                for index in range(0, len(response), 8)
            ]
        except ValueError:
            continue
        if len(values) == len(REG_NAMES):
            return dict(zip(REG_NAMES, values))
    raise RuntimeError("mGBA returned no complete register response")


def _read_memory(client: GdbClient, address: int, length: int) -> bytes:
    output = bytearray()
    for offset in range(0, length, 0x200):
        size = min(0x200, length - offset)
        for _ in range(12):
            response = client.request(f"m{address + offset:x},{size:x}")
            if response.startswith("E"):
                raise RuntimeError(f"memory read failed at 0x{address + offset:x}: {response}")
            if _is_stop(response) or response == "OK":
                continue
            try:
                data = bytes.fromhex(response)
            except ValueError:
                continue
            if len(data) == size:
                output.extend(data)
                break
        else:
            raise RuntimeError(f"no memory response at 0x{address + offset:x}")
    return bytes(output)


def _continue_until_stop(client: GdbClient, timeout: float) -> str:
    """Continue once and ignore queued non-stop replies until a stop."""

    sock = client._require_socket()
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        client.continue_running()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = client._read_packet().decode("ascii", errors="replace")
            if _is_stop(response):
                return response
        raise TimeoutError("target did not stop before timeout")
    except socket.timeout as exc:
        raise TimeoutError("target did not stop before timeout") from exc
    finally:
        sock.settimeout(old_timeout)


def _interrupt_until_stop(client: GdbClient, timeout: float = 2.0) -> str:
    sock = client._require_socket()
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        sock.sendall(b"\x03")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = client._read_packet().decode("ascii", errors="replace")
            if _is_stop(response):
                return response
        raise TimeoutError("target did not stop after interrupt")
    except socket.timeout as exc:
        raise TimeoutError("target did not stop after interrupt") from exc
    finally:
        sock.settimeout(old_timeout)


def _step_until_stop(client: GdbClient, timeout: float = 2.0) -> str:
    sock = client._require_socket()
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    try:
        time.sleep(client.packet_delay)
        client._send_packet(b"s")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            response = client._read_packet().decode("ascii", errors="replace")
            if _is_stop(response):
                return response
        raise TimeoutError("target did not stop after single-step")
    except socket.timeout as exc:
        raise TimeoutError("target did not stop after single-step") from exc
    finally:
        sock.settimeout(old_timeout)


def _valid_region(address: int, length: int) -> bool:
    return any(
        start <= address and address + length <= end
        for start, end in (
            (ROM_BASE, ROM_BASE + ROM_SIZE),
            (EWRAM_START, EWRAM_END),
            (IWRAM_START, IWRAM_END),
            (VRAM_START, VRAM_END),
        )
    )


def _summary(client: GdbClient, address: int, length: int) -> Optional[dict[str, object]]:
    if not _valid_region(address, length):
        return None
    try:
        return summarize(_read_memory(client, address, length), address)
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _display_io(client: GdbClient) -> dict[str, str]:
    return {
        name: hex32(int.from_bytes(_read_memory(client, address, 2), "little"))
        for name, address in DISPLAY_IO.items()
    }


def _connect(client: GdbClient, source_port: Optional[int]) -> None:
    if source_port is None:
        client.connect()
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(client.timeout)
    try:
        sock.bind(("127.0.0.1", source_port))
        sock.connect((client.host, client.port))
        client.sock = sock
        client.buffer = b""
    except BaseException:
        sock.close()
        raise


def _static_gate(rom: bytes) -> dict[str, object]:
    ranges = (
        (MAP_LOOKUP_ENTRY, MAP_LOOKUP_WRAPPER + 0x12),
        (GLYPH_FIELD_WRITE - 2, GLYPH_FIELD_WRITE + 2),
        (GLYPH_FIELD_READ - 2, GLYPH_FIELD_READ + 2),
        (COMPOSER_ENTRY, COMPOSER_CALL + 4),
        (RENDERER_ENTRY, RENDERER_ENTRY + 2),
        (RENDERER_KERNEL, RENDERER_WRITE_AFTER + 2),
    )
    rows = [
        row
        for start, end in ranges
        for row in _capstone_instructions(rom, start, end)
    ]
    by_address = {int(row["address"]): row for row in rows}

    def instruction(address: int) -> str:
        row = by_address[address]
        return f"{hex32(address)}: {row['mnemonic']} {row['op_str']}".rstrip()

    return {
        "encoding": "ARM7TDMI Thumb",
        "two_byte_map": {
            "lookup_entry": hex32(MAP_LOOKUP_ENTRY),
            "first_byte_instruction": instruction(MAP_LOOKUP_FIRST_BYTE),
            "match_instruction": instruction(MAP_LOOKUP_MATCH),
            "fallback_instruction": instruction(MAP_LOOKUP_FALLBACK),
            "map_base": hex32(MAP_BASE),
            "runtime_lookup_confirmed": True,
            "unicode_identity_confirmed": False,
        },
        "glyph_field": {
            "write_instruction": instruction(GLYPH_FIELD_WRITE),
            "field_offset": "0x4a",
            "reader_entry": hex32(GLYPH_READER_ENTRY),
            "field_read": instruction(GLYPH_FIELD_READ),
        },
        "composer": {
            "entry": hex32(COMPOSER_ENTRY),
            "call_instruction": instruction(COMPOSER_CALL),
            "renderer_entry": instruction(RENDERER_ENTRY),
            "kernel_entry": instruction(RENDERER_KERNEL),
            "writer_instruction": instruction(RENDERER_WRITE),
            "writer_after": instruction(RENDERER_WRITE_AFTER),
        },
        "semantic_name_assigned": False,
    }


class GlyphSinkTrace:
    def __init__(
        self,
        client: GdbClient,
        rom: bytes,
        *,
        max_records: int,
        max_events: int,
    ) -> None:
        self.client = client
        self.rom = rom
        self.max_records = max_records
        self.max_events = max_events
        self.events: list[dict[str, object]] = []
        self.hit_counts = {hex32(address): 0 for address in BREAKPOINTS}
        self.watch_hit_count = 0
        self.loader_records: list[dict[str, object]] = []
        self.consumer_reads: list[dict[str, object]] = []
        self.lookup_receipts: list[dict[str, object]] = []
        self.glyph_field_receipts: list[dict[str, object]] = []
        self.composer_receipts: list[dict[str, object]] = []
        self.renderer_entries: list[dict[str, object]] = []
        self.kernel_receipts: list[dict[str, object]] = []
        self.writer_receipts: list[dict[str, object]] = []
        self._last_loader: Optional[dict[str, object]] = None
        self._last_lookup: Optional[dict[str, object]] = None
        self._last_kernel: Optional[dict[str, object]] = None
        self._last_consumer: Optional[dict[str, object]] = None
        self._breakpoints: list[int] = []
        self._detail_breakpoints_active = True

    def install(self) -> None:
        for address in dict.fromkeys(BREAKPOINTS):
            _request_ok(self.client, f"Z1,{address:x},2")
            self._breakpoints.append(address)

    def uninstall(self) -> None:
        try:
            _request_ok(self.client, f"z3,{KEYINPUT:x},2")
        except (ConnectionError, OSError, RuntimeError, TimeoutError):
            pass
        for address in reversed(self._breakpoints):
            try:
                _request_ok(self.client, f"z1,{address:x},2")
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass

    def _remove_detail_breakpoints(self) -> None:
        """Let the bounded glyph cohort drain before observing its renderer."""

        if not self._detail_breakpoints_active:
            return
        detail = {
            CONSUMER_BYTE_READ,
            CONSUMER_CONTROL_BRANCH,
            MAP_LOOKUP_ENTRY,
            MAP_LOOKUP_FIRST_BYTE,
            MAP_LOOKUP_MATCH,
            MAP_LOOKUP_FALLBACK,
            MAP_LOOKUP_WRAPPER,
            GLYPH_FIELD_WRITE,
        }
        for address in tuple(self._breakpoints):
            if address not in detail:
                continue
            try:
                _request_ok(self.client, f"z1,{address:x},2")
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                continue
            self._breakpoints.remove(address)
        self._detail_breakpoints_active = False

    def _event(self, stop: str, address: Optional[int], regs: dict[str, int]) -> dict[str, object]:
        return {
            "stop": stop.split(";", 1)[0],
            "stop_kind": parse_stop_watch(stop)[0],
            "stop_address": None if address is None else hex32(address),
            "pc": hex32(regs["pc"]),
            "registers": snapshot(regs),
        }

    def _save_event(self, event: dict[str, object]) -> None:
        if len(self.events) < self.max_events:
            self.events.append(event)

    def _record_loader(self, buffer: dict[str, object]) -> None:
        if self._last_loader is None or len(self.loader_records) >= self.max_records:
            return
        index = self._last_loader.get("loader_index")
        self.loader_records.append({
            "string_id": f"afej.loader.index.{index}",
            "reachability": "natural_keyinput",
            "loader_index": index,
            "caller_lr": self._last_loader.get("caller_lr"),
            "caller_callsite": self._last_loader.get("caller_callsite"),
            "source_pointer": self._last_loader.get("source_pointer"),
            "source_hash_window": self._last_loader.get("source_hash_window"),
            "destination": self._last_loader.get("destination"),
            "buffer": buffer,
        })

    def handle_stop(self, stop: str) -> dict[str, object]:
        stop_kind, stop_address = parse_stop_watch(stop)
        regs = _read_registers(self.client)
        pc = regs["pc"] & 0xFFFFFFFF
        if hex32(pc) in self.hit_counts:
            self.hit_counts[hex32(pc)] += 1
        if stop_address == KEYINPUT:
            self.watch_hit_count += 1
            event = self._event(stop, stop_address, regs)
            event["kind"] = "keyinput_poll"
            self._save_event(event)
            return event

        event = self._event(stop, stop_address, regs)
        if pc == LOADER_ENTRY:
            index = regs["r0"]
            callsite = loader_caller_from_lr(regs["lr"])
            self._last_loader = {
                "loader_index": index,
                "caller_lr": hex32(regs["lr"]),
                "caller_callsite": callsite,
                "provenance": table_provenance(self.rom, index),
            }
            event.update({
                "kind": "loader_entry",
                "loader_index": index,
                "caller_lr": hex32(regs["lr"]),
                "caller_callsite": callsite,
                "provenance": self._last_loader["provenance"],
            })
        elif pc == LOADER_BL:
            source = regs["r0"]
            event.update({
                "kind": "loader_copy_callsite",
                "source_pointer": hex32(source),
                "destination": hex32(regs["r1"]),
                "copy_wrapper": hex32(COPY_WRAPPER),
                "worker": hex32(WORKER),
                "source_hash_window": _summary(self.client, source & ~1, 0x40),
            })
            if self._last_loader is not None:
                self._last_loader.update({
                    "source_pointer": hex32(source),
                    "destination": hex32(regs["r1"]),
                    "source_hash_window": event["source_hash_window"],
                })
        elif pc == LOADER_RETURN:
            buffer = buffer_summary(_read_memory(self.client, BUFFER, BUFFER_SIZE))
            event.update({"kind": "loader_return", "buffer": buffer})
            self._record_loader(buffer)
        elif pc == CONSUMER_BYTE_READ:
            pointer = regs["r6"]
            value = _read_memory(self.client, pointer, 1)[0]
            event.update({
                "kind": "text_byte_read",
                "buffer_pointer": hex32(pointer),
                "byte_value": hex32(value),
                "buffer_offset_if_base": pointer - BUFFER
                if BUFFER <= pointer < BUFFER + BUFFER_SIZE else None,
                "static_branch_target": _opaque_byte_branch_target(value),
            })
            self._last_consumer = event.copy()
            if len(self.consumer_reads) < self.max_records:
                self.consumer_reads.append(event.copy())
        elif pc == CONSUMER_CONTROL_BRANCH:
            event.update({
                "kind": "opaque_control_branch",
                "source_byte": self._last_consumer.get("byte_value")
                if self._last_consumer else None,
                "source_pointer": self._last_consumer.get("buffer_pointer")
                if self._last_consumer else None,
                "branch_target": hex32(CONSUMER_CONTROL_BRANCH),
                "semantic_name_assigned": False,
            })
        elif pc == MAP_LOOKUP_FIRST_BYTE:
            pointer = regs["r0"]
            pair = _read_memory(self.client, pointer, 2)
            self._last_lookup = {
                "input_pointer": hex32(pointer),
                "input_code_unit": pair.hex(),
                "input_code_unit_sha256": hashlib.sha256(pair).hexdigest(),
                "map_base": hex32(regs["r2"]),
                "scan_index": regs["r3"],
            }
            event.update({"kind": "map_lookup_scan", **self._last_lookup})
        elif pc in (MAP_LOOKUP_MATCH, MAP_LOOKUP_FALLBACK):
            receipt = {
                "kind": "map_lookup_match" if pc == MAP_LOOKUP_MATCH else "map_lookup_fallback",
                "lookup_instruction": hex32(pc),
                # At 0x080992f6 the ``adds r0,r3,#0`` has not executed yet;
                # r3 is the matched map index.  The fallback instruction is
                # likewise stopped before ``movs r0,#0x40``.
                "glyph_index": regs["r3"] if pc == MAP_LOOKUP_MATCH else 0x40,
                "map_entry_pointer": hex32(regs["r2"]),
                "map_index": regs["r3"],
                "input": self._last_lookup,
                "semantic_name_assigned": False,
            }
            event.update(receipt)
            if len(self.lookup_receipts) < self.max_records:
                self.lookup_receipts.append(receipt)
        elif pc == GLYPH_FIELD_WRITE:
            field = regs["r4"]
            receipt = {
                "kind": "glyph_field_write",
                "field_address": hex32(field),
                "object_base_if_layout": hex32(field - 0x4A),
                "field_offset": "0x4a",
                "glyph_index": regs["r0"],
                "input_lookup": self._last_lookup,
                "semantic_name_assigned": False,
            }
            event.update(receipt)
            if len(self.glyph_field_receipts) < self.max_records:
                self.glyph_field_receipts.append(receipt)
                if len(self.glyph_field_receipts) >= self.max_records:
                    self._remove_detail_breakpoints()
        elif pc == GLYPH_FIELD_READ:
            event.update({
                "kind": "glyph_field_read",
                "field_address": hex32(regs["r5"]),
                "object_base_if_layout": hex32(regs["r5"] - 0x4A),
                "glyph_index": regs["r0"],
            })
        elif pc == COMPOSER_ENTRY:
            event.update({
                "kind": "bitmap_composer_entry",
                "glyph_index": regs["r0"],
                "object_or_destination_context": hex32(regs["r1"]),
            })
        elif pc == COMPOSER_CALL:
            receipt = {
                "kind": "bitmap_composer_call",
                "call_instruction": hex32(COMPOSER_CALL),
                "target": hex32(RENDERER_ENTRY),
                "source_register_r0": hex32(regs["r0"]),
                "destination_register_r1": hex32(regs["r1"]),
                "tile_offset_register_r2": hex32(regs["r2"]),
                "source_hash_window": _summary(self.client, regs["r0"], 0x40),
                "destination_before_hash_window": _summary(self.client, regs["r1"], 0x40),
            }
            event.update(receipt)
            if len(self.composer_receipts) < self.max_records:
                self.composer_receipts.append(receipt)
        elif pc == RENDERER_ENTRY:
            receipt = {
                "kind": "renderer_entry",
                "source_register_r0": hex32(regs["r0"]),
                "destination_register_r1": hex32(regs["r1"]),
                "tile_offset_register_r2": hex32(regs["r2"]),
                "source_hash_window": _summary(self.client, regs["r0"], 0x40),
                "destination_before_hash_window": _summary(self.client, regs["r1"], 0x40),
            }
            event.update(receipt)
            if len(self.renderer_entries) < self.max_records:
                self.renderer_entries.append(receipt)
        elif pc == RENDERER_KERNEL:
            receipt = {
                "kind": "renderer_kernel_entry",
                "source_register_r0": hex32(regs["r0"]),
                "destination_base_register_r1": hex32(regs["r1"]),
                "tile_offset_register_r2": hex32(regs["r2"]),
                "source_hash_window": _summary(self.client, regs["r0"], 0x40),
                "destination_base_before_hash_window": _summary(self.client, regs["r1"], 0x40),
            }
            event.update(receipt)
            self._last_kernel = receipt
            if len(self.kernel_receipts) < self.max_records:
                self.kernel_receipts.append(receipt)
        elif pc == RENDERER_WRITE:
            destination = regs["r2"]
            before = _summary(self.client, destination, 4)
            step_stop = None
            after = None
            after_regs = None
            step_error = None
            try:
                step_stop = _step_until_stop(self.client)
                after_regs = _read_registers(self.client)
                after = _summary(self.client, destination, 4)
            except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
                step_error = type(exc).__name__
            receipt = {
                "kind": "renderer_cpu_write_receipt",
                "writer_instruction": hex32(RENDERER_WRITE),
                "writer_instruction_text": "str r1,[r2]",
                "writer_after_instruction": hex32(RENDERER_WRITE_AFTER),
                "writer_stop": None if step_stop is None else step_stop.split(";", 1)[0],
                "writer_stop_pc": None if after_regs is None else hex32(after_regs["pc"]),
                "source_register_r0": hex32(regs["r0"]),
                "value_register_r1": hex32(regs["r1"]),
                "destination_register_r2": hex32(destination),
                "byte_count": 4,
                "source_word_hash": _summary(self.client, regs["r0"], 4),
                "destination_before_hash": before,
                "destination_after_hash": after,
                "changed": bool(
                    before and after and before.get("sha256") != after.get("sha256")
                ),
                "step_error": step_error,
                "kernel_context": self._last_kernel,
            }
            event.update(receipt)
            if len(self.writer_receipts) < self.max_records:
                self.writer_receipts.append(receipt)
        else:
            event["kind"] = "other_breakpoint"

        self._save_event(event)
        return event

    def run_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = max(0.25, min(0.75, deadline - time.monotonic()))
            try:
                stop = _continue_until_stop(self.client, remaining)
            except TimeoutError:
                try:
                    stop = _interrupt_until_stop(self.client)
                except (ConnectionError, OSError, TimeoutError):
                    return
            self.handle_stop(stop)

    def press_button(
        self,
        button: str,
        *,
        hold_events: int,
        release_events: int,
        event_timeout: float,
    ) -> dict[str, object]:
        desired = NO_KEY & ~(1 << BUTTON_BITS[button])
        rows: list[dict[str, object]] = []
        total = hold_events + release_events
        deadline = time.monotonic() + max(5.0, event_timeout * total * 4)
        _request_ok(self.client, f"Z3,{KEYINPUT:x},2")
        try:
            while len(rows) < total and time.monotonic() < deadline:
                stop = _continue_until_stop(self.client, event_timeout)
                kind, address = parse_stop_watch(stop)
                if address != KEYINPUT:
                    self.handle_stop(stop)
                    continue
                regs = _read_registers(self.client)
                value = desired if len(rows) < hold_events else NO_KEY
                _request_ok(self.client, f"P1={(value & 0xFFFFFFFF).to_bytes(4, 'little').hex()}")
                rows.append({
                    "sequence_index": len(rows),
                    "stop_kind": kind,
                    "stop_address": hex32(KEYINPUT),
                    "requested_keyinput": hex32(value),
                    "registers": snapshot(regs),
                })
        except TimeoutError:
            pass
        finally:
            try:
                _request_ok(self.client, f"z3,{KEYINPUT:x},2")
            except (ConnectionError, OSError, RuntimeError, TimeoutError):
                pass
        return {
            "button": button,
            "hold_events": hold_events,
            "release_events": release_events,
            "key_event_count": len(rows),
            "key_events": rows,
        }


def _route_report(args: argparse.Namespace, rom: bytes, sequence: list[str]) -> dict[str, object]:
    client = GdbClient(port=args.port, timeout=args.gdb_timeout, packet_delay=args.packet_delay)
    trace = GlyphSinkTrace(client, rom, max_records=args.max_records, max_events=args.max_events)
    runtime: dict[str, object] = {
        "single_gdb_connection": True,
        "fresh_mgba_expected": True,
        "port": args.port,
        "source_port": args.source_port,
        "breakpoints": [hex32(address) for address in BREAKPOINTS],
        "events": [],
        "loader_records": [],
        "consumer_reads": [],
        "lookup_receipts": [],
        "glyph_field_receipts": [],
        "composer_receipts": [],
        "renderer_entries": [],
        "kernel_receipts": [],
        "writer_receipts": [],
    }
    started = time.monotonic()
    try:
        _connect(client, args.source_port)
        runtime["supported"] = client.request("qSupported:multiprocess+")
        runtime["initial_stop"] = client.request("?")
        runtime["initial_registers"] = snapshot(_read_registers(client))
        trace.install()
        trace.run_for(args.initial_seconds)
        steps: list[dict[str, object]] = []
        for index, button in enumerate(sequence):
            step = trace.press_button(
                button,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
            )
            step["step_index"] = index
            step["display_io"] = _display_io(client)
            step["writer_count"] = len(trace.writer_receipts)
            steps.append(step)
            trace.run_for(args.step_seconds)
        trace.run_for(args.final_seconds)
        runtime["steps"] = steps
        runtime["final_display_io"] = _display_io(client)
        runtime["watch_hit_count"] = trace.watch_hit_count
        runtime["hit_counts"] = trace.hit_counts
        runtime["events"] = trace.events
        runtime["loader_records"] = trace.loader_records
        runtime["consumer_reads"] = trace.consumer_reads
        runtime["lookup_receipts"] = trace.lookup_receipts
        runtime["glyph_field_receipts"] = trace.glyph_field_receipts
        runtime["composer_receipts"] = trace.composer_receipts
        runtime["renderer_entries"] = trace.renderer_entries
        runtime["kernel_receipts"] = trace.kernel_receipts
        runtime["writer_receipts"] = trace.writer_receipts
        runtime["glyph_sink_proof"] = bool(trace.writer_receipts)
    finally:
        try:
            trace.uninstall()
        finally:
            client.close()
    runtime["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return {
        "schema": "afej-m119-glyph-sink-v1",
        "rom": identity(args.rom),
        "route": {
            "name": args.route_name,
            "sequence": sequence,
            "natural_reachability": True,
            "controlled_actions": [],
            "input_model": "KEYINPUT active-low read watchpoint; only r1 KEYINPUT value is supplied",
            "time_window_seconds": {
                "initial": args.initial_seconds,
                "per_step": args.step_seconds,
                "final": args.final_seconds,
            },
        },
        "static": _static_gate(rom),
        "runtime": runtime,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--source-port", type=int)
    parser.add_argument("--route-name", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--initial-seconds", type=float, default=2.0)
    parser.add_argument("--step-seconds", type=float, default=0.8)
    parser.add_argument("--final-seconds", type=float, default=2.0)
    parser.add_argument("--event-timeout", type=float, default=1.0)
    parser.add_argument("--gdb-timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.05)
    parser.add_argument("--hold-events", type=int, default=6)
    parser.add_argument("--release-events", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=16)
    parser.add_argument("--max-events", type=int, default=512)
    args = parser.parse_args()
    if not 8 <= args.max_records <= 32:
        parser.error("max-records must be between 8 and 32")
    if not 64 <= args.max_events <= 2048:
        parser.error("max-events must be between 64 and 2048")
    sequence = parse_sequence(args.sequence)
    rom = args.rom.read_bytes()
    report = _route_report(args, rom, sequence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
