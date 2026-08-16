#!/usr/bin/env python3
"""Bounded A9PJ M1.7 font-record to name-entry tile trace.

This is a game-specific orchestration layer over ``core/gba``.  It reaches the
already verified name-entry keyboard, then watches the two observed code units
(``0x005E`` and ``0x0066``) while the A9PJ renderer is running.  The static
renderer path is represented by two Thumb store PCs:

* ``0x08004C82``: ``str r0, [r2, #0x20]``;
* ``0x08004D1A``: ``stm r3!, {r0}``.

The report keeps only registers, addresses, control-flow classification and
SHA-256 values.  ROM/font records and runtime bytes are read only in order to
produce hashes; raw capture belongs in the caller's ignored/private dump
directory.  A record read, a CPU store, a DMA control write, and a BIOS PC are
separate evidence classes and are never collapsed into one generic "text
write" result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import capture  # noqa: E402
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402
from m15_navigate_probe import (  # noqa: E402
    BUTTON_BITS,
    KEYINPUT,
    NO_KEY,
    button_value,
    identity,
    press_button,
)
from m16_keyboard_metadata import KNOWN_KANA  # noqa: E402
from m16_name_entry_probe import (  # noqa: E402
    BG0CNT,
    BG1_SCREENBASE,
    EXPECTED_KEYBOARD_TILE_IDS,
    read_display_maps,
)


EXPECTED_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"
VRAM = 0x06000000
VRAM_END = VRAM + 0x18000
FONT_RECORD_TABLE_BASE = 0x08089E00
FONT_RECORD_STRIDE = 0x18
FONT_RECORD_LENGTH = 0x18
RECORD_READ_PC = 0x08004A3A
RECORD_READ_SITE_PCS = (0x08004A3A, 0x08004B16)
RENDERER_ENTRY_PC = 0x080049A0
RECORD_ARITHMETIC_PC = 0x080049C8

# These are the two live instructions in the renderer's VRAM-producing
# branch.  The report derives the effective store address from the stopped
# registers and this table, rather than guessing from a disassembly label.
STORE_POINTS: dict[int, dict[str, int | str]] = {
    0x08004C82: {
        "instruction": "str r0, [r2, #0x20]",
        "base_register": "r2",
        "offset": 0x20,
    },
    0x08004D1A: {
        "instruction": "stm r3!, {r0}",
        "base_register": "r3",
        "offset": 0,
    },
}

# M1.6 metadata is deliberately repeated as commit-safe evidence, not as raw
# tile data.  The labels are the rendered system-order annotations.
KEYBOARD_TILE_METADATA = (
    ("a-row-1", "あ", 1, 0x06004020, "b5ae44407e13c9f6c085af00c74f47811dff6afe93020f068bdc33b8c1ff39c2"),
    ("a-row-2", "い", 2, 0x06004040, "924e28947f080def610d22c48b729b3bd86957983b679572aeb6d9da293c19f7"),
    ("a-row-3", "う", 3, 0x06004060, "742d18b92af37549e33283797b7e075eafb142426f58e19ba048a7c85c81db77"),
    ("a-row-4", "え", 4, 0x06004080, "f78b8247c640a8454bd21432ae49d56aa3aeca8e06aa03faf896f7b6de83a22d"),
    ("a-row-5", "お", 5, 0x060040A0, "4b2dd5435a020f9d11e7864f352821765e1e87b007aff7bdbba3bdc51f13a579"),
    ("ka-row-1", "か", 27, 0x06004360, "5255f765f120619881a9b57377c69d2f132a5a9ef15971ed2e3fb8df1a92e4ee"),
    ("ka-row-2", "き", 28, 0x06004380, "17ed557f340f161ec70e34d1a24cf117a395b0dd3b23511e4dd58ae852d488a5"),
    ("ka-row-3", "く", 29, 0x060043A0, "7baefffa17c0fa8fb70c8f2f2289b44e7a82e31e68289fa8b5df0cc93240e746"),
)

CODE_UNIT_LAYOUT = {
    0x005E: ("a-row-1", "あ", 1),
    0x0066: ("a-row-3", "う", 3),
}

# A DMA control write is a useful negative/positive boundary even when the
# actual glyph path is a CPU store.  DMA3 is the one bounded channel watched in
# this slice; unknown channels are not silently ruled out.
DMA3_BASE = 0x040000D4
DMA3_CONTROL = DMA3_BASE + 8
DMA3_REGISTER_LENGTH = 0x0C

REGISTER_NAMES = {
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08X}"


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: hex32(value)
        for name, value in registers.items()
        if name in REGISTER_NAMES
    }


def font_record_address(code_unit: int) -> int:
    if not 0 <= code_unit <= 0xFFFF:
        raise ValueError("code unit must fit an unsigned 16-bit value")
    return FONT_RECORD_TABLE_BASE + code_unit * FONT_RECORD_STRIDE


def code_unit_from_record(address: int) -> int | None:
    if address < FONT_RECORD_TABLE_BASE:
        return None
    delta = address - FONT_RECORD_TABLE_BASE
    if delta % FONT_RECORD_STRIDE:
        return None
    code_unit = delta // FONT_RECORD_STRIDE
    return code_unit if code_unit <= 0xFFFF else None


def classify_pc(pc: int) -> str:
    """Classify the execution origin without calling BIOS a generic copier."""

    address = pc & ~1
    if 0 <= address < 0x00004000:
        return "bios"
    if 0x08000000 <= address < 0x0A000000:
        return "cpu-game-rom"
    if 0x02000000 <= address < 0x03000000:
        return "ewram"
    if 0x03000000 <= address < 0x04000000:
        return "iwram"
    return "other"


def memory_region(address: int) -> str:
    if VRAM <= address < VRAM_END:
        return "vram"
    if 0x02000000 <= address < 0x03000000:
        return "ewram"
    if 0x03000000 <= address < 0x04000000:
        return "iwram"
    if 0x08000000 <= address < 0x0A000000:
        return "rom"
    return "other"


def renderer_destination(
    context_base: int,
    tile_selector: int,
    row_selector: int,
    context_base_offset: int,
    context_row_stride: int,
    context_extra: int,
) -> int:
    """Reproduce the literal Thumb address arithmetic at 0x08004C54.

    ``context_base_offset`` is ``[context]``, ``context_row_stride`` is the
    signed halfword at ``context+0x10``, and ``context_extra`` is
    ``[context+0x14]``.  ``context_base`` is retained as an explicit argument
    so callers/tests can show which context produced the formula.
    """

    del context_base  # the pointer identifies the record; fields carry math
    return (
        VRAM
        + ((tile_selector & 0xFFFFFFFF) << 5)
        + context_base_offset
        + (row_selector * 4 * context_row_stride)
        + context_extra
    ) & 0xFFFFFFFF


def store_address(registers: dict[str, int], store_pc: int) -> int:
    normalized = store_pc & ~1
    point = STORE_POINTS[normalized]
    base = registers[str(point["base_register"])]
    return (base + int(point["offset"])) & 0xFFFFFFFF


def keyboard_tile_for_address(address: int) -> dict[str, object] | None:
    for slot, label, tile_id, tile_address, known_hash in KEYBOARD_TILE_METADATA:
        if tile_address <= address < tile_address + 0x20:
            return {
                "slot": slot,
                "known_layout_label": label,
                "tile_id": tile_id,
                "tile_address": hex32(tile_address),
                "known_tile_sha256": known_hash,
            }
    return None


def read_u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def read_i16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little", signed=True)


def read_context(client: GdbClient, registers: dict[str, int]) -> dict[str, object]:
    """Read only arithmetic fields and a hash for the renderer context."""

    sp = registers["sp"]
    stack = client.read_memory(sp, 0x10)
    context_pointer = read_u32(stack, 0)
    context = client.read_memory(context_pointer, 0x18)
    tile_selector = read_u32(stack, 8)
    row_selector = read_u32(stack, 0x0C)
    base_offset = read_u32(context, 0)
    row_stride = read_i16(context, 0x10)
    extra = read_u32(context, 0x14)
    formula = renderer_destination(
        context_pointer,
        tile_selector,
        row_selector,
        base_offset,
        row_stride,
        extra,
    )
    return {
        "context_pointer": hex32(context_pointer),
        "context_sha256": digest(context),
        "stack_selector_tile": tile_selector,
        "stack_selector_row": row_selector,
        "context_base_offset": hex32(base_offset),
        "context_row_stride_signed": row_stride,
        "context_extra": hex32(extra),
        "formula_destination": hex32(formula),
    }


def read_tile_hash(client: GdbClient, address: int) -> dict[str, object]:
    base = address & ~0x1F
    data = client.read_memory(base, 0x20)
    known = keyboard_tile_for_address(base)
    return {
        "tile_address": hex32(base),
        "tile_sha256": digest(data),
        "keyboard_position": known,
    }


def watch_in_range(address: int | None, requested: int, length: int) -> bool:
    return address is not None and requested <= address < requested + length


def safe_remove_watch(client: GdbClient, spec: dict[str, int]) -> None:
    try:
        client.remove_watchpoint(spec["address"], spec["length"], spec["watch_type"])
    except (RuntimeError, OSError, ConnectionError):
        pass


def safe_remove_breakpoint(client: GdbClient, address: int) -> None:
    try:
        client.remove_breakpoint(address)
    except (RuntimeError, OSError, ConnectionError):
        pass


def install_watch(
    client: GdbClient,
    active: dict[str, dict[str, int]],
    setup: list[dict[str, object]],
    role: str,
    address: int,
    length: int,
    watch_type: int,
) -> None:
    spec = {"address": address, "length": length, "watch_type": watch_type}
    item: dict[str, object] = {
        "role": role,
        "address": hex32(address),
        "length": length,
        "watch_type": watch_type,
        "status": "requested",
    }
    try:
        client.set_watchpoint(address, kind=length, watch_type=watch_type)
    except (RuntimeError, OSError, ConnectionError) as exc:
        item["status"] = "unavailable"
        item["error"] = str(exc)
    else:
        active[role] = spec
        item["status"] = "armed"
    setup.append(item)


def matching_watch(
    active: dict[str, dict[str, int]], address: int | None
) -> tuple[str, dict[str, int]] | None:
    for role, spec in active.items():
        if watch_in_range(address, spec["address"], spec["length"]):
            return role, spec
    return None


def process_watch_stop(
    client: GdbClient,
    stop: str,
    *,
    active_watches: dict[str, dict[str, int]],
    trace: dict[str, Any],
    phase: str,
    step_after: bool = True,
) -> None:
    kind, address = parse_stop_watch(stop)
    found = matching_watch(active_watches, address)
    registers = client.read_registers()
    if found is None:
        trace["unexpected_stops"].append(
            {
                "phase": phase,
                "stop": stop,
                "stop_kind": kind,
                "stop_address": None if address is None else hex32(address),
                "registers": register_snapshot(registers),
            }
        )
        return

    role, spec = found
    active_watches.pop(role)
    # Remove before any diagnostic ``m`` packet.  This is required for read
    # watchpoints on the font record and mirrors the M1.6 self-trigger fix.
    safe_remove_watch(client, spec)
    event: dict[str, object] = {
        "phase": phase,
        "role": role,
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else hex32(address),
        "registers": register_snapshot(registers),
        "writer_class": classify_pc(registers["pc"]),
    }

    if role.startswith("record_"):
        code_unit = int(role.split("_")[1], 16)
        record_address = font_record_address(code_unit)
        event.update(
            {
                "code_unit": hex32(code_unit),
                "record_address": hex32(record_address),
                "record_length": FONT_RECORD_LENGTH,
                "record_sha256": digest(client.read_memory(record_address, FONT_RECORD_LENGTH)),
                "record_read_static_candidates": [hex32(pc) for pc in RECORD_READ_SITE_PCS],
                "record_read_observed_pc": hex32(registers["pc"]),
            }
        )
        trace["record_reads"].append(event)
    elif role.startswith("bg1_"):
        event["tile"] = read_tile_hash(client, spec["address"])
        trace["tile_watch_hits"].append(event)
    elif role == "dma3_control":
        data = client.read_memory(DMA3_BASE, DMA3_REGISTER_LENGTH)
        event["dma3"] = {
            "sample": "before_control_store",
            "source": hex32(read_u32(data, 0)),
            "destination": hex32(read_u32(data, 4)),
            "count_control": hex32(read_u32(data, 8)),
        }
        trace["dma_control_hits"].append(event)
    else:
        trace["other_watch_hits"].append(event)

    if step_after:
        event["step_after_watch"] = client.request("s")
        if role == "dma3_control":
            after = client.read_memory(DMA3_BASE, DMA3_REGISTER_LENGTH)
            event["dma3_after_control_store"] = {
                "sample": "after_control_store",
                "source": hex32(read_u32(after, 0)),
                "destination": hex32(read_u32(after, 4)),
                "count_control": hex32(read_u32(after, 8)),
            }


def process_store_breakpoint(
    client: GdbClient,
    stop: str,
    *,
    active_watches: dict[str, dict[str, int]],
    trace: dict[str, Any],
    phase: str,
) -> None:
    registers = client.read_registers()
    raw_pc = registers["pc"]
    pc = raw_pc & ~1
    if pc not in STORE_POINTS:
        trace["unexpected_stops"].append(
            {
                "phase": phase,
                "stop": stop,
                "kind": "breakpoint",
                "registers": register_snapshot(registers),
            }
        )
        return

    record_pointer = (registers["r12"] - FONT_RECORD_STRIDE) & 0xFFFFFFFF
    code_unit = code_unit_from_record(record_pointer)
    destination = store_address(registers, pc)
    context: dict[str, object] | None = None
    try:
        context = read_context(client, registers)
    except (RuntimeError, OSError, ConnectionError, ValueError) as exc:
        trace["errors"].append(
            {"phase": phase, "where": "renderer-context", "error": str(exc), "pc": hex32(pc)}
        )

    point = STORE_POINTS[pc]
    hit: dict[str, object] = {
        "phase": phase,
        "stop": stop,
        "store_pc": hex32(pc),
        "instruction": point["instruction"],
        "writer_class": classify_pc(pc),
        "lr": hex32(registers["lr"]),
        "registers": register_snapshot(registers),
        "font_record_pointer_from_r12": hex32(record_pointer),
        "code_unit": None if code_unit is None else hex32(code_unit),
        "store_address": hex32(destination),
        "store_region": memory_region(destination),
        "keyboard_position": keyboard_tile_for_address(destination),
        "context": context,
        "static_record_read_pc": hex32(RECORD_READ_PC),
        "static_renderer_entry_pc": hex32(RENDERER_ENTRY_PC),
        "static_record_arithmetic_pc": hex32(RECORD_ARITHMETIC_PC),
    }
    if context is not None:
        formula_destination = int(str(context["formula_destination"]), 16)
        hit["renderer_formula_destination"] = hex32(formula_destination)
        hit["renderer_formula_available"] = True
        # 0x08004C82 stores the first output word at formula+0x20.  The later
        # 0x08004D1A store follows the renderer's pointer walk, so comparing
        # its live r3 with the original formula would be a false mismatch.
        hit["store_offset_from_renderer_formula"] = hex32(
            (destination - formula_destination) & 0xFFFFFFFF
        )
        hit["formula_matches_current_base_register"] = (
            formula_destination
            == (registers[str(point["base_register"])] & 0xFFFFFFFF)
        )

    # If a BG1 tile range overlaps the exact instruction about to write it,
    # remove that one-shot watch before stepping.  The breakpoint's decoded
    # Thumb store is the stronger evidence and avoids a self-trigger loop.
    for role in list(active_watches):
        spec = active_watches[role]
        if role.startswith("bg1_") and (
            spec["address"] <= destination < spec["address"] + spec["length"]
            or destination <= spec["address"] < destination + 4
        ):
            safe_remove_watch(client, spec)
            active_watches.pop(role)
            hit.setdefault("tile_watch_suppressed", []).append(role)

    trace["store_hits"].append(hit)

    # A breakpoint stops before the store.  Complete exactly that instruction,
    # then hash the affected 32-byte tile; no raw tile bytes enter the report.
    safe_remove_breakpoint(client, pc)
    hit["step_after_store"] = client.request("s")
    try:
        hit["post_store_tile"] = read_tile_hash(client, destination)
    except (RuntimeError, OSError, ConnectionError, ValueError) as exc:
        trace["errors"].append(
            {"phase": phase, "where": "post-store-tile", "error": str(exc), "pc": hex32(pc)}
        )
    client.set_breakpoint(pc)


def process_stop(
    client: GdbClient,
    stop: str,
    *,
    active_watches: dict[str, dict[str, int]],
    trace: dict[str, Any],
    phase: str,
) -> None:
    if parse_stop_watch(stop)[0] is not None:
        process_watch_stop(
            client,
            stop,
            active_watches=active_watches,
            trace=trace,
            phase=phase,
        )
        return
    process_store_breakpoint(
        client,
        stop,
        active_watches=active_watches,
        trace=trace,
        phase=phase,
    )


def inject_button_trace(
    client: GdbClient,
    button: str,
    *,
    input_register: int,
    hold_events: int,
    release_events: int,
    event_timeout: float,
    active_watches: dict[str, dict[str, int]],
    trace: dict[str, Any],
) -> dict[str, object]:
    desired = button_value(button)
    result: dict[str, object] = {
        "button": button,
        "hold_events": hold_events,
        "release_events": release_events,
        "events": [],
        "termination": "completed",
    }
    key_spec = {"address": KEYINPUT, "length": 2, "watch_type": 3}
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    try:
        for index in range(hold_events + release_events):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                result["termination"] = "keyinput-watch-timeout"
                try:
                    result["interrupt"] = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError) as exc:
                    result["termination"] = "keyinput-watch-timeout-interrupt-failed"
                    result["interrupt_error"] = str(exc)
                break

            kind, address = parse_stop_watch(stop)
            if address == KEYINPUT:
                registers = client.read_registers()
                event = {
                    "index": index,
                    "role": "keyinput",
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": hex32(KEYINPUT),
                    "requested_keyinput": hex32(desired if index < hold_events else NO_KEY),
                    "registers": register_snapshot(registers),
                }
                result["events"].append(event)
                client.write_register(
                    input_register,
                    desired if index < hold_events else NO_KEY,
                )
                continue

            process_stop(
                client,
                stop,
                active_watches=active_watches,
                trace=trace,
                phase=f"{button}:{index}",
            )
            result["events"].append({"index": index, "role": "non-key-stop", "stop": stop})
    finally:
        client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
    result["event_count"] = len(result["events"])
    return result


def drain_trace(
    client: GdbClient,
    *,
    seconds: float,
    active_watches: dict[str, dict[str, int]],
    trace: dict[str, Any],
    phase: str,
    max_stops: int = 16,
) -> dict[str, object]:
    """Process only the still-armed trace points after a button sequence."""

    deadline = time.monotonic() + seconds
    stops = 0
    while stops < max_stops and time.monotonic() < deadline:
        remaining = max(0.05, deadline - time.monotonic())
        try:
            stop = client.continue_until_stop(min(remaining, 0.5))
        except TimeoutError:
            try:
                interrupt = client.interrupt(timeout=2.0)
            except (TimeoutError, OSError, ConnectionError) as exc:
                return {"stops": stops, "termination": "interrupt-failed", "error": str(exc)}
            return {"stops": stops, "termination": "timeout-interrupted", "interrupt": interrupt}
        process_stop(
            client,
            stop,
            active_watches=active_watches,
            trace=trace,
            phase=phase,
        )
        stops += 1
    return {"stops": stops, "termination": "bounded-drain"}


def initial_trace() -> dict[str, Any]:
    return {
        "record_reads": [],
        "store_hits": [],
        "tile_watch_hits": [],
        "dma_control_hits": [],
        "other_watch_hits": [],
        "unexpected_stops": [],
        "errors": [],
    }


def post_identity(trace: dict[str, Any]) -> list[dict[str, object]]:
    """Classify only paths with all three M1.7 dimensions present."""

    results: list[dict[str, object]] = []
    for code_unit, (slot, label, expected_tile_id) in CODE_UNIT_LAYOUT.items():
        reads = [
            item for item in trace["record_reads"]
            if item.get("code_unit") == hex32(code_unit)
        ]
        stores = [
            item for item in trace["store_hits"]
            if item.get("code_unit") == hex32(code_unit)
        ]
        candidates: list[dict[str, object]] = []
        for store in stores:
            tile = store.get("post_store_tile")
            position = store.get("keyboard_position")
            tile_hash = tile.get("tile_sha256") if isinstance(tile, dict) else None
            known_hash = position.get("known_tile_sha256") if isinstance(position, dict) else None
            candidates.append(
                {
                    "store_pc": store.get("store_pc"),
                    "store_address": store.get("store_address"),
                    "renderer_formula_destination": store.get("renderer_formula_destination"),
                    "renderer_formula_available": store.get("renderer_formula_available"),
                    "store_offset_from_renderer_formula": store.get("store_offset_from_renderer_formula"),
                    "keyboard_position": position,
                    "post_store_tile_sha256": tile_hash,
                    "known_position_tile_sha256": known_hash,
                    "hash_matches_position": tile_hash is not None and tile_hash == known_hash,
                    "record_read_seen": bool(reads),
                }
            )
        confirmed = any(
            candidate["record_read_seen"]
            and candidate["renderer_formula_available"] is True
            and isinstance(candidate["keyboard_position"], dict)
            and candidate["keyboard_position"].get("slot") == slot
            and candidate["keyboard_position"].get("tile_id") == expected_tile_id
            and candidate["hash_matches_position"] is True
            for candidate in candidates
        )
        status = "confirmed" if confirmed else (
            "provisional" if reads or stores else "unknown"
        )
        results.append(
            {
                "code_unit": hex32(code_unit),
                "expected_layout_slot": slot,
                "expected_layout_label": label,
                "expected_tile_id": expected_tile_id,
                "record_read_count": len(reads),
                "store_count": len(stores),
                "status": status,
                "candidates": candidates,
            }
        )
    return results


def keyboard_tile_hashes(client: GdbClient) -> list[dict[str, object]]:
    result = []
    for slot, label, tile_id, address, known_hash in KEYBOARD_TILE_METADATA:
        data = client.read_memory(address, 0x20)
        result.append(
            {
                "slot": slot,
                "known_layout_label": label,
                "tile_id": tile_id,
                "address": hex32(address),
                "sha256": digest(data),
                "m16_sha256": known_hash,
                "matches_m16": digest(data) == known_hash,
            }
        )
    return result


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=0.4)
    parser.add_argument("--drain-seconds", type=float, default=0.35)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.input_register <= 12:
        parser.error("input-register must be r0..r12")

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "scope": {
            "milestone": "M1.7",
            "navigation": "adaptive START to existing BG1 keyboard signature; no startup baseline",
            "input_plan": ["A -> 0x005E / あ", "RIGHT", "A -> 0x0066 / う"],
            "code_unit_font_record_formula": "0x08089E00 + code_unit * 0x18",
            "renderer_entry_pc": hex32(RENDERER_ENTRY_PC),
            "record_read_pc": hex32(RECORD_READ_PC),
            "store_points": {
                hex32(pc): dict(point) for pc, point in STORE_POINTS.items()
            },
            "keyinput": {"address": hex32(KEYINPUT), "destination_register": f"r{args.input_register}"},
            "bg1": {"screenbase": hex32(BG1_SCREENBASE), "charbase": hex32(0x4000), "tile_bytes": 0x20},
            "dma_watch": {"channel": 3, "control_address": hex32(DMA3_CONTROL)},
            "record_watch_type": "read, one-shot, 2-byte first-half access",
            "raw_policy": "ROM, RAM, VRAM and images remain only in private/ignored dump-dir",
        },
        "navigation": [],
        "trace": initial_trace(),
    }
    client = GdbClient(args.host, args.port, timeout=8.0)
    active_watches: dict[str, dict[str, int]] = {}
    trace = report["trace"]
    assert isinstance(trace, dict)
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(args.settle_seconds)
        screen, _bg0, _bg1 = read_display_maps(client)
        for _ in range(2):
            if screen["keyboard_layout"]["confirmed"]:
                break
            nav = press_button(
                client,
                "start",
                input_register=args.input_register,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
            )
            client.continue_and_interrupt(args.step_settle_seconds)
            screen, _bg0, _bg1 = read_display_maps(client)
            nav["screen"] = screen
            report["navigation"].append(nav)
        report["keyboard_gate"] = screen["keyboard_layout"]
        if not screen["keyboard_layout"]["confirmed"]:
            report["termination"] = "keyboard-gate-failed"
            report["reason"] = "known BG1 keyboard signature did not reproduce; trace skipped"
            report["trace"] = trace
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"wrote {args.output}")
            return

        report["pre_trace_screen"] = screen
        report["pre_trace_keyboard_tiles"] = keyboard_tile_hashes(client)

        setup: list[dict[str, object]] = []
        # Record watches prove an actual ROM read; the store breakpoints prove
        # the consumer's conversion path even if mGBA cannot watch ROM ranges.
        install_watch(
            client, active_watches, setup, "record_005E",
            font_record_address(0x005E), 2, 3,
        )
        install_watch(
            client, active_watches, setup, "record_0066",
            font_record_address(0x0066), 2, 3,
        )
        install_watch(
            client, active_watches, setup, "bg1_a_row_1",
            0x06004020, 0x20, 2,
        )
        install_watch(
            client, active_watches, setup, "bg1_a_row_2",
            0x06004040, 0x20, 2,
        )
        install_watch(
            client, active_watches, setup, "dma3_control",
            DMA3_CONTROL, 4, 2,
        )
        report["watch_setup"] = setup
        for pc in STORE_POINTS:
            client.set_breakpoint(pc)
        report["breakpoints_armed"] = [hex32(pc) for pc in STORE_POINTS]

        first = inject_button_trace(
            client, "a", input_register=args.input_register,
            hold_events=args.hold_events, release_events=args.release_events,
            event_timeout=args.event_timeout, active_watches=active_watches,
            trace=trace,
        )
        report["first_input"] = first
        report["first_drain"] = drain_trace(
            client, seconds=args.drain_seconds, active_watches=active_watches,
            trace=trace, phase="after-first-a",
        )

        middle = inject_button_trace(
            client, "right", input_register=args.input_register,
            hold_events=args.hold_events, release_events=args.release_events,
            event_timeout=args.event_timeout, active_watches=active_watches,
            trace=trace,
        )
        report["cursor_move"] = middle
        report["middle_drain"] = drain_trace(
            client, seconds=args.drain_seconds, active_watches=active_watches,
            trace=trace, phase="after-right",
        )

        second = inject_button_trace(
            client, "a", input_register=args.input_register,
            hold_events=args.hold_events, release_events=args.release_events,
            event_timeout=args.event_timeout, active_watches=active_watches,
            trace=trace,
        )
        report["second_input"] = second
        report["second_drain"] = drain_trace(
            client, seconds=args.drain_seconds, active_watches=active_watches,
            trace=trace, phase="after-second-a",
        )

        report["post_trace_screen"], _post_bg0, _post_bg1 = read_display_maps(client)
        report["post_trace_keyboard_tiles"] = keyboard_tile_hashes(client)
        report["identity_results"] = post_identity(trace)
        report["trace_summary"] = {
            "record_read_count": len(trace["record_reads"]),
            "store_hit_count": len(trace["store_hits"]),
            "tile_watch_hit_count": len(trace["tile_watch_hits"]),
            "dma_control_hit_count": len(trace["dma_control_hits"]),
            "confirmed_identity_count": sum(
                result["status"] == "confirmed" for result in report["identity_results"]
            ),
        }

        # Remove game breakpoints/watchpoints before invoking the shared final
        # capture.  This capture is standard core output and can safely write
        # raw regions only under the caller's private dump directory.
        for pc in STORE_POINTS:
            safe_remove_breakpoint(client, pc)
        for spec in list(active_watches.values()):
            safe_remove_watch(client, spec)
        active_watches.clear()
        report["core_capture"] = capture(
            client,
            run_seconds=0.05,
            breakpoint=None,
            breakpoint_timeout=1.0,
            watchpoint=None,
            watch_length=4,
            watch_type=2,
            watch_timeout=1.0,
            dump_dir=args.dump_dir,
        )
        report["termination"] = "bounded-trace-complete"
    finally:
        for pc in STORE_POINTS:
            safe_remove_breakpoint(client, pc)
        for spec in list(active_watches.values()):
            safe_remove_watch(client, spec)
        active_watches.clear()
        client.close()

    report["trace"] = trace
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    run()
