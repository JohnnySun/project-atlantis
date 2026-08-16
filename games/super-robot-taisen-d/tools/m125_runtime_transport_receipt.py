#!/usr/bin/env python3
"""Record the corrected-port M1.25 mGBA transport attempt.

The prior M1.22 attempt used a config port that this local mGBA executable
does not consume.  M1.25 uses the executable's verified hard-coded listener
port and records the still-negative result without emitting ROM bytes, source
text, raw memory, or screenshots.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping


EXPECTED_GAME_CODE = "A6SJ"
EXPECTED_PORT = 2348
EXPECTED_PATCHED_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
EXPECTED_BASE_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_BPS_SHA256 = "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"


class TransportReceiptReject(ValueError):
    """A corrected-port transport receipt failed closed."""


def _copy_mapping(value: Any, label: str) -> MutableMapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TransportReceiptReject(f"{label}_missing")
    return dict(value)


def _require(report: Mapping[str, Any], path: str, expected: Any) -> None:
    value: Any = report
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise TransportReceiptReject(f"missing_{path}")
        value = value[part]
    if value != expected:
        raise TransportReceiptReject(f"mismatch_{path}")


def build_receipt(
    m122_report: Mapping[str, Any],
    *,
    source_literal_port: int,
    binary_sha256: str,
    log_sha256: str,
    log_bytes: int,
    listener_observed: bool,
    rom_descriptor_observed: bool,
    probe_status: str,
) -> dict[str, Any]:
    _require(m122_report, "game_code", EXPECTED_GAME_CODE)
    _require(m122_report, "source_policy.source_text_emitted", False)
    _require(m122_report, "rom_and_bps.base_sha256", EXPECTED_BASE_SHA256)
    _require(m122_report, "rom_and_bps.patched_sha256", EXPECTED_PATCHED_SHA256)
    _require(m122_report, "rom_and_bps.bps_sha256", EXPECTED_BPS_SHA256)
    if source_literal_port != EXPECTED_PORT:
        raise TransportReceiptReject("source_listener_port_mismatch")
    if len(binary_sha256) != 64 or any(c not in "0123456789abcdef" for c in binary_sha256):
        raise TransportReceiptReject("invalid_binary_sha256")
    if len(log_sha256) != 64 or any(c not in "0123456789abcdef" for c in log_sha256):
        raise TransportReceiptReject("invalid_log_sha256")
    if log_bytes < 0:
        raise TransportReceiptReject("invalid_log_bytes")
    if listener_observed or rom_descriptor_observed or probe_status != "connection_refused":
        raise TransportReceiptReject("m122_negative_boundary_changed")

    static_target = _copy_mapping(m122_report.get("static_target"), "static_target")
    static_adjacent = _copy_mapping(m122_report.get("static_adjacent"), "static_adjacent")
    static_target["source_text_emitted"] = False
    static_adjacent["source_text_emitted"] = False
    return {
        "schema": "super-robot-taisen-d-m125-runtime-transport-receipt-v1",
        "milestone": "M1.25",
        "game_code": EXPECTED_GAME_CODE,
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "screenshots_emitted": False,
            "inherited_static_metadata": "M1.22/M1.9 source-safe hashes and counts",
        },
        "rom_and_bps": {
            "base_sha256": EXPECTED_BASE_SHA256,
            "patched_sha256": EXPECTED_PATCHED_SHA256,
            "bps_sha256": EXPECTED_BPS_SHA256,
            "bps_roundtrip": "byte-identical; inherited static M1.8/M1.9 gate",
        },
        "static_target": static_target,
        "static_adjacent": static_adjacent,
        "transport_correction": {
            "cli_documented_default_port": 2345,
            "config_port_attempted_in_m122": 24568,
            "config_override_consumed_by_this_build": False,
            "source_listener_port": source_literal_port,
            "source_listener_evidence": "GDBStubListen literal in local mGBA build source",
            "port_selection_verified": True,
        },
        "runtime_attempt": {
            "fresh_process": True,
            "rom_role": "patched M1.8 static POC",
            "listener_port": EXPECTED_PORT,
            "single_gdb_connection_attempt": True,
            "listener_observed": listener_observed,
            "rom_descriptor_observed": rom_descriptor_observed,
            "probe_status": probe_status,
            "connection_established": False,
            "launcher_log": {
                "bytes": log_bytes,
                "sha256": log_sha256,
                "raw_log_tracked": False,
            },
            "font_base": "not_observed",
            "consumer": "not_observed",
            "glyph_lookup": "not_observed",
            "tile_writer": "not_observed",
            "cache_or_vram": "not_observed",
            "screen": "not_observed",
            "result": "transport_negative_after_port_correction",
            "rom_or_translation_failure": False,
            "process_cleanup": "own mGBA process stopped cleanly",
        },
        "gate": {
            "base_patched_bps_hashes": True,
            "port_root_cause_from_m122_verified": True,
            "corrected_listener_port_attempted": True,
            "listener_observed": False,
            "font_base_nonzero": "not_observed",
            "target_consumer": "not_observed",
            "target_writer": "not_observed",
            "target_runtime_screen": "not_observed",
            "translation_status": "ai_draft",
            "m125_complete": False,
            "rom_or_translation_failure": False,
        },
        "next_condition": (
            "use a local mGBA build that both opens the ROM and binds its verified GDB port, "
            "then perform one font-base-guarded caller/consumer capture; do not infer runtime "
            "coverage from static hashes"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m122_report", type=Path)
    parser.add_argument("--source-listener-port", type=int, required=True)
    parser.add_argument("--binary-sha256", required=True)
    parser.add_argument("--log-sha256", required=True)
    parser.add_argument("--log-bytes", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.m122_report.read_text(encoding="utf-8"))
    receipt = build_receipt(
        report,
        source_literal_port=args.source_listener_port,
        binary_sha256=args.binary_sha256,
        log_sha256=args.log_sha256,
        log_bytes=args.log_bytes,
        listener_observed=False,
        rom_descriptor_observed=False,
        probe_status="connection_refused",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "m125_runtime_transport=accepted port={} listener={} result={}".format(
            receipt["runtime_attempt"]["listener_port"],
            receipt["runtime_attempt"]["listener_observed"],
            receipt["runtime_attempt"]["result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
