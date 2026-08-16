#!/usr/bin/env python3
"""Fail-closed structural and copyright-safety check for runtime QA reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORBIDDEN_KEYS = {"raw", "raw_bytes", "bytes", "text", "decoded_text", "rom_data", "memory_dump"}
VALID_STATUS = {"pass", "fail", "unknown"}


def walk(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_KEYS:
                errors.append(f"{path}.{key}: forbidden raw-content field")
            errors.extend(walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(walk(child, f"{path}[{index}]"))
    return errors


def validate(report: dict[str, Any]) -> list[str]:
    errors = walk(report)
    if report.get("format") != "project-atlantis-gba-runtime-validation-report-v1":
        errors.append("$.format: unexpected report format")
    if report.get("unknown_policy") != "fail-closed":
        errors.append("$.unknown_policy: expected fail-closed")
    phase = report.get("phase")
    if phase not in {"manifest", "static", "runtime"}:
        errors.append("$.phase: expected manifest, static, or runtime")
    status = report.get("status")
    if status not in VALID_STATUS:
        errors.append("$.status: expected pass, fail, or unknown")
    diagnostics = report.get("diagnostics")
    evidence = report.get("evidence")
    if not isinstance(diagnostics, list):
        errors.append("$.diagnostics: expected list")
    else:
        diagnostic_statuses: set[str] = set()
        for index, diagnostic in enumerate(diagnostics):
            if not isinstance(diagnostic, dict):
                errors.append(f"$.diagnostics[{index}]: expected object")
                continue
            diagnostic_status = diagnostic.get("status")
            if diagnostic_status not in VALID_STATUS:
                errors.append(f"$.diagnostics[{index}].status: invalid status")
            else:
                diagnostic_statuses.add(diagnostic_status)
            if not isinstance(diagnostic.get("code"), str) or not diagnostic.get("code"):
                errors.append(f"$.diagnostics[{index}].code: expected non-empty string")
            if not isinstance(diagnostic.get("message"), str) or not diagnostic.get("message"):
                errors.append(f"$.diagnostics[{index}].message: expected non-empty string")
        reduced = "fail" if "fail" in diagnostic_statuses else "unknown" if "unknown" in diagnostic_statuses else "pass"
        if status in VALID_STATUS and status != reduced:
            errors.append(f"$.status: expected {reduced} from diagnostic reduction")
    if not isinstance(evidence, dict):
        errors.append("$.evidence: expected object")
        return errors
    capabilities = evidence.get("capabilities")
    if not isinstance(capabilities, dict):
        if report.get("phase") == "runtime":
            errors.append("$.evidence.capabilities: expected object")
        return errors
    required = set(capabilities.get("required", []))
    exercised = set(capabilities.get("exercised", []))
    unproven = set(capabilities.get("unproven", []))
    if required - exercised != unproven:
        errors.append("$.evidence.capabilities: unproven must equal required minus exercised")
    if status == "pass" and unproven:
        errors.append("$.status: pass is forbidden with unproven capabilities")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid report: {exc}")
        return 2
    if not isinstance(report, dict):
        print("invalid report: root must be an object")
        return 2
    errors = validate(report)
    for error in errors:
        print(error)
    if errors:
        return 2
    print(f"valid fail-closed report: {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
