#!/usr/bin/env python3
"""M2.6 B3CJ target/runtime QA guard.

This diagnostic verifies the ignored M2.5 base ROM, target ROM, BPS and
static target/adjacent glyph evidence before making one GDB connection.  It
reuses the shared GDB client and capture helper; it never launches, stops or
reconnects to an emulator.  A missing listener is recorded as transport
pending, not as a translation or ROM failure.

Runtime dumps and capture summaries must stay under the ignored ``work/``
directory or ``/private/tmp``.  The JSON written by this tool contains hashes,
addresses, register/display metadata and errors only; it does not copy source
text or raw memory into a tracked file.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
CORE_GBA = REPO_ROOT / "core" / "gba"
M25_PATH = GAME_ROOT / "tools" / "build_m2_5_batch.py"
FONT_PATH = GAME_ROOT / "tools" / "inspect_font.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M25 = _load_module("b3cj_build_m25_for_m26", M25_PATH)
INSPECT_FONT = _load_module("b3cj_inspect_font_m26", FONT_PATH)
if str(CORE_GBA) not in sys.path:
    sys.path.insert(0, str(CORE_GBA))
from capture_runtime import capture as core_capture  # noqa: E402
from gdbstub_client import GdbClient  # noqa: E402


EXPECTED_BASE_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_BASE_CRC32 = "12afae5d"
EXPECTED_TARGET_SHA256 = "da9c99426bf80c18729256a694ce6e499eab6d036fe26887908b8cb44cdf5b16"
EXPECTED_TARGET_CRC32 = "74f884c4"
EXPECTED_BPS_SHA256 = "42618b4afffed33600f3f8f73b3e3f6bea3f7aa9ba8c74e5016121f9f7ec6e5b"
EXPECTED_BPS_SIZE = 1543
EXPECTED_BATCH_ID = "m2.5-prize-ui"
TARGET_ID = "b3cj:t2:024:0x0064"
EXPECTED_ALLOCATIONS = (
    ("ec64", 0x847, "這"),
    ("ec65", 0x848, "獎"),
    ("ec66", 0x849, "是"),
)
ADJACENT_GLYPH_ID = 0x846
EXPECTED_ROM_SIZE = 0x02000000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08x}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _static_glyph(data: bytes, font: Mapping[str, object], glyph_id: int) -> dict[str, object]:
    rendered = INSPECT_FONT.render_glyph(data, font, glyph_id)
    return {
        "glyph_id": f"0x{glyph_id:03x}",
        "cell_file_offset": rendered["cell_file_offset"],
        "cell_sha256": rendered["cell_sha256"],
        "render_sha256": rendered["render_sha256"],
        "rows": rendered["rows"],
    }


def verify_static_target(
    base_path: pathlib.Path,
    target_path: pathlib.Path,
    bps_path: pathlib.Path,
    applied_path: pathlib.Path,
    summary_path: pathlib.Path,
    plan_path: pathlib.Path,
) -> dict[str, object]:
    """Verify M2.5 artifacts and target/adjacent static render evidence."""

    base = base_path.read_bytes()
    target = target_path.read_bytes()
    applied = applied_path.read_bytes()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    plan = M25.load_plan(plan_path)

    _require(len(base) == EXPECTED_ROM_SIZE, "M2.5 base ROM size mismatch")
    _require(len(target) == EXPECTED_ROM_SIZE, "M2.5 target ROM size mismatch")
    _require(sha256_bytes(base) == EXPECTED_BASE_SHA256, "M2.5 base ROM SHA-256 mismatch")
    _require(crc32_bytes(base) == EXPECTED_BASE_CRC32, "M2.5 base ROM CRC32 mismatch")
    _require(sha256_bytes(target) == EXPECTED_TARGET_SHA256, "M2.5 target ROM SHA-256 mismatch")
    _require(crc32_bytes(target) == EXPECTED_TARGET_CRC32, "M2.5 target ROM CRC32 mismatch")
    _require(applied == target, "M2.5 BPS applied ROM differs from target ROM")
    _require(sha256_file(bps_path) == EXPECTED_BPS_SHA256, "M2.5 BPS SHA-256 mismatch")
    _require(bps_path.stat().st_size == EXPECTED_BPS_SIZE, "M2.5 BPS size mismatch")

    _require(summary.get("batch_id") == EXPECTED_BATCH_ID, "M2.5 summary batch mismatch")
    _require(summary.get("translated_string_ids") == [TARGET_ID], "M2.5 target ID mismatch")
    _require(summary.get("runtime_qa") == "pending", "M2.5 runtime status must remain pending")
    reextract = summary.get("reextract")
    _require(isinstance(reextract, dict), "M2.5 reextract summary missing")
    _require(reextract.get("records_total") == 361, "M2.5 record count mismatch")
    _require(reextract.get("target_records") == 1, "M2.5 target record count mismatch")
    _require(reextract.get("untouched_records") == 360, "M2.5 untouched record count mismatch")
    _require(summary.get("byte_level", {}).get("all_361_records_reextracted") is True, "M2.5 reextract proof missing")

    plan_records = plan.get("records")
    _require(isinstance(plan_records, list) and len(plan_records) == 1, "M2.5 plan record count mismatch")
    _require(plan_records[0]["string_id"] == TARGET_ID, "M2.5 plan target mismatch")
    _require(set(plan.get("adjacent_untouched_records", [])) == {
        "b3cj:t2:024:0x0046",
        "b3cj:t2:024:0x0078",
    }, "M2.5 adjacent record contract mismatch")

    base_font = INSPECT_FONT.parse_font_resource(base)
    target_font = INSPECT_FONT.parse_font_resource(target)
    allocations: list[dict[str, object]] = []
    for raw_hex, glyph_id, unicode_char in EXPECTED_ALLOCATIONS:
        raw = bytes.fromhex(raw_hex)
        base_lookup = INSPECT_FONT.lookup_code_unit(
            base,
            raw,
            slot_count=int(base_font["slot_count"]),
            font_base_file_offset=int(base_font["font_base_file_offset"]),
        )
        target_lookup = INSPECT_FONT.lookup_code_unit(
            target,
            raw,
            slot_count=int(target_font["slot_count"]),
            font_base_file_offset=int(target_font["font_base_file_offset"]),
        )
        _require(base_lookup["status"] == "fallback", f"base glyph {raw_hex} is not fallback")
        _require(target_lookup["status"] == "mapped", f"target glyph {raw_hex} is not mapped")
        _require(int(target_lookup["glyph_id"]) == glyph_id, f"target glyph {raw_hex} slot mismatch")
        rendered = _static_glyph(target, target_font, glyph_id)
        allocations.append(
            {
                "code_unit": raw_hex,
                "unicode": unicode_char,
                "glyph_id": f"0x{glyph_id:03x}",
                "base_status": base_lookup["status"],
                "target_status": target_lookup["status"],
                "target_cell_sha256": rendered["cell_sha256"],
                "target_render_sha256": rendered["render_sha256"],
                "target_rows": rendered["rows"],
            }
        )

    base_adjacent = _static_glyph(base, base_font, ADJACENT_GLYPH_ID)
    target_adjacent = _static_glyph(target, target_font, ADJACENT_GLYPH_ID)
    _require(base_adjacent["cell_sha256"] == target_adjacent["cell_sha256"], "adjacent glyph cell changed")
    _require(base_adjacent["render_sha256"] == target_adjacent["render_sha256"], "adjacent glyph render changed")

    return {
        "evidence_level": "confirmed-static-target",
        "batch_id": EXPECTED_BATCH_ID,
        "translated_string_ids": [TARGET_ID],
        "base": {
            "sha256": sha256_bytes(base),
            "crc32": crc32_bytes(base),
            "size": len(base),
        },
        "target": {
            "sha256": sha256_bytes(target),
            "crc32": crc32_bytes(target),
            "size": len(target),
        },
        "bps": {
            "sha256": sha256_file(bps_path),
            "size": bps_path.stat().st_size,
            "applied_byte_identical": True,
        },
        "changed_glyphs": allocations,
        "adjacent_untouched_glyph": {
            "glyph_id": f"0x{ADJACENT_GLYPH_ID:03x}",
            "base_cell_sha256": base_adjacent["cell_sha256"],
            "target_cell_sha256": target_adjacent["cell_sha256"],
            "base_render_sha256": base_adjacent["render_sha256"],
            "target_render_sha256": target_adjacent["render_sha256"],
            "byte_identical": True,
        },
        "reextract": {
            "records_total": reextract["records_total"],
            "target_records": reextract["target_records"],
            "untouched_records": reextract["untouched_records"],
            "adjacent_records_byte_identical": all(
                bool(item.get("byte_identical_to_clean"))
                for item in reextract.get("adjacent_untouched", [])
                if isinstance(item, dict)
            ),
        },
        "runtime_boundary": "Static target/adjacent evidence only; no palette, VRAM/OAM, screen readability, or natural reachability claim.",
    }


def handshake(
    port: int,
    *,
    host: str = "127.0.0.1",
    timeout: float = 5.0,
    packet_delay: float = 0.08,
    retry_delay: float = 0.25,
    capture_runtime: bool = False,
    run_seconds: float = 1.0,
    breakpoint_address: int | None = None,
    breakpoint_timeout: float = 5.0,
    watchpoint_address: int | None = None,
    watch_length: int = 4,
    watch_type: int = 2,
    watch_timeout: float = 5.0,
    dump_dir: pathlib.Path | None = None,
) -> dict[str, object]:
    """Make one connection, readiness-check qSupported, optionally capture."""

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
        "capture_requested": capture_runtime,
    }
    client = GdbClient(host, port, timeout=timeout, packet_delay=packet_delay, retry_delay=retry_delay)
    try:
        client.connect()
        result["connect"] = True
        result["qSupported"] = client.request("qSupported:multiprocess+")
        result["initial_stop"] = client.request("?")
        if capture_runtime:
            # The shared helper owns the standard registers/I/O/RAM/VRAM/OAM
            # capture.  It runs on this same client; no second connection is
            # opened.
            result["capture"] = core_capture(
                client,
                run_seconds=run_seconds,
                breakpoint=breakpoint_address,
                breakpoint_timeout=breakpoint_timeout,
                watchpoint=watchpoint_address,
                watch_length=watch_length,
                watch_type=watch_type,
                watch_timeout=watch_timeout,
                dump_dir=dump_dir,
            )
        else:
            result["handshake"] = "confirmed"
    except Exception as exc:  # diagnostic preserves exact transport failures
        result["handshake"] = "blocked"
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        client.close()
    if result.get("connect") and capture_runtime and "capture" in result:
        result["handshake"] = "confirmed"
    return result


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=pathlib.Path)
    parser.add_argument("target_rom", type=pathlib.Path)
    parser.add_argument("--bps", type=pathlib.Path, required=True)
    parser.add_argument("--bps-applied", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    parser.add_argument("--plan", type=pathlib.Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--process-pid", type=int)
    parser.add_argument("--launcher", default=None)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--run-seconds", type=float, default=1.0)
    parser.add_argument("--breakpoint", type=lambda value: int(value, 0))
    parser.add_argument("--breakpoint-timeout", type=float, default=5.0)
    parser.add_argument("--watchpoint", type=lambda value: int(value, 0))
    parser.add_argument("--watch-length", type=lambda value: int(value, 0), default=4)
    parser.add_argument("--watch-type", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument("--watch-timeout", type=float, default=5.0)
    parser.add_argument("--dump-dir", type=pathlib.Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report: dict[str, object] = {
            "game": "summon-night-craft-sword-3",
            "revision": "B3CJ",
            "milestone": "M2.6",
            "attempt": args.attempt,
            "diagnostic_only": True,
            "launcher": args.launcher,
            "process_pid": args.process_pid,
            "static_target": verify_static_target(
                args.base_rom,
                args.target_rom,
                args.bps,
                args.bps_applied,
                args.summary,
                args.plan,
            ),
            "runtime": handshake(
                args.port,
                capture_runtime=args.capture,
                run_seconds=args.run_seconds,
                breakpoint_address=args.breakpoint,
                breakpoint_timeout=args.breakpoint_timeout,
                watchpoint_address=args.watchpoint,
                watch_length=args.watch_length,
                watch_type=args.watch_type,
                watch_timeout=args.watch_timeout,
                dump_dir=args.dump_dir,
            ),
            "runtime_boundary": "A handshake failure is transport-only; static target proof does not identify live cache, VRAM/OAM, palette or screen readability.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        status = report["runtime"]["handshake"]
        print(f"B3CJ_M2_6_DIAGNOSTIC_OK attempt={args.attempt} handshake={status} output={args.output}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"runtime_m2_6.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
