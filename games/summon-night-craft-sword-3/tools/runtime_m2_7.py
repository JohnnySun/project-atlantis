#!/usr/bin/env python3
"""B3CJ M2.7 transport-only runtime QA guard.

This tool reuses the M2.6 hash/static guard and the shared GDB client.  It
never launches, stops, or reconnects to an emulator: launcher ownership and
listener checks are deliberately performed by the caller before this one
connection probe.  A successful probe may optionally run the existing core
capture on that same connection; it does not infer natural or controlled
consumer reachability from a handshake alone.

The JSON report is safe for a tracked research receipt: it contains hashes,
addresses, transport metadata, and error types only.  Runtime dumps and
capture output must remain under ignored ``work/`` or ``/private/tmp``.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
M26_PATH = GAME_ROOT / "tools" / "runtime_m2_6.py"
TARGET_ID = "b3cj:t2:024:0x0064"
CHANGED_GLYPHS = ("0x847", "0x848", "0x849")
ADJACENT_GLYPH = "0x846"


def _load_m26() -> Any:
    spec = importlib.util.spec_from_file_location("b3cj_runtime_m2_6_for_m2_7", M26_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {M26_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M26 = _load_m26()


def probe(
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
    """Make exactly one readiness-first GDB probe through the shared client."""

    return M26.handshake(
        port,
        host=host,
        timeout=timeout,
        packet_delay=packet_delay,
        retry_delay=retry_delay,
        capture_runtime=capture_runtime,
        run_seconds=run_seconds,
        breakpoint_address=breakpoint_address,
        breakpoint_timeout=breakpoint_timeout,
        watchpoint_address=watchpoint_address,
        watch_length=watch_length,
        watch_type=watch_type,
        watch_timeout=watch_timeout,
        dump_dir=dump_dir,
    )


def build_report(
    base_path: pathlib.Path,
    target_path: pathlib.Path,
    bps_path: pathlib.Path,
    applied_path: pathlib.Path,
    summary_path: pathlib.Path,
    plan_path: pathlib.Path,
    *,
    port: int,
    attempt: int,
    listener_status: str,
    launcher: str | None,
    process_pid: int | None,
    probe_kwargs: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a M2.7 report without turning static evidence into live proof."""

    static_target = M26.verify_static_target(
        base_path,
        target_path,
        bps_path,
        applied_path,
        summary_path,
        plan_path,
    )
    runtime = probe(port, **(probe_kwargs or {}))
    ready = bool(runtime.get("connect") and runtime.get("qSupported"))
    return {
        "game": "summon-night-craft-sword-3",
        "revision": "B3CJ",
        "milestone": "M2.7",
        "attempt": attempt,
        "target_string_id": TARGET_ID,
        "launcher": launcher,
        "process_pid": process_pid,
        "listener": {
            "port": port,
            "status": listener_status,
            "check_command": f"lsof -nP -iTCP:{port} -sTCP:LISTEN",
        },
        "static_target": {
            "evidence_level": static_target["evidence_level"],
            "translated_string_ids": static_target["translated_string_ids"],
            "changed_glyphs": static_target["changed_glyphs"],
            "adjacent_untouched_glyph": static_target["adjacent_untouched_glyph"],
            "reextract": static_target["reextract"],
        },
        "runtime": runtime,
        "runtime_coverage": {
            "transport": "confirmed" if ready else "blocked",
            "qSupported": ready,
            "consumer_hit": False,
            "reachability": "not-attempted-transport-blocked" if not ready else "pending-capture-review",
            "changed_glyphs": list(CHANGED_GLYPHS),
            "adjacent_untouched_glyph": ADJACENT_GLYPH,
            "vram_render": "not-captured" if not ready else "capture-required",
        },
        "boundary": (
            "M2.7 transport-only: no natural/controlled consumer, cache, VRAM, palette, "
            "tilemap, OAM, or screen-readability claim without qSupported and a recorded hit."
        ),
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=pathlib.Path)
    parser.add_argument("target_rom", type=pathlib.Path)
    parser.add_argument("--bps", type=pathlib.Path, required=True)
    parser.add_argument("--bps-applied", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    parser.add_argument("--plan", type=pathlib.Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--listener-status", choices=("confirmed", "absent", "unknown"), default="unknown")
    parser.add_argument("--process-pid", type=int)
    parser.add_argument("--launcher")
    parser.add_argument("--output", type=pathlib.Path, required=True)
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
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        report = build_report(
            args.base_rom,
            args.target_rom,
            args.bps,
            args.bps_applied,
            args.summary,
            args.plan,
            port=args.port,
            attempt=args.attempt,
            listener_status=args.listener_status,
            launcher=args.launcher,
            process_pid=args.process_pid,
            probe_kwargs={
                "capture_runtime": args.capture,
                "run_seconds": args.run_seconds,
                "breakpoint_address": args.breakpoint,
                "breakpoint_timeout": args.breakpoint_timeout,
                "watchpoint_address": args.watchpoint,
                "watch_length": args.watch_length,
                "watch_type": args.watch_type,
                "watch_timeout": args.watch_timeout,
                "dump_dir": args.dump_dir,
            },
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_M2_7_TRANSPORT_OK "
            f"attempt={args.attempt} listener={args.listener_status} "
            f"handshake={report['runtime']['handshake']} output={args.output}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"runtime_m2_7.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
