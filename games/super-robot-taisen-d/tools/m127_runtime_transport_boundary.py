#!/usr/bin/env python3
"""Record the bounded M1.27 mGBA/GDB transport boundary.

This receipt captures launcher, listener, connection, and stop-protocol
metadata from the two fresh mGBA candidates tried after M1.26.  It does not
read or copy raw logs, memory, screenshots, ROMs, or source records.  A
listener/connect success is kept separate from runtime evidence: both
candidate captures timed out before producing a verified font-base or
consumer event.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


EXPECTED_BASE_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_PATCHED_SHA256 = "b58ef43229be2a05217f2a5ac7c1cb0085cce53ce8fe0a17ea064d3355042cce"
EXPECTED_BPS_SHA256 = "4f694170e119fdf8a9f3113ddca9aec0850f07fdfd1adc75bfca46643a4e0f31"
EXPECTED_BPS_SIZE = 66


class RuntimeBoundaryReject(ValueError):
    """The inherited static identity or receipt shape failed closed."""


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeBoundaryReject("expected_object")
    return value


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeBoundaryReject(reason)


def build_report(m125: Mapping[str, Any]) -> Dict[str, Any]:
    policy = m125.get("source_policy", {})
    _require(policy.get("source_text_emitted") is False, "source_text_emitted")
    _require(policy.get("raw_memory_emitted") is False, "raw_memory_emitted")
    _require(policy.get("screenshots_emitted") is False, "screenshots_emitted")
    hashes = m125.get("rom_and_bps", {})
    _require(hashes.get("base_sha256") == EXPECTED_BASE_SHA256, "base_hash_mismatch")
    _require(hashes.get("patched_sha256") == EXPECTED_PATCHED_SHA256, "patched_hash_mismatch")
    _require(hashes.get("bps_sha256") == EXPECTED_BPS_SHA256, "bps_hash_mismatch")
    _require(hashes.get("bps_roundtrip") == "byte-identical; inherited static M1.8/M1.9 gate", "bps_roundtrip_mismatch")

    attempts = [
        {
            "candidate": "m127-sdl-0.11-no-display",
            "binary_sha256": "bb943473550547455a42703d48e6318962bbecc3a288605fa74cad6958942634",
            "version_family": "mGBA 0.11",
            "port": 2345,
            "port_selection": "documented_default_but_other_session_owned",
            "listener_observed": False,
            "rom_load_observed": False,
            "gdb_connection": "not_attempted",
            "capture_result": "video_driver_no_display",
            "runtime_data_observed": False,
            "process_cleanup": "own launcher exited cleanly",
        },
        {
            "candidate": "m127-headless-0.11-bind-negative",
            "binary_sha256": "96b63c18bca90d51c1f8ef4aa3e4f980bed24934bb441bb571b479f807cf2f46",
            "version_family": "mGBA 0.11",
            "port": 40731,
            "port_selection": "source_literal_private_candidate",
            "listener_observed": False,
            "rom_load_observed": True,
            "gdb_connection": "not_attempted",
            "capture_result": "gdb_bind_negative",
            "runtime_data_observed": False,
            "process_cleanup": "own launcher stopped cleanly",
        },
        {
            "candidate": "m127-headless-0.11-listener-stop-timeout",
            "binary_sha256": "f7b39f33569df81da66e25b80947d6f1fb70f273a53fa0b04d5c757d3338a5f4",
            "version_family": "mGBA 0.11",
            "port": 39123,
            "port_selection": "source_literal_private_candidate",
            "listener_observed": True,
            "rom_load_observed": True,
            "gdb_connection": "connect_ex_0",
            "capture_result": "m19_stop_protocol_timeout",
            "runtime_data_observed": False,
            "font_base": "not_observed",
            "consumer": "not_observed",
            "glyph": "not_observed",
            "writer": "not_observed",
            "cache_vram_screen": "not_observed",
            "process_cleanup": "own launcher stopped cleanly",
        },
        {
            "candidate": "m127-sdl-0.10.5-listener-stop-timeout",
            "binary_sha256": "00fee237414d86b368bca810350819bf03e76bcc5e6774d338123794dce116bb",
            "version_family": "mGBA 0.10.5",
            "port": 2349,
            "port_selection": "source_literal_private_candidate",
            "listener_observed": True,
            "rom_load_observed": True,
            "gdb_connection": "connect_ex_0",
            "capture_result": "m19_stop_protocol_timeout",
            "runtime_data_observed": False,
            "font_base": "not_observed",
            "consumer": "not_observed",
            "glyph": "not_observed",
            "writer": "not_observed",
            "cache_vram_screen": "not_observed",
            "process_cleanup": "own launcher stopped cleanly",
        },
    ]
    return {
        "schema": "super-robot-taisen-d-m127-runtime-transport-boundary-v1",
        "milestone": "M1.27",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "screenshots_emitted": False,
            "launcher_logs_tracked": False,
            "rom_bps_tracked": False,
            "source_safe_inherited_static_metadata": True,
        },
        "rom_and_bps": {
            "base_sha256": EXPECTED_BASE_SHA256,
            "patched_sha256": EXPECTED_PATCHED_SHA256,
            "bps_sha256": EXPECTED_BPS_SHA256,
            "bps_size": EXPECTED_BPS_SIZE,
            "bps_roundtrip": hashes["bps_roundtrip"],
        },
        "attempts": attempts,
        "runtime_coverage": {
            "listener_connect_success_count": sum(
                int(item["listener_observed"] and item["gdb_connection"] == "connect_ex_0")
                for item in attempts
            ),
            "font_base_observed": False,
            "consumer_observed": False,
            "glyph_observed": False,
            "writer_observed": False,
            "cache_vram_observed": False,
            "screen_observed": False,
            "target_record_verified": False,
            "runtime_evidence": "not_observed",
        },
        "gate": {
            "base_patched_bps_hashes": True,
            "static_bps_roundtrip_inherited": True,
            "listener_candidate_verified": True,
            "gdb_stop_protocol_verified": False,
            "font_base_guard": False,
            "target_consumer": False,
            "target_writer": False,
            "target_runtime_screen": False,
            "rom_or_translation_failure": False,
            "m127_complete": False,
        },
        "external_blocker": {
            "status": "runtime_stop_protocol_unavailable",
            "evidence": "0.11 headless and 0.10.5 SDL candidates both accepted a local connection but m19 bounded continue/stop timed out before any verified event",
            "safe_alternatives_attempted": [
                "0.11 SDL launch with dummy/no-display path",
                "0.11 headless literal-port bind candidate",
                "0.11 headless listener with authorized launcher and GDB",
                "0.10.5 SDL listener with authorized launcher and GDB",
            ],
            "next_condition": "obtain a local mGBA build/session with a working 0.10.5-compatible stop protocol and usable display/headless loop, then perform one font-base-guarded target capture",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m125-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(read_json(args.m125_report))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, RuntimeBoundaryReject, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"m127_runtime_transport_boundary_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m127_runtime_transport_boundary=accepted listeners={} runtime_evidence=not_observed".format(
            report["runtime_coverage"]["listener_connect_success_count"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
