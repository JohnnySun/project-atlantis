#!/usr/bin/env python3
"""Bounded A9PJ reset-to-name-entry BG1 asset provenance probe.

M1.7 proved that ``0x005E`` and ``0x0066`` feed a CPU renderer writing a
different VRAM slice.  This probe starts its write watches at the initial GDB
stop and follows the BG1 keyboard asset itself:

* BG1CNT and the first two BG1 tile ranges;
* DMA0--DMA3 control writes, including post-write source/destination/count;
* CPU/BIOS/DMA provenance at a BG1 tile hit;
* live register/stack pointer candidates and guided Thumb-BL caller candidates.

The output is commit-safe metadata only.  Raw RAM/VRAM and standard capture
files belong under the caller's ignored/private dump directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_DIR))

from capture_runtime import capture  # noqa: E402
from gdbstub_client import GdbClient, REG_NAMES, parse_stop_watch  # noqa: E402
from m15_navigate_probe import KEYINPUT, NO_KEY, button_value  # noqa: E402
from m16_name_entry_probe import read_display_maps  # noqa: E402
from m17_font_tile_probe import (  # noqa: E402
    KEYBOARD_TILE_METADATA,
    classify_pc,
    digest,
    hex32,
    identity,
    register_snapshot,
)


VRAM = 0x06000000
VRAM_END = VRAM + 0x18000
BG1CNT = 0x0400000A
BG1_CHARBLOCK = 0x4000
BG1_SLICE = VRAM + BG1_CHARBLOCK
BG1_SLICE_LENGTH = 0x100
BG1_TILE_1 = BG1_SLICE + 0x20
BG1_TILE_2 = BG1_SLICE + 0x40
FONT_CALLER_LR = 0x080063C7
FONT_RECORD_BASE = 0x08089E00
FONT_RECORD_STRIDE = 0x18
BIOS_END = 0x00004000
DMA_BASES = {
    0: 0x040000B0,
    1: 0x040000BC,
    2: 0x040000C8,
    3: 0x040000D4,
}
DMA_CONTROL_OFFSET = 8
DMA_REGISTER_LENGTH = 0x0C
REGISTER_POINTER_NAMES = (
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr",
)


def decode_bgcnt(value: int) -> dict[str, object]:
    charblock = (value >> 2) & 0x03
    screenblock = (value >> 8) & 0x1F
    return {
        "value": hex32(value),
        "charblock": charblock,
        "charbase_offset": hex32(charblock * 0x4000),
        "bpp": 8 if value & 0x80 else 4,
        "screenblock": screenblock,
        "screenbase_offset": hex32(screenblock * 0x800),
    }


def dma_transfer_length(channel: int, count_control: int) -> dict[str, int]:
    count_mask = 0xFFFF if channel == 3 else 0x3FFF
    count = count_control & count_mask
    if count == 0:
        count = 0x10000 if channel == 3 else 0x4000
    unit_bytes = 4 if count_control & (1 << 26) else 2
    return {
        "count_units": count,
        "unit_bytes": unit_bytes,
        "length_bytes": count * unit_bytes,
    }


def region(address: int) -> str:
    if 0x08000000 <= address < 0x0A000000:
        return "rom"
    if 0x02000000 <= address < 0x03000000:
        return "ewram"
    if 0x03000000 <= address < 0x04000000:
        return "iwram"
    if VRAM <= address < VRAM_END:
        return "vram"
    return "other"


def read_u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def is_queued_stop_or_ack(response: str) -> bool:
    """Identify non-data packets observed once after a watch/step stop."""

    return response == "OK" or response.startswith(("S", "T")) or (
        parse_stop_watch(response)[0] is not None
    )


def read_registers_after_stop(client: GdbClient, *, retries: int = 8) -> dict[str, int]:
    """Read registers while tolerating mGBA's duplicated stop notification.

    Some watchpoint hits on the temporary mGBA build leave a second identical
    ``T05watch:...`` packet queued.  The core client correctly returns that
    packet, but it is not a register payload.  Consume only that known duplicate
    and retry the normal ``g`` request; any other malformed response remains a
    hard failure.
    """

    for attempt in range(retries + 1):
        response = client.request("g")
        if len(response) % 8 == 0:
            values = [
                int.from_bytes(bytes.fromhex(response[index:index + 8]), "little")
                for index in range(0, len(response), 8)
            ]
            if len(values) == len(REG_NAMES):
                return dict(zip(REG_NAMES, values))
        if attempt < retries and not response.startswith("E"):
            continue
        raise RuntimeError(f"malformed register response: {response!r}")
    raise AssertionError("unreachable")


def read_memory_after_stop(
    client: GdbClient,
    address: int,
    length: int,
    *,
    chunk_size: int = 0x200,
    retries: int = 8,
) -> bytes:
    """Read memory while consuming only queued duplicate stop packets."""

    output = bytearray()
    for offset in range(0, length, chunk_size):
        size = min(chunk_size, length - offset)
        for attempt in range(retries + 1):
            response = client.request(f"m{address + offset:x},{size:x}")
            if attempt < retries and is_queued_stop_or_ack(response):
                continue
            if response.startswith("E"):
                raise RuntimeError(
                    f"memory read failed at 0x{address + offset:x}: {response}"
                )
            try:
                chunk = bytes.fromhex(response)
            except ValueError as exc:
                raise RuntimeError(
                    f"malformed memory response at 0x{address + offset:x}: {response!r}"
                ) from exc
            if len(chunk) != size:
                if attempt < retries:
                    continue
                raise RuntimeError(
                    f"short memory read at 0x{address + offset:x}: "
                    f"{len(chunk)} != {size}"
                )
            output.extend(chunk)
            break
        else:
            raise AssertionError("unreachable")
    return bytes(output)


class StopTolerantMemoryClient:
    """Read-only adapter for the existing M1.6 display-map parser."""

    def __init__(self, client: GdbClient) -> None:
        self.client = client

    def read_memory(self, address: int, length: int, chunk_size: int = 0x200) -> bytes:
        return read_memory_after_stop(
            self.client, address, length, chunk_size=chunk_size,
        )


def read_display_maps_after_stop(client: GdbClient) -> tuple[dict[str, object], bytes, bytes]:
    """Reuse M1.6's layout logic through the duplicate-stop-safe adapter."""

    return read_display_maps(StopTolerantMemoryClient(client))


