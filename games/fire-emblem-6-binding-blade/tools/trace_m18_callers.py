#!/usr/bin/env python3
"""Enumerate and trace FE6 M1.8 text-loader callers.

This is a game-specific layer over ``core/gba/gdbstub_client.py``.  The
static part scans the reviewed AFEJ ROM for ARM7TDMI two-halfword Thumb BL
encodings whose target is the proven loader entry at ``0x08013ad0``.  It
groups those callsites by a conservative push/return function span and keeps
the nearby index-source disassembly as evidence.

The optional runtime part uses one private mGBA GDB session.  It records
caller/callsite, loader index, pointer-table provenance, EWRAM output hashes,
control-marker offsets, the known VRAM sink, and display-register/VRAM
summaries.  Natural navigation and an index overwritten at a confirmed
callsite are separate ``reachability`` values.  It never writes the ROM or
serializes raw ROM/RAM/full text; the JSON report belongs under ignored
``work/``.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Iterable, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from capture_runtime import summarize  # noqa: E402
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


ROM_BASE = 0x08000000
ROM_SIZE = 8 * 1024 * 1024
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)

POINTER_TABLE = 0x080F635C
POINTER_TABLE_END = 3342
CALLER_INDEX_TABLE = 0x08691738
BUFFER = 0x02029404
BUFFER_SIZE = 0x400
RENDER_SINK = 0x06014000

LOADER_ENTRY = 0x08013AD0
LOADER_BL = 0x08013B02
LOADER_RETURN = 0x08013B08
COPY_WRAPPER = 0x0800384C
WORKER = 0x0300323C
HIGH_CALLER = 0x08098AFC
HIGH_CALLSITE = 0x08098B10

KEYINPUT = 0x04000130
NO_KEY = 0x03FF
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

# Keep the runtime set deliberately small.  The static report covers every
# direct callsite; these groups are the best bounded non-selector candidates
# to try during natural navigation.
DEFAULT_RUNTIME_CALLSITES = (
    0x080985EC,  # argument/stack-derived index, caller 0x080985d8
    0x0809867A,  # runtime halfword-derived index, caller 0x08098624
    0x08098694,
    0x0808E7EC,  # generic multi-argument formatter/layout candidate
    0x080917E0,
    0x08092146,
    0x08095DB6,
    HIGH_CALLSITE,
)


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def u16(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset:offset + 2], "little")


def u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    return int.from_bytes(rom[offset:offset + 4], "little")


def is_rom_pointer(value: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + ROM_SIZE


def thumb_bl_target(first: int, second: int, address: int) -> int:
    """Decode an ARM7TDMI two-halfword Thumb BL pair.

    GBA Thumb BL is encoded as ``11110 S imm10`` followed by
    ``11111 imm11``.  This is the ARM7TDMI Thumb encoding; calling it a
    later-ARM Thumb instruction would incorrectly import a later-ARM
    architectural assumption into the provenance record.
    """

    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("not an ARM7TDMI Thumb BL pair")
    offset = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if offset & (1 << 22):
        offset -= 1 << 23
    return (address + 4 + offset) & 0xFFFFFFFF


def scan_direct_calls(rom: bytes, target: int = LOADER_ENTRY) -> list[int]:
    """Return all aligned ROM addresses of BL pairs targeting ``target``."""

    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    calls: list[int] = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        address = ROM_BASE + offset
        if thumb_bl_target(first, second, address) == target:
            calls.append(address)
    return calls


def is_prologue_halfword(value: int) -> bool:
    """Recognize Thumb PUSH forms that save LR."""

    return value & 0xFF00 == 0xB500


def is_return_halfword(value: int) -> bool:
    """Recognize conservative Thumb return forms."""

    # BX Rm, including BX LR and the common tail-call register returns.
    if value & 0xFF87 == 0x4700:
        return True
    # POP {...,PC}; bit 8 selects PC in the Thumb POP encoding.
    if value & 0xFF00 == 0xBD00 and value & 0x0100:
        return True
    # MOV PC, Rm (rare in this ROM, but a valid return/tail-call boundary).
    return value & 0xFF87 == 0x4687


def prologue_addresses(rom: bytes) -> list[int]:
    return [
        ROM_BASE + offset
        for offset in range(0, len(rom) - 1, 2)
        if is_prologue_halfword(int.from_bytes(rom[offset:offset + 2], "little"))
    ]


def return_addresses(rom: bytes, start: int, end: int) -> list[int]:
    start_offset = max(0, start - ROM_BASE)
    end_offset = min(len(rom) - 1, end - ROM_BASE)
    return [
        ROM_BASE + offset
        for offset in range(start_offset, end_offset, 2)
        if is_return_halfword(int.from_bytes(rom[offset:offset + 2], "little"))
    ]


def _capstone_instructions(rom: bytes, start: int, end: int) -> list[dict[str, object]]:
    """Disassemble a bounded window when Capstone is available.

    Static grouping does not depend on Capstone: the BL/prologue/return
    decoder above is the reproducible fallback.  Capstone only makes the
    committed tool's source evidence easier to audit locally.
    """

    try:
        from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
    except ImportError:
        return []
    offset = max(0, start - ROM_BASE)
    limit = min(len(rom), end - ROM_BASE)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    return [
        {
            "address": instruction.address,
            "mnemonic": instruction.mnemonic,
            "op_str": instruction.op_str,
        }
        for instruction in md.disasm(rom[offset:limit], ROM_BASE + offset)
    ]


def _instruction_text(rows: Iterable[dict[str, object]]) -> list[str]:
    return [
        f"{hex32(int(row['address']))}: {row['mnemonic']} {row['op_str']}".rstrip()
        for row in rows
    ]


def _classify_index_source(context: list[str]) -> str:
    joined = " ".join(context).lower()
    if "ldrh" in joined or "ldrsb" in joined or "ldrb" in joined:
        return "runtime_structure_or_table_halfword"
    if "ldr r0, [r7]" in joined or "ldr r0, [sp" in joined:
        return "caller_argument_or_stack_word"
    if "movs r0, #" in joined or "ldr r0, [pc" in joined:
        return "literal_or_rom_literal"
    if "ldr r0, [r" in joined:
        return "register_indirect_word"
    return "opaque_register_value"


def _function_for_call(
    callsite: int, prologues: list[int], returns: list[int]
) -> dict[str, object]:
    """Find a nearest push/return span without naming its semantics."""

    # A function in this ROM is small compared with the 8 MiB image.  Bound
    # the look-back so a random B5xx halfword in unrelated code/data cannot
    # become a fake owner of a callsite with no local prologue.
    lookback = callsite - 0x1000
    first_candidate = bisect.bisect_left(prologues, lookback)
    end_candidate = bisect.bisect_right(prologues, callsite)
    candidates = prologues[first_candidate:end_candidate]
    first_return = bisect.bisect_left(returns, lookback)
    end_return = bisect.bisect_left(returns, callsite)
    returns_before_call = returns[first_return:end_return]
    start: Optional[int] = None
    for candidate in reversed(candidates):
        if not any(candidate <= address < callsite for address in returns_before_call):
            start = candidate
            break
    if start is None and candidates:
        start = candidates[-1]

    if start is None:
        return {
            "function_start": None,
            "function_return": None,
            "function_boundary_confidence": "unknown_no_push_lr_before_call",
        }

    return_index = bisect.bisect_left(returns, callsite)
    function_return = (
        returns[return_index]
        if return_index < len(returns) and returns[return_index] < callsite + 0x1000
        else None
    )
    return {
        "function_start": hex32(start),
        "function_return": None if function_return is None else hex32(function_return),
        "function_boundary_confidence": "prologue_and_first_return"
        if function_return is not None
        else "prologue_no_return_within_bound",
    }


def static_callsite_records(rom: bytes) -> list[dict[str, object]]:
    """Build auditable records for every direct loader BL callsite."""

    calls = scan_direct_calls(rom)
    prologues = prologue_addresses(rom)
    returns = return_addresses(rom, ROM_BASE, ROM_BASE + len(rom))
    records: list[dict[str, object]] = []
    for callsite in calls:
        context_rows = _capstone_instructions(rom, callsite - 0x18, callsite + 4)
        context = _instruction_text(context_rows)
        row: dict[str, object] = {
            "callsite": hex32(callsite),
            "halfwords": [hex(u16(rom, callsite)), hex(u16(rom, callsite + 2))],
            "target": hex32(thumb_bl_target(u16(rom, callsite), u16(rom, callsite + 2), callsite)),
            "index_source": _classify_index_source(context),
            "index_source_disassembly": context,
        }
        row.update(_function_for_call(callsite, prologues, returns))
        records.append(row)
    return records


def group_static_calls(records: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = {}
    for record in records:
        key = record["function_start"] or "unknown"
        groups.setdefault(str(key), []).append(record)
    return groups


def table_provenance(rom: bytes, index: int) -> dict[str, object]:
    if not 0 <= index < POINTER_TABLE_END:
        return {"table_index": index, "within_proven_table": False}
    entry = POINTER_TABLE + index * 4
    source = u32(rom, entry)
    return {
        "table_index": index,
        "within_proven_table": is_rom_pointer(source),
        "table_entry": hex32(entry),
        "source_pointer": hex32(source),
    }


def buffer_summary(data: bytes) -> dict[str, object]:
    terminator = data.find(b"\x00")
    scan_end = len(data) if terminator < 0 else terminator + 1
    return {
        "address": hex32(BUFFER),
        "buffer_length": len(data),
        "buffer_sha256": hashlib.sha256(data).hexdigest(),
        "logical_terminator_offset": None if terminator < 0 else terminator,
        "control_marker_offsets": {
            f"0x{value:02x}": [
                index for index, byte in enumerate(data[:scan_end]) if byte == value
            ]
            for value in (0x00, 0x01, 0x04, 0xFF)
        },
    }


def identity(rom_path: Path) -> dict[str, object]:
    data = rom_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
    if len(data) != ROM_SIZE or game_code != EXPECTED_GAME_CODE or digest != EXPECTED_SHA256:
        raise ValueError(
            f"reviewed AFEJ identity mismatch: size={len(data)} game_code={game_code!r} sha256={digest}"
        )
    return {"size": len(data), "game_code": game_code, "sha256": digest}


def static_report(rom: bytes) -> dict[str, object]:
    records = static_callsite_records(rom)
    groups = group_static_calls(records)
    candidate = next(
        (record for record in records if record["callsite"] == hex32(0x080985EC)),
        None,
    )
    return {
        "target": hex32(LOADER_ENTRY),
        "encoding": "ARM7TDMI two-halfword Thumb BL",
        "direct_callsite_count": len(records),
        "direct_callsites": records,
        "caller_function_group_count": len(groups),
        "caller_groups": {
            key: {
                "callsite_count": len(value),
                "callsites": [row["callsite"] for row in value],
                "index_sources": sorted({str(row["index_source"]) for row in value}),
            }
            for key, value in sorted(groups.items())
        },
        "non_selector_candidate": candidate,
        "selector_reference": {
            "function_start": hex32(HIGH_CALLER),
            "callsite": hex32(HIGH_CALLSITE),
            "table": hex32(CALLER_INDEX_TABLE),
        },
    }


def snapshot(regs: dict[str, int]) -> dict[str, str]:
    names = {"pc", "lr", "sp", "cpsr", "r0", "r1", "r2", "r7"}
    return {name: hex32(value) for name, value in regs.items() if name in names}


def display_state(client: GdbClient) -> dict[str, object]:
    # This is the same bounded standard region used by core/gba capture.  It
    # is captured only at the end of a step, not on every KEYINPUT poll.
    io = display_io(client)
    vram = client.read_memory(0x06000000, 0x18000)
    summary = summarize(vram, 0x06000000)
    return {
        "io": io,
        "vram": summary,
    }


def display_io(client: GdbClient) -> dict[str, str]:
    """Read only display registers for fast per-step runtime receipts."""

    values = {
        name: int.from_bytes(client.read_memory(address, 2), "little")
        for name, address in {
            "DISPCNT": 0x04000000,
            "BG0CNT": 0x04000008,
            "BG1CNT": 0x0400000A,
            "BG2CNT": 0x0400000C,
            "BG3CNT": 0x0400000E,
        }.items()
    }
    return {name: hex32(value) for name, value in values.items()}


def loader_caller_from_lr(lr: int) -> Optional[str]:
    if not (lr & 1):
        return None
    return hex32((lr & ~1) - 4)


class RuntimeTrace:
    def __init__(
        self,
        client: GdbClient,
        rom: bytes,
        static: dict[str, object],
        callsites: Iterable[int],
        max_records: int,
        probe_index: Optional[int],
    ) -> None:
        self.client = client
        self.rom = rom
        self.static = static
        self.callsite_rows = {
            int(str(row["callsite"]), 16): row
            for row in static["direct_callsites"]  # type: ignore[index]
        }
        self.callsites = tuple(dict.fromkeys(callsites))
        self.max_records = max_records
        self.probe_index = probe_index
        self.events: list[dict[str, object]] = []
        self.loader_records: list[dict[str, object]] = []
        self.render_events: list[dict[str, object]] = []
        self._last_loader: Optional[dict[str, object]] = None
        self._reachability = "natural"

    def install(self, watch_renderer: bool) -> None:
        for address in (*self.callsites, LOADER_ENTRY, LOADER_BL, LOADER_RETURN):
            self.client.set_breakpoint(address)
        if watch_renderer:
            self.client.set_watchpoint(RENDER_SINK, kind=1, watch_type=2)

    def uninstall(self, watch_renderer: bool) -> None:
        if watch_renderer:
            try:
                self.client.remove_watchpoint(RENDER_SINK, kind=1, watch_type=2)
            except (ConnectionError, OSError, RuntimeError):
                pass
        for address in (*self.callsites, LOADER_ENTRY, LOADER_BL, LOADER_RETURN):
            try:
                self.client.remove_breakpoint(address)
            except (ConnectionError, OSError, RuntimeError):
                pass

    def _callsite_row(self, callsite: int) -> dict[str, object]:
        return self.callsite_rows.get(
            callsite,
            {
                "callsite": hex32(callsite),
                "function_start": None,
                "function_return": None,
                "index_source": "not-in-static-report",
            },
        )

    def handle_stop(self, stop: str) -> dict[str, object]:
        kind, address = parse_stop_watch(stop)
        regs = self.client.read_registers()
        pc = regs["pc"] & 0xFFFFFFFF
        row: dict[str, object] = {
            "stop": stop,
            "stop_kind": kind,
            "stop_address": None if address is None else hex32(address),
            "registers": snapshot(regs),
            "reachability": self._reachability,
        }

        if pc in self.callsites:
            callsite = pc
            if self.probe_index is not None and callsite == 0x080985EC:
                self.client.write_register(0, self.probe_index)
                self._reachability = "controlled"
                row["controlled_index_overwrite"] = self.probe_index
                row["reachability"] = "controlled"
            row.update({
                "kind": "direct_loader_callsite",
                "callsite": hex32(callsite),
                "caller_lr": hex32(regs["lr"]),
                "loader_index_argument": regs["r0"],
                "caller": self._callsite_row(callsite),
                "provenance": table_provenance(self.rom, regs["r0"]),
            })
        elif pc == LOADER_ENTRY:
            index = regs["r0"]
            callsite = loader_caller_from_lr(regs["lr"])
            row.update({
                "kind": "loader_entry",
                "loader_index": index,
                "caller_lr": hex32(regs["lr"]),
                "derived_callsite": callsite,
                "caller": self._callsite_row(int(callsite, 16)) if callsite else None,
                "provenance": table_provenance(self.rom, index),
            })
        elif pc == LOADER_BL:
            index: Optional[int] = None
            try:
                index = int.from_bytes(self.client.read_memory(regs["r7"], 4), "little")
            except (ConnectionError, OSError, RuntimeError):
                pass
            callsite = loader_caller_from_lr(regs["lr"])
            row.update({
                "kind": "loader_copy_callsite",
                "loader_index": index,
                "source_pointer": hex32(regs["r0"]),
                "destination": hex32(regs["r1"]),
                "worker": hex32(WORKER),
                "copy_wrapper": hex32(COPY_WRAPPER),
                "caller_lr": hex32(regs["lr"]),
                "derived_callsite": callsite,
                "caller": self._callsite_row(int(callsite, 16)) if callsite else None,
                "provenance": table_provenance(self.rom, index)
                if index is not None
                else None,
            })
            self._last_loader = row
        elif pc == LOADER_RETURN:
            row.update({"kind": "loader_return", **buffer_summary(
                self.client.read_memory(BUFFER, BUFFER_SIZE)
            )})
            if self._last_loader is not None and len(self.loader_records) < self.max_records:
                prior = self._last_loader
                index = prior.get("loader_index")
                self.loader_records.append({
                    "string_id": f"afej.loader.index.{index}",
                    "reachability": prior.get("reachability", self._reachability),
                    "caller_lr": prior.get("caller_lr"),
                    "caller_callsite": prior.get("derived_callsite"),
                    "caller": prior.get("caller"),
                    "loader_index": index,
                    "provenance": prior.get("provenance"),
                    "source_pointer": prior.get("source_pointer"),
                    "buffer": {key: value for key, value in row.items()
                               if key in {"address", "buffer_length", "buffer_sha256",
                                          "logical_terminator_offset", "control_marker_offsets"}},
                })
        elif address == RENDER_SINK:
            row.update({"kind": "renderer_vram_sink_write", "sink": hex32(RENDER_SINK)})
            self.render_events.append(row)
        elif address == BUFFER:
            row.update({"kind": "ewram_buffer_write_watch", "buffer": hex32(BUFFER)})
        else:
            row["kind"] = "other_stop"

        self.events.append(row)
        return row

    def continue_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                stop = self.client.continue_until_stop(min(0.5, max(0.25, deadline - time.monotonic())))
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
        key_events: list[dict[str, object]] = []
        self.client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
        try:
            deadline = time.monotonic() + max(5.0, event_timeout * (hold_events + release_events) * 2)
            while len(key_events) < hold_events + release_events and time.monotonic() < deadline:
                try:
                    stop = self.client.continue_until_stop(event_timeout)
                except TimeoutError:
                    try:
                        stop = self.client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        break
                stop_kind, stop_address = parse_stop_watch(stop)
                regs = self.client.read_registers()
                if stop_address != KEYINPUT:
                    self.handle_stop(stop)
                    continue
                index = len(key_events)
                value = desired if index < hold_events else NO_KEY
                self.client.write_register(1, value)
                key_events.append({
                    "index": index,
                    "stop": stop,
                    "stop_kind": stop_kind,
                    "stop_address": hex32(KEYINPUT),
                    "requested_keyinput": hex32(value),
                    "registers": snapshot(regs),
                })
        finally:
            self.client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
        return {
            "button": button,
            "hold_events": hold_events,
            "release_events": release_events,
            "key_event_count": len(key_events),
            "key_events": key_events,
        }


def parse_sequence(value: str) -> list[str]:
    sequence = [part.strip().lower() for part in value.split(",") if part.strip()]
    if not sequence or any(part not in BUTTON_BITS for part in sequence):
        raise ValueError(f"sequence must contain known buttons: {sorted(BUTTON_BITS)}")
    return sequence


def parse_callsites(value: str) -> list[int]:
    result = [int(part.strip(), 0) for part in value.split(",") if part.strip()]
    if not result:
        raise ValueError("at least one runtime callsite is required")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--static-output", type=Path)
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="write the full static callsite report without connecting to mGBA",
    )
    parser.add_argument("--sequence", default="start,a,a,a,a")
    parser.add_argument("--initial-seconds", type=float, default=3.0)
    parser.add_argument("--step-seconds", type=float, default=0.8)
    parser.add_argument(
        "--screen-every",
        type=int,
        default=1,
        help="capture full display/VRAM state every N steps; 0 captures only final state",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="skip full VRAM reads but retain per-step display-register summaries",
    )
    parser.add_argument("--event-timeout", type=float, default=1.0)
    parser.add_argument("--hold-events", type=int, default=6)
    parser.add_argument("--release-events", type=int, default=3)
    parser.add_argument("--max-records", type=int, default=32)
    parser.add_argument(
        "--runtime-callsites",
        default=",".join(hex(address) for address in DEFAULT_RUNTIME_CALLSITES),
    )
    parser.add_argument(
        "--probe-index",
        type=lambda value: int(value, 0),
        help="controlled replacement for r0 at the confirmed 0x080985ec callsite",
    )
    parser.add_argument(
        "--force-callsite",
        action="store_true",
        help="controlled probe: set PC to 0x080985ec before the bounded loader run",
    )
    parser.add_argument("--watch-renderer", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_records <= 32:
        parser.error("max-records must be between 1 and 32")
    sequence = parse_sequence(args.sequence)
    callsites = parse_callsites(args.runtime_callsites)
    if args.force_callsite and args.probe_index is None:
        parser.error("--force-callsite requires --probe-index")
    if args.force_callsite and 0x080985EC not in callsites:
        parser.error("--force-callsite requires 0x080985ec in --runtime-callsites")
    rom = args.rom.read_bytes()
    rom_identity = identity(args.rom)
    static = static_report(rom)
    if args.static_output is not None:
        args.static_output.parent.mkdir(parents=True, exist_ok=True)
        args.static_output.write_text(
            json.dumps(static, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.static_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(static, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
        return
    if args.port is None:
        parser.error("--port is required unless --static-only is used")

    report: dict[str, object] = {
        "rom": rom_identity,
        "static_summary": {
            key: static[key]
            for key in ("target", "encoding", "direct_callsite_count",
                        "caller_function_group_count", "selector_reference",
                        "non_selector_candidate")
        },
        "runtime": {
            "reachability_model": {"natural": "KEYINPUT active-low navigation",
                                    "controlled": "r0 overwrite only at confirmed 0x080985ec"},
            "port": args.port,
            "runtime_callsites": [hex32(address) for address in callsites],
            "sequence": sequence,
            "loader_breakpoints": [hex32(address) for address in
                                    (LOADER_ENTRY, LOADER_BL, LOADER_RETURN)],
            "renderer_sink": {"address": hex32(RENDER_SINK), "watch_enabled": args.watch_renderer},
            "controlled_probe": None if not args.force_callsite else {
                "callsite": hex32(0x080985EC),
                "index": args.probe_index,
                "reachability": "controlled",
            },
            "events": [],
            "loader_records": [],
            "renderer_events": [],
            "screens": [],
        },
    }

    client = GdbClient(port=args.port, timeout=8.0, packet_delay=0.05)
    trace = RuntimeTrace(client, rom, static, callsites, args.max_records, args.probe_index)
    watch_renderer = bool(args.watch_renderer)
    try:
        client.connect()
        runtime = report["runtime"]
        assert isinstance(runtime, dict)
        runtime["supported"] = client.request("qSupported:multiprocess+")
        runtime["initial_stop"] = client.request("?")
        runtime["initial_registers"] = snapshot(client.read_registers())
        trace.install(watch_renderer)
        if args.force_callsite:
            # First let the real reset path reach a Thumb loader stop.  The
            # mGBA stub accepts PC writes but does not accept a standalone
            # CPSR write; jumping from the ARM reset stop would therefore
            # execute the candidate as ARM.  Reusing a live Thumb stop keeps
            # the controlled probe architecturally well-defined.
            warmup_deadline = time.monotonic() + max(5.0, args.initial_seconds)
            warmup_events: list[dict[str, object]] = []
            while time.monotonic() < warmup_deadline:
                try:
                    stop = client.continue_until_stop(args.event_timeout)
                except TimeoutError:
                    try:
                        stop = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        break
                warmup_events.append(trace.handle_stop(stop))
                registers = client.read_registers()
                if registers["pc"] == LOADER_ENTRY and registers["cpsr"] & 0x20:
                    runtime["thumb_state_seed"] = snapshot(registers)
                    break
            runtime["natural_warmup_events"] = warmup_events
            trace._reachability = "controlled"
            client.write_register(0, args.probe_index)
            client.write_register(15, 0x080985EC)
            deadline = time.monotonic() + max(5.0, args.initial_seconds)
            while not trace.loader_records and time.monotonic() < deadline:
                try:
                    stop = client.continue_until_stop(args.event_timeout)
                except TimeoutError:
                    try:
                        stop = client.interrupt(timeout=2.0)
                    except (TimeoutError, OSError, ConnectionError):
                        break
                trace.handle_stop(stop)
            runtime["controlled_probe_events"] = trace.events
            if args.no_display:
                runtime["controlled_probe_display_io"] = display_io(client)
            else:
                runtime["controlled_probe_display"] = display_state(client)
        else:
            trace.continue_for(args.initial_seconds)
            if args.no_display:
                runtime["pre_navigation_display_io"] = display_io(client)
                previous_display = None
            else:
                runtime["pre_navigation_display"] = display_state(client)
                previous_display = runtime["pre_navigation_display"]
            for step_number, button in enumerate(sequence, start=1):
                step = trace.press_button(
                    button,
                    hold_events=args.hold_events,
                    release_events=args.release_events,
                    event_timeout=args.event_timeout,
                )
                before_events = len(trace.events)
                trace.continue_for(args.step_seconds)
                step_events = trace.events[before_events:]
                step["loader_record_count_after_step"] = len(trace.loader_records)
                step["renderer_event_count"] = sum(
                    event.get("kind") == "renderer_vram_sink_write" for event in step_events
                )
                if args.no_display:
                    step["display_io"] = display_io(client)
                    step["display"] = None
                    step["display_changed"] = None
                elif args.screen_every and step_number % args.screen_every == 0:
                    current_display = display_state(client)
                    step["display"] = current_display
                    step["display_changed"] = current_display != previous_display
                    previous_display = current_display
                else:
                    step["display"] = None
                    step["display_changed"] = None
                runtime["screens"].append(step)
                if len(trace.loader_records) >= args.max_records:
                    break
            if args.no_display:
                runtime["final_display_io"] = display_io(client)
            else:
                runtime["final_display"] = display_state(client)
        runtime["events"] = trace.events
        runtime["loader_records"] = trace.loader_records
        runtime["renderer_events"] = trace.render_events
    finally:
        trace.uninstall(watch_renderer)
        client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
