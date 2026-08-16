#!/usr/bin/env python3
"""M2.4 B3CJ runtime-handshake diagnostic and static writer evidence.

This tool never launches or stops an emulator.  The caller must launch one
fresh mGBA process that points at the ignored M2.3 POC ROM, verify its PID and
listener independently, and then run this tool once against that listener.
The handshake uses the shared core/gba client, which sends GDB ACKs, waits
between packets, and retries one read timeout.  A failed handshake is a
recorded diagnostic result, not runtime evidence.

The static section is deliberately useful when no listener exists: it checks
the clean B3CJ ROM's reviewed function hashes and records the csm3-confirmed
output-buffer contracts for the two glyph writers.  Those contracts identify
RAM/output-buffer destinations and per-glyph strides; they do not identify a
live VRAM address or prove natural reachability.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
CORE_GBA = REPO_ROOT / "core" / "gba"
INSPECT_FONT_PATH = GAME_ROOT / "tools" / "inspect_font.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSPECT_FONT = _load_module("b3cj_inspect_font_m24", INSPECT_FONT_PATH)
if str(CORE_GBA) not in sys.path:
    sys.path.insert(0, str(CORE_GBA))
from gdbstub_client import GdbClient  # noqa: E402


EXPECTED_POC_SHA256 = "ce99a443cfab8f84cc7f7a0319b9271ce3173dc64c488ca138696ae938460a07"
EXPECTED_ROM_SIZE = 0x02000000

# These ranges are the local B3CJ bytes corresponding to the csm3 callsites.
# A range hash is the independent local-ROM check; the register/stride
# descriptions come from the reviewed assembly callsite, not from a live hit.
WRITER_FUNCTIONS = (
    ("sub_08002CB4", 0x00002CB4, 0x000031E8, "7ea0b0df799259d52eee5b818d7abcfa8fe51ddbdc0456fe202489769f67ee1b"),
    ("sub_080031E8", 0x000031E8, 0x0000348C, "f8c50f544edd95f65e987769c2add46ab779a02650a6220f43fc5bde17e69d9b"),
    ("sub_080036F8", 0x000036F8, 0x0000382E, "8593bbedfbfa610d0411f09ac808ccb4191ab7ff8b570f66168b94ddd639ee35"),
    ("sub_0800379C", 0x0000379C, 0x00003840, "f79dcb74807def1c83fce4a737ea97847baee59dc033e37850800dbbca566a0e"),
)

WRITER_PATHS = (
    {
        "caller": "sub_080036F8",
        "lookup": "sub_0800348C",
        "glyph_writer": "sub_08002CB4",
        "caller_output_buffer_register": "r0",
        "writer_destination_register": "r1",
        "writer_output_span": "0x80",
        "per_glyph_stride": "0x80",
        "evidence": "local function hashes plus csm3 callsite: lookup -> writer; caller r5/r0 increments by 0x80",
    },
    {
        "caller": "sub_0800379C",
        "lookup": "sub_0800348C",
        "glyph_writer": "sub_080031E8",
        "caller_output_buffer_register": "r0",
        "writer_destination_register": "r1",
        "writer_output_span": "0x40",
        "per_glyph_stride": "0x40",
        "evidence": "local function hashes plus csm3 callsite: lookup -> writer; caller r5/r0 increments by 0x40",
    },
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def static_writer_evidence(rom_data: bytes) -> dict[str, object]:
    """Verify local writer ranges and return non-raw destination evidence."""

    identity = INSPECT_FONT.verify_rom(rom_data)
    static = INSPECT_FONT.verify_static_evidence(rom_data)
    functions: list[dict[str, object]] = []
    for name, start, end, expected_hash in WRITER_FUNCTIONS:
        actual_hash = sha256_bytes(rom_data[start:end])
        if actual_hash != expected_hash:
            raise ValueError(f"writer function hash mismatch: {name}")
        functions.append(
            {
                "name": name,
                "file_range": f"0x{start:x}..0x{end:x}",
                "sha256": actual_hash,
                "matches_fixed_b3cj": True,
            }
        )
    return {
        "evidence_level": "confirmed-static",
        "rom_identity": identity,
        "reviewed_font_chain": {
            "function_checks": len(static["function_checks"]),
            "literal_checks": len(static["literal_checks"]),
            "font_base_runtime_global": "0x03002984",
            "lookup": "sub_0800348C",
        },
        "writer_function_checks": functions,
        "writer_paths": list(WRITER_PATHS),
        "boundary": "r1 output-buffer destination and 0x80/0x40 RAM writer spans are static; live VRAM/OAM destination is not proven",
    }


def static_poc_evidence(poc_path: pathlib.Path) -> dict[str, object]:
    """Check changed and adjacent untouched glyphs in the ignored POC ROM."""

    data = poc_path.read_bytes()
    if len(data) != EXPECTED_ROM_SIZE:
        raise ValueError(f"M2.3 POC size mismatch: 0x{len(data):x}")
    actual_sha256 = sha256_bytes(data)
    if actual_sha256 != EXPECTED_POC_SHA256:
        raise ValueError(f"M2.3 POC SHA-256 mismatch: {actual_sha256}")
    font = INSPECT_FONT.parse_font_resource(data)
    entries = []
    for label, code_unit, glyph_id, state in (
        ("untouched_adjacent", None, 0x844, "untouched_reference"),
        ("changed_de", bytes.fromhex("ec48"), 0x845, "changed_static_poc"),
        ("changed_ni", bytes.fromhex("ec49"), 0x846, "changed_static_poc"),
    ):
        lookup = None
        if code_unit is not None:
            lookup = INSPECT_FONT.lookup_code_unit(
                data,
                code_unit,
                slot_count=int(font["slot_count"]),
                font_base_file_offset=int(font["font_base_file_offset"]),
            )
        rendered = INSPECT_FONT.render_glyph(data, font, glyph_id)
        entries.append(
            {
                "label": label,
                "code_unit": None if code_unit is None else code_unit.hex(),
                "expected_glyph_id": f"0x{glyph_id:03x}",
                "lookup_status": "not_assigned" if lookup is None else lookup["status"],
                "lookup_glyph_id": None if lookup is None or lookup["glyph_id"] is None else f"0x{int(lookup['glyph_id']):03x}",
                "state": state,
                "cell_file_offset": rendered["cell_file_offset"],
                "cell_sha256": rendered["cell_sha256"],
                "rows": rendered["rows"],
            }
        )
        if state == "changed_static_poc" and (lookup is None or lookup["status"] != "mapped" or int(lookup["glyph_id"]) != glyph_id):
            raise ValueError(f"static POC lookup mismatch: {label}")
    return {
        "evidence_level": "confirmed-static-poc",
        "rom_sha256": actual_sha256,
        "font_base_file_offset": f"0x{int(font['font_base_file_offset']):x}",
        "cell_size": int(font["cell_size"]),
        "changed_and_adjacent": entries,
        "boundary": "static cell render only; no runtime palette, VRAM, tilemap, OAM, or screen-readability claim",
    }


def handshake(
    port: int,
    *,
    host: str = "127.0.0.1",
    timeout: float = 5.0,
    packet_delay: float = 0.08,
    retry_delay: float = 0.25,
) -> dict[str, object]:
    """Perform one connection and the minimal read-only GDB handshake."""

    result: dict[str, object] = {
        "host": host,
        "port": port,
        "single_connection": True,
        "packet_delay_seconds": packet_delay,
        "retry_delay_seconds": retry_delay,
        "timeout_seconds": timeout,
        "ack_and_retry_provider": "core/gba/gdbstub_client.py",
        "connect": False,
        "qSupported": None,
        "initial_stop": None,
        "error": None,
    }
    client = GdbClient(host, port, timeout=timeout, packet_delay=packet_delay, retry_delay=retry_delay)
    try:
        client.connect()
        result["connect"] = True
        result["qSupported"] = client.request("qSupported:multiprocess+")
        result["initial_stop"] = client.request("?")
        result["registers"] = client.read_registers()
        result["io"] = {
            name: int.from_bytes(client.read_memory(address, 2), "little")
            for name, address in {
                "DISPCNT": 0x04000000,
                "BG0CNT": 0x04000008,
                "BG1CNT": 0x0400000A,
                "BG2CNT": 0x0400000C,
                "BG3CNT": 0x0400000E,
                "KEYINPUT": 0x04000130,
            }.items()
        }
        result["handshake"] = "confirmed"
    except Exception as exc:  # diagnostic must preserve the exact transport failure
        result["handshake"] = "blocked"
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        client.close()
    return result


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="clean B3CJ ROM")
    parser.add_argument("--poc-rom", type=pathlib.Path, required=True, help="ignored M2.3 POC ROM")
    parser.add_argument("--port", type=int, required=True, help="one fresh mGBA GDB port")
    parser.add_argument("--output", type=pathlib.Path, required=True, help="ignored diagnostic JSON")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--process-pid", type=int)
    parser.add_argument("--launcher", default=None, help="launcher command recorded as provenance")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        rom_data = args.rom.read_bytes()
        report: dict[str, object] = {
            "game": "summon-night-craft-sword-3",
            "revision": "B3CJ",
            "attempt": args.attempt,
            "diagnostic_only": True,
            "launcher": args.launcher,
            "process_pid": args.process_pid,
            "static_writer": static_writer_evidence(rom_data),
            "static_poc": static_poc_evidence(args.poc_rom),
            "runtime": handshake(args.port),
            "runtime_boundary": "A handshake failure is not runtime evidence; static writer paths do not identify VRAM/OAM destinations.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        status = report["runtime"]["handshake"]
        print(f"B3CJ_M2_4_DIAGNOSTIC_OK attempt={args.attempt} handshake={status} output={args.output}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"runtime_m2_4.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