def change_watchpoint_after_stop(
    client: GdbClient,
    action: str,
    address: int,
    length: int,
    watch_type: int,
    *,
    retries: int = 8,
) -> None:
    """Issue Z/z while tolerating one queued non-OK response from mGBA."""

    payload = f"{action}{watch_type},{address:x},{length:x}"
    for attempt in range(retries + 1):
        response = client.request(payload)
        if response == "OK":
            return
        if attempt < retries and not response.startswith("E"):
            continue
        label = "watchpoint" if action == "Z" else "watchpoint removal"
        raise RuntimeError(f"{label} failed at 0x{address:x}: {response!r}")
    raise AssertionError("unreachable")


def is_stop_response(response: str) -> bool:
    kind, _address = parse_stop_watch(response)
    return kind is not None or response.startswith(("S", "T"))


def continue_until_stop_response(
    client: GdbClient,
    timeout: float,
    *,
    max_stale_packets: int = 8,
) -> str:
    """Continue until a stop packet, ignoring delayed command payloads."""

    deadline = time.monotonic() + timeout
    stale = 0
    while stale <= max_stale_packets:
        remaining = max(0.05, deadline - time.monotonic())
        response = client.continue_until_stop(remaining)
        if is_stop_response(response):
            return response
        stale += 1
        if time.monotonic() >= deadline:
            break
    raise TimeoutError("mGBA returned stale non-stop packets before the bounded timeout")


def step_until_stop_response(
    client: GdbClient,
    *,
    max_stale_packets: int = 4,
) -> str:
    """Single-step until mGBA returns S/T/watch rather than queued data."""

    for _attempt in range(max_stale_packets + 1):
        response = client.request("s")
        if is_stop_response(response):
            return response
    raise RuntimeError("mGBA returned stale non-stop packets during bounded step")


def write_register_after_stop(
    client: GdbClient,
    register_number: int,
    value: int,
    *,
    retries: int = 8,
) -> None:
    """Write one input register while tolerating delayed non-OK payloads."""

    raw = (value & 0xFFFFFFFF).to_bytes(4, "little").hex()
    payload = f"P{register_number:x}={raw}"
    for attempt in range(retries + 1):
        response = client.request(payload)
        if response == "OK":
            return
        if attempt < retries and not response.startswith("E"):
            continue
        raise RuntimeError(f"register write failed: {response!r}")
    raise AssertionError("unreachable")


