#!/usr/bin/env python3
"""Launch one owned mGBA process and run a manifest QA case safely."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.gba.runtime_session import (  # noqa: E402
    inspect_owner,
    launch,
    probe_port_free,
    process_identity,
    safe_terminate,
    wait_until_ready,
)


def write_report(value: dict[str, object], path: Path | None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(text, end="")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path} status={value['status']}", file=sys.stderr)


def parse_env(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        key, separator, item = value.partition("=")
        if not separator or not key:
            raise ValueError(f"invalid --env value: {value!r}")
        result[key] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--host", default="127.0.0.1")
    preflight.add_argument("--port", type=int, required=True)
    preflight.add_argument("--session-report", type=Path)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--pid", type=int, required=True)
    inspect.add_argument("--port", type=int, required=True)
    inspect.add_argument("--rom", type=Path, required=True)
    inspect.add_argument("--session-report", type=Path)
    run = sub.add_parser("run")
    run.add_argument("manifest", type=Path)
    run.add_argument("--rom", type=Path, required=True)
    run.add_argument("--mgba", type=Path, required=True)
    run.add_argument("--mgba-arg", action="append", default=[])
    run.add_argument("--env", action="append", default=[])
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, required=True)
    run.add_argument("--listener-timeout", type=float, default=8.0)
    run.add_argument("--runtime-report", type=Path, required=True)
    run.add_argument("--session-report", type=Path, required=True)
    run.add_argument("--log", type=Path, required=True)
    run.add_argument("--savestate", type=Path)
    args = parser.parse_args()

    if args.command == "preflight":
        value = probe_port_free(args.host, args.port)
        report = {
            "format": "project-atlantis-gba-runtime-session-v1",
            "status": "pass" if value["status"] == "free" else "unknown",
            "preflight": value,
        }
        write_report(report, args.session_report)
        return 0 if report["status"] == "pass" else 2
    if args.command == "inspect":
        value = inspect_owner(args.pid, args.port, args.rom.resolve())
        report = {
            "format": "project-atlantis-gba-runtime-session-v1",
            "status": "pass" if value["ready"] else "unknown",
            "ownership": value,
        }
        write_report(report, args.session_report)
        return 0 if report["status"] == "pass" else 2

    report: dict[str, object] = {
        "format": "project-atlantis-gba-runtime-session-v1",
        "status": "unknown",
        "preflight": probe_port_free(args.host, args.port),
        "ownership": None,
        "runtime_exit": None,
        "cleanup": None,
    }
    if report["preflight"]["status"] != "free":  # type: ignore[index]
        write_report(report, args.session_report)
        return 2
    process = None
    handle = None
    identity = None
    try:
        process, handle = launch(
            args.mgba,
            args.rom.resolve(),
            args.mgba_arg,
            args.log,
            env=parse_env(args.env),
        )
        identity = process_identity(process.pid)
        if identity is None:
            report["ownership"] = {"ready": False, "reason": "child identity unavailable"}
            return_code = 2
        else:
            ownership = wait_until_ready(
                process.pid,
                args.port,
                args.rom.resolve(),
                args.listener_timeout,
            )
            report["ownership"] = ownership
            if not ownership["ready"]:
                return_code = 2
            else:
                command = [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "gba-runtime-qa.py"),
                    "runtime",
                    str(args.manifest),
                    "--host",
                    args.host,
                    "--port",
                    str(args.port),
                    "--rom",
                    str(args.rom.resolve()),
                    "--output",
                    str(args.runtime_report),
                ]
                if args.savestate:
                    command.extend(["--savestate", str(args.savestate)])
                completed = subprocess.run(command, check=False)
                report["runtime_exit"] = completed.returncode
                report["status"] = {0: "pass", 1: "fail"}.get(completed.returncode, "unknown")
                return_code = completed.returncode if completed.returncode in {0, 1, 2} else 2
    except (OSError, ValueError) as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        return_code = 2
    finally:
        if process is not None and identity is not None:
            report["cleanup"] = safe_terminate(process, identity)
        elif process is not None:
            report["cleanup"] = {"status": "refused_without_identity", "pid": process.pid}
        if handle is not None:
            handle.close()
        write_report(report, args.session_report)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
