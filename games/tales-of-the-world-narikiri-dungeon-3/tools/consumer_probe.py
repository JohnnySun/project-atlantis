#!/usr/bin/env python3
"""Bounded B3TJ string-consumer probe using the shared ``core/gba`` client.

This tool is game-specific only where it names the B3TJ record, KEYINPUT
navigation point and post-hit VRAM observation.  GDB packet transport,
watchpoints, register access and standard GBA region capture come from
``core/gba/gdbstub_client.py``; no per-game transport or renderer is copied.

The normal run settles at the title screen, then emulates a short active-low
START/A sequence by intercepting the game's KEYINPUT read and overriding the
destination register.  It watches one concrete direct-pointer string record
(``sjis:0x146EE0``), removes the input/record watches on a hit, and watches
one bounded post-hit VRAM write slice.  Raw dumps and optional rendered PPMs
belong in ``/private/tmp`` or ignored ``games/<game>/work`` only.

No decoded source text is printed.  The JSON report contains offsets,
registers, stop packets, hashes and ROM-to-VRAM exact-match metadata.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
from gdbstub_client import GdbClient, parse_stop_watch  # noqa: E402


ROM_BASE = 0x08000000
EXPECTED_SIZE = 16 * 1024 * 1024
EXPECTED_CRC32 = 0x1867CCEF

TARGET_RECORD_OFFSET = 0x146EE0
TARGET_RECORD_ADDRESS = ROM_BASE + TARGET_RECORD_OFFSET
KEYINPUT_ADDRESS = 0x04000130
VRAM_ADDRESS = 0x06000000

NO_KEY = 0x03FF
KEY_BITS = {"a": 0, "b": 1, "select": 2, "start": 3, "right": 4, "left": 5, "up": 6, "down": 7, "r": 8, "l": 9}

REGION_SIZES = {
    "vram": (VRAM_ADDRESS, 0x18000),
    "palette": (0x05000000, 0x400),
    "oam": (0x07000000, 0x400),
    "iwram": (0x03000000, 0x8000),
}


def parse_sequence(spec: str) -> list[tuple[str, int]]:
    phases: list[tuple[str, int]] = []
    for item in spec.split(","):
        name, count_text = item.split(":", 1)
        name = name.strip().lower()
        if name not in KEY_BITS and name != "none":
            raise ValueError(f"unknown key phase: {name}")
        count = int(count_text, 0)
        if count < 1:
            raise ValueError("key phase counts must be positive")
        phases.append((name, count))
    if not phases:
        raise ValueError("sequence must contain at least one phase")
    return phases


def key_value(name: str) -> int:
    if name == "none":
        return NO_KEY
    return NO_KEY & ~(1 << KEY_BITS[name])


def b3tj_identity(rom: bytes) -> dict[str, object]:
    crc32 = binascii.crc32(rom) & 0xFFFFFFFF
    title = rom[0xA0:0xAC].split(b"\0", 1)[0]
    game_code = rom[0xAC:0xB0]
    maker_code = rom[0xB0:0xB2]
    result = {
        "size": len(rom),
        "crc32": f"{crc32:08X}",
        "title_ascii": title.decode("ascii", errors="replace"),
        "game_code": game_code.decode("ascii", errors="replace"),
        "maker_code": maker_code.decode("ascii", errors="replace"),
    }
    if (
        len(rom) != EXPECTED_SIZE
        or crc32 != EXPECTED_CRC32
        or title != b"TOWNARIKIRI3"
        or game_code != b"B3TJ"
        or maker_code != b"AF"
    ):
        raise ValueError(f"ROM identity mismatch: {result}")
    return result


def io_value(client: GdbClient, address: int, length: int = 2) -> int:
    return int.from_bytes(client.read_memory(address, length), "little")


def render_parameters(dispcnt: int, bg1cnt: int) -> dict[str, object]:
    return {
        "dispcnt": f"0x{dispcnt:04X}",
        "bg1cnt": f"0x{bg1cnt:04X}",
        "bg1_charbase": ((bg1cnt >> 2) & 0x3) * 0x4000,
        "bg1_screenbase": ((bg1cnt >> 8) & 0x1F) * 0x800,
        "bg1_bpp": 8 if bg1cnt & 0x80 else 4,
        "obj_mapping": "1d" if dispcnt & 0x40 else "2d",
    }


def exact_tile_matches(rom: bytes, vram: bytes, *, tile_size: int = 32) -> list[dict[str, object]]:
    """Find exact ROM copies for nonzero, tile-aligned VRAM tiles."""

    matches: list[dict[str, object]] = []
    seen: set[tuple[int, int]] = set()
    for vram_offset in range(0, len(vram) - tile_size + 1, tile_size):
        tile = vram[vram_offset : vram_offset + tile_size]
        if not any(tile):
            continue
        first = rom.find(tile)
        if first < 0:
            continue
        count = 0
        offsets: list[int] = []
        cursor = first
        while cursor >= 0 and len(offsets) < 8:
            offsets.append(cursor)
            count += 1
            cursor = rom.find(tile, cursor + 1)
        key = (vram_offset, first)
        if key in seen:
            continue
        seen.add(key)
        matches.append(
            {
                "vram_offset": f"0x{vram_offset:05X}",
                "rom_offsets": [f"0x{offset:06X}" for offset in offsets],
                "rom_match_count_capped": count,
            }
        )
    return matches


def register_snapshot(registers: dict[str, int]) -> dict[str, str]:
    return {
        name: f"0x{value:08X}"
        for name, value in registers.items()
        if name in {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "sp", "lr", "pc", "cpsr"}
    }


def read_regions(client: GdbClient, dump_dir: Path | None) -> tuple[dict[str, object], dict[str, bytes]]:
    data: dict[str, bytes] = {}
    summaries: dict[str, object] = {}
    for name, (address, length) in REGION_SIZES.items():
        raw = client.read_memory(address, length)
        data[name] = raw
        summaries[name] = {
            "address": f"0x{address:08X}",
            "length": length,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "nonzero_bytes": sum(value != 0 for value in raw),
        }
        if dump_dir is not None:
            dump_dir.mkdir(parents=True, exist_ok=True)
            (dump_dir / f"{name}.bin").write_bytes(raw)
    return summaries, data


def run_probe(
    rom_path: Path,
    *,
    host: str,
    port: int,
    settle_seconds: float,
    per_event_timeout: float,
    post_hit_timeout: float,
    sequence: list[tuple[str, int]],
    dump_dir: Path | None,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    identity = b3tj_identity(rom)
    client = GdbClient(host, port, timeout=8.0)
    key_watch = False
    record_watch = False
    vram_watch = False
    report: dict[str, object] = {
        "rom": str(rom_path),
        "identity": identity,
        "target_record": {
            "string_id": f"sjis:0x{TARGET_RECORD_OFFSET:06X}",
            "file_offset": f"0x{TARGET_RECORD_OFFSET:06X}",
            "gba_address": f"0x{TARGET_RECORD_ADDRESS:08X}",
        },
        "sequence": [{"key": name, "events": count} for name, count in sequence],
        "key_events": [],
        "record_hit": None,
        "post_hit_vram": None,
    }

    try:
        client.connect()
        report["supported"] = client.request("qSupported:multiprocess+")
        report["initial_stop"] = client.request("?")
        report["initial_registers"] = register_snapshot(client.read_registers())

        report["settle_stop"] = client.continue_and_interrupt(settle_seconds)
        report["settled_io"] = {
            "dispcnt": f"0x{io_value(client, 0x04000000):04X}",
            "bg1cnt": f"0x{io_value(client, 0x0400000A):04X}",
        }

        client.set_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
        key_watch = True
        client.set_watchpoint(TARGET_RECORD_ADDRESS, kind=1, watch_type=3)
        record_watch = True

        target_hit = False
        event_index = 0
        for phase, event_count in sequence:
            desired = key_value(phase)
            for _ in range(event_count):
                try:
                    stop = client.continue_until_stop(per_event_timeout)
                except TimeoutError:
                    report["termination"] = "input-watch-timeout"
                    break
                kind, address = parse_stop_watch(stop)
                registers = client.read_registers()
                event = {
                    "index": event_index,
                    "phase": phase,
                    "requested_keyinput": f"0x{desired:04X}",
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                    "registers": register_snapshot(registers),
                }
                report["key_events"].append(event)
                event_index += 1

                if address is not None and TARGET_RECORD_ADDRESS <= address < TARGET_RECORD_ADDRESS + 4:
                    report["record_hit"] = {
                        "stop": stop,
                        "stop_kind": kind,
                        "stop_address": f"0x{address:08X}",
                        "registers": register_snapshot(registers),
                        "caller_lr": f"0x{registers['lr']:08X}",
                        "pc": f"0x{registers['pc']:08X}",
                        "stack_pointer": f"0x{registers['sp']:08X}",
                    }
                    target_hit = True
                    break

                if address is None or not (KEYINPUT_ADDRESS <= address < KEYINPUT_ADDRESS + 2):
                    report["termination"] = "unexpected-stop"
                    break

                # mGBA stops after the load. r1 is the destination register in
                # B3TJ's observed KEYINPUT polling instruction.
                client.write_register(1, desired)
            if target_hit or report.get("termination") in {"input-watch-timeout", "unexpected-stop"}:
                break

        if not target_hit and "termination" not in report:
            report["termination"] = "sequence-exhausted-without-record-hit"

        if key_watch:
            client.remove_watchpoint(KEYINPUT_ADDRESS, kind=2, watch_type=3)
            key_watch = False
        if record_watch:
            client.remove_watchpoint(TARGET_RECORD_ADDRESS, kind=1, watch_type=3)
            record_watch = False

        if target_hit:
            # Observe the next bounded screen update separately.  If the text
            # consumer writes glyph data after reading this record, the VRAM
            # write stop gives a concrete second runtime edge; otherwise the
            # absence is retained as a negative result.
            client.set_watchpoint(VRAM_ADDRESS, kind=4, watch_type=2)
            vram_watch = True
            try:
                stop = client.continue_until_stop(post_hit_timeout)
                kind, address = parse_stop_watch(stop)
                regs = client.read_registers()
                report["post_hit_vram"] = {
                    "stop": stop,
                    "stop_kind": kind,
                    "stop_address": None if address is None else f"0x{address:08X}",
                    "registers": register_snapshot(regs),
                }
            except TimeoutError:
                report["post_hit_vram"] = {"result": "no-vram-write-before-timeout"}
                try:
                    client.interrupt(timeout=2.0)
                except (TimeoutError, OSError, ConnectionError):
                    pass
            finally:
                client.remove_watchpoint(VRAM_ADDRESS, kind=4, watch_type=2)
                vram_watch = False

            report["post_hit_io"] = {
                "dispcnt": io_value(client, 0x04000000),
                "bg1cnt": io_value(client, 0x0400000A),
            }
            report["render_parameters"] = render_parameters(
                report["post_hit_io"]["dispcnt"], report["post_hit_io"]["bg1cnt"]
            )
            summaries, raw = read_regions(client, dump_dir)
            report["regions"] = summaries
            report["rom_to_vram_exact_tiles"] = exact_tile_matches(rom, raw["vram"])
            report["exact_tile_match_count"] = len(report["rom_to_vram_exact_tiles"])
    finally:
        for address, kind, watch_type, active in (
            (KEYINPUT_ADDRESS, 2, 3, key_watch),
            (TARGET_RECORD_ADDRESS, 1, 3, record_watch),
            (VRAM_ADDRESS, 4, 2, vram_watch),
        ):
            if active:
                try:
                    client.remove_watchpoint(address, kind=kind, watch_type=watch_type)
                except (RuntimeError, TimeoutError, OSError, ConnectionError):
                    pass
        client.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--settle-seconds", type=float, default=1.0)
    parser.add_argument("--per-event-timeout", type=float, default=5.0)
    parser.add_argument("--post-hit-timeout", type=float, default=3.0)
    parser.add_argument(
        "--sequence",
        default="start:8,none:12,a:8,none:12",
        help="comma-separated key:event-count phases",
    )
    parser.add_argument("--dump-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        sequence = parse_sequence(args.sequence)
    except ValueError as exc:
        parser.error(str(exc))
    result = run_probe(
        args.rom,
        host=args.host,
        port=args.port,
        settle_seconds=args.settle_seconds,
        per_event_timeout=args.per_event_timeout,
        post_hit_timeout=args.post_hit_timeout,
        sequence=sequence,
        dump_dir=args.dump_dir,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