def hash_region(
    client: GdbClient,
    address: int,
    length: int,
    *,
    max_length: int = 0x10000,
) -> dict[str, object]:
    result: dict[str, object] = {
        "address": hex32(address),
        "length": length,
        "region": region(address),
    }
    if length <= 0 or length > max_length or result["region"] == "other":
        result["status"] = "not-hashed"
        return result
    try:
        data = read_memory_after_stop(client, address & ~1, length)
    except (RuntimeError, OSError, ConnectionError) as exc:
        result["status"] = "read-failed"
        result["error"] = str(exc)
        return result
    result.update({"status": "hashed", "sha256": digest(data)})
    return result


def live_pointer_candidates(
    client: GdbClient,
    registers: dict[str, int],
    *,
    length: int = 0x20,
) -> list[dict[str, object]]:
    """Hash small live regions pointed to by writer registers.

    This is intentionally runtime-only.  It does not claim that every pointer
    register is the source operand; the instruction PC and caller context must
    corroborate a candidate before it can be called source-identical.
    """

    seen: set[tuple[int, int]] = set()
    candidates: list[dict[str, object]] = []
    for name in REGISTER_POINTER_NAMES:
        value = registers.get(name)
        if value is None:
            continue
        address = value & ~1
        if region(address) not in {"rom", "ewram", "iwram"}:
            continue
        key = (address, length)
        if key in seen:
            continue
        seen.add(key)
        item = {"register": name, **hash_region(client, address, length)}
        candidates.append(item)
    return candidates


def stack_return_candidates(
    client: GdbClient,
    registers: dict[str, int],
    *,
    length: int = 0x100,
    limit: int = 8,
) -> dict[str, object]:
    """Keep stack hash plus plausible Thumb return addresses, never raw stack."""

    sp = registers.get("sp", 0)
    result: dict[str, object] = {"sp": hex32(sp), "length": length}
    try:
        data = read_memory_after_stop(client, sp, length)
    except (RuntimeError, OSError, ConnectionError) as exc:
        result["status"] = "read-failed"
        result["error"] = str(exc)
        return result
    result["status"] = "hashed"
    result["stack_sha256"] = digest(data)
    returns: list[dict[str, object]] = []
    for offset in range(0, max(0, len(data) - 3), 4):
        value = read_u32(data, offset)
        if value & 1 and 0x08000000 <= value < 0x0A000000:
            returns.append({"stack_offset": offset, "return_bus": hex32(value)})
            if len(returns) >= limit:
                break
    result["return_candidates"] = returns
    return result


def thumb_bl_target(first: int, second: int, pc: int) -> int | None:
    """Decode one Thumb-1 BL pair, returning the odd target bus address."""

    if (first & 0xF800) != 0xF000 or (second & 0xF800) != 0xF800:
        return None
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    imm11 = second & 0x07FF
    value = (sign << 22) | (imm10 << 12) | (i1 << 11) | (i2 << 10) | (imm11 << 1)
    if sign:
        value -= 1 << 23
    return (pc + 4 + value) | 1


