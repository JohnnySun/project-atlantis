"""Command-line interface for manifest validation and GBA QA reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .manifest import ManifestError, load_manifest
from .result import Report
from .runtime import run_runtime
from .static_checks import run_static


def _write(report: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"wrote {output} status={report['status']}", file=sys.stderr)


def _unknown(phase: str, message: str) -> Report:
    report = Report(phase)
    report.add("unknown", f"{phase}.manifest", message)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-manifest")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("--output", type=Path)
    static = sub.add_parser("static")
    static.add_argument("manifest", type=Path)
    static.add_argument("--base-rom", required=True, type=Path)
    static.add_argument("--candidate-rom", type=Path)
    static.add_argument("--output", type=Path)
    runtime = sub.add_parser("runtime")
    runtime.add_argument("manifest", type=Path)
    runtime.add_argument("--host", default="127.0.0.1")
    runtime.add_argument("--port", required=True, type=int)
    runtime.add_argument("--rom", required=True, type=Path)
    runtime.add_argument("--savestate", type=Path, help="local state file pinned by runtime.savestate")
    runtime.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        report = _unknown(args.command, str(exc))
        _write(report.to_dict(), getattr(args, "output", None))
        return report.exit_code
    if args.command == "validate-manifest":
        report = Report("manifest")
        report.add("pass", "manifest.valid", "manifest passed strict built-in validation")
        report.evidence["case_id"] = manifest["case_id"]
    elif args.command == "static":
        report = run_static(manifest, args.base_rom, args.candidate_rom)
    else:
        report = run_runtime(manifest, args.host, args.port, args.rom, args.savestate)
    _write(report.to_dict(), args.output)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
