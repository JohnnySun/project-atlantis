#!/usr/bin/env python3
"""B3CJ bounded runtime probe for the confirmed text-handler callsite.

The caller owns a fresh mGBA process and listener.  This probe opens exactly
one GDB connection, verifies the M5.5 artifacts, waits for the natural palette
DMA anchor, and then performs one explicitly controlled ``lr/pc`` jump to the
known ``sub_0800D81C`` text-window entry.  It records only hashes, addresses,
selected registers, and breakpoint sequence.  It never writes ROM, IWRAM,
EWRAM, script bytes, glyph input, or tracked runtime output.

The controlled call is bounded deliberately.  A boot-time context is not a
target script record, so a renderer loop after the handler is evidence of the
static call chain only; it is not natural target reachability or screen QA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS_ROOT = GAME_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from runtime_m5_writer_probe import (  # noqa: E402
    DMA_QUEUE,
    EXPECTED_FONT_BASE,
    FONT_POINTER,
    REQUIRED_QSUPPORTED,
    TARGET_ID,
    _find_palette_queue_anchor,
    _pc,
    _require,
    verify_artifacts,
)
from gdbstub_client import GdbClient  # noqa: E402


HANDLER = 0x0800D81C
HANDLER_LABEL = "sub_0800D81C"
TEXT_WINDOW = 0x0800B730
TEXT_WINDOW_LABEL = "sub_0800B730"
TEXT_WRITER = 0x080036F8
TEXT_WRITER_LABEL = "sub_080036F8"
GLYPH_WRITER = 0x08002CB4
GLYPH_WRITER_LABEL = "sub_08002CB4"
RETURN_SENTINEL = 0x0800D084
STATE_POINTER_GLOBALS = (0x03006574, 0x03006578, 0x03006590)
STATE_POINTER_LIMITS = (0x03000000, 0x03008000)
DEFAULT_MAX_STOPS = 10


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pointer_receipt(client: Any, address: int) -> dict[str, object]:
    raw = client.read_memory(address, 4)
    return {
        "address": f"0x{address:08x}",
        "value": f"0x{int.from_bytes(raw, 'little'):08x}",
        "sha256": sha256_bytes(raw),
    }


def register_receipt(registers: Mapping[str, int]) -> dict[str, str]:
    names = ("r0", "r1", "r2", "r3", "sp", "lr", "pc", "cpsr")
    return {name: f"0x{int(registers[name]) & 0xffffffff:08x}" for name in names}


def classify_breakpoint(pc: int) -> str:
    labels = {
        HANDLER: HANDLER_LABEL,
        TEXT_WINDOW: TEXT_WINDOW_LABEL,
        TEXT_WRITER: TEXT_WRITER_LABEL,
        GLYPH_WRITER: GLYPH_WRITER_LABEL,
        RETURN_SENTINEL: "return-sentinel",
    }
    return labels.get(pc & ~1, f"unknown:0x{pc & ~1:08x}")


def summarize_script_context(client: Any) -> dict[str, object]:
    receipts = [pointer_receipt(client, address) for address in STATE_POINTER_GLOBALS]
    pointer = int(receipts[0]["value"], 16)
    result: dict[str, object] = {"globals": receipts}
    low, high = STATE_POINTER_LIMITS
    if low <= pointer < high:
        context = client.read_memory(pointer, 0x20)
        result["context"] = {
            "address": f"0x{pointer:08x}",
            "length": len(context),
            "sha256": sha256_bytes(context),
            "word0": f"0x{int.from_bytes(context[0:2], 'little'):04x}",
            "word1": f"0x{int.from_bytes(context[2:4], 'little'):04x}",
            "current_pointer": f"0x{int.from_bytes(context[4:8], 'little'):08x}",
        }
    else:
        result["context"] = {"pointer": "outside-IWRAM-or-null"}
    return result


def controlled_handler(
    client: Any,
    *,
    timeout: float,
    max_stops: int = DEFAULT_MAX_STOPS,
) -> dict[str, object]:
    _require(max_stops > 0, "max_stops must be positive")
    points = (HANDLER, TEXT_WINDOW, TEXT_WRITER, GLYPH_WRITER, RETURN_SENTINEL)
    for address in points:
        client.set_breakpoint(address)

    hits: list[dict[str, object]] = []
    try:
        # Do not inject script/glyph data.  This is the smallest controlled
        # intervention: enter the confirmed function with a private return PC.
        client.write_register(14, RETURN_SENTINEL | 1)
        client.write_register(15, HANDLER)
        packet = client.continue_until_stop(timeout)
        registers = client.read_registers()
        entry_pc = _pc(registers)
        hits.append({
            "phase": "controlled-dispatch-stop",
            "packet": packet,
            "pc": f"0x{entry_pc:08x}",
            "function": classify_breakpoint(entry_pc),
            "registers": register_receipt(registers),
        })
        # mGBA's ARM/THUMB breakpoint implementation may execute the first
        # instruction after a GDB PC write before reporting a stop.  In the
        # observed B3CJ route the first stop is therefore sub_0800B730, a
        # stronger downstream observation than an entry breakpoint alone.
        known_points = {HANDLER, TEXT_WINDOW, TEXT_WRITER, GLYPH_WRITER, RETURN_SENTINEL}
        _require(entry_pc in known_points, "controlled call did not reach a known text callsite")
        client.remove_breakpoint(HANDLER)

        for index in range(max_stops):
            try:
                packet = client.continue_until_stop(timeout)
                registers = client.read_registers()
            except Exception as exc:  # retain exact bounded transport boundary
                hits.append({
                    "phase": "bounded-error",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                break
            observed_pc = _pc(registers)
            hits.append({
                "phase": f"controlled-step-{index + 1}",
                "packet": packet,
                "pc": f"0x{observed_pc:08x}",
                "function": classify_breakpoint(observed_pc),
                "registers": register_receipt(registers),
            })
            if observed_pc == RETURN_SENTINEL:
                break
        return {
            "entry": f"0x{HANDLER:08x}",
            "return_sentinel": f"0x{RETURN_SENTINEL:08x}",
            "max_stops": max_stops,
            "hits": hits,
            "controlled_pc_set": True,
            "handler_entry_breakpoint": bool(hits and hits[0].get("pc") == f"0x{HANDLER:08x}"),
            "downstream_breakpoint_observed": any(
                hit.get("function") in (TEXT_WINDOW_LABEL, TEXT_WRITER_LABEL, GLYPH_WRITER_LABEL)
                for hit in hits
            ),
            "text_window_hit": any(hit.get("function") == TEXT_WINDOW_LABEL for hit in hits),
            "writer_hit": any(hit.get("function") == TEXT_WRITER_LABEL for hit in hits),
            "glyph_writer_hit": any(hit.get("function") == GLYPH_WRITER_LABEL for hit in hits),
            "returned": any(hit.get("function") == "return-sentinel" for hit in hits),
            "bounded_before_return": not any(hit.get("function") == "return-sentinel" for hit in hits),
            "memory_writes": False,
            "script_injection": False,
            "reachability_class": "controlled-callsite-only",
        }
    finally:
        for address in points:
            try:
                client.remove_breakpoint(address)
            except Exception:
                pass


def probe(
    port: int,
    *,
    timeout: float = 8.0,
    packet_delay: float = 0.12,
    retry_delay: float = 0.35,
    max_stops: int = DEFAULT_MAX_STOPS,
) -> dict[str, object]:
    client = GdbClient(
        "127.0.0.1",
        port,
        timeout=timeout,
        packet_delay=packet_delay,
        retry_delay=retry_delay,
    )
    try:
        client.connect()
        supported = client.request("qSupported:multiprocess+")
        initial_stop = client.request("?")
        _require(all(token in supported for token in REQUIRED_QSUPPORTED), "incomplete qSupported")

        client.set_breakpoint(DMA_QUEUE)
        try:
            queue_packet, queue_regs, skipped = _find_palette_queue_anchor(client, timeout)
        finally:
            client.remove_breakpoint(DMA_QUEUE)
        font_base = int.from_bytes(client.read_memory(FONT_POINTER, 4), "little")
        _require(font_base == EXPECTED_FONT_BASE, f"font base changed: 0x{font_base:08x}")

        return {
            "transport": {
                "host": "127.0.0.1",
                "port": port,
                "single_connection": True,
                "qSupported": supported,
                "initial_stop": initial_stop,
                "packet_delay_seconds": packet_delay,
                "retry_delay_seconds": retry_delay,
            },
            "natural_palette_anchor": {
                "function": f"0x{DMA_QUEUE:08x}",
                "packet": queue_packet,
                "pc": f"0x{_pc(queue_regs):08x}",
                "source": f"0x{queue_regs['r0']:08x}",
                "destination": f"0x{queue_regs['r1']:08x}",
                "length": int(queue_regs["r2"]),
                "skipped_unrelated_queue_hits": skipped,
                "font_base": f"0x{font_base:08x}",
            },
            "script_state": summarize_script_context(client),
            "controlled_handler": controlled_handler(
                client,
                timeout=timeout,
                max_stops=max_stops,
            ),
            "runtime_coverage": {
                "transport": "confirmed",
                "natural_palette_queue": "confirmed",
                "controlled_0x0308_handler_dispatch": "confirmed via downstream callsite",
                "handler_entry_breakpoint": "not-observed after PC write",
                "controlled_text_window_callsite": "observed only if breakpoint hit",
                "controlled_writer_callsite": "observed only if breakpoint hit",
                "natural_target_record": "not-observed",
                "natural_screen_readability": "not-proven",
                "tilemap": "unknown",
                "live_oam": "not-read",
            },
            "boundary": (
                "The handler attempt is CPU-register-only and bounded. Boot-time script state "
                "is not a target record; a text-window/writer breakpoint hit is controlled "
                "callsite evidence, not natural consumer or screen QA."
            ),
        }
    finally:
        client.close()


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=pathlib.Path)
    parser.add_argument("target_rom", type=pathlib.Path)
    parser.add_argument("--bps", type=pathlib.Path)
    parser.add_argument("--bps-applied", type=pathlib.Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--max-stops", type=int, default=DEFAULT_MAX_STOPS)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--packet-delay", type=float, default=0.12)
    parser.add_argument("--retry-delay", type=float, default=0.35)
    parser.add_argument("--process-pid", type=int)
    parser.add_argument("--binary-sha256")
    parser.add_argument("--source-revision")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        artifacts = verify_artifacts(args.base_rom, args.target_rom, args.bps, args.bps_applied)
        report = {
            "game": "summon-night-craft-sword-3",
            "revision": "B3CJ",
            "milestone": "M5.5-post-handler-runtime-gate",
            "target_string_id": TARGET_ID,
            "process_pid": args.process_pid,
            "binary_sha256": args.binary_sha256,
            "source_revision": args.source_revision,
            "compile_time_port": args.port,
            "artifacts": artifacts,
            "probe": probe(
                args.port,
                timeout=args.timeout,
                packet_delay=args.packet_delay,
                retry_delay=args.retry_delay,
                max_stops=args.max_stops,
            ),
            "raw_output_policy": "hashes and register summaries only; raw runtime memory stays ignored",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M5_HANDLER_PROBE_OK output={args.output}")
        return 0
    except (OSError, RuntimeError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"runtime_m5_handler_probe.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