def find_thumb_bl_callers(
    rom: bytes,
    target_bus: int,
    *,
    limit: int = 16,
) -> list[dict[str, object]]:
    """Find ROM BL sites targeting one live writer candidate.

    This scan is only run after a runtime BG1 writer PC is observed.  It is a
    guided caller candidate list, not an unsupported claim that every matching
    BL executes in the captured transition.
    """

    target = target_bus & ~1
    hits: list[dict[str, object]] = []
    for offset in range(0, max(0, len(rom) - 3), 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        pc = 0x08000000 + offset
        decoded = thumb_bl_target(first, second, pc)
        if decoded is None or (decoded & ~1) != target:
            continue
        hits.append(
            {
                "call_site_bus": hex32(pc),
                "call_site_file_offset": hex32(offset),
                "target_bus": hex32(decoded),
                "caller_return_bus": hex32(pc + 4),
            }
        )
        if len(hits) >= limit:
            break
    return hits


def tile_metadata(address: int) -> dict[str, object] | None:
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


def tile_hash(client: GdbClient, address: int) -> dict[str, object]:
    base = address & ~0x1F
    data = read_memory_after_stop(client, base, 0x20)
    return {
        "tile_address": hex32(base),
        "tile_sha256": digest(data),
        "keyboard_position": tile_metadata(base),
    }


def overlaps(address: int, length: int, target: int, target_length: int) -> bool:
    return address < target + target_length and target < address + max(length, 1)


def safe_remove_watch(client: GdbClient, spec: dict[str, int]) -> None:
    try:
        change_watchpoint_after_stop(
            client, "z", spec["address"], spec["length"], spec["watch_type"],
        )
    except (RuntimeError, OSError, ConnectionError):
        pass


def remove_active_watches(client: GdbClient, active: dict[str, dict[str, int]]) -> None:
    """Remove only this probe's still-active points before bulk map reads."""

    for spec in list(active.values()):
        safe_remove_watch(client, spec)
    active.clear()


def arm_watch(
    client: GdbClient,
    active: dict[str, dict[str, int]],
    setup: list[dict[str, object]],
    role: str,
    address: int,
    length: int,
    watch_type: int,
    *,
    fallback_length: int | None = None,
    setup_note: str | None = None,
) -> bool:
    item: dict[str, object] = {
        "role": role,
        "requested_address": hex32(address),
        "requested_length": length,
        "watch_type": watch_type,
        "status": "requested",
    }
    attempted = [length]
    if fallback_length is not None and fallback_length != length:
        attempted.append(fallback_length)
    last_error = ""
    actual_length: int | None = None
    for candidate_length in attempted:
        try:
            change_watchpoint_after_stop(
                client, "Z", address, candidate_length, watch_type,
            )
        except (RuntimeError, OSError, ConnectionError) as exc:
            last_error = str(exc)
            continue
        actual_length = candidate_length
        break
    if actual_length is None:
        item.update({"status": "unavailable", "error": last_error, "attempted_lengths": attempted})
    else:
        active[role] = {"address": address, "length": actual_length, "watch_type": watch_type}
        item.update({"status": "armed", "actual_length": actual_length})
    if setup_note:
        item["note"] = setup_note
    setup.append(item)
    return actual_length is not None


def matching_watch(
    active: dict[str, dict[str, int]], address: int | None
) -> tuple[str, dict[str, int]] | None:
    if address is None:
        return None
    for role, spec in active.items():
        if spec["address"] <= address < spec["address"] + spec["length"]:
            return role, spec
    return None


def dma_event_metadata(
    client: GdbClient,
    channel: int,
    before: bytes,
    after: bytes,
) -> dict[str, object]:
    before_count = read_u32(before, 8)
    after_count = read_u32(after, 8)
    length_info = dma_transfer_length(channel, after_count)
    source = read_u32(after, 0)
    destination = read_u32(after, 4)
    result: dict[str, object] = {
        "channel": channel,
        "before": {
            "source": hex32(read_u32(before, 0)),
            "destination": hex32(read_u32(before, 4)),
            "count_control": hex32(before_count),
        },
        "after": {
            "source": hex32(source),
            "destination": hex32(destination),
            "count_control": hex32(after_count),
            **length_info,
        },
        "target_overlap": {
            "tile_1": overlaps(destination, length_info["length_bytes"], BG1_TILE_1, 0x20),
            "tile_2": overlaps(destination, length_info["length_bytes"], BG1_TILE_2, 0x20),
            "bg1_slice": overlaps(destination, length_info["length_bytes"], BG1_SLICE, BG1_SLICE_LENGTH),
        },
    }
    length = length_info["length_bytes"]
    if length <= 0x10000:
        result["source_hash"] = hash_region(client, source, length)
    for tile_name, tile_address in (("tile_1", BG1_TILE_1), ("tile_2", BG1_TILE_2)):
        if overlaps(destination, length, tile_address, 0x20):
            offset = tile_address - destination
            if 0 <= offset and offset + 0x20 <= length:
                result[f"source_{tile_name}_hash"] = hash_region(client, source + offset, 0x20)
    return result


def complete_step(
    client: GdbClient,
    *,
    active: dict[str, dict[str, int]],
    trace: dict[str, Any],
    state: dict[str, Any],
    phase: str,
) -> str:
    """Complete the watched instruction and accept a nested watch.

    A watchpoint can leave more than one stop notification queued.  A packet
    that names no still-active watch is consumed as that duplicate; the step is
    retried so a genuinely nested watch is not mistaken for a completed step.
    """

    for attempt in range(3):
        response = step_until_stop_response(client)
        kind, address = parse_stop_watch(response)
        if kind is None:
            return response
        if matching_watch(active, address) is not None:
            process_watch_stop(
                client,
                response,
                active=active,
                trace=trace,
                state=state,
                phase=f"{phase}:step",
            )
            return response
        if attempt == 2:
            trace["unexpected_stops"].append(
                {
                    "phase": f"{phase}:step",
                    "stop": response,
                    "stop_kind": kind,
                    "stop_address": None if address is None else hex32(address),
                    "reason": "queued-stop-without-active-watch",
                }
            )
            return response
    raise AssertionError("unreachable")


def process_watch_stop(
    client: GdbClient,
    stop: str,
    *,
    active: dict[str, dict[str, int]],
    trace: dict[str, Any],
    state: dict[str, Any],
    phase: str,
) -> None:
    kind, address = parse_stop_watch(stop)
    found = matching_watch(active, address)
    registers = read_registers_after_stop(client)
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
    active.pop(role)
    safe_remove_watch(client, spec)
    event: dict[str, object] = {
        "index": state["event_index"],
        "phase": phase,
        "role": role,
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else hex32(address),
        "registers": register_snapshot(registers),
        "writer_pc": hex32(registers["pc"]),
        "lr": hex32(registers["lr"]),
        "writer_class": classify_pc(registers["pc"]),
    }
    state["event_index"] += 1

    if role.startswith("bg1_tile_") or role == "bg1_slice":
        base = BG1_TILE_1 if role.endswith("tile_1") else BG1_TILE_2 if role.endswith("tile_2") else (address or BG1_SLICE)
        event["target_tile"] = tile_metadata(base)
        event["tile_hash_at_stop"] = tile_hash(client, base)
        event["live_pointer_candidates"] = live_pointer_candidates(client, registers)
        event["stack_call_candidates"] = stack_return_candidates(client, registers)
        event["matching_dma_event_indices"] = [
            item["index"]
            for item in trace["dma_control_writes"]
            if item.get("dma", {}).get("target_overlap", {}).get("bg1_slice")
        ]
        event["mechanism_initial"] = (
            "bios-copy-candidate" if event["writer_class"] == "bios"
            else "cpu-or-dma-candidate" if event["writer_class"] == "cpu-game-rom"
            else "unknown-writer"
        )
        event["step_after_watch"] = complete_step(
            client, active=active, trace=trace, state=state, phase=phase,
        )
        event["tile_hash_after_step"] = tile_hash(client, base)
        trace["bg1_writes"].append(event)
    elif role == "bg1cnt":
        event["value_at_stop"] = hex32(int.from_bytes(read_memory_after_stop(client, BG1CNT, 2), "little"))
        event["decode_at_stop"] = decode_bgcnt(int(event["value_at_stop"], 16))
        event["step_after_watch"] = complete_step(
            client, active=active, trace=trace, state=state, phase=phase,
        )
        after_value = int.from_bytes(read_memory_after_stop(client, BG1CNT, 2), "little")
        event["value_after_step"] = hex32(after_value)
        event["decode_after_step"] = decode_bgcnt(after_value)
        trace["bg1cnt_writes"].append(event)
    elif role.startswith("dma"):
        channel = int(role.split("_")[1])
        base = DMA_BASES[channel]
        before = read_memory_after_stop(client, base, DMA_REGISTER_LENGTH)
        event["step_after_watch"] = complete_step(
            client, active=active, trace=trace, state=state, phase=phase,
        )
        after = read_memory_after_stop(client, base, DMA_REGISTER_LENGTH)
        event["dma"] = dma_event_metadata(client, channel, before, after)
        trace["dma_control_writes"].append(event)
        state["dma_hits"][channel] = state["dma_hits"].get(channel, 0) + 1
        if state["dma_hits"][channel] < state["max_dma_hits"]:
            arm_watch(
                client,
                active,
                state["watch_setup"],
                role,
                base + DMA_CONTROL_OFFSET,
                4,
                2,
                setup_note=f"rearm {state['dma_hits'][channel]}/{state['max_dma_hits'] - 1}",
            )
    else:
        trace["other_watch_hits"].append(event)
        event["step_after_watch"] = complete_step(
            client, active=active, trace=trace, state=state, phase=phase,
        )


def run_window(
    client: GdbClient,
    *,
    seconds: float,
    event_timeout: float,
    active: dict[str, dict[str, int]],
    trace: dict[str, Any],
    state: dict[str, Any],
    phase: str,
    max_stops: int,
) -> dict[str, object]:
    deadline = time.monotonic() + seconds
    stops = 0
    while stops < max_stops and time.monotonic() < deadline:
        remaining = min(event_timeout, max(0.05, deadline - time.monotonic()))
        try:
            stop = continue_until_stop_response(client, remaining)
        except TimeoutError:
            try:
                terminal = client.interrupt(timeout=2.0)
            except (TimeoutError, OSError, ConnectionError) as exc:
                return {"phase": phase, "stops": stops, "termination": "interrupt-failed", "error": str(exc)}
            return {
                "phase": phase,
                "stops": stops,
                "termination": "bounded-timeout-interrupted",
                "terminal_stop": terminal,
            }
        stops += 1
        if parse_stop_watch(stop)[0] is not None:
            process_watch_stop(
                client, stop, active=active, trace=trace, state=state, phase=phase,
            )
            continue
        trace["non_watch_stops"].append(
            {"phase": phase, "stop": stop, "registers": register_snapshot(read_registers_after_stop(client))}
        )
        return {"phase": phase, "stops": stops, "termination": "unexpected-non-watch-stop"}
    return {"phase": phase, "stops": stops, "termination": "bounded-stop-cap"}


def inject_button(
    client: GdbClient,
    button: str,
    *,
    input_register: int,
    hold_events: int,
    release_events: int,
    event_timeout: float,
    active: dict[str, dict[str, int]],
    trace: dict[str, Any],
    state: dict[str, Any],
    prepare_asset_watches: Callable[[], None] | None = None,
) -> dict[str, object]:
    desired = button_value(button)
    events: list[dict[str, object]] = []
    change_watchpoint_after_stop(client, "Z", KEYINPUT, 2, 3)
    if prepare_asset_watches is not None:
        prepare_asset_watches()
    try:
        for index in range(hold_events + release_events):
            try:
                stop = continue_until_stop_response(client, event_timeout)
            except TimeoutError:
                try:
                    terminal = client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError) as exc:
                    return {
                        "button": button,
                        "events": events,
                        "termination": "keyinput-timeout-interrupt-failed",
                        "error": str(exc),
                    }
                return {
                    "button": button,
                    "events": events,
                    "termination": "keyinput-timeout-interrupted",
                    "terminal_stop": terminal,
                }
            kind, address = parse_stop_watch(stop)
            if address == KEYINPUT:
                registers = read_registers_after_stop(client)
                value = desired if index < hold_events else NO_KEY
                events.append(
                    {
                        "index": index,
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": hex32(KEYINPUT),
                        "requested_keyinput": hex32(value),
                        "registers": register_snapshot(registers),
                    }
                )
                write_register_after_stop(client, input_register, value)
                continue
            process_watch_stop(
                client, stop, active=active, trace=trace, state=state, phase=f"{button}:{index}",
            )
            events.append({"index": index, "role": "non-key-watch", "stop": stop})
    finally:
        change_watchpoint_after_stop(client, "z", KEYINPUT, 2, 3)
    return {
        "button": button,
        "hold_events": hold_events,
        "release_events": release_events,
        "events": events,
        "termination": "completed",
    }


