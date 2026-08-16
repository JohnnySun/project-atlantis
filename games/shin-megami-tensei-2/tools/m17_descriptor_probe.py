#!/usr/bin/env python3
"""Bounded A5TJ descriptor-selection and indirect-dispatch probe.

The static mode verifies the selector, its literal pools and direct callers,
then describes the bounded descriptor window as a variable command stream.
The runtime mode connects to one already-running, session-owned mGBA GDB stub.
It can drive a short KEYINPUT transition after an idle read window and records
only addresses, PC/LR, selected registers, lengths, hashes and counts.

This tool deliberately does not scan ROM glyph patterns, emit ROM/RAM/VRAM
bytes, or create a source table.  It is an engineering probe for the M1.7
descriptor -> queue -> callback path only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m16_queue_probe import (  # noqa: E402
    DMA3_REGISTERS,
    LZ77_WRAM_WRAPPER,
    QUEUE_BASE,
    QUEUE_ENTRY_STRIDE,
    QUEUE_PRODUCER,
    ROM_BASE,
    ROM_LIMIT,
    STAGING_BASE,
    address_metadata,
    direct_bl_callers,
    hex_address,
    read_u16,
    read_u32,
    sha256,
    thumb_bl_target,
    thumb_literal_load,
)


SELECTOR = 0x080BA8D8
SELECTOR_FUNCTION_END = 0x080BA91C
SELECTOR_GROUP0_TABLE = 0x08182B20
SELECTOR_GROUP1_TABLE = 0x08182B54
SELECTOR_DATA_REF = 0x08182B70
TARGET_DESCRIPTOR = 0x081869C8
DESCRIPTOR_NEXT = 0x08186C34
DESCRIPTOR_SENTINEL = 0x10241224
CALLBACK_TABLE = 0x0815EEEC
CALLBACK_TABLE_ENTRY_COUNT = 25
CALLBACK_TABLE_STRIDE = 8
INDIRECT_TRAMPOLINE = 0x0815CCCC
DESCRIPTOR_CURSOR_GLOBAL = 0x03003B84

STAGING_WRITER = 0x080BAEF0
MODE_WRITER = 0x080BAFB8
LZ_SOURCE_CANDIDATES = (0x081839F4, 0x081845E4)
OBJ_VRAM_BASE = 0x06013000
OAM_BASE = 0x07000000

CALLERS = (
    {
        "function_start": 0x08138FB8,
        "function_end": 0x08138FDE,
        "callsite": 0x08138FD0,
        "group": 0,
        "selector_kind": "runtime_halfword_table",
        "counter_global": 0x0203DB40,
        "table_pointer_global": 0x03006950,
        "literal_loads": (0x08138FBA, 0x08138FC4, 0x08138FD4),
    },
    {
        "function_start": 0x08139040,
        "function_end": 0x0813906C,
        "callsite": 0x08139058,
        "group": 1,
        "selector_kind": "runtime_halfword_table",
        "counter_global": 0x0203DB40,
        "table_pointer_global": 0x03006950,
        "literal_loads": (0x08139042, 0x0813904C, 0x0813905C, 0x08139062),
    },
    {
        "function_start": 0x0813A8B8,
        "function_end": 0x0813A8DA,
        "callsite": 0x0813A8C6,
        "group": 1,
        "selector_kind": "constant",
        "constant_selector": 1,
        "literal_loads": (0x0813A8BA, 0x0813A8CA, 0x0813A8D0),
    },
)

# These advances are read from the callback bodies' progress updates and
# cursor loads.  They describe the number of payload words following the
# opcode, not a guessed fixed descriptor record size.
CALLBACK_PAYLOAD_WORDS = {
    0: 0,
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
    6: 0,
    7: 0,
    8: 0,
    9: 0,
    10: 1,
    11: 2,
    12: 3,
    13: 4,
    14: 5,
    15: 6,
    16: 7,
    17: 1,
    18: 3,
    19: 0,
    20: 1,
    21: 0,
    22: 0,
    23: 0,
    24: 0,
}

CALLBACK_DESCRIPTIONS = {
    0: "load global argument and advance",
    1: "wait/decrement entry argument",
    2: "clear entry argument",
    3: "load entry timing fields",
    4: "decrement entry timing",
    5: "return",
    6: "return",
    7: "conditional sub-sequence",
    8: "conditional sub-sequence",
    9: "entry-state helper",
    10: "indirect bx r3 with one payload word",
    11: "indirect bx r3 with function and argument",
    12: "indirect bx r3 with function and two arguments",
    13: "indirect bx r4 with four payload words",
    14: "indirect bx r5 with five payload words",
    15: "indirect bx r6 with six payload words",
    16: "indirect bx r7 with seven payload words",
    17: "store entry field from one payload word",
    18: "conditional three-word resource operation",
    19: "load global sentinel field",
    20: "indirect bx r3 with one payload word",
    21: "enqueue derived resource",
    22: "fixed helper call",
    23: "fixed helper call",
    24: "fixed helper call",
}

KEY_VALUES = {
    "none": 0x03FF,
    "a": 0x03FE,
    "b": 0x03FD,
    "select": 0x03FB,
    "start": 0x03F7,
    "right": 0x03EF,
    "left": 0x03DF,
    "up": 0x03BF,
    "down": 0x037F,
    "r": 0x02FF,
    "l": 0x01FF,
}


def _rom_offset(address: int) -> int | None:
    if ROM_BASE <= address < ROM_LIMIT:
        return address - ROM_BASE
    return None


def _address_with_offset(address: int, rom_size: int | None = None) -> dict[str, object]:
    return address_metadata(address, rom_size)


def _u32_words(data: bytes, start: int, end: int) -> list[int]:
    if start < ROM_BASE or end < start or end > ROM_BASE + len(data):
        raise ValueError("ROM word window outside data")
    if (start - ROM_BASE) % 4 or (end - start) % 4:
        raise ValueError("ROM word window must be 4-byte aligned")
    return [read_u32(data, address) for address in range(start, end, 4)]


def _function_pointer(value: int) -> bool:
    return ROM_BASE <= (value & ~1) < ROM_LIMIT and bool(value & 1)


def _pointer_ref(data: bytes, word_address: int, value: int) -> dict[str, object]:
    target = value & ~1
    return {
        "word_address": hex_address(word_address),
        "word_rom_offset": hex_address(word_address - ROM_BASE),
        "target": address_metadata(target, len(data)),
        "thumb": True,
    }


def _hash_code_segments(data: bytes, segments: Iterable[tuple[int, int]]) -> str:
    joined = b"".join(data[start - ROM_BASE : end - ROM_BASE] for start, end in segments)
    return sha256(joined)


def _validate_thumb_function(
    data: bytes,
    *,
    entry: int,
    end: int,
    code_segments: tuple[tuple[int, int], ...],
    prologue: int | None = None,
    terminal: int | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "entry": hex_address(entry),
        "end_exclusive": hex_address(end),
        "code_segments": [
            {"start": hex_address(start), "end": hex_address(stop)}
            for start, stop in code_segments
        ],
        "code_hash": _hash_code_segments(data, code_segments),
        "arm7tdmi_thumb_boundary": True,
    }
    if prologue is not None:
        actual = read_u16(data, entry)
        result["prologue_halfword"] = f"0x{actual:04x}"
        result["prologue_matches"] = actual == prologue
    if terminal is not None:
        actual = read_u16(data, end - 2)
        result["terminal_halfword"] = f"0x{actual:04x}"
        result["terminal_matches"] = actual == terminal
    return result


def selector_static(data: bytes) -> dict[str, object]:
    selector_segments = (
        (SELECTOR, 0x080BA8E8),
        (0x080BA8EC, 0x080BA906),
        (0x080BA914, SELECTOR_FUNCTION_END),
    )
    literals = [
        thumb_literal_load(data, address)
        for address in (0x080BA8E4, 0x080BA8EC, 0x080BA8F8, 0x080BA900, 0x080BA914)
    ]
    literal_pool_ranges = (
        (0x080BA8E8, 0x080BA8EC),
        (0x080BA908, 0x080BA914),
        (0x080BA91C, 0x080BA920),
    )
    table_index = (SELECTOR_DATA_REF - SELECTOR_GROUP1_TABLE) // 4
    selected = read_u32(data, SELECTOR_DATA_REF)
    return {
        "entry": hex_address(SELECTOR),
        "function": _validate_thumb_function(
            data,
            entry=SELECTOR,
            end=SELECTOR_FUNCTION_END,
            code_segments=selector_segments,
            prologue=0xB500,
            terminal=0x4700,
        ),
        "literal_loads": literals,
        "literal_pools": [
            {
                "start": hex_address(start),
                "end": hex_address(end),
                "hash": sha256(data[start - ROM_BASE : end - ROM_BASE]),
            }
            for start, end in literal_pool_ranges
        ],
        "selector_operation": {
            "group_zero_table": address_metadata(SELECTOR_GROUP0_TABLE, len(data)),
            "group_nonzero_table": address_metadata(SELECTOR_GROUP1_TABLE, len(data)),
            "index_source": "original r1 low 16 bits",
            "entry_stride": 4,
            "data_ref": address_metadata(SELECTOR_DATA_REF, len(data)),
            "table_index": table_index,
            "selected_descriptor": address_metadata(selected, len(data)),
            "selected_descriptor_matches_target": selected == TARGET_DESCRIPTOR,
            "queue_call": {
                "target": hex_address(QUEUE_PRODUCER),
                "argument_1": "0xffff",
                "saved_handle_global": hex_address(0x0300463C),
            },
        },
    }


def _callsite_metadata(data: bytes, spec: dict[str, object]) -> dict[str, object]:
    start = int(spec["function_start"])
    end = int(spec["function_end"])
    callsite = int(spec["callsite"])
    literals = [thumb_literal_load(data, address) for address in spec["literal_loads"]]
    target = thumb_bl_target(data, callsite)
    result: dict[str, object] = {
        "function": _validate_thumb_function(
            data,
            entry=start,
            end=end,
            code_segments=((start, end),),
            prologue=0xB500,
            terminal=0x4700,
        ),
        "callsite": hex_address(callsite),
        "callsite_target": None if target is None else hex_address(target),
        "callsite_target_matches_selector": target == SELECTOR,
        "literal_loads": literals,
        "group": int(spec["group"]),
        "selector_kind": str(spec["selector_kind"]),
        "prepared_argument": {
            "group": int(spec["group"]),
            "selector": (
                int(spec["constant_selector"])
                if "constant_selector" in spec
                else "halfword[*(0x03006950) + 2 * halfword[0x0203db40]]"
            ),
        },
    }
    if "counter_global" in spec:
        result["counter_global"] = hex_address(int(spec["counter_global"]))
        result["table_pointer_global"] = hex_address(int(spec["table_pointer_global"]))
    return result


def _callback_table_static(data: bytes) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for index in range(CALLBACK_TABLE_ENTRY_COUNT):
        address = CALLBACK_TABLE + index * CALLBACK_TABLE_STRIDE
        pointer = read_u32(data, address)
        entries.append(
            {
                "index": index,
                "entry_address": hex_address(address),
                "stride": CALLBACK_TABLE_STRIDE,
                "function": address_metadata(pointer & ~1, len(data)),
                "thumb": bool(pointer & 1),
                "payload_words": CALLBACK_PAYLOAD_WORDS[index],
                "description": CALLBACK_DESCRIPTIONS[index],
            }
        )
    table_bytes = data[CALLBACK_TABLE - ROM_BASE : CALLBACK_TABLE - ROM_BASE + CALLBACK_TABLE_ENTRY_COUNT * CALLBACK_TABLE_STRIDE]
    return {
        "base": address_metadata(CALLBACK_TABLE, len(data)),
        "entry_count": CALLBACK_TABLE_ENTRY_COUNT,
        "stride": CALLBACK_TABLE_STRIDE,
        "region_end": hex_address(CALLBACK_TABLE + CALLBACK_TABLE_ENTRY_COUNT * CALLBACK_TABLE_STRIDE),
        "table_hash": sha256(table_bytes),
        "entries": entries,
        "dispatch": {
            "command_shift": 3,
            "pointer_field": 0,
            "indirect_trampoline": hex_address(INDIRECT_TRAMPOLINE),
        },
    }


def _known_thumb_target(data: bytes, entry: int, window_length: int, role: str) -> dict[str, object]:
    window = data[entry - ROM_BASE : entry - ROM_BASE + window_length]
    return {
        "role": role,
        "entry": address_metadata(entry, len(data)),
        "thumb_pointer": address_metadata(entry | 1, len(data)),
        "entry_halfword": f"0x{read_u16(data, entry):04x}",
        "bounded_window_length": window_length,
        "bounded_window_hash": sha256(window),
        "arm7tdmi_thumb_entry": True,
    }


def _first_command_run(data: bytes, start: int, end: int) -> dict[str, object]:
    commands: list[dict[str, object]] = []
    cursor = start
    status = "sentinel_reached"
    ambiguity: dict[str, object] | None = None
    while cursor + 4 <= end:
        opcode = read_u32(data, cursor)
        if opcode == DESCRIPTOR_SENTINEL:
            return {
                "start": hex_address(start),
                "end_exclusive": hex_address(cursor + 4),
                "status": status,
                "command_count": len(commands),
                "commands": commands,
                "sentinel": hex_address(cursor),
                "sentinel_rom_offset": hex_address(cursor - ROM_BASE),
            }
        if opcode not in CALLBACK_PAYLOAD_WORDS:
            status = "ambiguous_non_callback_word"
            ambiguity = {
                "address": hex_address(cursor),
                "rom_offset": hex_address(cursor - ROM_BASE),
                "word_class": "not_in_bounded_callback_table",
            }
            break
        payload_words = CALLBACK_PAYLOAD_WORDS[opcode]
        payload_end = cursor + 4 * (1 + payload_words)
        if payload_end > end:
            status = "truncated_payload"
            ambiguity = {
                "address": hex_address(cursor),
                "required_payload_words": payload_words,
            }
            break
        payload_refs = []
        for index in range(payload_words):
            value = read_u32(data, cursor + 4 * (index + 1))
            if _function_pointer(value):
                payload_refs.append(_pointer_ref(data, cursor + 4 * (index + 1), value))
        callback_address = CALLBACK_TABLE + opcode * CALLBACK_TABLE_STRIDE
        if _rom_offset(callback_address) is not None and callback_address + 4 <= ROM_BASE + len(data):
            callback = address_metadata(
                read_u32(data, callback_address) & ~1,
                len(data),
            )
        else:
            callback = {
                "address": None,
                "region": "synthetic_or_unavailable",
                "index": opcode,
            }
        commands.append(
            {
                "address": hex_address(cursor),
                "rom_offset": hex_address(cursor - ROM_BASE),
                "opcode": opcode,
                "callback": callback,
                "payload_words": payload_words,
                "payload_function_pointer_count": len(payload_refs),
                "payload_function_pointers": payload_refs,
            }
        )
        cursor = payload_end
    result: dict[str, object] = {
        "start": hex_address(start),
        "end_exclusive": hex_address(cursor),
        "status": status,
        "command_count": len(commands),
        "commands": commands,
    }
    if ambiguity is not None:
        result["ambiguity"] = ambiguity
    return result


def _descriptor_static(data: bytes) -> dict[str, object]:
    words = _u32_words(data, TARGET_DESCRIPTOR, DESCRIPTOR_NEXT)
    sentinels = [
        TARGET_DESCRIPTOR + index * 4
        for index, value in enumerate(words)
        if value == DESCRIPTOR_SENTINEL
    ]
    pointer_refs = [
        _pointer_ref(data, TARGET_DESCRIPTOR + index * 4, value)
        for index, value in enumerate(words)
        if _function_pointer(value)
    ]
    target_counts: Counter[str] = Counter(
        str(ref["target"]["address"]) for ref in pointer_refs
    )
    nonzero_opcode_counts: Counter[str] = Counter()
    nonzero_opcode_locations: dict[str, list[str]] = defaultdict(list)
    for index, value in enumerate(words):
        if value in CALLBACK_PAYLOAD_WORDS and value != 0:
            key = str(value)
            nonzero_opcode_counts[key] += 1
            if len(nonzero_opcode_locations[key]) < 12:
                nonzero_opcode_locations[key].append(
                    hex_address(TARGET_DESCRIPTOR + index * 4)
                )
    post_sentinel_headers = []
    for sentinel in sentinels:
        next_start = sentinel + 4
        header_end = min(next_start + 12, DESCRIPTOR_NEXT)
        header = data[next_start - ROM_BASE : header_end - ROM_BASE]
        post_sentinel_headers.append(
            {
                "sentinel": hex_address(sentinel),
                "following_word_count_bounded": (header_end - next_start) // 4,
                "following_words_hash": sha256(header),
            }
        )
    return {
        "address": address_metadata(TARGET_DESCRIPTOR, len(data)),
        "window_end": address_metadata(DESCRIPTOR_NEXT, len(data)),
        "window_length": DESCRIPTOR_NEXT - TARGET_DESCRIPTOR,
        "window_word_count": len(words),
        "window_hash": sha256(data[TARGET_DESCRIPTOR - ROM_BASE : DESCRIPTOR_NEXT - ROM_BASE]),
        "record_layout": {
            "kind": "variable_length_command_stream_with_sentinel_boundaries",
            "fixed_stride_bytes": None,
            "sentinel": hex_address(DESCRIPTOR_SENTINEL),
            "sentinel_count": len(sentinels),
            "sentinel_addresses": [hex_address(address) for address in sentinels],
            "post_sentinel_header_observation": post_sentinel_headers,
            "boundary_status": "first run decodes; later runs require live entry state because sentinel changes queue progress",
        },
        "first_decodable_run": _first_command_run(data, TARGET_DESCRIPTOR, DESCRIPTOR_NEXT),
        "nonzero_callback_opcode_occurrences": dict(sorted(nonzero_opcode_counts.items())),
        "nonzero_callback_opcode_location_samples": dict(sorted(nonzero_opcode_locations.items())),
        "function_pointer_ref_count": len(pointer_refs),
        "function_pointer_refs": pointer_refs,
        "function_pointer_target_counts": dict(sorted(target_counts.items())),
        "target_pointer_refs": {
            "080baef1": sum(1 for ref in pointer_refs if ref["target"]["address"] == hex_address(STAGING_WRITER)),
            "080bafb9": sum(1 for ref in pointer_refs if ref["target"]["address"] == hex_address(MODE_WRITER)),
        },
    }


def build_static_report(data: bytes) -> dict[str, object]:
    direct_callers = direct_bl_callers(data, SELECTOR)
    selector_pointer = (SELECTOR + 1).to_bytes(4, "little")
    selector_pointer_ref_count = sum(
        data[offset : offset + 4] == selector_pointer
        for offset in range(0, len(data) - 3, 4)
    )
    return {
        "schema": "smt2.m1.7.static.v1",
        "rom": {"size": len(data), "sha256": sha256(data)},
        "selector": selector_static(data),
        "direct_bl_callers": direct_callers,
        "selector_thumb_pointer_ref_count": selector_pointer_ref_count,
        "caller_validation": [_callsite_metadata(data, spec) for spec in CALLERS],
        "callback_table": _callback_table_static(data),
        "known_thumb_targets": [
            _known_thumb_target(data, STAGING_WRITER, 0x78, "descriptor_0x080baef1_staging_candidate"),
            _known_thumb_target(data, MODE_WRITER, 0x80, "descriptor_0x080bafb9_mode_candidate"),
            _known_thumb_target(data, INDIRECT_TRAMPOLINE, 2, "callback_indirect_trampoline"),
        ],
        "descriptor": _descriptor_static(data),
        "negative_scope": {
            "not_repeated": "reset_to_start_glyph_scan",
            "runtime_required": "selector and indirect callback must be observed in a triggerable resource transition",
        },
    }


def _register_metadata(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: hex_address(registers[name])
        for name in ("r0", "r1", "r2", "r3", "sp", "lr", "pc")
    }


def _read_live_u32(client: GdbClient, address: int) -> int | None:
    try:
        raw = client.read_memory(address, 4)
    except (ConnectionError, RuntimeError, TimeoutError):
        return None
    return int.from_bytes(raw, "little")


def _rom_lz_length(rom: bytes, source: int) -> int | None:
    offset = _rom_offset(source)
    if offset is None or offset + 4 > len(rom):
        return None
    header = int.from_bytes(rom[offset : offset + 4], "little")
    if header & 0xFF != 0x10:
        return None
    return (header >> 8) & 0xFFFFFF


def _return_candidates(client: GdbClient, registers: dict[str, int], limit: int = 3) -> list[dict[str, object]]:
    try:
        raw = client.read_memory(registers["sp"], 0x40)
    except (ConnectionError, RuntimeError, TimeoutError):
        return []
    result = []
    for offset in range(0, len(raw) - 3, 4):
        value = int.from_bytes(raw[offset : offset + 4], "little")
        if ROM_BASE <= (value & ~1) < ROM_LIMIT:
            result.append(
                {
                    "stack_offset": offset,
                    "address": hex_address(value & ~1),
                    "thumb": bool(value & 1),
                }
            )
            if len(result) >= limit:
                break
    return result


def _queue_entry_metadata(client: GdbClient, address: int) -> dict[str, object] | None:
    if not 0x02000000 <= address < 0x02040000:
        return None
    try:
        raw = client.read_memory(address, 0x24)
    except (ConnectionError, RuntimeError, TimeoutError):
        return None
    return {
        "address": hex_address(address),
        "length": len(raw),
        "hash": sha256(raw),
        "state": hex_address(int.from_bytes(raw[0:2], "little")),
        "type": hex_address(int.from_bytes(raw[2:4], "little")),
        "argument": hex_address(int.from_bytes(raw[4:6], "little")),
        "progress": hex_address(int.from_bytes(raw[0x10:0x14], "little")),
        "source": address_metadata(int.from_bytes(raw[0x14:0x18], "little")),
        "sentinel": hex_address(int.from_bytes(raw[0x20:0x24], "little")),
    }


def _oam_metadata(client: GdbClient, address: int) -> dict[str, object] | None:
    try:
        raw = client.read_memory(OAM_BASE, 0x400)
    except (ConnectionError, RuntimeError, TimeoutError):
        return None
    active = []
    for index in range(128):
        base = index * 8
        attr0 = int.from_bytes(raw[base : base + 2], "little")
        attr1 = int.from_bytes(raw[base + 2 : base + 4], "little")
        attr2 = int.from_bytes(raw[base + 4 : base + 6], "little")
        if attr0 & 0x3FF == 0x3FF:
            continue
        active.append(
            {
                "index": index,
                "attr0": f"0x{attr0:04x}",
                "attr1": f"0x{attr1:04x}",
                "attr2": f"0x{attr2:04x}",
                "tile_index": attr2 & 0x03FF,
            }
        )
    return {
        "watch_address": hex_address(address),
        "oam_hash": sha256(raw),
        "active_count": len(active),
        "active_tile_index_count": len({item["tile_index"] for item in active}),
    }


class _KeyScheduler:
    def __init__(self, names: list[str], idle_reads: int, hold_reads: int, gap_reads: int) -> None:
        self.names = names
        self.idle_reads = idle_reads
        self.hold_reads = hold_reads
        self.gap_reads = gap_reads
        self.reads = 0
        self.sent = []

    def value_for_next_read(self) -> int:
        self.reads += 1
        if self.reads <= self.idle_reads:
            return KEY_VALUES["none"]
        phase = self.reads - self.idle_reads - 1
        cycle = self.hold_reads + self.gap_reads
        index = phase // cycle
        if index >= len(self.names):
            return KEY_VALUES["none"]
        if phase % cycle < self.hold_reads:
            name = self.names[index]
            self.sent.append(name)
            return KEY_VALUES[name]
        return KEY_VALUES["none"]


def _parse_key_sequence(value: str) -> list[str]:
    names = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [name for name in names if name not in KEY_VALUES or name == "none"]
    if invalid:
        raise ValueError(f"unsupported key names: {','.join(invalid)}")
    return names


def _append_event(events: list[dict[str, object]], item: dict[str, object], limit: int) -> None:
    if len(events) < limit:
        events.append(item)


def _event_base(site: str, registers: dict[str, int]) -> dict[str, object]:
    return {
        "site": site,
        "pc": hex_address(registers["pc"]),
        "lr": hex_address(registers["lr"]),
        "registers": _register_metadata(registers),
    }


def trace(
    *,
    port: int,
    rom: bytes,
    max_stops: int,
    record_limit: int,
    timeout: float,
    wall_seconds: float,
    key_sequence: list[str],
    idle_key_reads: int,
    hold_key_reads: int,
    gap_key_reads: int,
    watch_lz_source: bool,
    watch_dma: bool = True,
    watch_display: bool = True,
    watch_queue: bool = True,
    force_selector_index: int | None = None,
) -> dict[str, object]:
    client = GdbClient(port=port, timeout=max(timeout, 1.0), packet_delay=0.05)
    events: list[dict[str, object]] = []
    site_counts: Counter[str] = Counter()
    watch_counts: Counter[str] = Counter()
    install_failures: list[dict[str, object]] = []
    installed_breakpoints: list[int] = []
    installed_watchpoints: list[tuple[int, int, int]] = []
    scheduler = _KeyScheduler(key_sequence, idle_key_reads, hold_key_reads, gap_key_reads)
    key_reads = 0
    stopped_reason = "limit"
    stop_count = 0
    started = time.monotonic()
    force_context: dict[str, int] | None = None
    force_injected = False
    force_completed = False
    forced_return_guard = 0x080AD2E0

    site_by_pc = {
        SELECTOR: "selector_entry",
        QUEUE_PRODUCER: "queue_producer",
        INDIRECT_TRAMPOLINE: "indirect_trampoline",
        STAGING_WRITER: "staging_writer_candidate",
        MODE_WRITER: "mode_writer",
        LZ77_WRAM_WRAPPER: "lz77_wrapper",
        0x080AD388: "callback_one_payload",
        0x080AD3A8: "callback_two_payload",
        0x080AD418: "callback_five_payload",
        0x080AD4D0: "callback_conditional_resource",
    }
    site_by_pc.update({int(spec["callsite"]): f"selector_callsite_{spec['function_start']:08x}" for spec in CALLERS})
    if force_selector_index is not None:
        site_by_pc[forced_return_guard] = "forced_return_guard"

    watch_names: dict[int, str] = {
        STAGING_BASE: "staging_buffer",
        0x03006950: "selector_table_pointer_global",
    }
    if watch_display:
        watch_names.update({OBJ_VRAM_BASE: "obj_vram", OAM_BASE: "oam"})
    if watch_queue:
        watch_names.update(
            {
                QUEUE_BASE: "queue_slot_0",
                QUEUE_BASE + QUEUE_ENTRY_STRIDE: "queue_slot_1",
                QUEUE_BASE + 2 * QUEUE_ENTRY_STRIDE: "queue_slot_2",
            }
        )
    if watch_dma:
        for name, address in DMA3_REGISTERS.items():
            watch_names[address] = f"dma3_{name}"
    if watch_lz_source:
        for address in LZ_SOURCE_CANDIDATES:
            watch_names[address] = f"lz_source_{address:08x}"

    def install_breakpoint(address: int) -> None:
        try:
            client.set_breakpoint(address, kind=2, point_type=1)
            installed_breakpoints.append(address)
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "breakpoint", "address": hex_address(address), "error": type(exc).__name__})

    def install_watchpoint(address: int, kind: int, watch_type: int) -> None:
        try:
            client.set_watchpoint(address, kind=kind, watch_type=watch_type)
            installed_watchpoints.append((address, kind, watch_type))
        except (ConnectionError, RuntimeError, TimeoutError) as exc:
            install_failures.append({"kind": "watchpoint", "address": hex_address(address), "error": type(exc).__name__})

    client.connect()
    try:
        for address in sorted(set(site_by_pc) | {int(spec["callsite"]) for spec in CALLERS}):
            install_breakpoint(address)
        install_watchpoint(STAGING_BASE, 4, 2)
        if watch_display:
            install_watchpoint(OBJ_VRAM_BASE, 4, 2)
            install_watchpoint(OAM_BASE, 4, 2)
        if watch_queue:
            for address in (QUEUE_BASE, QUEUE_BASE + QUEUE_ENTRY_STRIDE, QUEUE_BASE + 2 * QUEUE_ENTRY_STRIDE):
                install_watchpoint(address, 4, 2)
        install_watchpoint(0x03006950, 4, 2)
        if watch_dma:
            for address in DMA3_REGISTERS.values():
                install_watchpoint(address, 4, 2)
        if watch_lz_source:
            for address in LZ_SOURCE_CANDIDATES:
                install_watchpoint(address, 4, 3)
        install_watchpoint(0x04000130, 2, 3)

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
            if watch_kind == "rwatch" and watch_address == 0x04000130:
                key_reads += 1
                key_value = scheduler.value_for_next_read()
                if force_selector_index is not None and not force_injected and scheduler.reads > idle_key_reads:
                    before = client.read_registers()
                    force_context = {
                        "pc": before["pc"],
                        "lr": before["lr"],
                        "r0": before["r0"],
                        "r1": before["r1"],
                        "r2": before["r2"],
                        "r3": before["r3"],
                    }
                    selected = read_u32(
                        rom,
                        SELECTOR_GROUP1_TABLE + force_selector_index * 4,
                    )
                    live_selector_table = _read_live_u32(client, 0x03006950)
                    live_selector_counter = _read_live_u32(client, 0x0203DB40)
                    site_counts["synthetic_selector_injection"] += 1
                    _append_event(
                        events,
                        {
                            "kind": "synthetic_override",
                            "site": "synthetic_selector_injection",
                            "pc": hex_address(SELECTOR),
                            "lr": hex_address(before["lr"]),
                            "registers_before": _register_metadata(before),
                            "group": 1,
                            "selector": force_selector_index,
                            "table_base": address_metadata(SELECTOR_GROUP1_TABLE, len(rom)),
                            "selected_descriptor": address_metadata(selected, len(rom)),
                            "target_descriptor_selected": selected == TARGET_DESCRIPTOR,
                            "live_selector_table_pointer": (
                                address_metadata(live_selector_table, len(rom))
                                if live_selector_table is not None
                                else None
                            ),
                            "live_selector_counter": (
                                hex_address(live_selector_counter)
                                if live_selector_counter is not None
                                else None
                            ),
                            "synthetic": True,
                        },
                        record_limit,
                    )
                    client.write_register(0, 1)
                    client.write_register(1, force_selector_index)
                    client.write_register(14, forced_return_guard)
                    client.write_register(15, SELECTOR)
                    force_injected = True
                else:
                    client.write_register(0, key_value)
                continue
            registers = client.read_registers()
            if watch_kind in {"watch", "awatch", "rwatch"} and watch_address is not None:
                name = watch_names.get(watch_address, "other_watchpoint")
                watch_counts[name] += 1
                item: dict[str, object] = {
                    "kind": "watchpoint",
                    "site": name,
                    "pc": hex_address(registers["pc"]),
                    "lr": hex_address(registers["lr"]),
                    "watch_address": hex_address(watch_address),
                    "registers": _register_metadata(registers),
                }
                if name == "staging_buffer":
                    try:
                        sample = client.read_memory(STAGING_BASE, 0x40)
                    except (ConnectionError, RuntimeError, TimeoutError):
                        sample = b""
                    item.update({"length": len(sample), "hash": sha256(sample) if sample else None})
                elif name == "obj_vram":
                    try:
                        sample = client.read_memory(OBJ_VRAM_BASE, 0x40)
                    except (ConnectionError, RuntimeError, TimeoutError):
                        sample = b""
                    item.update({"length": len(sample), "hash": sha256(sample) if sample else None})
                elif name == "oam":
                    item["oam"] = _oam_metadata(client, watch_address)
                elif name.startswith("queue_slot_"):
                    item["entry"] = _queue_entry_metadata(client, watch_address)
                elif name.startswith("lz_source_"):
                    item["source"] = address_metadata(watch_address, len(rom))
                elif name.startswith("dma3_"):
                    item["length"] = 4
                _append_event(events, item, record_limit)
                continue
            if "T05" not in stop and not stop.startswith("S"):
                stopped_reason = "unexpected-stop"
                break
            site = site_by_pc.get(registers["pc"])
            if site is None:
                _append_event(
                    events,
                    {
                        "kind": "unexpected_stop",
                        "site": "unknown_breakpoint",
                        "pc": hex_address(registers["pc"]),
                        "lr": hex_address(registers["lr"]),
                        "registers": _register_metadata(registers),
                    },
                    record_limit,
                )
                stopped_reason = "unexpected-breakpoint"
                break
            site_counts[site] += 1
            item = {"kind": "breakpoint", **_event_base(site, registers)}
            if site == "forced_return_guard":
                item["synthetic"] = True
                item["forced_selector_index"] = force_selector_index
                item["resumed_host_context"] = False
                item["fail_closed"] = True
                _append_event(events, item, record_limit)
                force_completed = True
                stopped_reason = "forced-selector-return"
                break
            if site != "indirect_trampoline" or _rom_offset(registers["r3"] & ~1) is not None:
                item["return_candidates"] = _return_candidates(client, registers)
            if site.startswith("selector_callsite_"):
                item["prepared_group"] = registers["r0"]
                item["prepared_selector"] = registers["r1"] & 0xFFFF
            elif site == "selector_entry":
                group = registers["r0"] & 0xFFFF
                selector = registers["r1"] & 0xFFFF
                table = SELECTOR_GROUP0_TABLE if group == 0 else SELECTOR_GROUP1_TABLE
                selected = read_u32(rom, table + selector * 4) if _rom_offset(table + selector * 4) is not None else 0
                item["group"] = group
                item["selector"] = selector
                item["table_base"] = address_metadata(table, len(rom))
                item["selected_descriptor"] = address_metadata(selected, len(rom))
                item["target_descriptor_selected"] = selected == TARGET_DESCRIPTOR
            elif site == "queue_producer":
                item["source"] = address_metadata(registers["r0"], len(rom))
                item["argument"] = hex_address(registers["r1"])
                if force_injected and registers["r0"] == TARGET_DESCRIPTOR:
                    item["synthetic_selector_source"] = True
            elif site == "indirect_trampoline":
                item["target"] = address_metadata(registers["r3"] & ~1, len(rom))
                item["target_thumb"] = bool(registers["r3"] & 1)
                item["queue_entry"] = _queue_entry_metadata(client, registers["r0"])
                item["argument"] = hex_address(registers["r1"])
            elif site.startswith("callback_"):
                cursor = _read_live_u32(client, DESCRIPTOR_CURSOR_GLOBAL)
                item["descriptor_cursor"] = address_metadata(cursor, len(rom)) if cursor is not None else None
                if cursor is not None and ROM_BASE <= cursor < ROM_LIMIT:
                    payload = _read_live_u32(client, cursor)
                    item["payload_target"] = address_metadata(payload & ~1, len(rom)) if payload is not None else None
                    item["payload_thumb"] = bool(payload & 1) if payload is not None else None
            elif site == "lz77_wrapper":
                item["source"] = address_metadata(registers["r0"], len(rom))
                item["destination"] = address_metadata(registers["r1"])
                item["length"] = _rom_lz_length(rom, registers["r0"])
            elif site == "staging_writer_candidate":
                item["source_registers"] = {
                    "r0": address_metadata(registers["r0"], len(rom)),
                    "r1": address_metadata(registers["r1"], len(rom)),
                }
                item["expected_destinations"] = [hex_address(STAGING_BASE), hex_address(STAGING_BASE + 0x1000)]
            elif site == "mode_writer":
                item["mode"] = registers["r1"]
                item["input_pointer"] = address_metadata(registers["r0"], len(rom))
            _append_event(events, item, record_limit)
        else:
            stopped_reason = "stop-or-wall-limit"
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
        "schema": "smt2.m1.7.runtime.v1",
        "port": port,
        "rom": {"size": len(rom), "sha256": sha256(rom)},
        "bounds": {
            "max_stops": max_stops,
            "record_limit": record_limit,
            "timeout_seconds": timeout,
            "wall_seconds": wall_seconds,
            "idle_key_reads": idle_key_reads,
            "hold_key_reads": hold_key_reads,
            "gap_key_reads": gap_key_reads,
            "key_sequence": key_sequence,
            "watch_lz_source": watch_lz_source,
            "watch_dma": watch_dma,
            "watch_display": watch_display,
            "watch_queue": watch_queue,
            "force_selector_index": force_selector_index,
        },
        "stopped_reason": stopped_reason,
        "stop_count": stop_count,
        "keyinput_read_hits": key_reads,
        "keys_requested": scheduler.sent,
        "force_selector": {
            "requested": force_selector_index is not None,
            "injected": force_injected,
            "completed": force_completed,
            "synthetic": force_selector_index is not None,
            "resumed_host_context": False,
        },
        "breakpoint_counts": dict(sorted(site_counts.items())),
        "watchpoint_counts": dict(sorted(watch_counts.items())),
        "install_failures": install_failures,
        "events": events,
    }


def runtime_summary(report: dict[str, object]) -> dict[str, object]:
    events = report.get("events", [])
    if not isinstance(events, list):
        events = []
    selected = [
        event
        for event in events
        if isinstance(event, dict) and event.get("site") == "selector_entry"
    ]
    target_selected = [
        event
        for event in selected
        if isinstance(event, dict) and event.get("target_descriptor_selected") is True
    ]
    indirect_targets = Counter()
    for event in events:
        if isinstance(event, dict) and event.get("site") == "indirect_trampoline":
            target = event.get("target")
            if isinstance(target, dict) and isinstance(target.get("address"), str):
                indirect_targets[target["address"]] += 1
    source_addresses = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        source = event.get("source")
        if isinstance(source, dict) and isinstance(source.get("address"), str):
            source_addresses.add(source["address"])
    return {
        "schema": "smt2.m1.7.runtime-summary.v1",
        "stopped_reason": report.get("stopped_reason"),
        "stop_count": report.get("stop_count", 0),
        "keyinput_read_hits": report.get("keyinput_read_hits", 0),
        "keys_requested": report.get("keys_requested", []),
        "breakpoint_counts": report.get("breakpoint_counts", {}),
        "watchpoint_counts": report.get("watchpoint_counts", {}),
        "selector_hit_count": len(selected),
        "target_descriptor_selected_count": len(target_selected),
        "indirect_target_counts": dict(sorted(indirect_targets.items())),
        "distinct_source_addresses": sorted(source_addresses),
        "install_failure_count": len(report.get("install_failures", [])) if isinstance(report.get("install_failures", []), list) else 0,
        "event_count": len(events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="local A5TJ ROM; never copied to output")
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--input-report", type=Path)
    parser.add_argument("--port", type=int, default=2367)
    parser.add_argument("--max-stops", type=int, default=420)
    parser.add_argument("--record-limit", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--wall-seconds", type=float, default=45.0)
    parser.add_argument("--key-sequence", default="a,down,a,b,right,left")
    parser.add_argument("--idle-key-reads", type=int, default=10)
    parser.add_argument("--hold-key-reads", type=int, default=2)
    parser.add_argument("--gap-key-reads", type=int, default=2)
    parser.add_argument("--no-lz-source-watch", action="store_true")
    parser.add_argument("--force-selector-index", type=int, help="synthetically call selector with group=1 at this index after idle input; report is marked synthetic")
    parser.add_argument(
        "--lean-transition",
        action="store_true",
        help="keep selector/queue/indirect/writer/LZ and input watches, omit DMA/display/queue-slot watches",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_stops <= 0 or args.record_limit <= 0 or args.timeout <= 0 or args.wall_seconds <= 0:
        parser.error("bounds must be positive")
    if args.idle_key_reads < 0 or args.hold_key_reads <= 0 or args.gap_key_reads < 0:
        parser.error("key read bounds are invalid")
    if args.force_selector_index is not None and not 0 <= args.force_selector_index < 0x10000:
        parser.error("--force-selector-index must fit the selector's low 16-bit argument")
    rom = args.rom.read_bytes()
    if args.summary:
        if args.input_report is None:
            parser.error("--summary requires --input-report")
        report = runtime_summary(json.loads(args.input_report.read_text(encoding="utf-8")))
    elif args.static_only:
        report = build_static_report(rom)
    else:
        try:
            key_sequence = _parse_key_sequence(args.key_sequence)
        except ValueError as exc:
            parser.error(str(exc))
        report = trace(
            port=args.port,
            rom=rom,
            max_stops=args.max_stops,
            record_limit=args.record_limit,
            timeout=args.timeout,
            wall_seconds=args.wall_seconds,
            key_sequence=key_sequence,
            idle_key_reads=args.idle_key_reads,
            hold_key_reads=args.hold_key_reads,
            gap_key_reads=args.gap_key_reads,
            watch_lz_source=not args.no_lz_source_watch,
            watch_dma=not args.lean_transition,
            watch_display=not args.lean_transition,
            watch_queue=not args.lean_transition,
            force_selector_index=args.force_selector_index,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
