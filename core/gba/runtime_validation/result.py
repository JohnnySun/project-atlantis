"""Shared result model and fail-closed status reduction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


VALID_STATUSES = {"pass", "fail", "unknown"}


@dataclass
class Report:
    phase: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        status: str,
        code: str,
        message: str,
        **details: Any,
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid diagnostic status: {status}")
        row: dict[str, Any] = {
            "status": status,
            "code": code,
            "message": message,
        }
        if details:
            row["details"] = details
        self.diagnostics.append(row)

    @property
    def status(self) -> str:
        statuses = {row["status"] for row in self.diagnostics}
        if "fail" in statuses:
            return "fail"
        if "unknown" in statuses:
            return "unknown"
        return "pass"

    @property
    def exit_code(self) -> int:
        return {"pass": 0, "fail": 1, "unknown": 2}[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "project-atlantis-gba-runtime-validation-report-v1",
            "phase": self.phase,
            "status": self.status,
            "unknown_policy": "fail-closed",
            "diagnostics": self.diagnostics,
            "evidence": self.evidence,
        }
