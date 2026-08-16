#!/usr/bin/env python3
"""Bounded A5TJ selector-table initializer and natural-dispatch probe.

Static mode finds Thumb literal-load/store candidates for the runtime selector
table pointer and records bounded caller metadata.  Runtime mode connects to
one fresh, session-owned mGBA GDB stub, arms the selector pointer before
continuing from reset, and drives one explicitly named natural input path.

The report is metadata-only: addresses, PC/LR, selected registers, lengths,
hashes, counts, and bounded source classifications.  It never writes the
selector table, injects selector state, emits raw memory, or scans glyph
patterns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m16_queue_probe import (  # noqa: E402
    ROM_BASE,
    ROM_LIMIT,
    QUEUE_PRODUCER,
    address_metadata,
    direct_bl_callers,
    hex_address,
    read_u16,
    read_u32,
    sha256,
    thumb_literal_load,
    thumb_bl_target,
)
from m17_descriptor_probe import (  # noqa: E402
    CALLBACK_PAYLOAD_WORDS,
    CALLERS,
    CALLBACK_TABLE,
    CALLBACK_TABLE_STRIDE,
    DESCRIPTOR_CURSOR_GLOBAL,
    INDIRECT_TRAMPOLINE,
    KEY_VALUES,
    SELECTOR,
    SELECTOR_GROUP0_TABLE,
    SELECTOR_GROUP1_TABLE,
    STAGING_WRITER,
    MODE_WRITER,
    TARGET_DESCRIPTOR,
    _parse_key_sequence,
    _queue_entry_metadata,
    _read_live_u32,
    _register_metadata,
    _return_candidates,
)


SCHEMA_STATIC = "smt2.m1.8.static.v1"
SCHEMA_RUNTIME = "smt2.m1.8.runtime.v1"
SCHEMA_SUMMARY = "smt2.m1.8.runtime-summary.v1"

SELECTOR_TABLE_GLOBAL = 0x03006950
SELECTOR_COUNTER_GLOBAL = 0x0203DB40
SELECTOR_GLOBAL_SPAN = 0x10
SELECTOR_TABLE_ENTRY_COUNT = 4
KEYINPUT = 0x04000130
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
PALETTE_BASE = 0x05000000
PALETTE_LENGTH = 0x400
OAM_BASE = 0x07000000
OAM_LENGTH = 0x400
DISPCNT = 0x04000000

CALLBACK_SITES = {
    0x080AD388: "callback_one_payload",
    0x080AD3A8: "callback_two_payload",
    0x080AD3CC: "callback_three_payload",
    0x080AD418: "callback_five_payload",
    0x080AD4D0: "callback_conditional_resource",
}


def _rom_offset(address: int) -> int | None:
    if ROM_BASE <= address < ROM_LIMIT:
        return address - ROM_BASE
    return None


def _u32_occurrences(data: bytes, value: int) -> list[int]:
    needle = value.to_bytes(4, "little")
    return [offset for offset in range(0, len(data) - 3, 4) if data[offset : offset + 4] == needle]


def _decode_thumb_store(data: bytes, instruction_address: int) -> dict[str, object] | None:
    """Decode bounded Thumb-1 store forms used by initializer candidates."""
    instruction = read_u16(data, instruction_address)
    if instruction & 0xF800 == 0x6000:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_imm",
            "source_register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 4,
            "width": 4,
        }
    if instruction & 0xF800 == 0x7000:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_byte_imm",
            "source_register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F),
            "width": 1,
        }
    if instruction & 0xF800 == 0x8000:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_halfword_imm",
            "source_register": instruction & 7,
            "base_register": (instruction >> 3) & 7,
            "offset": ((instruction >> 6) & 0x1F) * 2,
            "width": 2,
        }
    if instruction & 0xF000 == 0x9000 and not instruction & 0x0800:
        return {
            "instruction": f"0x{instruction:04x}",
            "form": "str_word_sp_relative",
            "source_register": (instruction >> 8) & 7,
            "base_register": 13,
            "offset": (instruction & 0xFF) * 4,
            "width": 4,
        }
    if instruction & 0xF800 == 0x5000:
        operation = (instruction >> 9) & 7
        if operation in (0, 1, 2):
            return {
                "instruction": f"0x{instruction:04x}",
                "form": {0: "str_word_reg", 1: "str_halfword_reg", 2: "str_byte_reg"}[operation],
                "source_register": instruction & 7,
                "base_register": (instruction >> 3) & 7,
                "offset_register": (instruction >> 6) & 7,
                "width": {0: 4, 1: 2, 2: 1}[operation],
            }
    return None


def _find_thumb_function_start(data: bytes, address: int, search_bytes: int = 0x100) -> int | None:
    if _rom_offset(address) is None:
        return None
    start = max(ROM_BASE, address - search_bytes)
    for candidate in range(address & ~1, start - 2, -2):
        halfword = read_u16(data, candidate)
        if halfword & 0xFF00 == 0xB500:
            return candidate
    return None


def _function_window(data: bytes, start: int | None, length: int = 0x80) -> dict[str, object] | None:
    if start is None or _rom_offset(start) is None:
        return None
    window = data[start - ROM_BASE : min(len(data), start - ROM_BASE + length)]
    return {
        "entry": address_metadata(start, len(data)),
        "length": len(window),
        "hash": sha256(window),
        "prologue_halfword": f"0x{read_u16(data, start):04x}",
        "thumb": True,
    }


def _literal_refs_to(data: bytes, literal_value: int) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    for offset in range(0, max(0, len(data) - 1), 2):
        instruction_address = ROM_BASE + offset
        try:
            item = thumb_literal_load(data, instruction_address)
        except (ValueError, IndexError):
            continue
        literal_address = int(str(item["literal_address"]), 16)
        value = int(str(item["value"]), 16)
        if value != literal_value:
            continue
        refs.append(
            {
                "instruction": hex_address(instruction_address),
                "literal_address": hex_address(literal_address),
                "register": item["register"],
                "value": hex_address(value),
                "rom_offset": hex_address(instruction_address - ROM_BASE),
            }
        )
    return refs


def _initializer_candidates(data: bytes, literal_refs: list[dict[str, object]]) -> list[dict[str, object]]:
    return _initializer_candidates_with_bl_index(data, literal_refs, _thumb_bl_index(data))


def _thumb_bl_index(data: bytes, limit_per_target: int = 32) -> dict[int, list[int]]:
    """Build one bounded Thumb BL target index for caller cross-checks."""
    index: dict[int, list[int]] = {}
    for offset in range(0, max(0, len(data) - 3), 2):
        address = ROM_BASE + offset
        target = thumb_bl_target(data, address)
        if target is None:
            continue
        callers = index.setdefault(target, [])
        if len(callers) < limit_per_target:
            callers.append(address)
    return index


def _initializer_candidates_with_bl_index(
    data: bytes,
    literal_refs: list[dict[str, object]],
    bl_index: dict[int, list[int]],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for ref in literal_refs:
        instruction = int(str(ref["instruction"]), 16)
        loaded_register = int(ref["register"])
        for offset in range(2, 0x12, 2):
            store_address = instruction + offset
            if _rom_offset(store_address) is None or store_address + 2 > ROM_BASE + len(data):
                break
            store = _decode_thumb_store(data, store_address)
            if store is None or store["base_register"] != loaded_register:
                continue
            function_start = _find_thumb_function_start(data, instruction)
            target = function_start or instruction
            direct_callers = [hex_address(address) for address in bl_index.get(target, [])[:8]]
            caller_metadata = []
            for callsite in direct_callers:
                call_address = int(callsite, 16)
                caller_start = _find_thumb_function_start(data, call_address)
                caller_metadata.append(
                    {
                        "callsite": callsite,
                        "function": _function_window(data, caller_start),
                    }
                )
            candidates.append(
                {
                    "literal_load": ref,
                    "store": {
                        **store,
                        "instruction": hex_address(store_address),
                        "watch_stop_pc": hex_address(store_address + 2),
                    },
                    "function": _function_window(data, function_start),
                    "direct_callers": caller_metadata,
                    "arm7tdmi_thumb_boundary": function_start is not None,
                }
            )
            break
    return candidates


def static_report(data: bytes) -> dict[str, object]:
    pointer_literal_refs = _literal_refs_to(data, SELECTOR_TABLE_GLOBAL)
    counter_literal_refs = _literal_refs_to(data, SELECTOR_COUNTER_GLOBAL)
    bl_index = _thumb_bl_index(data)
    candidates = _initializer_candidates_with_bl_index(data, pointer_literal_refs, bl_index)
    caller_validation = []
    for spec in CALLERS:
        callsite = int(spec["callsite"])
        target = thumb_bl_target(data, callsite)
        caller_validation.append(
            {
                "callsite": hex_address(callsite),
                "target": None if target is None else hex_address(target),
                "selector_target": target == SELECTOR,
                "function_start": hex_address(int(spec["function_start"])),
                "function_end": hex_address(int(spec["function_end"])),
            }
        )
    return {
        "schema": SCHEMA_STATIC,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "aligned Thumb literal-load/store candidates and bounded BL refs",
            "glyph_pattern_scan": False,
            "selector_table_global": hex_address(SELECTOR_TABLE_GLOBAL),
            "selector_counter_global": hex_address(SELECTOR_COUNTER_GLOBAL),
        },
        "pointer_literal_word_occurrences": len(_u32_occurrences(data, SELECTOR_TABLE_GLOBAL)),
        "counter_literal_word_occurrences": len(_u32_occurrences(data, SELECTOR_COUNTER_GLOBAL)),
        "pointer_literal_refs": pointer_literal_refs,
        "counter_literal_refs": counter_literal_refs,
        "initializer_candidates": candidates,
        "selector_callers": caller_validation,
        "known_consumer_targets": {
            "selector": hex_address(SELECTOR),
            "queue_producer": hex_address(QUEUE_PRODUCER),
            "indirect_trampoline": hex_address(INDIRECT_TRAMPOLINE),
            "staging_writer_candidate": hex_address(STAGING_WRITER),
            "mode_writer_candidate": hex_address(MODE_WRITER),
        },
        "runtime_requirement": "natural selector read and callback/producer evidence; no synthetic table/state writes",
    }


def _safe_read(client: GdbClient, address: int, length: int) -> bytes:
    try:
        return client.read_memory(address, length)
    except (ConnectionError, RuntimeError, TimeoutError):
        return b""


def _screen_metadata(client: GdbClient) -> dict[str, object]:
    vram = _safe_read(client, VRAM_BASE, VRAM_LENGTH)
    palette = _safe_read(client, PALETTE_BASE, PALETTE_LENGTH)
    oam = _safe_read(client, OAM_BASE, OAM_LENGTH)
    io = _safe_read(client, DISPCNT, 0x10)
    return {
        "dispcnt": hex_address(int.from_bytes(io[:2], "little")) if len(io) >= 2 else None,
        "vram_length": len(vram),
        "vram_hash": sha256(vram) if vram else None,
        "palette_length": len(palette),
        "palette_hash": sha256(palette) if palette else None,
        "oam_length": len(oam),
        "oam_hash": sha256(oam) if oam else None,
    }


class _NaturalKeyDriver:
    def __init__(self, names: list[str], idle_reads: int, hold_reads: int, gap_reads: int) -> None:
        self.names = names
        self.idle_reads = idle_reads
        self.hold_reads = hold_reads
        self.gap_reads = gap_reads
        self.reads = 0
        self.sent: list[str] = []
        self.completed: list[str] = []

    def next_value(self) -> tuple[int, str | None]:
        self.reads += 1
        if self.reads <= self.idle_reads:
            return KEY_VALUES["none"], None
        phase = self.reads - self.idle_reads - 1
        cycle = self.hold_reads + self.gap_reads
        index = phase // cycle
        if index >= len(self.names):
            return KEY_VALUES["none"], None
        within = phase % cycle
        if within < self.hold_reads:
            name = self.names[index]
            if within == 0:
                self.sent.append(name)
                return KEY_VALUES[name], f"sent:{name}"
            return KEY_VALUES[name], None
        if within == self.hold_reads:
            name = self.names[index]
            self.completed.append(name)
            return KEY_VALUES["none"], f"complete:{name}"
        return KEY_VALUES["none"], None


def _descriptor_command_metadata(client: GdbClient, rom: bytes, cursor: int | None) -> dict[str, object] | None:
    if cursor is None or _rom_offset(cursor) is None:
        return None
    raw = _safe_read(client, cursor, 0x20)
    candidates = []
    for address in (cursor - 4, cursor):
        if _rom_offset(address) is None:
            continue
        value = read_u32(rom, address)
        if value in CALLBACK_PAYLOAD_WORDS:
            candidates.append(
                {
                    "address": hex_address(address),
                    "opcode": value,
                    "payload_words": CALLBACK_PAYLOAD_WORDS[value],
                    "callback": address_metadata(
                        read_u32(rom, CALLBACK_TABLE + value * CALLBACK_TABLE_STRIDE) & ~1,
                        len(rom),
                    ),
                }
            )
    return {
        "cursor": address_metadata(cursor, len(rom)),
        "window_length": len(raw),
        "window_hash": sha256(raw) if raw else None,
        "opcode_candidates": candidates,
    }


def _initializer_chain(
    data: bytes,
    writer_pc: int,
    lr: int,
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    matches = []
    for candidate in candidates:
        store = candidate.get("store", {})
        if not isinstance(store, dict):
            continue
        if store.get("watch_stop_pc") == hex_address(writer_pc):
            matches.append(candidate)
    caller_layers = []
    for candidate in matches:
        for caller in candidate.get("direct_callers", []):
            if not isinstance(caller, dict):
                continue
            caller_site = caller.get("callsite")
            if not isinstance(caller_site, str):
                continue
            call_address = int(caller_site, 16)
            if lr in (call_address, call_address + 4, call_address + 5, call_address + 1):
                caller_layers.append({"layer": 1, **caller})
    return {
        "writer_pc": hex_address(writer_pc),
        "writer_lr": hex_address(lr),
        "static_candidate_count": len(matches),
        "static_candidates": [
            {
                "function": candidate.get("function"),
                "store": candidate.get("store"),
                "direct_caller_count": len(candidate.get("direct_callers", [])),
            }
            for candidate in matches
        ],
        "lr_matches": caller_layers,
        "depth": min(3, 1 + len(caller_layers)) if matches else 1,
        "status": "candidate_matched" if matches else "runtime_writer_not_in_static_literal_candidates",
    }


def trace(
    *,
    port: int,
    rom: bytes,
    path_id: str,
    key_sequence: list[str],
    max_stops: int,
    record_limit: int,
    timeout: float,
    wall_seconds: float,
    idle_key_reads: int,
    hold_key_reads: int,
    gap_key_reads: int,
    initializer_only: bool = False,
) -> dict[str, object]:
    client = GdbClient(port=port, timeout=max(timeout, 1.0), packet_delay=0.05)
    driver = _NaturalKeyDriver(key_sequence, idle_key_reads, hold_key_reads, gap_key_reads)
    static = static_report(rom)
    initializer_candidates = static["initializer_candidates"]
    if not isinstance(initializer_candidates, list):
        initializer_candidates = []
    site_by_pc: dict[int, str] = {}
    if not initializer_only:
        site_by_pc.update(
            {
                SELECTOR: "selector_entry",
                QUEUE_PRODUCER: "queue_producer",
                INDIRECT_TRAMPOLINE: "indirect_trampoline",
                STAGING_WRITER: "staging_writer_candidate",
                MODE_WRITER: "mode_writer_candidate",
                **CALLBACK_SITES,
            }
        )
        for spec in CALLERS:
            site_by_pc[int(spec["callsite"])] = f"selector_callsite_{int(spec['function_start']):08x}"
    for candidate in initializer_candidates:
        store = candidate.get("store", {})
        function = candidate.get("function")
        if isinstance(store, dict):
            store_pc = store.get("watch_stop_pc")
            if isinstance(store_pc, str):
                site_by_pc[int(store_pc, 16)] = "selector_initializer_store"
        if isinstance(function, dict):
            entry = function.get("entry")
            if isinstance(entry, dict) and isinstance(entry.get("address"), str):
                site_by_pc[int(entry["address"], 16)] = "selector_initializer_candidate"

    events: list[dict[str, object]] = []
    site_counts: Counter[str] = Counter()
    watch_counts: Counter[str] = Counter()
    install_failures: list[dict[str, object]] = []
    installed_breakpoints: list[int] = []
    installed_watchpoints: list[tuple[int, int, int]] = []
    table_base: int | None = None
    stop_count = 0
    started = time.monotonic()
    stopped_reason = "limit"
    natural_selector_hits = 0
    target_descriptor_hits = 0
    before_global = b""
    screen_metadata: dict[str, object] | None = None

    def add_event(item: dict[str, object]) -> None:
        if len(events) < record_limit:
            item.setdefault("path_id", path_id)
            item.setdefault("elapsed_ms", round((time.monotonic() - started) * 1000, 1))
            events.append(item)

    def install_breakpoint(address: int) -> None:
        try:
            client.set_breakpoint(address, kind=2, point_type=1)
            installed_breakpoints.append(address)
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "breakpoint", "address": hex_address(address), "error": type(exc).__name__})

    def install_watchpoint(address: int, kind: int, watch_type: int, name: str) -> None:
        try:
            client.set_watchpoint(address, kind=kind, watch_type=watch_type)
            installed_watchpoints.append((address, kind, watch_type))
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "watchpoint", "address": hex_address(address), "name": name, "error": type(exc).__name__})

    client.connect()
    try:
        for address in sorted(set(site_by_pc)):
            install_breakpoint(address)
        install_watchpoint(SELECTOR_TABLE_GLOBAL, 4, 2, "selector_table_pointer_global")
        install_watchpoint(SELECTOR_TABLE_GLOBAL, 2, 2, "selector_table_pointer_global")
        install_watchpoint(SELECTOR_TABLE_GLOBAL + 2, 2, 2, "selector_table_pointer_global")
        install_watchpoint(SELECTOR_COUNTER_GLOBAL, 4, 2, "selector_counter_global")
        install_watchpoint(KEYINPUT, 2, 3, "keyinput")
        before_global = _safe_read(client, SELECTOR_TABLE_GLOBAL, SELECTOR_GLOBAL_SPAN)

        while stop_count < max_stops and time.monotonic() - started < wall_seconds:
            try:
                stop = client.continue_until_stop(timeout=timeout)
            except TimeoutError:
                stopped_reason = "timeout"
                try:
                    client.interrupt(timeout=1.0)
                except (ConnectionError, RuntimeError, TimeoutError):
                    pass
                break
            stop_count += 1
            watch_kind, watch_address = parse_stop_watch(stop)
            if watch_kind == "rwatch" and watch_address == KEYINPUT:
                value, phase = driver.next_value()
                if phase is not None:
                    add_event(
                        {
                            "kind": "input",
                            "site": "keyinput_scheduler",
                            "phase": phase,
                            "key": phase.split(":", 1)[1],
                            "key_reads": driver.reads,
                        }
                    )
                client.write_register(0, value)
                continue

            registers = client.read_registers()
            elapsed = round((time.monotonic() - started) * 1000, 1)
            if watch_kind in {"watch", "awatch"} and watch_address is not None:
                if watch_address == SELECTOR_TABLE_GLOBAL:
                    name = "selector_table_pointer_global"
                elif watch_address == SELECTOR_COUNTER_GLOBAL:
                    name = "selector_counter_global"
                elif table_base is not None and table_base <= watch_address < table_base + SELECTOR_TABLE_ENTRY_COUNT * 2:
                    name = "selector_table_entry_span"
                else:
                    name = "other_watchpoint"
                watch_counts[name] += 1
                after_global = _safe_read(client, SELECTOR_TABLE_GLOBAL, SELECTOR_GLOBAL_SPAN)
                store = _decode_thumb_store(rom, registers["pc"] - 2) if _rom_offset(registers["pc"] - 2) is not None else None
                source_value = None
                if isinstance(store, dict):
                    source_value = registers.get(f"r{store['source_register']}")
                entry_value = None
                entry_index = None
                if name == "selector_table_pointer_global":
                    entry_value = _read_live_u32(client, SELECTOR_TABLE_GLOBAL)
                    candidate_table = source_value if source_value is not None else entry_value
                    if candidate_table is not None and 0x02000000 <= candidate_table < 0x04000000:
                        table_base = candidate_table
                        for index in range(SELECTOR_TABLE_ENTRY_COUNT):
                            install_watchpoint(table_base + index * 2, 2, 2, "selector_table_entry_span")
                elif name == "selector_counter_global":
                    entry_value = _read_live_u32(client, SELECTOR_COUNTER_GLOBAL)
                elif table_base is not None:
                    raw_entry = _safe_read(client, watch_address, 2)
                    entry_value = int.from_bytes(raw_entry, "little") if len(raw_entry) == 2 else None
                    entry_index = (watch_address - table_base) // 2
                item: dict[str, object] = {
                    "kind": "watchpoint",
                    "site": name,
                    "pc": hex_address(registers["pc"]),
                    "lr": hex_address(registers["lr"]),
                    "watch_address": hex_address(watch_address),
                    "registers": _register_metadata(registers),
                    "before_global_hash": sha256(before_global) if before_global else None,
                    "after_global_hash": sha256(after_global) if after_global else None,
                    "global_span_length": len(after_global),
                    "store": store,
                    "source_register_value": address_metadata(source_value, len(rom)) if source_value is not None else None,
                    "entry_index": entry_index,
                    "entry_value": hex_address(entry_value) if entry_value is not None else None,
                    "table_base": address_metadata(table_base, len(rom)) if table_base is not None else None,
                    "initializer_chain": _initializer_chain(rom, registers["pc"], registers["lr"], initializer_candidates),
                }
                if name == "selector_table_pointer_global" and table_base is not None:
                    table_bytes = _safe_read(client, table_base, SELECTOR_TABLE_ENTRY_COUNT * 2)
                    item["table_entry_span"] = {
                        "address": address_metadata(table_base, len(rom)),
                        "length": len(table_bytes),
                        "hash": sha256(table_bytes) if table_bytes else None,
                    }
                add_event(item)
                before_global = after_global
                continue

            if "T05" not in stop and not stop.startswith("S"):
                stopped_reason = "unexpected-stop"
                add_event({"kind": "unexpected_stop", "site": "unknown_stop", "pc": hex_address(registers["pc"]), "lr": hex_address(registers["lr"]), "registers": _register_metadata(registers)})
                break
            site = site_by_pc.get(registers["pc"])
            if site is None:
                stopped_reason = "unexpected-breakpoint"
                add_event({"kind": "unexpected_stop", "site": "unknown_breakpoint", "pc": hex_address(registers["pc"]), "lr": hex_address(registers["lr"]), "registers": _register_metadata(registers)})
                break
            site_counts[site] += 1
            item = {
                "kind": "breakpoint",
                "site": site,
                "pc": hex_address(registers["pc"]),
                "lr": hex_address(registers["lr"]),
                "registers": _register_metadata(registers),
                "elapsed_ms": elapsed,
            }
            if site.startswith("selector_callsite_"):
                item["prepared_group"] = registers["r0"] & 0xFFFF
                item["prepared_selector"] = registers["r1"] & 0xFFFF
                item["live_table_pointer"] = address_metadata(_read_live_u32(client, SELECTOR_TABLE_GLOBAL) or 0, len(rom))
                item["live_counter"] = hex_address(_read_live_u32(client, SELECTOR_COUNTER_GLOBAL) or 0)
            elif site == "selector_entry":
                group = registers["r0"] & 0xFFFF
                selector = registers["r1"] & 0xFFFF
                table = SELECTOR_GROUP0_TABLE if group == 0 else SELECTOR_GROUP1_TABLE
                selected = read_u32(rom, table + selector * 4) if _rom_offset(table + selector * 4) is not None else 0
                item.update(
                    {
                        "group": group,
                        "selector": selector,
                        "table_base": address_metadata(table, len(rom)),
                        "selected_descriptor": address_metadata(selected, len(rom)),
                        "target_descriptor_selected": selected == TARGET_DESCRIPTOR,
                        "natural": True,
                    }
                )
                natural_selector_hits += 1
                if selected == TARGET_DESCRIPTOR:
                    target_descriptor_hits += 1
            elif site == "queue_producer":
                item.update(
                    {
                        "source": address_metadata(registers["r0"], len(rom)),
                        "argument": hex_address(registers["r1"]),
                        "natural": True,
                    }
                )
            elif site == "indirect_trampoline":
                target = registers["r3"] & ~1
                cursor = _read_live_u32(client, DESCRIPTOR_CURSOR_GLOBAL)
                item.update(
                    {
                        "target": address_metadata(target, len(rom)),
                        "target_thumb": bool(registers["r3"] & 1),
                        "queue_entry": _queue_entry_metadata(client, registers["r0"]),
                        "argument": hex_address(registers["r1"]),
                        "descriptor_command": _descriptor_command_metadata(client, rom, cursor),
                    }
                )
            elif site.startswith("callback_"):
                cursor = _read_live_u32(client, DESCRIPTOR_CURSOR_GLOBAL)
                item["descriptor_command"] = _descriptor_command_metadata(client, rom, cursor)
            elif site == "selector_initializer_candidate":
                item["initializer_candidate"] = True
                item["static_chain"] = _initializer_chain(rom, registers["pc"], registers["lr"], initializer_candidates)
            elif site in {"staging_writer_candidate", "mode_writer_candidate"}:
                item["source_registers"] = {
                    "r0": address_metadata(registers["r0"], len(rom)),
                    "r1": address_metadata(registers["r1"], len(rom)),
                }
            else:
                item["return_candidates"] = _return_candidates(client, registers)
            add_event(item)
        else:
            stopped_reason = "stop-or-wall-limit"
        try:
            screen_metadata = _screen_metadata(client)
        except (ConnectionError, RuntimeError, TimeoutError):
            screen_metadata = None
    finally:
        for address in reversed(installed_breakpoints):
            try:
                client.remove_breakpoint(address, kind=2, point_type=1)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        for address, kind, watch_type in reversed(installed_watchpoints):
            try:
                client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
            except (ConnectionError, RuntimeError, TimeoutError):
                pass
        client.close()

    return {
        "schema": SCHEMA_RUNTIME,
        "path_id": path_id,
        "natural": True,
        "synthetic": False,
        "port": port,
        "rom": {"size": len(rom), "sha256": sha256(rom)},
        "bounds": {
            "max_stops": max_stops,
            "record_limit": record_limit,
            "timeout_seconds": timeout,
            "wall_seconds": wall_seconds,
            "key_sequence": key_sequence,
            "idle_key_reads": idle_key_reads,
            "hold_key_reads": hold_key_reads,
            "gap_key_reads": gap_key_reads,
            "selector_global": hex_address(SELECTOR_TABLE_GLOBAL),
            "selector_global_span": SELECTOR_GLOBAL_SPAN,
            "selector_table_entry_count": SELECTOR_TABLE_ENTRY_COUNT,
            "table_writes": False,
            "initializer_only": initializer_only,
        },
        "stopped_reason": stopped_reason,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "stop_count": stop_count,
        "keyinput_read_hits": driver.reads,
        "keys_requested": driver.sent,
        "completed_transitions": driver.completed,
        "screen": screen_metadata,
        "initializer": {
            "table_base": address_metadata(table_base, len(rom)) if table_base is not None else None,
            "candidate_count": len(initializer_candidates),
        },
        "natural_selector_hits": natural_selector_hits,
        "target_descriptor_hits": target_descriptor_hits,
        "breakpoint_counts": dict(sorted(site_counts.items())),
        "watchpoint_counts": dict(sorted(watch_counts.items())),
        "install_failures": install_failures,
        "events": events,
    }


def runtime_summary(report: dict[str, object]) -> dict[str, object]:
    events = report.get("events", [])
    if not isinstance(events, list):
        events = []
    selector_hits = [event for event in events if isinstance(event, dict) and event.get("site") == "selector_entry"]
    target_hits = [event for event in selector_hits if isinstance(event, dict) and event.get("target_descriptor_selected") is True]
    producer_sources = Counter()
    indirect_targets = Counter()
    for event in events:
        if not isinstance(event, dict):
            continue
        source = event.get("source")
        if isinstance(source, dict) and isinstance(source.get("address"), str):
            producer_sources[source["address"]] += 1
        target = event.get("target")
        if isinstance(target, dict) and isinstance(target.get("address"), str):
            indirect_targets[target["address"]] += 1
    return {
        "schema": SCHEMA_SUMMARY,
        "path_id": report.get("path_id"),
        "natural": report.get("natural") is True,
        "synthetic": report.get("synthetic") is True,
        "stopped_reason": report.get("stopped_reason"),
        "elapsed_seconds": report.get("elapsed_seconds"),
        "stop_count": report.get("stop_count", 0),
        "keyinput_read_hits": report.get("keyinput_read_hits", 0),
        "keys_requested": report.get("keys_requested", []),
        "completed_transitions": report.get("completed_transitions", []),
        "screen": report.get("screen"),
        "initializer": report.get("initializer"),
        "natural_selector_hits": len(selector_hits),
        "target_descriptor_hits": len(target_hits),
        "breakpoint_counts": report.get("breakpoint_counts", {}),
        "watchpoint_counts": report.get("watchpoint_counts", {}),
        "producer_source_counts": dict(sorted(producer_sources.items())),
        "indirect_target_counts": dict(sorted(indirect_targets.items())),
        "install_failure_count": len(report.get("install_failures", [])) if isinstance(report.get("install_failures", []), list) else 0,
        "event_count": len(events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--input-report", type=Path)
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--path-id", default="natural-transition")
    parser.add_argument("--key-sequence", default="a,start,a,b,down,a")
    parser.add_argument("--idle-key-reads", type=int, default=40)
    parser.add_argument("--hold-key-reads", type=int, default=2)
    parser.add_argument("--gap-key-reads", type=int, default=3)
    parser.add_argument("--max-stops", type=int, default=520)
    parser.add_argument("--record-limit", type=int, default=320)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=45.0)
    parser.add_argument("--initializer-only", action="store_true", help="only arm selector initializer candidates and narrow table watches")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.summary:
        if args.input_report is None:
            parser.error("--summary requires --input-report")
        report = runtime_summary(json.loads(args.input_report.read_text(encoding="utf-8")))
    elif args.static_only:
        report = static_report(args.rom.read_bytes())
    else:
        if args.max_stops <= 0 or args.record_limit <= 0 or args.timeout <= 0 or args.wall_seconds <= 0:
            parser.error("bounds must be positive")
        if args.idle_key_reads < 0 or args.hold_key_reads <= 0 or args.gap_key_reads < 0:
            parser.error("key read bounds are invalid")
        try:
            names = _parse_key_sequence(args.key_sequence)
        except ValueError as exc:
            parser.error(str(exc))
        report = trace(
            port=args.port,
            rom=args.rom.read_bytes(),
            path_id=args.path_id,
            key_sequence=names,
            max_stops=args.max_stops,
            record_limit=args.record_limit,
            timeout=args.timeout,
            wall_seconds=args.wall_seconds,
            idle_key_reads=args.idle_key_reads,
            hold_key_reads=args.hold_key_reads,
            gap_key_reads=args.gap_key_reads,
            initializer_only=args.initializer_only,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
