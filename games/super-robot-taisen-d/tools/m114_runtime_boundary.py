#!/usr/bin/env python3
"""Normalize a bounded M1.14 runtime trace into source-safe evidence.

The input is an ignored mGBA/GDB trace.  This tool deliberately refuses to
turn a glyph-complete event into target proof unless the observed consumer
source pointer and unit count match the requested source record.  It emits
only hashes, addresses, code-unit metadata, counts, and gate statuses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from m19_runtime_trace import classify_trace_events  # noqa: E402
from m19_runtime_qa import PATCHED_ROM_SHA256, ROM_BASE, code_units, read_payload  # noqa: E402


class RuntimeBoundaryReject(ValueError):
    """A trace did not satisfy the bounded normalization contract."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise RuntimeBoundaryReject("trace_not_object")
    return value


def build_report(trace: Mapping[str, Any], rom: bytes) -> Dict[str, Any]:
    if sha256(rom) != PATCHED_ROM_SHA256:
        raise RuntimeBoundaryReject("patched_rom_hash_mismatch")
    if trace.get("rom", {}).get("sha256") != PATCHED_ROM_SHA256:
        raise RuntimeBoundaryReject("trace_rom_hash_mismatch")
    gdb = trace.get("gdb")
    if not isinstance(gdb, Mapping) or gdb.get("single_connection") is not True:
        raise RuntimeBoundaryReject("single_connection_gate_failed")
    initializer = trace.get("initializer")
    if not isinstance(initializer, Mapping) or initializer.get("nonzero_base_guard") is not True:
        raise RuntimeBoundaryReject("font_base_guard_failed")
    controlled = trace.get("controlled_call")
    if not isinstance(controlled, Mapping):
        raise RuntimeBoundaryReject("controlled_trace_missing")
    try:
        source_offset = int(controlled["source_offset"])
        expected_pointer = f"0x{ROM_BASE + source_offset:08X}"
        expected_units = code_units(read_payload(rom, source_offset)[0])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeBoundaryReject("requested_record_metadata_invalid") from exc
    events = controlled.get("events")
    if not isinstance(events, list):
        raise RuntimeBoundaryReject("trace_events_missing")
    classification = classify_trace_events(
        events,
        expected_source_pointer=expected_pointer,
        expected_unit_count=len(expected_units),
    )
    observed_code_units = classification["observed_code_units"]
    raw_complete = bool(controlled.get("complete_observed", False))
    return {
        "schema": "super-robot-taisen-d-m114-runtime-boundary-v1",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "normalization_policy": "target_proof_requires_observed_source_pointer_and_unit_count_match",
        },
        "rom": {
            "sha256": sha256(rom),
            "expected_sha256": PATCHED_ROM_SHA256,
            "hash_match": True,
        },
        "gdb": {
            "port": gdb.get("port"),
            "single_connection": True,
            "fresh_process_required": bool(gdb.get("fresh_process_required", True)),
        },
        "initializer": {
            "nonzero_base_guard": True,
            "slot_values": initializer.get("slot_values", {}),
            "event_count": int(initializer.get("event_count", 0)),
        },
        "requested_record": {
            "source_offset": source_offset,
            "source_pointer": expected_pointer,
            "expected_unit_count": len(expected_units),
            "observed_source_pointers": classification["observed_source_pointers"],
            "observed_code_units": observed_code_units,
            "codepage_count": classification["codepage_count"],
            "glyph_count": classification["glyph_count"],
            "tile_writer_count": classification["tile_writer_count"],
            "complete_event_raw": raw_complete,
            "consumer_argument_match": classification["consumer_argument_match"],
            "unit_loop_status": classification["unit_loop_status"],
        },
        "runtime_boundary": {
            "font_initialization": "positive_nonzero_bases",
            "consumer_entry": "reached_bounded_breakpoint_set",
            "requested_record_consumption": (
                "not_observed_due_to_source_pointer_mismatch"
                if not classification["consumer_argument_match"]
                else "bounded_candidate"
            ),
            "target_writer_destination": "not_proven",
            "target_tile_cache_hash": "not_proven",
            "target_screen_hash": "not_observed",
            "natural_or_unmatched_consumer_interleaving": not classification["consumer_argument_match"],
            "rom_or_translation_failure": False,
        },
        "next_runtime_gate": {
            "required": "callsite_breakpoint_or_verified_callee_entry_state",
            "reason": "a glyph-complete event from another source buffer cannot prove the requested record",
        },
        "gate": {
            "patched_rom_hash_match": True,
            "font_base_nonzero": True,
            "source_pointer_match": classification["consumer_argument_match"],
            "requested_target_render_proven": False,
            "natural_screen_proven": False,
            "translation_status": "ai_draft",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(read_json(args.trace), args.rom.read_bytes())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, RuntimeBoundaryReject, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"m114_runtime_boundary_rejected={exc}", file=sys.stderr)
        return 2
    print(
        "m114_runtime_boundary=accepted source_offset=0x{:06X} argument_match={} status={}".format(
            report["requested_record"]["source_offset"],
            report["requested_record"]["consumer_argument_match"],
            report["requested_record"]["unit_loop_status"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
