#!/usr/bin/env python3
"""Capture bounded natural FE6 caller and renderer receipts.

This is the M1.9 runtime layer for the reviewed Japanese AFEJ ROM.  It uses
only active-low KEYINPUT reads to navigate a fresh mGBA process; it never
writes a game state, selector, index, PC, or ROM.  A route report keeps hashes
and structural offsets, not raw ROM/RAM or decoded Japanese text.

The static part records direct ARM7TDMI Thumb BL callers of the two reviewed
non-selector candidate functions.  The runtime part stops at the candidate
callers, the loader, the EWRAM text consumer, and the renderer's CPU writer.
The writer receipt is dynamic: it follows the destination register at the
renderer kernel and records the pre/post hash plus DMA3 metadata.  The old
fixed ``0x06014000`` watchpoint is retained only as a comparison event; it is
not the renderer-discovery mechanism.

Reports belong under ignored ``games/.../work/`` or ``/private/tmp``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import summarize  # noqa: E402
from gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch  # noqa: E402
from trace_m18_callers import (  # noqa: E402
    BUFFER,
    BUFFER_SIZE,
    CALLER_INDEX_TABLE,
    COPY_WRAPPER,
    EXPECTED_GAME_CODE,
    EXPECTED_SHA256,
    HIGH_CALLER,
    HIGH_CALLSITE,
    KEYINPUT,
    LOADER_BL,
    LOADER_ENTRY,
    LOADER_RETURN,
    NO_KEY,
    POINTER_TABLE,
    POINTER_TABLE_END,
    RENDER_SINK,
    ROM_BASE,
    ROM_SIZE,
    WORKER,
    _capstone_instructions,
    _classify_index_source,
    _function_for_call,
    buffer_summary,
    display_io,
    display_state,
    hex32,
    identity,
    loader_caller_from_lr,
    prologue_addresses,
    return_addresses,
    scan_direct_calls,
    snapshot,
    table_provenance,
    thumb_bl_target,
    u16,
    u32,
)


# M1.8's two non-selector families.  0x080985ec is the direct loader BL;
# 0x08098624 is the other candidate function entry, whose loader BLs are the
# two addresses below.
CANDIDATE_CALLER = 0x080985D8
CANDIDATE_CALLER_ALT = 0x08098624
CANDIDATE_DIRECT_CALL = 0x080985EC
CANDIDATE_ALT_CALLS = (0x0809867A, 0x08098694)

# The requested M1.9 hit-count addresses are kept as named counters even when
# a route is negative.  Function-entry hits and direct-call hits are separate
# so a candidate function entry cannot be mistaken for a loader callsite.
HIT_ADDRESSES = (
    CANDIDATE_DIRECT_CALL,
    CANDIDATE_CALLER_ALT,
    HIGH_CALLSITE,
    LOADER_ENTRY,
)
CANDIDATE_ENTRIES = (CANDIDATE_CALLER, CANDIDATE_CALLER_ALT, HIGH_CALLER)

# Consumer/renderer addresses established by the earlier M1 baseline.  The
# 0x080995a6 instruction is ``str r1,[r2]`` in this ARM7TDMI Thumb image.
CONSUMER_ENTRY = 0x08098C00
CONSUMER_BYTE_READ = 0x08098C24
CONSUMER_CONTROL_BRANCH = 0x08098C78
GLYPH_READER_ENTRY = 0x08098F68
GLYPH_FIELD_READ = 0x08098F78
COMPOSER_ENTRY = 0x08099424
COMPOSER_CALL = 0x08099460
RENDERER_ENTRY = 0x080995B0
RENDERER_KERNEL = 0x08099580
RENDERER_WRITE = 0x080995A6

DMA3_SOURCE = 0x040000D4
DMA3_CONTROL = 0x040000DE

EWRAM_START = 0x02000000
EWRAM_END = 0x02040000
IWRAM_START = 0x03000000
IWRAM_END = 0x03008000
VRAM_START = 0x06000000
VRAM_END = 0x06018000

BUTTON_BITS = {
    "a": 0,
    "b": 1,
    "select": 2,
    "start": 3,
    "right": 4,
    "left": 5,
    "up": 6,
    "down": 7,
    "r": 8,
    "l": 9,
}


def _direct_call_rows(rom: bytes, target: int) -> list[dict[str, object]]:
    """Return direct BL rows with conservative caller and disassembly data."""

    prologues = prologue_addresses(rom)
    returns = return_addresses(rom, ROM_BASE, ROM_BASE + len(rom))
    rows: list[dict[str, object]] = []
    for callsite in scan_direct_calls(rom, target):
        context_rows = _capstone_instructions(rom, callsite - 0x20, callsite + 4)
        context = [
            f"{hex32(int(row['address']))}: {row['mnemonic']} {row['op_str']}".rstrip()
            for row in context_rows
        ]
        row: dict[str, object] = {
            "callsite": hex32(callsite),
            "target": hex32(thumb_bl_target(u16(rom, callsite), u16(rom, callsite + 2), callsite)),
            "halfwords": [hex(u16(rom, callsite)), hex(u16(rom, callsite + 2))],
            "index_source": _classify_index_source(context),
            "index_source_disassembly": context,
        }
        row.update(_function_for_call(callsite, prologues, returns))
        rows.append(row)
    return rows


def static_candidate_report(rom: bytes) -> dict[str, object]:
    """Enumerate the candidate functions and one layer of their direct callers."""

    targets = {
        hex32(CANDIDATE_CALLER): _direct_call_rows(rom, CANDIDATE_CALLER),
        hex32(CANDIDATE_CALLER_ALT): _direct_call_rows(rom, CANDIDATE_CALLER_ALT),
        hex32(HIGH_CALLER): _direct_call_rows(rom, HIGH_CALLER),
    }
    return {
        "encoding": "ARM7TDMI two-halfword Thumb BL",
        "candidate_functions": {
            hex32(CANDIDATE_CALLER): {
                "role": "non_selector_loader_caller_candidate",
                "direct_loader_callsite": hex32(CANDIDATE_DIRECT_CALL),
                "direct_callers": targets[hex32(CANDIDATE_CALLER)],
            },
            hex32(CANDIDATE_CALLER_ALT): {
                "role": "alternate_non_selector_loader_caller_candidate",
                "direct_loader_callsites": [hex32(value) for value in CANDIDATE_ALT_CALLS],
                "direct_callers": targets[hex32(CANDIDATE_CALLER_ALT)],
            },
            hex32(HIGH_CALLER): {
                "role": "known_selector_caller_reference",
                "direct_loader_callsite": hex32(HIGH_CALLSITE),
                "direct_callers": targets[hex32(HIGH_CALLER)],
                "selector_table": hex32(CALLER_INDEX_TABLE),
            },
        },
        "direct_loader_callsite_count": len(scan_direct_calls(rom, LOADER_ENTRY)),
        "next_trigger_gate": {
            "natural_candidate_callsites": [
                hex32(CANDIDATE_DIRECT_CALL),
                *[hex32(value) for value in CANDIDATE_ALT_CALLS],
            ],
            "selector_reference": hex32(HIGH_CALLSITE),
            "no_state_or_index_write": True,
        },
    }


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


def _read_summary(client: GdbClient, address: int, length: int) -> Optional[dict[str, object]]:
    if not _valid_region(address, length):
        return None
    try:
        return summarize(read_memory_after_stop(client, address, length), address)
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
        return None


def _dma3_receipt(client: GdbClient) -> dict[str, object]:
    """Record DMA3 register metadata without preserving the register bytes."""

    try:
        source = read_memory_after_stop(client, DMA3_SOURCE, 12)
        control = read_memory_after_stop(client, DMA3_CONTROL, 2)
    except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
        return {"read_error": type(exc).__name__}
    src = int.from_bytes(source[0:4], "little")
    dst = int.from_bytes(source[4:8], "little")
    count = int.from_bytes(source[8:10], "little")
    control_value = int.from_bytes(control, "little")
    return {
        "register_block": summarize(source + control, DMA3_SOURCE),
        "source_register": hex32(src),
        "destination_register": hex32(dst),
        "count_register": hex32(count),
        "control": hex32(control_value),
        "active": bool(control_value & 0x8000),
    }


def read_registers_after_stop(client: GdbClient) -> dict[str, int]:
    """Read registers while tolerating mGBA's duplicate watch-stop reply.

    With a read watchpoint, the reviewed mGBA build can return the same
    ``T05rwatch`` stop packet once more in response to the first ``g`` query.
    Drain at most two such packets; an unbounded retry would hide a broken
    connection or turn a runtime receipt into an implicit wait loop.
    """

    expected_length = len(REG_NAMES) * 8
    for _ in range(5):
        response = client.request("g")
        if response.startswith(("T", "S")):
            continue
        if len(response) != expected_length:
            continue
        values = [
            int.from_bytes(bytes.fromhex(response[index:index + 8]), "little")
            for index in range(0, len(response), 8)
        ]
        if len(values) != len(REG_NAMES):
            raise RuntimeError(f"expected {len(REG_NAMES)} registers, got {len(values)}")
        return dict(zip(REG_NAMES, values))
    raise RuntimeError("mGBA returned no complete register response")


def request_ok_after_stop(client: GdbClient, payload: str) -> str:
    """Send a point-management request while draining one stale GDB reply."""

    expected_register_length = len(REG_NAMES) * 8
    for _ in range(5):
        response = client.request(payload)
        if response == "OK":
            return response
        if response.startswith(("T", "S")) or len(response) == expected_register_length:
            continue
        raise RuntimeError(f"unexpected GDB response for {payload!r}: {response!r}")
    raise RuntimeError(f"no OK response for {payload!r}")


def write_register_after_stop(client: GdbClient, register_number: int, value: int) -> None:
    raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
    request_ok_after_stop(client, f"P{register_number:x}={raw}")


def read_memory_after_stop(client: GdbClient, address: int, length: int) -> bytes:
    """Read one bounded memory block while ignoring stale non-memory replies."""

    output = bytearray()
    for offset in range(0, length, 0x200):
        chunk_length = min(0x200, length - offset)
        chunk_address = address + offset
        for _ in range(5):
            response = client.request(f"m{chunk_address:x},{chunk_length:x}")
            if response.startswith(("T", "S")) or response == "OK":
                continue
            if response.startswith("E"):
                raise RuntimeError(f"memory read failed at 0x{chunk_address:x}: {response}")
            try:
                data = bytes.fromhex(response)
            except ValueError:
                continue
            if len(data) == chunk_length:
                output.extend(data)
                break
        else:
            raise RuntimeError(f"no {chunk_length}-byte memory response at 0x{chunk_address:x}")
    return bytes(output)


def display_io_after_stop(client: GdbClient) -> dict[str, str]:
    values = {
        name: int.from_bytes(read_memory_after_stop(client, address, 2), "little")
        for name, address in {
            "DISPCNT": 0x04000000,
            "BG0CNT": 0x04000008,
            "BG1CNT": 0x0400000A,
            "BG2CNT": 0x0400000C,
            "BG3CNT": 0x0400000E,
        }.items()
    }
    return {name: hex32(value) for name, value in values.items()}


def display_state_after_stop(client: GdbClient) -> dict[str, object]:
    vram = read_memory_after_stop(client, 0x06000000, 0x18000)
    return {"io": display_io_after_stop(client), "vram": summarize(vram, 0x06000000)}


def connect_client(client: GdbClient, source_port: Optional[int]) -> None:
    """Connect one client, optionally using a deterministic loopback source port."""

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


class NaturalTrace:
    """One fresh mGBA session; all route events share one GDB connection."""

    def __init__(
        self,
        client: GdbClient,
        rom: bytes,
        static: dict[str, object],
        *,
        max_records: int,
        max_consumer_reads: int,
        max_writer_receipts: int,
        watch_fixed_sink: bool,
    ) -> None:
        self.client = client
        self.rom = rom
        self.static = static
        self.max_records = max_records
        self.max_consumer_reads = max_consumer_reads
        self.max_writer_receipts = max_writer_receipts
        self.watch_fixed_sink = watch_fixed_sink
        self.events: list[dict[str, object]] = []
        self.loader_records: list[dict[str, object]] = []
        self.consumer_reads: list[dict[str, object]] = []
        self.renderer_events: list[dict[str, object]] = []
        self.writer_receipts: list[dict[str, object]] = []
        self.caller_hits: list[dict[str, object]] = []
        self.hit_counts = {hex32(address): 0 for address in HIT_ADDRESSES}
        self.entry_hit_counts = {hex32(address): 0 for address in CANDIDATE_ENTRIES}
        self._last_loader: Optional[dict[str, object]] = None
        self._last_kernel: Optional[dict[str, object]] = None
        self._last_writer: Optional[dict[str, object]] = None
        self._ewram_watch_armed = False
        self._ewram_watch_eligible = False
        self._dynamic_watch: Optional[tuple[int, int, int]] = None
        self._fixed_watch_armed = False
        self._writer_breakpoint_active = True
        self._breakpoints: list[int] = []
        self.key_events: list[dict[str, object]] = []

    @property
    def runtime_breakpoints(self) -> tuple[int, ...]:
        return (
            *CANDIDATE_ENTRIES,
            CANDIDATE_DIRECT_CALL,
            *CANDIDATE_ALT_CALLS,
            HIGH_CALLSITE,
            LOADER_ENTRY,
            LOADER_BL,
            LOADER_RETURN,
            CONSUMER_ENTRY,
            CONSUMER_BYTE_READ,
            CONSUMER_CONTROL_BRANCH,
            GLYPH_READER_ENTRY,
            GLYPH_FIELD_READ,
            COMPOSER_ENTRY,
            COMPOSER_CALL,
            RENDERER_ENTRY,
            RENDERER_KERNEL,
            RENDERER_WRITE,
        )

    def install(self) -> None:
        for address in dict.fromkeys(self.runtime_breakpoints):
            request_ok_after_stop(self.client, f"Z1,{address:x},2")
            self._breakpoints.append(address)
        if self.watch_fixed_sink:
            try:
                request_ok_after_stop(self.client, f"Z2,{RENDER_SINK:x},4")
                self._fixed_watch_armed = True
            except (ConnectionError, OSError, RuntimeError):
                self._fixed_watch_armed = False

    def uninstall(self) -> None:
        self._remove_ewram_watch()
        self._remove_dynamic_watch()
        if self._fixed_watch_armed:
            try:
                request_ok_after_stop(self.client, f"z2,{RENDER_SINK:x},4")
            except (ConnectionError, OSError, RuntimeError):
                pass
            self._fixed_watch_armed = False
        for address in reversed(self._breakpoints):
            try:
                request_ok_after_stop(self.client, f"z1,{address:x},2")
            except (ConnectionError, OSError, RuntimeError):
                pass

    def _remove_ewram_watch(self) -> None:
        if not self._ewram_watch_armed:
            return
        try:
            request_ok_after_stop(self.client, f"z3,{BUFFER:x},1")
        except (ConnectionError, OSError, RuntimeError):
            pass
        self._ewram_watch_armed = False

    def _arm_ewram_watch(self) -> None:
        if self._ewram_watch_armed or len(self.consumer_reads) >= self.max_consumer_reads:
            return
        try:
            request_ok_after_stop(self.client, f"Z3,{BUFFER:x},1")
        except (ConnectionError, OSError, RuntimeError):
            return
        self._ewram_watch_armed = True

    def _remove_dynamic_watch(self) -> None:
        if self._dynamic_watch is None:
            return
        address, kind, watch_type = self._dynamic_watch
        try:
            request_ok_after_stop(self.client, f"z{watch_type},{address:x},{kind:x}")
        except (ConnectionError, OSError, RuntimeError):
            pass
        self._dynamic_watch = None

    def _arm_dynamic_watch(self, address: int) -> Optional[str]:
        self._remove_dynamic_watch()
        if not _valid_region(address, 4):
            return "destination_outside_traced_GBA_RAM_regions"
        try:
            request_ok_after_stop(self.client, f"Z2,{address:x},4")
        except (ConnectionError, OSError, RuntimeError) as exc:
            return f"watchpoint_error:{type(exc).__name__}"
        self._dynamic_watch = (address, 4, 2)
        return None

    def _callsite_row(self, callsite: Optional[int]) -> Optional[dict[str, object]]:
        return None if callsite is None else {"callsite": hex32(callsite)}

    def _record(self, event: dict[str, object]) -> None:
        if len(self.events) < 512:
            self.events.append(event)

    def _base_event(self, stop: str, kind: Optional[str], address: Optional[int], regs: dict[str, int]) -> dict[str, object]:
        return {
            "stop": stop,
            "stop_kind": kind,
            "stop_address": None if address is None else hex32(address),
            "pc": hex32(regs["pc"]),
            "registers": snapshot(regs),
        }

    def _source_hash(self, source: int) -> Optional[dict[str, object]]:
        # A bounded hash window proves that the runtime source pointer was
        # actually read, without emitting any source bytes to the report.
        return _read_summary(self.client, source, 0x100) if source else None

    def _record_loader_return(self, buffer: dict[str, object]) -> None:
        prior = self._last_loader
        self._ewram_watch_eligible = True
        if prior is None or len(self.loader_records) >= self.max_records:
            self._arm_ewram_watch()
            return
        index = prior.get("loader_index")
        self.loader_records.append({
            "string_id": f"afej.loader.index.{index}",
            "reachability": "natural_keyinput",
            "caller_lr": prior.get("caller_lr"),
            "caller_callsite": prior.get("derived_callsite"),
            "caller_function": prior.get("caller_function"),
            "loader_index": index,
            "provenance": prior.get("provenance"),
            "source_pointer": prior.get("source_pointer"),
            "source_hash_window": prior.get("source_hash_window"),
            "destination": prior.get("destination"),
            "buffer": buffer,
        })
        self._arm_ewram_watch()

    def _handle_consumer(self, pc: int, regs: dict[str, int], event: dict[str, object]) -> None:
        if pc == CONSUMER_BYTE_READ and len(self.consumer_reads) < self.max_consumer_reads:
            pointer = regs.get("r6", BUFFER)
            try:
                value = read_memory_after_stop(self.client, pointer, 1)[0]
            except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
                value = None
            event.update({
                "consumer": "text_byte_read",
                "buffer_pointer_register": hex32(pointer),
                "byte_value": None if value is None else hex32(value),
                "token_class": None if value is None else (
                    "opaque_0x01" if value == 0x01 else "opaque_byte"
                ),
            })
            if value is not None:
                event["buffer_offset_if_base"] = (
                    pointer - BUFFER if BUFFER <= pointer < BUFFER + BUFFER_SIZE else None
                )
            self.consumer_reads.append(event.copy())
            if len(self.consumer_reads) >= self.max_consumer_reads:
                self._remove_ewram_watch()
        elif pc == CONSUMER_CONTROL_BRANCH:
            event["consumer"] = "control_branch_unclassified"
            event["control_value_register_r0"] = hex32(regs["r0"])
            if len(self.consumer_reads) < self.max_consumer_reads:
                self.consumer_reads.append(event.copy())
        elif pc in (CONSUMER_ENTRY, GLYPH_READER_ENTRY, GLYPH_FIELD_READ):
            event["consumer"] = {
                CONSUMER_ENTRY: "text_consumer_entry",
                GLYPH_READER_ENTRY: "glyph_reader_entry",
                GLYPH_FIELD_READ: "glyph_field_read",
            }[pc]
            if pc == GLYPH_FIELD_READ:
                event["glyph_field_address"] = hex32(regs["r5"])
            if len(self.consumer_reads) < self.max_consumer_reads:
                self.consumer_reads.append(event.copy())

    def _handle_renderer(self, pc: int, regs: dict[str, int], event: dict[str, object]) -> None:
        if pc == COMPOSER_ENTRY:
            event.update({
                "renderer": "bitmap_composer_entry",
                "source_register_r0": hex32(regs["r0"]),
                "destination_base_register_r1": hex32(regs["r1"]),
                "tile_offset_register_r2": hex32(regs["r2"]),
                "source_hash_window": _read_summary(self.client, regs["r0"], 0x40),
                "destination_base_hash_window": _read_summary(self.client, regs["r1"], 0x40),
            })
        elif pc == COMPOSER_CALL:
            event["renderer"] = "bitmap_composer_call"
        elif pc == RENDERER_ENTRY:
            event.update({
                "renderer": "renderer_entry",
                "source_register_r0": hex32(regs["r0"]),
                "destination_register_r1": hex32(regs["r1"]),
                "destination_register_r2": hex32(regs["r2"]),
            })
        elif pc == RENDERER_KERNEL:
            destination = regs["r2"]
            event.update({
                "renderer": "cpu_word_kernel_entry",
                "source_register_r0": hex32(regs["r0"]),
                "value_register_r1": hex32(regs["r1"]),
                "destination_register_r2": hex32(destination),
                "source_hash_window": _read_summary(self.client, regs["r0"], 0x40),
                "destination_before_hash": _read_summary(self.client, destination, 4),
                "dma3": _dma3_receipt(self.client),
            })
            self._last_kernel = event.copy()
            if len(self.writer_receipts) < self.max_writer_receipts:
                event["dynamic_watch_error"] = self._arm_dynamic_watch(destination)
        elif pc == RENDERER_WRITE:
            event.update({
                "renderer": "cpu_thumb_str32_before_write",
                "writer_instruction": "str r1, [r2]",
                "source_register_r1": hex32(regs["r1"]),
                "destination_register_r2": hex32(regs["r2"]),
                "byte_count": 4,
                "destination_before_hash": _read_summary(self.client, regs["r2"], 4),
                "dma3": _dma3_receipt(self.client),
            })
            self._last_writer = event.copy()
        self.renderer_events.append(event.copy())

    def _handle_write_watch(self, stop: str, address: int, regs: dict[str, int], event: dict[str, object]) -> None:
        dynamic = self._dynamic_watch is not None and address == self._dynamic_watch[0]
        fixed = address == RENDER_SINK
        if not (dynamic or fixed):
            return
        event.update({
            "renderer": "dynamic_vram_or_ram_write_watch" if dynamic else "fixed_sink_comparison_watch",
            "watch_destination": hex32(address),
            "byte_count": 4,
            "writer_pc_after_access": hex32(regs["pc"]),
            "destination_after_hash": _read_summary(self.client, address, 4),
            "value_register_r1": hex32(regs["r1"]),
            "destination_register_r2": hex32(regs["r2"]),
            "dma3": _dma3_receipt(self.client),
        })
        if dynamic and len(self.writer_receipts) < self.max_writer_receipts:
            event["writer_kind"] = "CPU ARM7TDMI Thumb str r1,[r2]"
            event["source_hash_window"] = None if self._last_kernel is None else self._last_kernel.get("source_hash_window")
            event["renderer_kernel"] = None if self._last_kernel is None else self._last_kernel.get("pc")
            self.writer_receipts.append(event.copy())
            self._remove_dynamic_watch()
        self.renderer_events.append(event.copy())

    def handle_stop(self, stop: str) -> dict[str, object]:
        stop_kind, stop_address = parse_stop_watch(stop)
        regs = read_registers_after_stop(self.client)
        pc = regs["pc"] & 0xFFFFFFFF
        event = self._base_event(stop, stop_kind, stop_address, regs)

        for address in HIT_ADDRESSES:
            if pc == address:
                self.hit_counts[hex32(address)] += 1
        for address in CANDIDATE_ENTRIES:
            if pc == address:
                self.entry_hit_counts[hex32(address)] += 1

        if stop_address is not None:
            self._handle_write_watch(stop, stop_address, regs, event)
            if stop_address == BUFFER:
                event.update({
                    "kind": "ewram_text_buffer_read_watch",
                    "buffer": hex32(BUFFER),
                    "read_pc": hex32(pc),
                })
                self._handle_consumer(pc, regs, event)
                self._record(event)
                return event
            if stop_address == KEYINPUT:
                event["kind"] = "keyinput_poll"
                self._record(event)
                return event

        if pc in CANDIDATE_ENTRIES:
            event.update({
                "kind": "candidate_function_entry",
                "candidate_function": hex32(pc),
                "caller_lr": hex32(regs["lr"]),
                "argument_registers": {
                    "r0": hex32(regs["r0"]),
                    "r1": hex32(regs["r1"]),
                    "r2": hex32(regs["r2"]),
                },
            })
            self.caller_hits.append(event.copy())
        elif pc in (CANDIDATE_DIRECT_CALL, *CANDIDATE_ALT_CALLS, HIGH_CALLSITE):
            event.update({
                "kind": "natural_direct_loader_callsite",
                "callsite": hex32(pc),
                "caller_lr": hex32(regs["lr"]),
                "loader_index_argument": regs["r0"],
                "provenance": table_provenance(self.rom, regs["r0"]),
            })
            self.caller_hits.append(event.copy())
        elif pc == LOADER_ENTRY:
            index = regs["r0"]
            callsite = loader_caller_from_lr(regs["lr"])
            event.update({
                "kind": "natural_loader_entry",
                "loader_index": index,
                "caller_lr": hex32(regs["lr"]),
                "derived_callsite": callsite,
                "caller_function": (
                    hex32(CANDIDATE_CALLER)
                    if callsite == hex32(CANDIDATE_DIRECT_CALL)
                    else hex32(CANDIDATE_CALLER_ALT)
                    if callsite in {hex32(value) for value in CANDIDATE_ALT_CALLS}
                    else hex32(HIGH_CALLER)
                    if callsite == hex32(HIGH_CALLSITE)
                    else "unknown"
                ),
                "provenance": table_provenance(self.rom, index),
            })
            self._last_loader = event.copy()
        elif pc == LOADER_BL:
            index = None
            try:
                index = int.from_bytes(read_memory_after_stop(self.client, regs["r7"], 4), "little")
            except (ConnectionError, OSError, RuntimeError, TimeoutError, ValueError):
                pass
            if index is None and self._last_loader is not None:
                index = self._last_loader.get("loader_index")
            source = regs["r0"]
            event.update({
                "kind": "natural_loader_copy_callsite",
                "loader_index": index,
                "copy_wrapper": hex32(COPY_WRAPPER),
                "worker": hex32(WORKER),
                "copy_wrapper_lr": hex32(regs["lr"]),
                "source_pointer": hex32(source),
                "destination": hex32(regs["r1"]),
                "source_hash_window": self._source_hash(source),
                "provenance": table_provenance(self.rom, index) if isinstance(index, int) else None,
            })
            if self._last_loader is not None:
                self._last_loader.update({
                    "loader_index": index,
                    "source_pointer": hex32(source),
                    "destination": hex32(regs["r1"]),
                    "source_hash_window": event.get("source_hash_window"),
                })
        elif pc == LOADER_RETURN:
            event.update({
                "kind": "natural_loader_return",
                "buffer": buffer_summary(read_memory_after_stop(self.client, BUFFER, BUFFER_SIZE)),
            })
            self._record_loader_return(event["buffer"])
        elif pc in (CONSUMER_ENTRY, CONSUMER_BYTE_READ, CONSUMER_CONTROL_BRANCH, GLYPH_READER_ENTRY, GLYPH_FIELD_READ):
            event["kind"] = "natural_text_consumer"
            self._handle_consumer(pc, regs, event)
        elif pc in (COMPOSER_ENTRY, COMPOSER_CALL, RENDERER_ENTRY, RENDERER_KERNEL, RENDERER_WRITE):
            event["kind"] = "natural_renderer"
            self._handle_renderer(pc, regs, event)
        elif pc == LOADER_BL:
            event["kind"] = "natural_loader_copy_callsite"
        else:
            event["kind"] = "other_stop"

        self._record(event)
        return event

    def continue_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = max(0.25, min(0.75, deadline - time.monotonic()))
            try:
                stop = self.client.continue_until_stop(remaining)
            except TimeoutError:
                try:
                    stop = self.client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
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
        # mGBA can leave one watch-stop reply queued while the target is
        # stopped.  Do not keep the EWRAM read watchpoint active while the
        # separate KEYINPUT watchpoint is installed.
        self._remove_ewram_watch()
        request_ok_after_stop(self.client, f"Z3,{KEYINPUT:x},2")
        try:
            deadline = time.monotonic() + max(5.0, event_timeout * (hold_events + release_events) * 3)
            while len(rows) < hold_events + release_events and time.monotonic() < deadline:
                try:
                    stop = self.client.continue_until_stop(event_timeout)
                except TimeoutError:
                    try:
                        stop = self.client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        break
                kind, address = parse_stop_watch(stop)
                if address != KEYINPUT:
                    self.handle_stop(stop)
                    continue
                regs = read_registers_after_stop(self.client)
                value = desired if len(rows) < hold_events else NO_KEY
                write_register_after_stop(self.client, 1, value)
                row = {
                    "sequence_index": len(rows),
                    "stop_kind": kind,
                    "stop_address": hex32(KEYINPUT),
                    "requested_keyinput": hex32(value),
                    "registers": snapshot(regs),
                }
                rows.append(row)
                self.key_events.append(row)
        finally:
            try:
                request_ok_after_stop(self.client, f"z3,{KEYINPUT:x},2")
            except (ConnectionError, OSError, RuntimeError):
                pass
            if self._ewram_watch_eligible:
                self._arm_ewram_watch()
        return {
            "button": button,
            "hold_events": hold_events,
            "release_events": release_events,
            "key_event_count": len(rows),
            "key_events": rows,
        }


def parse_sequence(value: str) -> list[str]:
    sequence = [part.strip().lower() for part in value.split(",") if part.strip()]
    if not sequence or any(part not in BUTTON_BITS for part in sequence):
        raise ValueError(f"sequence must contain known buttons: {sorted(BUTTON_BITS)}")
    return sequence


def _route_report(
    *,
    args: argparse.Namespace,
    rom: bytes,
    route_name: str,
    sequence: list[str],
    static: dict[str, object],
) -> dict[str, object]:
    report: dict[str, object] = {
        "rom": {
            "game_code": rom[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "route": {
            "name": route_name,
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
        "static": static,
        "runtime": {},
    }
    client = GdbClient(port=args.port, timeout=args.gdb_timeout, packet_delay=args.packet_delay)
    trace = NaturalTrace(
        client,
        rom,
        static,
        max_records=args.max_records,
        max_consumer_reads=args.max_consumer_reads,
        max_writer_receipts=args.max_writer_receipts,
        watch_fixed_sink=not args.no_fixed_sink_watch,
    )
    started = time.monotonic()
    runtime: dict[str, object] = {
        "single_gdb_connection": True,
        "fresh_mgba_expected": True,
        "port": args.port,
        "source_port": args.source_port,
        "requested_hit_addresses": [hex32(address) for address in HIT_ADDRESSES],
        "candidate_entry_hit_addresses": [hex32(address) for address in CANDIDATE_ENTRIES],
        "renderer_addresses": {
            "consumer_entry": hex32(CONSUMER_ENTRY),
            "consumer_byte_read": hex32(CONSUMER_BYTE_READ),
            "consumer_control_branch": hex32(CONSUMER_CONTROL_BRANCH),
            "renderer_entry": hex32(RENDERER_ENTRY),
            "renderer_kernel": hex32(RENDERER_KERNEL),
            "renderer_write_instruction": hex32(RENDERER_WRITE),
            "fixed_sink_comparison": hex32(RENDER_SINK),
        },
        "events": [],
        "caller_hits": [],
        "loader_records": [],
        "consumer_reads": [],
        "renderer_events": [],
        "writer_receipts": [],
    }
    try:
        connect_client(client, args.source_port)
        runtime["supported"] = client.request("qSupported:multiprocess+")
        runtime["initial_stop"] = client.request("?")
        runtime["initial_registers"] = snapshot(read_registers_after_stop(client))
        trace.install()
        trace.continue_for(args.initial_seconds)
        route_steps: list[dict[str, object]] = []
        for step_index, button in enumerate(sequence):
            step = trace.press_button(
                button,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
            )
            before = len(trace.events)
            trace.continue_for(args.step_seconds)
            step_events = trace.events[before:]
            step.update({
                "step_index": step_index,
                "display_io": display_io_after_stop(client),
                "loader_record_count": len(trace.loader_records),
                "candidate_hit_count": {
                    hex32(CANDIDATE_DIRECT_CALL): trace.hit_counts[hex32(CANDIDATE_DIRECT_CALL)],
                    hex32(CANDIDATE_CALLER_ALT): trace.entry_hit_counts[hex32(CANDIDATE_CALLER_ALT)],
                },
                "renderer_event_count": len(step_events),
            })
            route_steps.append(step)
            if len(trace.loader_records) >= args.max_records:
                break
        trace.continue_for(args.final_seconds)
        runtime["steps"] = route_steps
        if args.no_display:
            runtime["final_display_io"] = display_io_after_stop(client)
        else:
            runtime["final_display"] = display_state_after_stop(client)
        runtime["hit_counts"] = trace.hit_counts
        runtime["candidate_entry_hit_counts"] = trace.entry_hit_counts
        runtime["caller_hits"] = trace.caller_hits
        runtime["loader_records"] = trace.loader_records
        runtime["consumer_reads"] = trace.consumer_reads
        runtime["renderer_events"] = trace.renderer_events
        runtime["writer_receipts"] = trace.writer_receipts
        runtime["events"] = trace.events
        runtime["natural_second_caller_hit"] = bool(
            trace.hit_counts[hex32(CANDIDATE_DIRECT_CALL)]
            or trace.entry_hit_counts[hex32(CANDIDATE_CALLER_ALT)]
        )
        runtime["renderer_writer_proof"] = bool(trace.writer_receipts)
    finally:
        try:
            trace.uninstall()
        finally:
            client.close()
    runtime["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["runtime"] = runtime
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument(
        "--source-port",
        type=int,
        help="optional fixed 127.0.0.1 source port for deterministic local GDB connects",
    )
    parser.add_argument("--route-name", required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--static-output", type=Path)
    parser.add_argument("--initial-seconds", type=float, default=3.0)
    parser.add_argument("--step-seconds", type=float, default=0.8)
    parser.add_argument("--final-seconds", type=float, default=1.5)
    parser.add_argument("--event-timeout", type=float, default=1.0)
    parser.add_argument("--gdb-timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.05)
    parser.add_argument("--hold-events", type=int, default=6)
    parser.add_argument("--release-events", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=32)
    parser.add_argument("--max-consumer-reads", type=int, default=32)
    parser.add_argument("--max-writer-receipts", type=int, default=32)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--no-fixed-sink-watch", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_records <= 32:
        parser.error("max-records must be between 1 and 32")
    if not 1 <= args.max_consumer_reads <= 64:
        parser.error("max-consumer-reads must be between 1 and 64")
    if not 1 <= args.max_writer_receipts <= 64:
        parser.error("max-writer-receipts must be between 1 and 64")
    sequence = parse_sequence(args.sequence)
    rom_identity = identity(args.rom)
    rom = args.rom.read_bytes()
    static = static_candidate_report(rom)
    if args.static_output is not None:
        args.static_output.parent.mkdir(parents=True, exist_ok=True)
        args.static_output.write_text(
            json.dumps({"rom": rom_identity, "static": static}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    report = _route_report(
        args=args,
        rom=rom,
        route_name=args.route_name,
        sequence=sequence,
        static=static,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
