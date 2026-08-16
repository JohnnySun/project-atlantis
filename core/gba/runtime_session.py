"""Own, verify, and safely clean up one mGBA/GDB runtime process."""

from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Sequence


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def probe_port_free(host: str, port: int) -> dict[str, object]:
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


def process_identity(pid: int, *, runner: CommandRunner = subprocess.run) -> dict[str, object] | None:
    completed = runner(
        ["ps", "-p", str(pid), "-o", "pid=,ppid=,lstart=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    line = completed.stdout.strip()
    if not line:
        return None
    match = re.fullmatch(
        r"\s*(\d+)\s+(\d+)\s+([A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})\s+(.+)",
        line,
    )
    if match is None:
        return None
    return {
        "pid": int(match.group(1)),
        "ppid": int(match.group(2)),
        "start": match.group(3),
        "command": match.group(4),
    }


def identity_matches(expected: dict[str, object], actual: dict[str, object] | None) -> bool:
    return actual is not None and all(actual.get(key) == expected.get(key) for key in ("pid", "ppid", "start", "command"))


def command_contains_rom(command: str, rom_path: Path) -> bool:
    expected = str(rom_path.resolve())
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return expected in tokens


def listener_pids(output: str, port: int) -> set[int]:
    pids: set[int] = set()
    for line in output.splitlines():
        if "LISTEN" not in line or f":{port}" not in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            pids.add(int(parts[1]))
    return pids


def listener_output(port: int, *, runner: CommandRunner = subprocess.run) -> str:
    completed = runner(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def inspect_owner(
    pid: int,
    port: int,
    rom_path: Path,
    *,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    identity = process_identity(pid, runner=runner)
    output = listener_output(port, runner=runner)
    pids = listener_pids(output, port)
    command = str(identity["command"]) if identity else ""
    process_matches = command_contains_rom(command, rom_path) if command else False
    listener_matches = pids == {pid}
    return {
        "pid": pid,
        "port": port,
        "process_alive": identity is not None,
        "process_matches_rom": process_matches,
        "listener_pids": sorted(pids),
        "listener_matches_exact_pid": listener_matches,
        "ready": identity is not None and process_matches and listener_matches,
        "identity": identity,
    }


def wait_until_ready(
    pid: int,
    port: int,
    rom_path: Path,
    timeout: float,
    *,
    interval: float = 0.1,
    runner: CommandRunner = subprocess.run,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = inspect_owner(pid, port, rom_path, runner=runner)
    while not last["ready"] and time.monotonic() < deadline:
        if not last["process_alive"]:
            break
        time.sleep(interval)
        last = inspect_owner(pid, port, rom_path, runner=runner)
    return last


def safe_terminate(
    process: subprocess.Popen[bytes],
    identity: dict[str, object],
    *,
    runner: CommandRunner = subprocess.run,
    timeout: float = 3.0,
) -> dict[str, object]:
    current = process_identity(process.pid, runner=runner)
    if current is None:
        return {"status": "already_exited", "pid": process.pid}
    if not identity_matches(identity, current):
        return {"status": "refused_identity_changed", "pid": process.pid}
    process.terminate()
    try:
        process.wait(timeout=timeout)
        return {"status": "terminated", "pid": process.pid}
    except subprocess.TimeoutExpired:
        current = process_identity(process.pid, runner=runner)
        if not identity_matches(identity, current):
            return {"status": "refused_identity_changed_after_term", "pid": process.pid}
        process.kill()
        process.wait(timeout=timeout)
        return {"status": "killed_after_timeout", "pid": process.pid}


def launch_command(executable: Path, rom_path: Path, extra_args: Sequence[str]) -> list[str]:
    return [str(executable.resolve()), *extra_args, "-g", str(rom_path.resolve())]


def launch(
    executable: Path,
    rom_path: Path,
    extra_args: Sequence[str],
    log_path: Path,
    *,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[bytes], object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("wb")
    process = subprocess.Popen(
        launch_command(executable, rom_path, extra_args),
        cwd=Path.cwd(),
        env={**os.environ, **(env or {})},
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    return process, handle
