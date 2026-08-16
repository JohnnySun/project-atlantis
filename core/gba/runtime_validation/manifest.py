"""Strict loader for the runtime-validation case manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
TOP_LEVEL_KEYS = {
    "$schema",
    "format_version",
    "case_id",
    "description",
    "rom",
    "static",
    "runtime",
    "provenance",
}
ROM_KEYS = {"sha256", "size", "game_code_hex"}
STATIC_KEYS = {"change_policy", "regions", "pointers", "records"}
CHANGE_POLICY_KEYS = {"allowed_changed_ranges", "allow_size_change", "require_change"}
REGION_KEYS = {"id", "offset", "length", "policy"}
POINTER_KEYS = {"id", "offset", "encoding", "target_ranges", "alignment", "alias_group"}
RECORD_KEYS = {
    "id", "offset", "allocated_length", "unit_bytes", "terminator",
    "allowed_values", "control_values", "newline_values", "preserve_controls", "layout",
}
LAYOUT_KEYS = {"glyph_widths", "default_width", "max_width", "max_lines"}
RUNTIME_KEYS = {
    "required_capabilities", "gdb_timeout_seconds", "connect_timeout_seconds",
    "controlled_write_ranges", "actions", "assertions",
}
ACTION_KEYS = {
    "id", "op", "seconds", "timeout_seconds", "slice_seconds",
    "per_read_timeout_seconds", "condition", "keys", "destination_register",
    "hold_reads", "release_reads", "regions", "renders", "register_regions",
    "address", "length", "watch_type", "controlled", "register", "value", "data_hex",
}
ASSERTION_KEYS = {"kind", "id", "before", "after", "snapshot", "path", "value"}
OPS = {
    "wait_until", "run", "keys", "capture", "breakpoint", "watchpoint", "step",
    "write_register", "write_memory",
}


class ManifestError(ValueError):
    pass


def integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ManifestError(f"{field} must be an integer, not bool")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ManifestError(f"{field} is not an integer: {value!r}") from exc
    raise ManifestError(f"{field} must be an integer or 0x-prefixed string")


def _require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be an object")
    return value


def _reject_extra(value: dict[str, Any], allowed: set[str], field: str) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        raise ManifestError(f"unknown fields in {field}: {', '.join(extra)}")


def _object_list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be an array")
    output = []
    for index, row in enumerate(value):
        output.append(_require_object(row, f"{field}[{index}]"))
    return output


def _require_fields(value: dict[str, Any], fields: set[str], field: str) -> None:
    missing = sorted(fields - set(value))
    if missing:
        raise ManifestError(f"missing fields in {field}: {', '.join(missing)}")


def _validate_static(spec: dict[str, Any]) -> None:
    _reject_extra(spec, STATIC_KEYS, "static")
    if "change_policy" in spec:
        policy = _require_object(spec["change_policy"], "static.change_policy")
        _reject_extra(policy, CHANGE_POLICY_KEYS, "static.change_policy")
    for name, allowed, required in (
        ("regions", REGION_KEYS, {"id", "offset", "length", "policy"}),
        ("pointers", POINTER_KEYS, {"id", "offset", "target_ranges"}),
        ("records", RECORD_KEYS, {"id", "offset", "allocated_length", "allowed_values"}),
    ):
        for index, row in enumerate(_object_list(spec.get(name, []), f"static.{name}")):
            field = f"static.{name}[{index}]"
            _reject_extra(row, allowed, field)
            _require_fields(row, required, field)
            if name == "records" and "layout" in row:
                layout = _require_object(row["layout"], f"{field}.layout")
                _reject_extra(layout, LAYOUT_KEYS, f"{field}.layout")
                _require_fields(layout, {"max_width", "max_lines"}, f"{field}.layout")


def _validate_runtime(spec: dict[str, Any]) -> None:
    _reject_extra(spec, RUNTIME_KEYS, "runtime")
    capabilities = spec.get("required_capabilities", [])
    if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
        raise ManifestError("runtime.required_capabilities must be an array of strings")
    for index, row in enumerate(_object_list(spec.get("actions", []), "runtime.actions")):
        field = f"runtime.actions[{index}]"
        _reject_extra(row, ACTION_KEYS, field)
        _require_fields(row, {"op"}, field)
        op = row["op"]
        if op not in OPS:
            raise ManifestError(f"{field}.op is unsupported: {op!r}")
        required = {
            "wait_until": {"condition"},
            "run": {"seconds"},
            "keys": {"keys", "destination_register"},
            "capture": set(),
            "breakpoint": {"address"},
            "watchpoint": {"address"},
            "step": set(),
            "write_register": {"controlled", "register", "value"},
            "write_memory": {"controlled", "address", "data_hex"},
        }[op]
        _require_fields(row, required, field)
        if op == "wait_until":
            _require_object(row["condition"], f"{field}.condition")
        for name in ("regions", "renders", "register_regions"):
            if name in row:
                _object_list(row[name], f"{field}.{name}")
    for index, row in enumerate(_object_list(spec.get("assertions", []), "runtime.assertions")):
        field = f"runtime.assertions[{index}]"
        _reject_extra(row, ASSERTION_KEYS, field)
        _require_fields(row, {"kind", "id", "path"}, field)
        kind = row["kind"]
        if kind in {"changed", "unchanged"}:
            _require_fields(row, {"before", "after"}, field)
        elif kind in {"equals", "positive"}:
            _require_fields(row, {"snapshot"}, field)
            if kind == "equals":
                _require_fields(row, {"value"}, field)
        else:
            raise ManifestError(f"{field}.kind is unsupported: {kind!r}")


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    manifest = _require_object(manifest, "manifest")
    _reject_extra(manifest, TOP_LEVEL_KEYS, "manifest")
    if manifest.get("format_version") != 1:
        raise ManifestError("format_version must be exactly 1")
    case_id = manifest.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        raise ManifestError("case_id must match [a-z0-9][a-z0-9._-]{2,79}")
    rom = _require_object(manifest.get("rom"), "rom")
    _reject_extra(rom, ROM_KEYS, "rom")
    sha256 = rom.get("sha256")
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ManifestError("rom.sha256 must be 64 lowercase hex characters")
    if "size" in rom and integer(rom["size"], "rom.size") <= 0:
        raise ManifestError("rom.size must be positive")
    for section in ("static", "runtime"):
        if section in manifest:
            _require_object(manifest[section], section)
    if "static" not in manifest and "runtime" not in manifest:
        raise ManifestError("manifest needs at least one of static or runtime")
    if "static" in manifest:
        _validate_static(manifest["static"])
    if "runtime" in manifest:
        _validate_runtime(manifest["runtime"])
    return manifest
