#!/usr/bin/env python3
"""Bounded A6SJ font-slot, resource, and glyph-provenance probe.

The probe has two deliberately separate phases:

* The initializer phase uses the ROM's existing ARM ``BX`` instruction at
  ``0x08000210`` to enter the already verified Thumb initializer callsite.
  It sets write watchpoints on the two runtime font slots and records only
  registers, addresses, hashes, and counts.
* The optional consumer phase is refused unless both slots contain non-zero
  live pointers.  It then uses the previously traced text consumer with a
  bounded, temporary call setup and records one narrow and one wide glyph.

No ROM bytes, complete source records, or memory dumps are written by this
tool.  Runtime output is metadata-only and belongs under ignored ``work/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from core.gba.gdbstub_client import GdbClient, parse_stop_watch
except ModuleNotFoundError as exc:  # pragma: no cover - direct script execution
    if exc.name != "core":
        raise
    # The script directory is first on sys.path when invoked by filename;
    # resolve the repository root so this game-specific tool still reuses the
    # shared core client rather than the historical game-local client.
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from core.gba.gdbstub_client import GdbClient, parse_stop_watch


ROM_BASE = 0x08000000
ROM_END = 0x08800000

NARROW_SLOT = 0x020131D0
WIDE_SLOT = 0x020103AC
SLOTS = {"narrow": NARROW_SLOT, "wide": WIDE_SLOT}

INITIALIZER = 0x080083A0
INITIALIZER_CALLSITE = 0x08014E8C
NARROW_STORE = 0x08008456
WIDE_STORE = 0x08008462
RESOURCE_RESOLVER = 0x08003290
RESOURCE_TABLE = 0x08081E58
RESOURCE_DESCRIPTOR = 0x081196B8

ROM_BX = 0x08000210
ROM_BX_TARGET = 0x08014E85

CONSUMER = 0x08008724
CODEPAGE_LOOKUP = 0x080085FC
NARROW_GLYPH_ADD = 0x080088C8
WIDE_GLYPH_ADD = 0x08008818
TILE_WRITER = 0x08008650
GLYPH_COMPLETE = 0x0800894C

SOURCE_CONTEXTS = (0x7B380, 0x7B3FC)
DEFAULT_TILE_BUFFER = 0x02019010
TEMP_STACK = 0x0203FF00
TILE_HASH_LENGTH = 0x400
TILE_OUTPUT_LENGTH = 0x80
MEMORY_WRITE_CHUNK = 0x80


class ProbeError(RuntimeError):
    """A bounded probe could not establish its required invariant."""


def address(value: int) -> str:
    return f"0x{value:08X}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def summarize_bytes(data: bytes, start: int) -> Dict[str, Any]:
    return {
        "address": address(start),
        "length": len(data),
        "sha256": sha256(data),
        "nonzero_bytes": sum(byte != 0 for byte in data),
    }


def read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ProbeError(f"u32 outside ROM: 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def static_resource_metadata(rom: bytes) -> Dict[str, Dict[str, Any]]:
    """Resolve the two slot resources through the bounded known descriptor."""
    table_root = read_u32(rom, RESOURCE_TABLE - ROM_BASE)
    if table_root != RESOURCE_DESCRIPTOR:
        raise ProbeError(
            f"resource table root changed: {address(table_root)} != "
            f"{address(RESOURCE_DESCRIPTOR)}"
        )

    # 0x08008450 calls resource resolver (r0=0, r1=3), and 0x0800845e
    # calls it (r0=0, r1=2).  The resolver adds the descriptor's relative
    # entry to the descriptor base returned from 0x08081e58.
    entries = {"narrow": (3, NARROW_STORE), "wide": (2, WIDE_STORE)}
    result: Dict[str, Dict[str, Any]] = {}
    for name, (index, store_pc) in entries.items():
        relative = read_u32(rom, RESOURCE_DESCRIPTOR - ROM_BASE + index * 4)
        pointer = RESOURCE_DESCRIPTOR + relative
        if not ROM_BASE <= pointer < ROM_END:
            raise ProbeError(f"resource pointer outside ROM: {address(pointer)}")
        result[name] = {
            "slot": address(SLOTS[name]),
            "resolver": address(RESOURCE_RESOLVER),
            "resolver_group": 0,
            "resolver_index": index,
            "descriptor": address(RESOURCE_DESCRIPTOR),
            "descriptor_relative": f"0x{relative:08X}",
            "resource_pointer": address(pointer),
            "resource_file_offset": f"0x{pointer - ROM_BASE:06X}",
            "store_pc": address(store_pc),
            "compression": "not observed; live pointer remains ROM-mapped",
        }
    return result


def gdb_pc_argument(target: int, mode: str) -> int:
    """Return the GDB P15 value for an instruction at ``target``.

    mGBA's GDB stub exposes the architectural PC (the next prefetched
    instruction) and its write helpers add one instruction width.  The
    caller must already be in the requested decoder mode.
    """
    if mode == "thumb":
        width = 2
    elif mode == "arm":
        width = 4
    else:
        raise ValueError(f"unsupported mode: {mode}")
    if target < width:
        raise ValueError("target is below instruction width")
    return target - width


def _parse_string_id(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ProbeError(f"invalid string_id: {value!r}")


def load_source_records(path: Path) -> Dict[int, Dict[str, Any]]:
    records: Dict[int, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            offset = _parse_string_id(row["string_id"])
            text = row.get("text")
            if not isinstance(text, str):
                raise ProbeError(f"source record {address(offset)} has no text")
            records[offset] = {"offset": offset, "text": text, "locale": row.get("locale", "ja")}
    return records


def encoded_source(text: str) -> bytes:
    try:
        return text.encode("shift_jis", errors="strict")
    except UnicodeEncodeError as exc:
        raise ProbeError(f"source is not strict Shift-JIS: {text!r}") from exc


def code_unit_identities(text: str) -> List[Dict[str, Any]]:
    """Map source characters to the little-endian code units read by ldrh."""
    rows: List[Dict[str, Any]] = []
    byte_offset = 0
    for character in text:
        encoded = encoded_source(character)
        if len(encoded) not in (1, 2):
            raise ProbeError(f"unexpected Shift-JIS unit length: {len(encoded)}")
        rows.append(
            {
                "character": character,
                "code_unit": f"0x{int.from_bytes(encoded, 'little'):04X}",
                "source_byte_offset": byte_offset,
                "source_bytes": encoded.hex(),
                "width_class": "double_byte" if len(encoded) == 2 else "single_byte",
            }
        )
        byte_offset += len(encoded)
    return rows


def source_metadata(record: Mapping[str, Any]) -> Dict[str, Any]:
    text = str(record["text"])
    raw = encoded_source(text)
    # NUL is the ignored table terminator and is not part of the source hash.
    controls = [
        {"byte_offset": index, "value": f"0x{value:02X}"}
        for index, value in enumerate(raw)
        if value == 0 or value in (0xF0, 0xF1, 0xF2, 0xF3, 0xFE, 0xFF)
    ]
    return {
        "string_id": address(int(record["offset"])),
        "source_hash": sha256(raw),
        "source_length": len(raw),
        "terminator": "NUL (excluded from source hash)",
        "control_tokens": controls,
        "code_units": code_unit_identities(text),
    }


def source_record_summary(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Return source provenance without reproducing the source record."""
    return {
        key: metadata[key]
        for key in ("string_id", "source_hash", "source_length", "terminator", "control_tokens")
        if key in metadata
    }


