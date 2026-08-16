#!/usr/bin/env python3
"""Bounded A9PJ name-entry input, RAM-diff, and consumer probe.

This probe reuses the M1.5 KEYINPUT path and the shared ``core/gba`` client and
capture.  It reaches the already identified name-entry screen, inputs the
known first-row kana positions ``あ`` then ``い``, and compares full EWRAM and
IWRAM snapshots around those actions.  JSON contains hashes, changed ranges,
short code-unit candidates, stop registers, and tilemap metadata only.  Raw
regions are written only to the caller's ignored/private dump directory.

Run once without ``--write-watch-address`` to obtain bounded diff candidates.
Run again on a fresh mGBA process with the selected candidate address to record
the writer PC/LR.  ``--read-watch-address`` arms a one-shot read watchpoint
before the second known kana so the display-side consumer can be observed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


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
from m16_keyboard_metadata import analyze as analyze_keyboard  # noqa: E402
from m16_keyboard_metadata import KNOWN_KANA  # noqa: E402


VRAM = 0x06000000
EWRAM = 0x02000000
EWRAM_SIZE = 0x40000
IWRAM = 0x03000000
IWRAM_SIZE = 0x8000
DISPCNT = 0x04000000
BG0CNT = 0x04000008
BG1_SCREENBASE = 0x0800
SCREENBLOCK_BYTES = 0x800
READ_CHUNK = 0x200
EXPECTED_KEYBOARD_TILE_IDS = (1, 2, 3, 4, 5, 27, 28, 29)
FONT_RECORD_TABLE_BASE = 0x08089E00
FONT_RECORD_STRIDE = 0x18
REGISTER_NAMES = {
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
    "r10", "r11", "r12", "sp", "lr", "pc", "cpsr",
}


def is_ram_address(address: int) -> bool:
    """Keep optional watchpoints inside the two sampled working-RAM regions."""

    return (
        EWRAM <= address < EWRAM + EWRAM_SIZE
        or IWRAM <= address < IWRAM + IWRAM_SIZE
    )


def parse_address(value: str | None) -> int | None:
    return None if value is None else int(value, 0)


def font_record_address(code_unit: int) -> int:
    """Map the observed renderer code unit to its ROM font-record address."""

    if not 0 <= code_unit <= 0xFFFF:
        raise ValueError("code unit must fit an unsigned 16-bit value")
    return FONT_RECORD_TABLE_BASE + code_unit * FONT_RECORD_STRIDE


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    """Keep all GPRs needed to interpret the writer/reader call sites."""

    return {
        name: f"0x{value:08X}"
        for name, value in registers.items()
        if name in REGISTER_NAMES
    }


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def memory_summary(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08X}",
        "length": len(data),
        "sha256": digest(data),
        "nonzero_bytes": sum(value != 0 for value in data),
    }


def read_memory_snapshot(client: GdbClient) -> dict[str, bytes]:
    """Read bounded full EWRAM/IWRAM images while the target is stopped."""

    return {
        "ewram": client.read_memory(EWRAM, EWRAM_SIZE, chunk_size=READ_CHUNK),
        "iwram": client.read_memory(IWRAM, IWRAM_SIZE, chunk_size=READ_CHUNK),
    }


def diff_ranges(
    before: bytes,
    after: bytes,
    base_address: int,
    *,
    max_ranges: int = 96,
) -> dict[str, object]:
    """Summarize changed runs without returning the raw memory image."""

    if len(before) != len(after):
        raise ValueError("memory snapshots must have equal lengths")
    changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
    runs: list[dict[str, object]] = []
    if changed:
        start = previous = changed[0]
        for index in changed[1:] + [None]:
            if index is not None and index == previous + 1:
                previous = index
                continue
            length = previous - start + 1
            left = before[start:previous + 1]
            right = after[start:previous + 1]
            if len(runs) < max_ranges:
                runs.append(
                    {
                        "address": f"0x{base_address + start:08X}",
                        "offset": start,
                        "length": length,
                        "changed_bytes": sum(a != b for a, b in zip(left, right)),
                        "before_sha256": digest(left),
                        "after_sha256": digest(right),
                    }
                )
            start = index
            if index is not None:
                previous = index
    return {
        "base_address": f"0x{base_address:08X}",
        "length": len(before),
        "changed_bytes": len(changed),
        "changed_run_count": sum(
            1
            for index, next_index in zip(changed, changed[1:])
            if next_index != index + 1
        ) + (1 if changed else 0),
        "first_changed_address": None if not changed else f"0x{base_address + changed[0]:08X}",
        "last_changed_address": None if not changed else f"0x{base_address + changed[-1]:08X}",
        "runs": runs,
        "runs_omitted": max(0, (sum(
            1
            for index, next_index in zip(changed, changed[1:])
            if next_index != index + 1
        ) + (1 if changed else 0)) - len(runs)),
    }


def word(data: bytes, offset: int, width: int = 2) -> int:
    return int.from_bytes(data[offset:offset + width], "little")


def append_candidates(
    before: bytes,
    first: bytes,
    second: bytes,
    base_address: int,
    *,
    max_candidates: int = 64,
) -> list[dict[str, object]]:
    """Find stable-first-word plus adjacent-second-word append patterns."""

    candidates: list[dict[str, object]] = []
    for offset in range(0, len(before) - 4, 2):
        before_first = word(before, offset)
        first_first = word(first, offset)
        second_first = word(second, offset)
        first_second = word(first, offset + 2)
        second_second = word(second, offset + 2)
        if before_first == first_first or first_first != second_first:
            continue
        if first_second == second_second:
            continue
        candidates.append(
            {
                "address": f"0x{base_address + offset:08X}",
                "offset": offset,
                "width": 2,
                "first_code_unit_le": f"0x{first_first:04X}",
                "second_slot_before_le": f"0x{first_second:04X}",
                "second_code_unit_le": f"0x{second_second:04X}",
                "before_word_sha256": digest(before[offset:offset + 4]),
                "first_word_sha256": digest(first[offset:offset + 4]),
                "second_word_sha256": digest(second[offset:offset + 4]),
            }
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def read_display_maps(client: GdbClient) -> tuple[dict[str, object], bytes, bytes]:
    """Read I/O plus BG0/BG1 maps, not full raw VRAM."""

    dispcnt = int.from_bytes(client.read_memory(DISPCNT, 2), "little")
    bgcnt = [
        int.from_bytes(client.read_memory(BG0CNT + index * 2, 2), "little")
        for index in range(4)
    ]
    bg0 = client.read_memory(VRAM, SCREENBLOCK_BYTES, chunk_size=READ_CHUNK)
    bg1 = client.read_memory(VRAM + BG1_SCREENBASE, SCREENBLOCK_BYTES, chunk_size=READ_CHUNK)
    selected_entries = []
    for slot, label, x, y in KNOWN_KANA:
        entry = int.from_bytes(bg1[2 * (y * 32 + x):2 * (y * 32 + x) + 2], "little")
        selected_entries.append(
            {
                "slot": slot,
                "known_layout_label": label,
                "x": x,
                "y": y,
                "entry": f"0x{entry:04X}",
                "tile_id": entry & 0x03FF,
                "hflip": (entry >> 10) & 1,
                "vflip": (entry >> 11) & 1,
                "palette_bank": (entry >> 12) & 0x0F,
            }
        )
    tile_ids = [entry["tile_id"] for entry in selected_entries]
    layout_matches = sum(
        actual == expected
        for actual, expected in zip(tile_ids, EXPECTED_KEYBOARD_TILE_IDS)
    )
    return (
        {
            "dispcnt": f"0x{dispcnt:04X}",
            "bgcnt": [f"0x{value:04X}" for value in bgcnt],
            "bg0_screenblock_sha256": digest(bg0),
            "bg1_screenblock_sha256": digest(bg1),
            "keyboard_layout": {
                "selected_tile_ids": tile_ids,
                "expected_tile_ids": list(EXPECTED_KEYBOARD_TILE_IDS),
                "position_match_count": layout_matches,
                "selected_positions": selected_entries,
                "confirmed": (
                    dispcnt == 0x1B40
                    and bgcnt[1] == 0x0106
                    and layout_matches == len(EXPECTED_KEYBOARD_TILE_IDS)
                ),
            },
        },
        bg0,
        bg1,
    )


def tilemap_diffs(before: bytes, after: bytes, *, max_entries: int = 64) -> dict[str, object]:
    """Summarize changed 16-bit tilemap entries, including flags only."""

    if len(before) != SCREENBLOCK_BYTES or len(after) != SCREENBLOCK_BYTES:
        raise ValueError("screenblock snapshots must be 0x800 bytes")
    changed: list[dict[str, object]] = []
    total = 0
    for index in range(0, SCREENBLOCK_BYTES, 2):
        left = before[index:index + 2]
        right = after[index:index + 2]
        if left == right:
            continue
        total += 1
        if len(changed) >= max_entries:
            continue
        left_value = int.from_bytes(left, "little")
        right_value = int.from_bytes(right, "little")
        changed.append(
            {
                "x": (index // 2) % 32,
                "y": (index // 2) // 32,
                "before_entry": f"0x{left_value:04X}",
                "after_entry": f"0x{right_value:04X}",
                "before_tile_id": left_value & 0x03FF,
                "after_tile_id": right_value & 0x03FF,
                "after_hflip": (right_value >> 10) & 1,
                "after_vflip": (right_value >> 11) & 1,
                "after_palette_bank": (right_value >> 12) & 0x0F,
            }
        )
    return {
        "changed_entry_count": total,
        "entries_omitted": max(0, total - len(changed)),
        "entries": changed,
    }


def watch_record(
    stop: str,
    client: GdbClient,
    *,
    index: int,
    role: str,
    watched_address: int | None = None,
) -> dict[str, object]:
    kind, address = parse_stop_watch(stop)
    registers = client.read_registers()
    record: dict[str, object] = {
        "index": index,
        "role": role,
        "stop": stop,
        "stop_kind": kind,
        "stop_address": None if address is None else f"0x{address:08X}",
        "registers": register_snapshot(registers),
    }
    if watched_address is not None:
        record["watched_address"] = f"0x{watched_address:08X}"
        record["code_unit_le_at_stop"] = f"0x{int.from_bytes(client.read_memory(watched_address, 2), 'little'):04X}"
    return record


def drive_button_with_watches(
    client: GdbClient,
    button: str,
    *,
    input_register: int,
    hold_events: int,
    release_events: int,
    event_timeout: float,
    watches: dict[str, tuple[int, int]],
) -> dict[str, object]:
    """Inject one button while accepting one-shot read/write watch stops."""

    desired = button_value(button)
    events: list[dict[str, object]] = []
    hits: list[dict[str, object]] = []
    active = dict(watches)
    termination = "completed"
    client.set_watchpoint(KEYINPUT, kind=2, watch_type=3)
    for role, (address, watch_type) in active.items():
        client.set_watchpoint(address, kind=2, watch_type=watch_type)
    try:
        for index in range(hold_events + release_events):
            try:
                stop = client.continue_until_stop(event_timeout)
            except TimeoutError:
                termination = "watchpoint-timeout"
                try:
                    interrupt_stop = client.interrupt(timeout=2.0)
                    events.append(watch_record(interrupt_stop, client, index=index, role="interrupt"))
                except (TimeoutError, OSError, ConnectionError):
                    termination = "watchpoint-timeout-interrupt-failed"
                break

            kind, address = parse_stop_watch(stop)
            if address == KEYINPUT:
                events.append(
                    {
                        "index": index,
                        "role": "keyinput",
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": f"0x{KEYINPUT:08X}",
                        "requested_keyinput": f"0x{(desired if index < hold_events else NO_KEY):04X}",
                        "registers": register_snapshot(client.read_registers()),
                    }
                )
                client.write_register(
                    input_register,
                    desired if index < hold_events else NO_KEY,
                )
                continue

            matching_role = next(
                (
                    role
                    for role, (watch_address, _watch_type) in active.items()
                    if address == watch_address
                ),
                None,
            )
            if matching_role is None:
                termination = "unexpected-stop"
                events.append(watch_record(stop, client, index=index, role="unexpected"))
                break

            watch_address, watch_type = active.pop(matching_role)
            # Remove a one-shot watchpoint before reading the watched word.
            # A read watchpoint would otherwise fire again on this diagnostic
            # ``m`` packet and desynchronise the remote stub response.
            client.remove_watchpoint(watch_address, kind=2, watch_type=watch_type)
            hit = watch_record(
                stop,
                client,
                index=index,
                role=matching_role,
                watched_address=watch_address,
            )
            hits.append(hit)
            # mGBA enters before the memory operation.  Complete it once with
            # the shared client's single-step, then continue the input loop.
            hit["step_after_watch"] = client.request("s")
            hit["code_unit_le_after_step"] = f"0x{int.from_bytes(client.read_memory(watch_address, 2), 'little'):04X}"
    finally:
        client.remove_watchpoint(KEYINPUT, kind=2, watch_type=3)
        for _role, (address, watch_type) in active.items():
            client.remove_watchpoint(address, kind=2, watch_type=watch_type)
    return {
        "button": button,
        "hold_events": hold_events,
        "release_events": release_events,
        "termination": termination,
        "events": events,
        "watch_hits": hits,
        "watch_hit_count": len(hits),
    }


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--event-timeout", type=float, default=3.0)
    parser.add_argument("--settle-seconds", type=float, default=5.0)
    parser.add_argument("--step-settle-seconds", type=float, default=0.75)
    parser.add_argument("--hold-events", type=int, default=18)
    parser.add_argument("--release-events", type=int, default=6)
    parser.add_argument("--input-register", type=int, default=1)
    parser.add_argument("--write-watch-address", type=parse_address)
    parser.add_argument("--read-watch-address", type=parse_address)
    parser.add_argument("--dump-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.input_register <= 12:
        parser.error("input register must be r0..r12")
    if args.write_watch_address is not None and not is_ram_address(args.write_watch_address):
        parser.error("write-watch-address must be inside sampled EWRAM or IWRAM")
    if args.read_watch_address is not None and not is_ram_address(args.read_watch_address):
        parser.error("read-watch-address must be inside sampled EWRAM or IWRAM")

    report: dict[str, object] = {
        "rom": identity(args.rom),
        "scope": {
            "navigation": "adaptive START navigation, bounded by the known BG1 keyboard signature",
            "input_plan": [
                {"button": "a", "known_slot": "a-row-1", "known_layout_label": "あ", "tilemap_xy": [1, 7]},
                {"button": "right", "known_effect": "bounded step to row-0 selection 2 (0x0066 / う)", "tilemap_xy": [2, 7]},
                {"button": "a", "known_slot": "row0-selection-2", "known_layout_label": "う", "tilemap_xy": [2, 7]},
            ],
            "ewram": {"address": f"0x{EWRAM:08X}", "length": EWRAM_SIZE},
            "iwram": {"address": f"0x{IWRAM:08X}", "length": IWRAM_SIZE},
            "keyinput": {"address": f"0x{KEYINPUT:08X}", "destination_register": f"r{args.input_register}"},
            "write_watch_address": None if args.write_watch_address is None else f"0x{args.write_watch_address:08X}",
            "read_watch_address": None if args.read_watch_address is None else f"0x{args.read_watch_address:08X}",
        },
        "navigation": [],
    }

    client = GdbClient("127.0.0.1", args.port, timeout=8.0)
    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())
        report["settle_stop"] = client.continue_and_interrupt(args.settle_seconds)
        initial_screen, _initial_bg0, _initial_bg1 = read_display_maps(client)
        report["pre_navigation_screen"] = initial_screen

        for step_index in range(2):
            if initial_screen["keyboard_layout"]["confirmed"]:
                break
            navigation_step = press_button(
                client,
                "start",
                input_register=args.input_register,
                hold_events=args.hold_events,
                release_events=args.release_events,
                event_timeout=args.event_timeout,
            )
            client.continue_and_interrupt(args.step_settle_seconds)
            screen, _bg0, _bg1 = read_display_maps(client)
            navigation_step["screen"] = screen
            report["navigation"].append(navigation_step)
            initial_screen = screen

        report["navigation_termination"] = (
            "keyboard-layout-confirmed"
            if initial_screen["keyboard_layout"]["confirmed"]
            else "keyboard-layout-not-confirmed"
        )
        if not initial_screen["keyboard_layout"]["confirmed"]:
            report["bounded_input_skipped"] = True
            report["reason"] = (
                "The bounded START navigation did not reproduce the known BG1 keyboard; "
                "no A/RIGHT/A input or RAM watchpoint was attempted."
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"wrote {args.output}")
            return

        pre_screen, pre_bg0, pre_bg1 = read_display_maps(client)
        pre_memory = read_memory_snapshot(client)
        report["pre_input_screen"] = pre_screen
        report["pre_input_memory"] = {
            "ewram": memory_summary(pre_memory["ewram"], EWRAM),
            "iwram": memory_summary(pre_memory["iwram"], IWRAM),
        }

        writer_watches = {}
        if args.write_watch_address is not None:
            writer_watches["writer"] = (args.write_watch_address, 2)
        first_input = drive_button_with_watches(
            client,
            "a",
            input_register=args.input_register,
            hold_events=args.hold_events,
            release_events=args.release_events,
            event_timeout=args.event_timeout,
            watches=writer_watches,
        )
        client.continue_and_interrupt(args.step_settle_seconds)
        first_screen, first_bg0, first_bg1 = read_display_maps(client)
        first_memory = read_memory_snapshot(client)
        report["first_input"] = first_input
        report["after_first_screen"] = first_screen
        report["after_first_memory"] = {
            "ewram": memory_summary(first_memory["ewram"], EWRAM),
            "iwram": memory_summary(first_memory["iwram"], IWRAM),
        }

        args.dump_dir.mkdir(parents=True, exist_ok=True)
        (args.dump_dir / "ewram_before.bin").write_bytes(pre_memory["ewram"])
        (args.dump_dir / "iwram_before.bin").write_bytes(pre_memory["iwram"])
        (args.dump_dir / "ewram_after_first.bin").write_bytes(first_memory["ewram"])
        (args.dump_dir / "iwram_after_first.bin").write_bytes(first_memory["iwram"])

        if args.read_watch_address is not None:
            read_watches = {"reader": (args.read_watch_address, 3)}
        else:
            read_watches = {}
        move_right = drive_button_with_watches(
            client,
            "right",
            input_register=args.input_register,
            hold_events=args.hold_events,
            release_events=args.release_events,
            event_timeout=args.event_timeout,
            watches=read_watches,
        )
        if move_right["watch_hit_count"]:
            read_watches = {}
        second_input = drive_button_with_watches(
            client,
            "a",
            input_register=args.input_register,
            hold_events=args.hold_events,
            release_events=args.release_events,
            event_timeout=args.event_timeout,
            watches=read_watches,
        )
        client.continue_and_interrupt(args.step_settle_seconds)
        second_screen, second_bg0, second_bg1 = read_display_maps(client)
        second_memory = read_memory_snapshot(client)
        report["move_right"] = move_right
        report["second_input"] = second_input
        report["after_second_screen"] = second_screen
        report["after_second_memory"] = {
            "ewram": memory_summary(second_memory["ewram"], EWRAM),
            "iwram": memory_summary(second_memory["iwram"], IWRAM),
        }
        (args.dump_dir / "ewram_after_second.bin").write_bytes(second_memory["ewram"])
        (args.dump_dir / "iwram_after_second.bin").write_bytes(second_memory["iwram"])

        ewram_candidates = append_candidates(
            pre_memory["ewram"], first_memory["ewram"], second_memory["ewram"], EWRAM
        )
        iwram_candidates = append_candidates(
            pre_memory["iwram"], first_memory["iwram"], second_memory["iwram"], IWRAM
        )
        report["diffs"] = {
            "ewram_before_to_first": diff_ranges(pre_memory["ewram"], first_memory["ewram"], EWRAM),
            "iwram_before_to_first": diff_ranges(pre_memory["iwram"], first_memory["iwram"], IWRAM),
            "ewram_first_to_second": diff_ranges(first_memory["ewram"], second_memory["ewram"], EWRAM),
            "iwram_first_to_second": diff_ranges(first_memory["iwram"], second_memory["iwram"], IWRAM),
            "ewram_append_candidates": ewram_candidates,
            "iwram_append_candidates": iwram_candidates,
        }
        code_unit_chain: dict[str, object] = {
            "status": "candidate-code-unit-to-font-record; glyph identity gate remains separate",
            "font_record_table_base_bus": f"0x{FONT_RECORD_TABLE_BASE:08X}",
            "font_record_stride": FONT_RECORD_STRIDE,
            "formula": "FONT_RECORD_TABLE_BASE + code_unit * 0x18",
            "renderer_function_pc": "0x080049A0",
            "record_arithmetic_pc": "0x080049C8",
            "records": [],
        }
        if ewram_candidates:
            candidate = ewram_candidates[0]
            first_code_unit = int(str(candidate["first_code_unit_le"]), 16)
            second_code_unit = int(str(candidate["second_code_unit_le"]), 16)
            code_unit_chain["records"] = [
                {
                    "known_slot": "a-row-1",
                    "layout_label": "あ",
                    "buffer_address": candidate["address"],
                    "code_unit_le": f"0x{first_code_unit:04X}",
                    "font_record_bus": f"0x{font_record_address(first_code_unit):08X}",
                },
                {
                    "known_slot": "a-row-2",
                    "layout_label": "い",
                    "buffer_address": f"0x{int(candidate['address'], 16) + 2:08X}",
                    "code_unit_le": f"0x{second_code_unit:04X}",
                    "font_record_bus": f"0x{font_record_address(second_code_unit):08X}",
                },
            ]
        report["code_unit_font_record_chain"] = code_unit_chain
        report["screen_tilemap_diffs"] = {
            "bg0_before_to_first": tilemap_diffs(pre_bg0, first_bg0),
            "bg0_first_to_second": tilemap_diffs(first_bg0, second_bg0),
            "bg1_before_to_first": tilemap_diffs(pre_bg1, first_bg1),
            "bg1_first_to_second": tilemap_diffs(first_bg1, second_bg1),
        }

        final_capture = capture(
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
        report["final_capture"] = final_capture
        final_vram = (args.dump_dir / "vram.bin").read_bytes()
        report["final_keyboard_metadata"] = analyze_keyboard(args.rom.read_bytes(), final_vram)
    finally:
        client.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    run()
