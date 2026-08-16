#!/usr/bin/env python3
"""B3CJ M5.5 controlled glyph-writer to VRAM runtime probe.

The caller owns the emulator process and listener.  This probe opens exactly
one GDB connection, checks readiness, waits for a natural DMA-queue anchor,
then performs one explicitly controlled call sequence:

``sub_080036F8`` -> ``sub_08002CB4`` -> ``sub_08006BA4`` ->
``DmaCopyMapAndPltt``.

It records only addresses, registers, counts and hashes.  It never launches
or stops mGBA, and it never writes raw memory, screenshots, or decoded source
to a tracked path.  The controlled call is not evidence of natural
``0x0308`` consumer reachability or a readable game screen.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import pathlib
import sys
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
CORE_GBA = REPO_ROOT / "core" / "gba"
if str(CORE_GBA) not in sys.path:
    sys.path.insert(0, str(CORE_GBA))
from gdbstub_client import GdbClient  # noqa: E402


EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_BASE_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_BASE_CRC32 = "12afae5d"
EXPECTED_TARGET_SHA256 = "acfb3587a8217bf4ea444daf25f32c0947998a9203ee874db5006d7b6b016db6"
EXPECTED_TARGET_CRC32 = "fc874c4d"
EXPECTED_BPS_SHA256 = "f0b030756e4744c5f5a42c8bb874341062c73df818ba86342e13a1cbe3c92b34"
EXPECTED_BPS_SIZE = 4856

TARGET_ID = "b3cj:t2:024:0x0064"
CHANGED_GLYPH_IDS = (0x847, 0x848, 0x849)
ADJACENT_GLYPH_ID = 0x846
TARGET_CODE_UNITS = (0xEC64, 0xEC65, 0xEC66)
# The extractor's code-unit labels are memory-order bytes.  ``ldrh`` in the
# game therefore observes 0x64ec/0x65ec/0x66ec, matching the existing M5.5
# payload contract; do not little-endian-swap these bytes a second time.
TARGET_CODEPAGE_BYTES = bytes.fromhex("ec64ec65ec660000")

FONT_POINTER = 0x03002984
EXPECTED_FONT_BASE = 0x094D5C88
FONT_CELL_STRIDE = 0x18
FONT_WRITER = 0x080036F8
GLYPH_WRITER = 0x08002CB4
DMA_QUEUE = 0x08006BA4
DMA_FLUSH = 0x08006AC4
RETURN_SENTINEL = 0x0800D084

INPUT_ADDRESS = 0x0203E000
OUTPUT_ADDRESS = 0x0203F000
ADJACENT_OUTPUT_ADDRESS = OUTPUT_ADDRESS + 0x180
VRAM_ADDRESS = 0x06010000
VRAM_LENGTH = 0x180
PALETTE_ADDRESS = 0x05000000
PALETTE_LENGTH = 0x400
REQUIRED_QSUPPORTED = (
    "swbreak+",
    "hwbreak+",
    "qXfer:features:read+",
    "qXfer:memory-map:read+",
    "QStartNoAckMode+",
)

IO_REGISTERS = {
    "DISPCNT": (0x04000000, 2),
    "BG0CNT": (0x04000008, 2),
    "BG1CNT": (0x0400000A, 2),
    "BG2CNT": (0x0400000C, 2),
    "BG3CNT": (0x0400000E, 2),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08x}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def summarize(data: bytes, address: int) -> dict[str, object]:
    return {
        "address": f"0x{address:08x}",
        "length": len(data),
        "nonzero_bytes": sum(byte != 0 for byte in data),
        "sha256": sha256_bytes(data),
    }


def glyph_id_from_pointer(glyph_pointer: int, font_base: int) -> int:
    delta = glyph_pointer - font_base
    _require(delta >= 0 and delta % FONT_CELL_STRIDE == 0, "runtime glyph pointer is not cell aligned")
    return delta // FONT_CELL_STRIDE


def verify_artifacts(
    base_path: pathlib.Path,
    target_path: pathlib.Path,
    bps_path: pathlib.Path | None = None,
    applied_path: pathlib.Path | None = None,
) -> dict[str, object]:
    """Verify the ignored M5.5 inputs before opening localhost."""

    base = base_path.read_bytes()
    target = target_path.read_bytes()
    _require(len(base) == 0x02000000 and len(target) == 0x02000000, "B3CJ ROM size mismatch")
    _require(sha256_bytes(base) == EXPECTED_BASE_SHA256, "clean B3CJ SHA-256 mismatch")
    _require(crc32_bytes(base) == EXPECTED_BASE_CRC32, "clean B3CJ CRC32 mismatch")
    _require(sha256_bytes(target) == EXPECTED_TARGET_SHA256, "M5.5 target SHA-256 mismatch")
    _require(crc32_bytes(target) == EXPECTED_TARGET_CRC32, "M5.5 target CRC32 mismatch")
    receipt: dict[str, object] = {
        "base": {"sha256": sha256_bytes(base), "crc32": crc32_bytes(base), "size": len(base)},
        "target": {"sha256": sha256_bytes(target), "crc32": crc32_bytes(target), "size": len(target)},
    }
    if bps_path is not None:
        _require(sha256_file(bps_path) == EXPECTED_BPS_SHA256, "M5.5 BPS SHA-256 mismatch")
        _require(bps_path.stat().st_size == EXPECTED_BPS_SIZE, "M5.5 BPS size mismatch")
        receipt["bps"] = {"sha256": EXPECTED_BPS_SHA256, "size": EXPECTED_BPS_SIZE}
    if applied_path is not None:
        applied = applied_path.read_bytes()
        _require(applied == target, "BPS applied ROM differs from target ROM")
        receipt["bps_apply"] = {"byte_identical": True, "sha256": sha256_bytes(applied)}
    return receipt


def _pc(registers: Mapping[str, int]) -> int:
    return int(registers["pc"]) & ~1


def continue_until_pc(
    client: Any,
    expected: Iterable[int],
    *,
    timeout: float,
    max_stops: int = 12,
) -> tuple[str, dict[str, int]]:
    expected_set = {int(address) & ~1 for address in expected}
    last_pc: int | None = None
    for _ in range(max_stops):
        packet = client.continue_until_stop(timeout)
        registers = client.read_registers()
        last_pc = _pc(registers)
        if last_pc in expected_set:
            return packet, registers
    wanted = ", ".join(f"0x{address:08x}" for address in sorted(expected_set))
    raise RuntimeError(f"runtime did not reach {wanted}; last_pc=0x{(last_pc or 0):08x}")


def _find_palette_queue_anchor(client: Any, timeout: float) -> tuple[str, dict[str, int], int]:
    """Skip unrelated DMA calls until the known natural palette queue callsite."""

    for skipped in range(32):
        packet, registers = continue_until_pc(client, (DMA_QUEUE,), timeout=timeout)
        if (
            registers.get("r0") == 0x03005D60
            and registers.get("r1") == PALETTE_ADDRESS
            and registers.get("r2") == PALETTE_LENGTH
        ):
            return packet, registers, skipped
    raise RuntimeError("natural palette DMA queue anchor was not observed within 32 queue hits")


def _set_call_registers(client: Any, entry: int, r0: int, r1: int, r2: int) -> None:
    client.write_register(0, r0)
    client.write_register(1, r1)
    client.write_register(2, r2)
    client.write_register(14, RETURN_SENTINEL | 1)
    # The current B3CJ execution is already THUMB; preserving CPSR while
    # writing an even function address matches the normal GDB callsite shape.
    client.write_register(15, entry)


def _call_to_sentinel(client: Any, entry: int, r0: int, r1: int, r2: int, timeout: float) -> tuple[str, dict[str, int]]:
    client.set_breakpoint(RETURN_SENTINEL)
    try:
        _set_call_registers(client, entry, r0, r1, r2)
        return continue_until_pc(client, (RETURN_SENTINEL,), timeout=timeout)
    finally:
        client.remove_breakpoint(RETURN_SENTINEL)


def _controlled_writer(client: Any, font_base: int, timeout: float) -> dict[str, object]:
    input_bytes = TARGET_CODEPAGE_BYTES
    client.write_memory(INPUT_ADDRESS, input_bytes)
    client.set_breakpoint(GLYPH_WRITER)
    client.set_breakpoint(RETURN_SENTINEL)
    hits: list[dict[str, object]] = []
    try:
        _set_call_registers(client, FONT_WRITER, OUTPUT_ADDRESS, INPUT_ADDRESS, 0)
        for expected_id, index in zip(CHANGED_GLYPH_IDS, range(1, len(CHANGED_GLYPH_IDS) + 1)):
            packet, registers = continue_until_pc(
                client,
                (GLYPH_WRITER, RETURN_SENTINEL),
                timeout=timeout,
            )
            if _pc(registers) == RETURN_SENTINEL:
                raise RuntimeError(f"controlled writer returned before glyph {index}")
            glyph_pointer = int(registers["r0"])
            output_pointer = int(registers["r1"])
            try:
                glyph_id = glyph_id_from_pointer(glyph_pointer, font_base)
            except ValueError as exc:
                raise RuntimeError(
                    f"controlled glyph pointer 0x{glyph_pointer:08x} is not aligned to font "
                    f"0x{font_base:08x} (output=0x{output_pointer:08x})"
                ) from exc
            _require(glyph_id == expected_id, f"controlled glyph {index} resolved to 0x{glyph_id:03x}")
            _require(output_pointer == OUTPUT_ADDRESS + (index - 1) * 0x80, "controlled output pointer stride changed")
            hits.append(
                {
                    "index": index,
                    "packet": packet,
                    "glyph_id": f"0x{glyph_id:03x}",
                    "glyph_pointer": f"0x{glyph_pointer:08x}",
                    "output_pointer": f"0x{output_pointer:08x}",
                }
            )
        packet, registers = continue_until_pc(client, (RETURN_SENTINEL,), timeout=timeout)
        return {
            "entry": f"0x{FONT_WRITER:08x}",
            "glyph_writer": f"0x{GLYPH_WRITER:08x}",
            "input_address": f"0x{INPUT_ADDRESS:08x}",
            "input_length": len(input_bytes),
            "return": {"packet": packet, "pc": f"0x{_pc(registers):08x}"},
            "hits": hits,
        }
    finally:
        client.remove_breakpoint(GLYPH_WRITER)
        client.remove_breakpoint(RETURN_SENTINEL)


def _controlled_adjacent(client: Any, font_base: int, timeout: float) -> dict[str, object]:
    output_pointer = ADJACENT_OUTPUT_ADDRESS
    glyph_pointer = font_base + ADJACENT_GLYPH_ID * FONT_CELL_STRIDE
    _call_to_sentinel(client, GLYPH_WRITER, glyph_pointer, output_pointer, 0, timeout)
    data = client.read_memory(output_pointer, 0x80)
    return {
        "glyph_id": f"0x{ADJACENT_GLYPH_ID:03x}",
        "glyph_pointer": f"0x{glyph_pointer:08x}",
        "output": summarize(data, output_pointer),
        "boundary": "physical adjacent cell only; it is not a natural codepage/consumer hit",
    }


def probe(
    port: int,
    *,
    host: str = "127.0.0.1",
    timeout: float = 8.0,
    packet_delay: float = 0.12,
    retry_delay: float = 0.35,
) -> dict[str, object]:
    """Run one controlled probe on an already-started, own mGBA process."""

    result: dict[str, object] = {
        "host": host,
        "port": port,
        "single_connection": True,
        "timeout_seconds": timeout,
        "packet_delay_seconds": packet_delay,
        "retry_delay_seconds": retry_delay,
        "client": "core/gba/gdbstub_client.py",
    }
    client = GdbClient(host, port, timeout=timeout, packet_delay=packet_delay, retry_delay=retry_delay)
    try:
        client.connect()
        supported = client.request("qSupported:multiprocess+")
        initial_stop = client.request("?")
        _require(all(token in supported for token in REQUIRED_QSUPPORTED), "mGBA qSupported contract is incomplete")
        result["qSupported"] = supported
        result["initial_stop"] = initial_stop

        client.set_breakpoint(DMA_QUEUE)
        try:
            queue_packet, queue_regs, skipped_queue_hits = _find_palette_queue_anchor(client, timeout)
        finally:
            client.remove_breakpoint(DMA_QUEUE)

        font_base = int.from_bytes(client.read_memory(FONT_POINTER, 4), "little")
        _require(font_base == EXPECTED_FONT_BASE, f"font base changed: 0x{font_base:08x}")
        result["natural_anchor"] = {
            "function": f"0x{DMA_QUEUE:08x}",
            "packet": queue_packet,
            "pc": f"0x{_pc(queue_regs):08x}",
            "source": f"0x{queue_regs['r0']:08x}",
            "destination": f"0x{queue_regs['r1']:08x}",
            "length": int(queue_regs["r2"]),
            "font_base": f"0x{font_base:08x}",
            "skipped_unrelated_queue_hits": skipped_queue_hits,
            "palette_contract": queue_regs["r0"] == 0x03005D60 and queue_regs["r1"] == PALETTE_ADDRESS and queue_regs["r2"] == PALETTE_LENGTH,
        }

        writer = _controlled_writer(client, font_base, timeout)
        output_slices = [
            summarize(client.read_memory(OUTPUT_ADDRESS + index * 0x80, 0x80), OUTPUT_ADDRESS + index * 0x80)
            for index in range(len(CHANGED_GLYPH_IDS))
        ]
        adjacent = _controlled_adjacent(client, font_base, timeout)

        _call_to_sentinel(client, DMA_QUEUE, OUTPUT_ADDRESS, VRAM_ADDRESS, VRAM_LENGTH, timeout)
        _call_to_sentinel(client, DMA_FLUSH, 0, 0, 0, timeout)
        vram = client.read_memory(VRAM_ADDRESS, VRAM_LENGTH)
        palette = client.read_memory(PALETTE_ADDRESS, PALETTE_LENGTH)
        display = {
            name: int.from_bytes(client.read_memory(address, length), "little")
            for name, (address, length) in IO_REGISTERS.items()
        }

        result["writer"] = writer
        result["writer_output_slices"] = output_slices
        result["adjacent"] = adjacent
        result["queue_flush"] = {
            "queue": {"function": f"0x{DMA_QUEUE:08x}", "source": f"0x{OUTPUT_ADDRESS:08x}", "destination": f"0x{VRAM_ADDRESS:08x}", "length": VRAM_LENGTH},
            "flush": {"function": f"0x{DMA_FLUSH:08x}", "return_pc": f"0x{RETURN_SENTINEL:08x}"},
            "vram": summarize(vram, VRAM_ADDRESS),
            "vram_glyph_slices": [
                summarize(vram[index * 0x80 : (index + 1) * 0x80], VRAM_ADDRESS + index * 0x80)
                for index in range(len(CHANGED_GLYPH_IDS))
            ],
        }
        result["palette"] = summarize(palette, PALETTE_ADDRESS)
        result["display_registers"] = {name: f"0x{value:04x}" for name, value in display.items()}
        result["runtime_coverage"] = {
            "transport": "confirmed",
            "natural_anchor": "DMA queue/palette callsite",
            "controlled_lookup_writer": "confirmed",
            "controlled_queue_flush_vram": "confirmed",
            "natural_0308_consumer": "not-observed",
            "natural_target_record_reachability": "not-observed",
            "screen_readability": "not-proven",
            "tilemap": "unknown",
            "live_oam": "not-read",
        }
        result["boundary"] = (
            "The controlled writer, queue, flush, and live VRAM hashes are confirmed on one fresh process. "
            "This does not prove natural 0x0308 consumer reachability, tilemap placement, palette usability, "
            "OAM layout, or readable screen output."
        )
        result["handshake"] = "confirmed"
        return result
    finally:
        client.close()


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=pathlib.Path)
    parser.add_argument("target_rom", type=pathlib.Path)
    parser.add_argument("--bps", type=pathlib.Path)
    parser.add_argument("--bps-applied", type=pathlib.Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
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
            "game": EXPECTED_GAME,
            "revision": EXPECTED_REVISION,
            "milestone": "M5.5-post-runtime-gate",
            "target_string_id": TARGET_ID,
            "process_pid": args.process_pid,
            "binary_sha256": args.binary_sha256,
            "source_revision": args.source_revision,
            "compile_time_port": args.port,
            "artifacts": artifacts,
            "probe": probe(
                args.port,
                host=args.host,
                timeout=args.timeout,
                packet_delay=args.packet_delay,
                retry_delay=args.retry_delay,
            ),
            "raw_output_policy": "hashes only; raw runtime memory and renders stay in /private/tmp or ignored work/",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M5_WRITER_PROBE_OK output={args.output}")
        return 0
    except (OSError, RuntimeError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"runtime_m5_writer_probe.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