def identity_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep one source-context identity, never a complete source string."""
    return {
        "source_offset": row["source_offset"],
        "source_byte_offset": row["source_byte_offset"],
        "code_unit": row["code_unit"],
        "unicode": row["character"],
        "width_class": row["width_class"],
    }


def _register_metadata(regs: Mapping[str, int], names: Iterable[str]) -> Dict[str, str]:
    return {name: address(int(regs[name])) for name in names}


def _slot_values(client: Any) -> Dict[str, int]:
    return {
        name: int.from_bytes(client.read_memory(slot, 4), "little")
        for name, slot in SLOTS.items()
    }


def _live_pointer_summary(client: Any, pointer: int, length: int = 0x100) -> Dict[str, Any]:
    data = client.read_memory(pointer, length)
    return summarize_bytes(data, pointer)


def write_bounded_memory(client: Any, start: int, data: bytes) -> None:
    """Write a bounded temporary buffer without an oversized GDB packet."""
    for offset in range(0, len(data), MEMORY_WRITE_CHUNK):
        client.write_memory(
            start + offset,
            data[offset : offset + MEMORY_WRITE_CHUNK],
        )


def _watch_event(
    client: Any,
    stop: str,
    regs: Mapping[str, int],
    slot_values: Mapping[str, int],
    static_resources: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    kind, watched = parse_stop_watch(stop)
    event: Dict[str, Any] = {
        "stop": stop,
        "watch_kind": kind,
        "watched_address": None if watched is None else address(watched),
        "pc": address(regs["pc"]),
        "lr": address(regs["lr"]),
        "writer_pc": address(max(0, regs["pc"] - 2)),
        "registers": _register_metadata(regs, ("r0", "r1", "r2", "r3", "sp", "lr", "pc")),
        "slots": {name: address(value) for name, value in slot_values.items()},
        "slot_nonzero_count": sum(value != 0 for value in slot_values.values()),
    }
    for name, pointer in slot_values.items():
        if pointer:
            event[name] = {
                "live_pointer": address(pointer),
                "live_region": "rom" if ROM_BASE <= pointer < ROM_END else "ram_or_io",
                "resource_hash": _live_pointer_summary(client, pointer),
                "static": dict(static_resources[name]),
            }
    return event


def capture_initializer(
    client: Any,
    rom: bytes,
    *,
    boot_seconds: float = 1.0,
    stop_timeout: float = 5.0,
) -> Dict[str, Any]:
    """Capture both slot writes through the known ROM-internal initializer path."""
    static_resources = static_resource_metadata(rom)
    boot_stop = client.continue_and_interrupt(boot_seconds)
    boot_regs = client.read_registers()
    events: List[Dict[str, Any]] = []
    caller_event: Optional[Dict[str, Any]] = None
    for slot in SLOTS.values():
        client.set_watchpoint(slot, 4, 2)
    client.set_breakpoint(INITIALIZER)
    try:
        # This uses only the existing ROM BX and the existing Thumb setup at
        # 0x08014e84.  No code or RAM is written to enter the initializer.
        client.write_register(0x19, 0x0000001F)  # CPSR: ARM/system for BX.
        client.write_register(0, ROM_BX_TARGET)
        client.write_register(15, gdb_pc_argument(ROM_BX, "arm"))

        for _ in range(8):
            try:
                stop = client.continue_until_stop(stop_timeout)
            except TimeoutError as exc:
                raise ProbeError("initializer did not hit both font slots") from exc
            regs = client.read_registers()
            kind, _watched = parse_stop_watch(stop)
            if kind is None and regs["pc"] == INITIALIZER:
                caller_event = {
                    "pc": address(regs["pc"]),
                    "lr": address(regs["lr"]),
                    # Thumb BL is four bytes and LR carries the return
                    # address with bit 0 set: callsite = LR - 5.
                    "caller_callsite": address(regs["lr"] - 5),
                    "caller_instruction_width": 4,
                    "arguments": _register_metadata(regs, ("r0", "r1", "r2", "r3")),
                }
                events.append({"kind": "initializer_entry", **caller_event})
                continue
            if kind is None:
                raise ProbeError(f"unexpected initializer stop: {stop} at {address(regs['pc'])}")
            values = _slot_values(client)
            events.append(
                {
                    "kind": "slot_write",
                    **_watch_event(client, stop, regs, values, static_resources),
                }
            )
            if all(values.values()):
                break
        final_slots = _slot_values(client)
    finally:
        try:
            client.remove_breakpoint(INITIALIZER)
        finally:
            for slot in SLOTS.values():
                client.remove_watchpoint(slot, 4, 2)

    if not all(final_slots.values()):
        raise ProbeError("initializer ended without two non-zero font bases")
    return {
        "phase": "font_resource_initializer",
        "navigation": {
            "mode": "rom_internal_bx_to_verified_initializer_callsite",
            "entry_bx": address(ROM_BX),
            "initializer_callsite": address(INITIALIZER_CALLSITE),
            "natural_window_stop": boot_stop,
            "boot_registers": _register_metadata(boot_regs, ("pc", "cpsr", "sp")),
        },
        "initializer_caller": caller_event,
        "slot_writer_static": {
            "narrow": {"store_pc": address(NARROW_STORE), "slot": address(NARROW_SLOT)},
            "wide": {"store_pc": address(WIDE_STORE), "slot": address(WIDE_SLOT)},
        },
        "resource_static": static_resources,
        "slot_values": {name: address(value) for name, value in final_slots.items()},
        "events": events,
    }


def _assert_initialized(client: Any) -> Dict[str, int]:
    values = _slot_values(client)
    if not all(values.values()):
        raise ProbeError(
            "consumer hijack refused: both font slots must be non-zero first; "
            f"observed={{{', '.join(f'{k}: {address(v)}' for k, v in values.items())}}}"
        )
    return values


def _source_identity_for_code_unit(
    source_rows: Sequence[Mapping[str, Any]], code_unit: int, source_offset: int
) -> Optional[Dict[str, Any]]:
    wanted = f"0x{code_unit & 0xFFFF:04X}"
    for row in source_rows:
        if row.get("source_offset") == address(source_offset) and row.get("code_unit") == wanted:
            return identity_metadata(row)
    return None


def capture_consumer(
    client: Any,
    *,
    source_offset: int,
    mode: str,
    source_rows: Sequence[Mapping[str, Any]],
    source_context: Mapping[str, Any],
    tile_buffer: int = DEFAULT_TILE_BUFFER,
) -> Dict[str, Any]:
    """Capture one bounded consumer glyph after the initializer guard."""
    # This guard is intentionally before every temporary stack/tile write.
    slot_values = _assert_initialized(client)
    if mode not in ("narrow", "wide"):
        raise ValueError(f"unsupported glyph mode: {mode}")
    glyph_add = NARROW_GLYPH_ADD if mode == "narrow" else WIDE_GLYPH_ADD
    base_slot = SLOTS[mode]
    glyph_length = 12 if mode == "narrow" else 24
    breakpoints = [CODEPAGE_LOOKUP, glyph_add, TILE_WRITER, GLYPH_COMPLETE]
    tile_writer_event: Optional[Dict[str, Any]] = None
    codepage_event: Optional[Dict[str, Any]] = None
    glyph_event: Optional[Dict[str, Any]] = None
    complete_event: Optional[Dict[str, Any]] = None

    for breakpoint in breakpoints:
        client.set_breakpoint(breakpoint)
    try:
        # The live base guard above is the only condition under which this
        # temporary consumer call is allowed.  The original ROM remains
        # untouched; the consumer receives the known source record and a
        # bounded existing tile buffer.
        client.write_memory(TEMP_STACK, struct.pack("<I", 1))
        write_bounded_memory(client, tile_buffer, bytes(TILE_HASH_LENGTH))
        client.write_register(0, ROM_BASE + source_offset)
        client.write_register(1, 0)
        client.write_register(2, 0)
        client.write_register(3, tile_buffer)
        client.write_register(13, TEMP_STACK)
        client.write_register(14, TEMP_STACK | 1)
        client.write_register(15, gdb_pc_argument(CONSUMER, "thumb"))

        for _ in range(80):
            try:
                stop = client.continue_until_stop(5.0)
            except TimeoutError as exc:
                raise ProbeError(f"consumer did not complete first {mode} glyph") from exc
            kind, _watched = parse_stop_watch(stop)
            if kind is not None:
                raise ProbeError(f"unexpected consumer watch stop: {stop}")
            regs = client.read_registers()
            pc = regs["pc"]
            if pc == CODEPAGE_LOOKUP:
                codepage_event = {
                    "pc": address(pc),
                    "lr": address(regs["lr"]),
                    "callsite": address(regs["lr"] - 5),
                    "code_unit": f"0x{regs['r0'] & 0xFFFF:04X}",
                    "mode": regs["r1"],
                    "source_pointer": address(regs["r5"]),
                    "identity": _source_identity_for_code_unit(
                        source_rows, regs["r0"], source_offset
                    ),
                }
            elif pc == glyph_add:
                glyph_pointer = regs["r0"]
                offset = regs["r4"]
                expected = slot_values[mode] + offset
                if glyph_pointer != expected:
                    raise ProbeError(
                        f"glyph pointer mismatch: {address(glyph_pointer)} != {address(expected)}"
                    )
                glyph_bytes = client.read_memory(glyph_pointer, glyph_length)
                glyph_event = {
                    "pc": address(pc),
                    "lr": address(regs["lr"]),
                    "base_slot": address(base_slot),
                    "initialized_base": address(slot_values[mode]),
                    "glyph_offset": f"0x{offset:04X}",
                    "glyph_pointer": address(glyph_pointer),
                    "glyph_bytes": summarize_bytes(glyph_bytes, glyph_pointer),
                }
            elif pc == TILE_WRITER:
                if tile_writer_event is None:
                    tile_writer_event = {
                        "pc": address(pc),
                        "lr": address(regs["lr"]),
                        "destination": address(regs["r0"]),
                        "tile_value": f"0x{regs['r1'] & 0xFFFF:04X}",
                        "callsite": address(regs["lr"] - 5),
                    }
                    client.remove_breakpoint(TILE_WRITER)
            elif pc == GLYPH_COMPLETE:
                tile_data = client.read_memory(tile_buffer, TILE_HASH_LENGTH)
                if tile_writer_event is None:
                    raise ProbeError("glyph completed without a tile writer event")
                tile_output_address = int(tile_writer_event["destination"], 16)
                tile_output = client.read_memory(tile_output_address, TILE_OUTPUT_LENGTH)
                complete_event = {
                    "pc": address(pc),
                    "tile_buffer": summarize_bytes(tile_data, tile_buffer),
                    "tile_writer_output": summarize_bytes(tile_output, tile_output_address),
                }
                break
            else:
                raise ProbeError(f"unexpected consumer stop: {stop} at {address(pc)}")
        else:
            raise ProbeError("consumer bounded stop budget exhausted")
    finally:
        for breakpoint in breakpoints:
            if breakpoint == TILE_WRITER and tile_writer_event is not None:
                continue
            try:
                client.remove_breakpoint(breakpoint)
            except Exception:
                pass

    if codepage_event is None or glyph_event is None or complete_event is None:
        raise ProbeError("consumer did not produce codepage, glyph, and tile events")
    return {
        "source_offset": address(source_offset),
        "source_context": source_record_summary(source_context),
        "mode": mode,
        "consumer": address(CONSUMER),
        "codepage_lookup": codepage_event,
        "glyph_addressing": glyph_event,
        "tile_writer": tile_writer_event,
        "glyph_complete": complete_event,
        "identity_status": (
            "confirmed only when codepage identity matches the strict Shift-JIS source "
            "context and glyph addressing reaches the initialized base"
        ),
    }


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--source-table", type=Path, required=True)
    parser.add_argument("--boot-seconds", type=float, default=1.0)
    parser.add_argument("--stop-timeout", type=float, default=5.0)
    parser.add_argument("--consumer-hijack", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    source_records = load_source_records(args.source_table)
    runtime_sources: List[Dict[str, Any]] = []
    source_context_metadata: Dict[int, Dict[str, Any]] = {}
    for offset in SOURCE_CONTEXTS:
        if offset not in source_records:
            raise ProbeError(f"required source context missing: {address(offset)}")
        metadata = source_metadata(source_records[offset])
        source_context_metadata[offset] = metadata
        runtime_sources.extend(
            {
                "source_offset": address(offset),
                **row,
            }
            for row in metadata["code_units"]
        )

    with GdbClient(port=args.port, timeout=max(4.0, args.stop_timeout)) as client:
        result: Dict[str, Any] = capture_initializer(
            client,
            rom,
            boot_seconds=args.boot_seconds,
            stop_timeout=args.stop_timeout,
        )
        result["source_contexts"] = [
            source_record_summary(source_context_metadata[offset]) for offset in SOURCE_CONTEXTS
        ]
        if args.consumer_hijack:
            result["glyph_provenance"] = [
                capture_consumer(
                    client,
                    source_offset=0x7B3FC,
                    mode="narrow",
                    source_rows=runtime_sources,
                    source_context=source_context_metadata[0x7B3FC],
                ),
                capture_consumer(
                    client,
                    source_offset=0x7B380,
                    mode="wide",
                    source_rows=runtime_sources,
                    source_context=source_context_metadata[0x7B380],
                ),
            ]

    if args.output is None:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        write_json(args.output, result)
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
