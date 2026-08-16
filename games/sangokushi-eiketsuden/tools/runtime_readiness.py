#!/usr/bin/env python3
"""Non-invasive B3EJ mGBA process/port readiness checks.

The check deliberately never opens a GDB connection: mGBA 0.10.x commonly
accepts only one client, and that connection belongs to the game harness.  A
preflight bind checks a candidate port before launch; the post-launch check
matches the exact child PID, ROM path and listener reported by ``lsof``.
Reports contain process/port metadata only.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
from pathlib import Path


def probe_port_free(host: str, port: int) -> dict[str, object]:
    """Bind and immediately release a candidate port without connecting."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as exc:
        return {
            "host": host,
            "port": port,
            "status": "unavailable",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    finally:
        sock.close()
    return {"host": host, "port": port, "status": "free"}


def process_command(pid: int) -> str:
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def process_matches_rom(command: str, rom_path: Path) -> bool:
    return str(rom_path.resolve()) in command


def listener_output(pid: int, port: int) -> str:
    completed = subprocess.run(
        [
            "lsof",
            "-nP",
            "-a",
            "-p",
            str(pid),
            f"-iTCP:{port}",
            "-sTCP:LISTEN",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def listener_matches_pid(output: str, pid: int, port: int) -> bool:
    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    return any(
        str(pid) in line and f":{port}" in line and "LISTEN" in line
        for line in lines[1:]
    )


def inspect_process(pid: int, port: int, rom_path: Path) -> dict[str, object]:
    command = process_command(pid)
    lsof = listener_output(pid, port)
    matches_rom = process_matches_rom(command, rom_path)
    matches_listener = listener_matches_pid(lsof, pid, port)
    return {
        "pid": pid,
        "port": port,
        "process_alive": bool(command),
        "process_matches_rom": matches_rom,
        "listener_matches_pid": matches_listener,
        "ready": bool(command) and matches_rom and matches_listener,
        "command_basename": Path(command.split(" ", 1)[0]).name if command else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--rom", type=Path)
    args = parser.parse_args()
    if args.preflight == (args.pid is not None or args.rom is not None):
        parser.error("choose --preflight or --pid with --rom")
    if args.preflight:
        report = probe_port_free(args.host, args.port)
    else:
        if args.pid is None or args.rom is None:
            parser.error("post-launch check requires --pid and --rom")
        report = inspect_process(args.pid, args.port, args.rom)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status", "ready" if report.get("ready") else "unavailable") in {"free", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