def keyboard_tiles(client: GdbClient) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for slot, label, tile_id, address, known_hash in KEYBOARD_TILE_METADATA:
        data = read_memory_after_stop(client, address, 0x20)
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


def initial_trace() -> dict[str, Any]:
    return {
        "bg1_writes": [],
        "bg1cnt_writes": [],
        "dma_control_writes": [],
        "other_watch_hits": [],
        "non_watch_stops": [],
        "unexpected_stops": [],
        "errors": [],
    }


def identity_results(trace: dict[str, Any], final_tiles: list[dict[str, object]]) -> list[dict[str, object]]:
    final_by_slot = {str(item["slot"]): item for item in final_tiles}
    results: list[dict[str, object]] = []
    for slot, label, tile_id, address, known_hash in KEYBOARD_TILE_METADATA[:2]:
        hits = [
            item for item in trace["bg1_writes"]
            if isinstance(item.get("target_tile"), dict)
            and item["target_tile"].get("slot") == slot
        ]
        candidates: list[dict[str, object]] = []
        for hit in hits:
            after = hit.get("tile_hash_after_step", {})
            after_hash = after.get("tile_sha256") if isinstance(after, dict) else None
            dma_matches = []
            for event in trace["dma_control_writes"]:
                dma = event.get("dma", {})
                overlap = dma.get("target_overlap", {}) if isinstance(dma, dict) else {}
                if overlap.get("bg1_slice"):
                    source_tile = dma.get(f"source_{'tile_1' if tile_id == 1 else 'tile_2'}_hash", {})
                    source_hash = source_tile.get("sha256") if isinstance(source_tile, dict) else None
                    dma_matches.append({
                        "event_index": event.get("index"),
                        "source_tile_sha256": source_hash,
                        "byte_identical_to_final": source_hash == after_hash == known_hash,
                    })
            candidates.append(
                {
                    "writer_pc": hit.get("writer_pc"),
                    "writer_class": hit.get("writer_class"),
                    "mechanism_initial": hit.get("mechanism_initial"),
                    "tile_hash_after_step": after_hash,
                    "known_tile_sha256": known_hash,
                    "hash_matches_known": after_hash == known_hash,
                    "dma_candidates": dma_matches,
                }
            )
        confirmed = any(
            candidate["hash_matches_known"]
            and any(item["byte_identical_to_final"] for item in candidate["dma_candidates"])
            for candidate in candidates
        )
        results.append(
            {
                "slot": slot,
                "known_layout_label": label,
                "tile_id": tile_id,
                "final_tile_hash": final_by_slot.get(slot, {}).get("sha256"),
                "write_hit_count": len(hits),
                "status": "confirmed" if confirmed else "provisional" if hits else "unknown",
                "candidates": candidates,
            }
        )
    return results


