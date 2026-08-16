#!/usr/bin/env python3
"""Build the source-safe M1.22 patched-runtime receipt.

M1.22 records one fresh, dedicated mGBA/GDB attempt for the existing M1.8
patched POC.  The attempt ended before a listener/connection was available, so
this tool deliberately records transport metadata and inherited static hashes
only.  It never reads the ROM or emits source text, raw memory, screenshots,
or work-directory output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping


EXPECTED_GAME_CODE = "A6SJ"
EXPECTED_PORT = 24568
EXPECTED_PATCHED_SHA256 = (
    "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
)
EXPECTED_BASE_SHA256 = (
    "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
)
EXPECTED_BPS_SHA256 = (
    "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"
)
EXPECTED_TARGET_OFFSET = 526424
EXPECTED_ADJACENT_OFFSET = 526432


class ReceiptError(ValueError):
    """A source-safe M1.22 receipt invariant failed closed."""


def _copy_mapping(value: Any, label: str) -> MutableMapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReceiptError(f"{label}_missing")
    return dict(value)


def _require(report: Mapping[str, Any], path: str, expected: Any) -> None:
    value: Any = report
    for component in path.split("."):
        if not isinstance(value, Mapping) or component not in value:
            raise ReceiptError(f"missing_{path}")
        value = value[component]
    if value != expected:
        raise ReceiptError(f"mismatch_{path}")


def build_receipt(
    m19_report: Mapping[str, Any],
    *,
    port: int,
    sandbox_probe_status: str,
    authorized_probe_status: str,
    launcher_log_sha256: str,
    launcher_log_bytes: int,
) -> dict[str, Any]:
    """Create a deterministic receipt from the audited M1.9 static report."""

    _require(m19_report, "game_code", EXPECTED_GAME_CODE)
    _require(m19_report, "source_policy.source_text_emitted", False)
    _require(m19_report, "source_policy.string_id", EXPECTED_TARGET_OFFSET)
    _require(m19_report, "static_adjacent.string_id", EXPECTED_ADJACENT_OFFSET)
    _require(m19_report, "rom_and_bps.base_sha256", EXPECTED_BASE_SHA256)
    _require(m19_report, "rom_and_bps.patched_sha256", EXPECTED_PATCHED_SHA256)
    _require(m19_report, "rom_and_bps.bps_sha256", EXPECTED_BPS_SHA256)
    if port != EXPECTED_PORT:
        raise ReceiptError("unexpected_dedicated_port")
    if len(launcher_log_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in launcher_log_sha256
    ):
        raise ReceiptError("invalid_launcher_log_sha256")
    if launcher_log_bytes < 0:
        raise ReceiptError("invalid_launcher_log_bytes")

    target_static = _copy_mapping(m19_report["static_target"], "static_target")
    adjacent_static = _copy_mapping(m19_report["static_adjacent"], "static_adjacent")
    target_static["source_text_emitted"] = False
    adjacent_static["source_text_emitted"] = False

    return {
        "schema": "super-robot-taisen-d-m122-runtime-receipt-v1",
        "milestone": "M1.22",
        "game_code": EXPECTED_GAME_CODE,
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "screenshots_emitted": False,
            "target_source_offset": EXPECTED_TARGET_OFFSET,
            "adjacent_source_offset": EXPECTED_ADJACENT_OFFSET,
            "inherited_source_metadata": "M1.9 source-safe hashes/counts only",
        },
        "rom_and_bps": {
            "base_sha256": EXPECTED_BASE_SHA256,
            "patched_sha256": EXPECTED_PATCHED_SHA256,
            "bps_sha256": EXPECTED_BPS_SHA256,
            "bps_roundtrip": "byte-identical; inherited static M1.8/M1.9 gate",
        },
        "static_target": target_static,
        "static_adjacent": adjacent_static,
        "runtime_attempt": {
            "fresh_process": True,
            "rom_role": "patched M1.8 static POC",
            "dedicated_port": port,
            "single_gdb_connection_attempt": True,
            "natural_paths_attempted": [],
            "controlled_consumer_attempted": False,
            "launcher_log": {
                "bytes": launcher_log_bytes,
                "sha256": launcher_log_sha256,
                "raw_log_tracked": False,
            },
            "sandbox_probe": {
                "status": sandbox_probe_status,
                "connection_established": False,
            },
            "authorized_probe": {
                "status": authorized_probe_status,
                "connection_established": False,
            },
            "listener_observed": False,
            "connection_established": False,
            "process_cleanup": "own mGBA process stopped cleanly",
            "coverage": {
                "initializer": "not_observed",
                "consumer": "not_observed",
                "glyph_lookup": "not_observed",
                "tile_writer": "not_observed",
                "cache_or_vram": "not_observed",
                "screen": "not_observed",
            },
            "result": "transport_negative",
            "rom_or_translation_failure": False,
        },
        "known_runtime_boundary": {
            "status": "inherited; not conflated with this transport attempt",
            "consumer_pc": "0x08008724",
            "known_caller_callsite": "0x08066050",
            "known_caller_lr": "0x08066055",
            "known_argument_shape": {
                "r0": "r7 RAM buffer, target source pointer not proven",
                "r1": "r5+0x400",
                "r2": "0x0D",
                "r3": "0x05",
                "stack_arg_0": "0x01",
            },
            "font_base_slots": {
                "narrow_slot": "0x020131D0",
                "wide_slot": "0x020103AC",
                "expected_nonzero_bases": {
                    "narrow": "0x0814F664",
                    "wide": "0x08120DBC",
                },
            },
            "next_trigger": (
                "obtain a working single GDB connection, then break at the verified "
                "caller/callsite and accept target proof only when source pointer and "
                "two-unit loop match 0x08080858"
            ),
        },
        "gate": {
            "static_target_metadata": True,
            "static_adjacent_unchanged": bool(adjacent_static.get("untouched")),
            "base_patched_bps_hashes": True,
            "font_base_nonzero": "not_observed_in_m122",
            "target_writer_destination": "not_observed",
            "target_runtime_screen": "not_observed",
            "translation_status": "ai_draft",
            "m122_complete": False,
            "reason": "GDB listener/connection was not available in the bounded attempt",
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m19_report", type=Path)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--sandbox-probe-status", required=True)
    parser.add_argument("--authorized-probe-status", required=True)
    parser.add_argument("--launcher-log-sha256", required=True)
    parser.add_argument("--launcher-log-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = json.loads(args.m19_report.read_text(encoding="utf-8"))
    receipt = build_receipt(
        report,
        port=args.port,
        sandbox_probe_status=args.sandbox_probe_status,
        authorized_probe_status=args.authorized_probe_status,
        launcher_log_sha256=args.launcher_log_sha256,
        launcher_log_bytes=args.launcher_log_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "m122_runtime_receipt=accepted "
        f"status={receipt['runtime_attempt']['result']} "
        f"listener={receipt['runtime_attempt']['listener_observed']} "
        f"target_screen={receipt['gate']['target_runtime_screen']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