def compare_font_path(trace: dict[str, Any]) -> dict[str, object]:
    writer_lrs = {item.get("lr") for item in trace["bg1_writes"]}
    writer_pcs = {item.get("writer_pc") for item in trace["bg1_writes"]}
    record_like = any(
        item.get("writer_class") == "cpu-game-rom"
        and item.get("lr") == hex32(FONT_CALLER_LR)
        for item in trace["bg1_writes"]
    )
    return {
        "known_font_caller_lr": hex32(FONT_CALLER_LR),
        "bg1_writer_lrs": sorted(value for value in writer_lrs if value),
        "bg1_writer_pcs": sorted(value for value in writer_pcs if value),
        "same_as_known_font_caller_lr": record_like,
        "font_record_path_shared_status": "shared-caller-candidate" if record_like else "no-shared-lr-observed",
        "font_record_formula": f"{hex32(FONT_RECORD_BASE)} + code_unit * 0x{FONT_RECORD_STRIDE:X}",
    }


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=0.75)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--max-dma-hits", type=int, default=4)
    parser.add_argument("--max-window-stops", type=int, default=64)
    parser.add_argument("--watch-slice", action="store_true")
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.input_register <= 12:
        parser.error("input-register must be r0..r12")
    if args.max_dma_hits < 1:
        parser.error("max-dma-hits must be positive")

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "scope": {
            "milestone": "M1.8",
            "watch_from": "initial GDB stop before runtime continue",
            "navigation": "bounded settle then adaptive START until BG1 keyboard signature",
            "input_register": f"r{args.input_register}",
            "bg1cnt": {
                "address": hex32(BG1CNT),
                "watch": "2-byte write",
                "expected_charbase_offset": hex32(BG1_CHARBLOCK),
            },
            "bg1_targets": {
                "tile_1": hex32(BG1_TILE_1),
                "tile_2": hex32(BG1_TILE_2),
                "slice": {"address": hex32(BG1_SLICE), "length": BG1_SLICE_LENGTH},
                "mode": "bounded-0x100-slice" if args.watch_slice else "two-32-byte-tiles",
            },
            "dma_channels": {
                str(channel): {"base": hex32(base), "control": hex32(base + DMA_CONTROL_OFFSET)}
                for channel, base in DMA_BASES.items()
            },
            "raw_policy": "ROM, RAM, VRAM and rendered images remain in private/ignored dump-dir",
        },
        "navigation": [],
        "trace": initial_trace(),
    }
    trace = report["trace"]
    assert isinstance(trace, dict)
    state: dict[str, Any] = {
        "event_index": 0,
        "dma_hits": {},
        "max_dma_hits": args.max_dma_hits,
        "watch_setup": [],
    }
    active: dict[str, dict[str, int]] = {}
    client = GdbClient(args.host, args.port, timeout=8.0)
    rom = args.rom.read_bytes()
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(read_registers_after_stop(client))

        setup = state["watch_setup"]
        def arm_asset_watches() -> None:
            arm_watch(client, active, setup, "bg1cnt", BG1CNT, 2, 2)
            if args.watch_slice:
                arm_watch(
                    client, active, setup, "bg1_slice", BG1_SLICE, BG1_SLICE_LENGTH, 2,
                    fallback_length=0x20,
                    setup_note="bounded first 0x100 bytes of BG1 charblock",
                )
            else:
                arm_watch(
                    client, active, setup, "bg1_tile_1", BG1_TILE_1, 0x20, 2,
                    fallback_length=2,
                    setup_note="tile ID 1 at keyboard (1,7)",
                )
                arm_watch(
                    client, active, setup, "bg1_tile_2", BG1_TILE_2, 0x20, 2,
                    fallback_length=2,
                    setup_note="tile ID 2 at keyboard (2,7)",
                    )
            for channel, base in DMA_BASES.items():
                arm_watch(
                    client, active, setup, f"dma_{channel}", base + DMA_CONTROL_OFFSET, 4, 2,
                    setup_note=f"DMA{channel} source/destination/count read after control store",
                )

        arm_asset_watches()
        report["watch_setup"] = setup

        report["boot_window"] = run_window(
            client,
            seconds=args.settle_seconds,
            event_timeout=args.event_timeout,
            active=active,
            trace=trace,
            state=state,
            phase="reset-to-settle",
            max_stops=args.max_window_stops,
        )
        # Keep the asset watches armed across the bounded START transition.
        # Reading large BG maps while a stop notification is pending can make
        # the temporary mGBA stub cross command boundaries, so the gate is
        # sampled only after this two-press window and after our points are
        # removed.
        for _ in range(2):
            remove_active_watches(client, active)
            navigation = inject_button(
                client,
                "start",
                input_register=args.input_register,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
                active=active,
                trace=trace,
                state=state,
                prepare_asset_watches=arm_asset_watches,
            )
            report["navigation"].append(navigation)
            report["navigation"].append(
                run_window(
                    client,
                    seconds=args.step_settle_seconds,
                    event_timeout=args.event_timeout,
                    active=active,
                    trace=trace,
                    state=state,
                    phase="after-start",
                    max_stops=args.max_window_stops,
                )
            )
        remove_active_watches(client, active)
        screen, _bg0, _bg1 = read_display_maps_after_stop(client)
        report["post_navigation_screen"] = screen
        report["keyboard_gate"] = screen["keyboard_layout"]
        report["pre_input_keyboard_tiles"] = keyboard_tiles(client)
        report["post_window_keyboard_tiles"] = report["pre_input_keyboard_tiles"]
        report["identity_results"] = identity_results(
            trace, report["pre_input_keyboard_tiles"]
        )
        report["font_path_comparison"] = compare_font_path(trace)
        report["trace_summary"] = {
            "bg1_write_count": len(trace["bg1_writes"]),
            "bg1cnt_write_count": len(trace["bg1cnt_writes"]),
            "dma_control_write_count": len(trace["dma_control_writes"]),
            "confirmed_identity_count": sum(
                item["status"] == "confirmed" for item in report["identity_results"]
            ),
            "provisional_identity_count": sum(
                item["status"] == "provisional" for item in report["identity_results"]
            ),
        }
        if not screen["keyboard_layout"]["confirmed"]:
            report["termination"] = "keyboard-gate-failed"
        else:
            report["gate_boundary"] = "keyboard signature confirmed after bounded navigation"

        # Guided caller candidates are calculated only from live writer PCs;
        # this avoids pretending that an unconstrained ROM BL scan found text.
        writer_targets: set[int] = set()
        for event in trace["bg1_writes"]:
            pc = event.get("writer_pc")
            if isinstance(pc, str):
                try:
                    base_pc = int(pc, 16) & ~1
                except ValueError:
                    continue
                writer_targets.update(max(0x08000000, base_pc - delta) for delta in (0, 2, 4, 6))
        report["guided_thumb_bl_callers"] = {
            hex32(target): find_thumb_bl_callers(rom, target)
            for target in sorted(writer_targets)
            if 0x08000000 <= target < 0x0A000000
        }

        for spec in list(active.values()):
            safe_remove_watch(client, spec)
        active.clear()
        # The bounded interrupt used to settle the final screen may leave one
        # S02 packet queued.  Prime the shared capture with the same guarded
        # register read; capture_runtime itself remains unchanged and is still
        # the source of the standard hashes/dumps.
        try:
            report["pre_capture_register_prime"] = register_snapshot(
                read_registers_after_stop(client)
            )
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
        except (RuntimeError, TimeoutError, OSError, ConnectionError) as exc:
            report["core_capture_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "boundary": "shared capture packet synchronization after game trace",
            }
            report["termination"] = "bounded-trace-complete-core-capture-limited"
        if "termination" not in report:
            report["termination"] = "bounded-transition-complete"
    finally:
        for spec in list(active.values()):
            safe_remove_watch(client, spec)
        active.clear()
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
