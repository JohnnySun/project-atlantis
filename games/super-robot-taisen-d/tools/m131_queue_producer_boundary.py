#!/usr/bin/env python3
"""Bound one verified queue producer/caller without assigning scene semantics.

M1.31 is intentionally narrower than a pointer scan.  It disassembles only
the already identified queue-entry drain window, joins the source-safe M1.28
layout contract, and reduces one common runtime-session report.  A queue
entry's argument layout is evidence about a caller contract, not proof that
the payload is story, speaker, branch, newline, or any other scene class.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence

import capstone


ROM_BASE = 0x08000000
EXPECTED_BASE_SHA256 = "12b706b637a6504cda20f213faa1f56451aaf8d5f54a7f48e8484d3b359a0e84"
EXPECTED_PATCHED_SHA256 = "6723931d0ba65b1645ab6a46f017ef30845f187f3e82e16c73479db14bf54b4f"
EXPECTED_RECORD_COUNT = 2325
QUEUE_WINDOW_START = 0x08008E02
QUEUE_WINDOW_END = 0x08008E32
QUEUE_LITERAL_ADDRESS = 0x08008E7C
EXPECTED_QUEUE_TABLE = 0x02011E20
EXPECTED_QUEUE_ENTRY_COUNT = 0x3C
EXPECTED_QUEUE_ENTRY_STRIDE = 4
EXPECTED_CONSUMER = 0x08008724
EXPECTED_CLEANUP = 0x0800536C


class QueueBoundaryReject(ValueError):
    """An M1.31 input or invariant failed closed."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def address(value: int) -> str:
    return f"0x{value:08X}"


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise QueueBoundaryReject(f"expected_object:{path}")
    return value


def _assert_source_safe(value: Any, path: str = "root") -> None:
    forbidden = {"text", "source", "raw", "pixels", "image", "screenshot", "dump"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in forbidden:
                raise QueueBoundaryReject(f"forbidden_key:{path}.{key}")
            _assert_source_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_source_safe(child, f"{path}[{index}]")


def _normalize(value: str) -> str:
    return value.replace(" ", "").lower()


EXPECTED_INSTRUCTIONS = {
    0x08008E02: ("ldr", "r7,[pc,#0x78]"),
    0x08008E04: ("ldr", "r5,[r7]"),
    0x08008E06: ("cmp", "r5,#0"),
    0x08008E08: ("beq", "#0x8008e2a"),
    0x08008E0A: ("adds", "r0,r5,#0"),
    0x08008E0C: ("adds", "r0,#8"),
    0x08008E0E: ("ldr", "r1,[r5,#4]"),
    0x08008E10: ("adds", "r2,r5,#0"),
    0x08008E12: ("adds", "r2,#0x46"),
    0x08008E14: ("ldrb", "r2,[r2]"),
    0x08008E16: ("ldr", "r3,[r5]"),
    0x08008E18: ("movs", "r4,#1"),
    0x08008E1A: ("str", "r4,[sp]"),
    0x08008E1C: ("bl", "#0x8008724"),
    0x08008E20: ("adds", "r0,r5,#0"),
    0x08008E22: ("bl", "#0x800536c"),
    0x08008E26: ("movs", "r0,#0"),
    0x08008E28: ("str", "r0,[r7]"),
    0x08008E2A: ("adds", "r7,#4"),
    0x08008E2C: ("adds", "r6,#1"),
    0x08008E2E: ("cmp", "r6,#0x3b"),
    0x08008E30: ("bls", "#0x8008e04"),
}


def _disassemble_window(rom: bytes) -> tuple[list[Any], dict[int, Any]]:
    start = QUEUE_WINDOW_START - ROM_BASE
    end = QUEUE_WINDOW_END - ROM_BASE
    if start < 0 or end > len(rom):
        raise QueueBoundaryReject("queue_window_outside_rom")
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    instructions = list(md.disasm(rom[start:end], QUEUE_WINDOW_START))
    actual = {int(item.address): item for item in instructions}
    if set(actual) != set(EXPECTED_INSTRUCTIONS):
        raise QueueBoundaryReject("queue_instruction_index_mismatch")
    mismatches = []
    for pc, expected in EXPECTED_INSTRUCTIONS.items():
        item = actual[pc]
        observed = (str(item.mnemonic), _normalize(str(item.op_str)))
        if observed != expected:
            mismatches.append({"pc": address(pc), "expected": expected, "observed": observed})
    if mismatches:
        raise QueueBoundaryReject("queue_instruction_mismatch")
    return instructions, actual


def _rom_queue_context(rom: bytes) -> dict[str, Any]:
    instructions, actual = _disassemble_window(rom)
    literal_offset = QUEUE_LITERAL_ADDRESS - ROM_BASE
    if literal_offset < 0 or literal_offset + 4 > len(rom):
        raise QueueBoundaryReject("queue_literal_outside_rom")
    literal_value = struct.unpack_from("<I", rom, literal_offset)[0]
    if literal_value != EXPECTED_QUEUE_TABLE:
        raise QueueBoundaryReject("queue_table_literal_mismatch")
    if actual[0x08008E1C].mnemonic != "bl" or actual[0x08008E22].mnemonic != "bl":
        raise QueueBoundaryReject("queue_call_target_instruction_mismatch")
    return {
        "window": {
            "start": address(QUEUE_WINDOW_START),
            "end_exclusive": address(QUEUE_WINDOW_END),
            "length": QUEUE_WINDOW_END - QUEUE_WINDOW_START,
            "instruction_count": len(instructions),
            "bytes_sha256": sha256(rom[QUEUE_WINDOW_START - ROM_BASE : QUEUE_WINDOW_END - ROM_BASE]),
            "instruction_index_sha256": sha256(
                "".join(f"{int(item.address):08x}:{item.mnemonic}:{item.op_str}\n" for item in instructions).encode("ascii")
            ),
        },
        "queue_table": {
            "literal_address": address(QUEUE_LITERAL_ADDRESS),
            "runtime_address": address(literal_value),
            "entry_count": EXPECTED_QUEUE_ENTRY_COUNT,
            "entry_index_max_inclusive": EXPECTED_QUEUE_ENTRY_COUNT - 1,
            "entry_stride_bytes": EXPECTED_QUEUE_ENTRY_STRIDE,
            "table_span_bytes": EXPECTED_QUEUE_ENTRY_COUNT * EXPECTED_QUEUE_ENTRY_STRIDE,
        },
        "guard_and_call": {
            "entry_pointer_register": "r5",
            "entry_pointer_load": "[r7]",
            "nonzero_compare_pc": address(0x08008E06),
            "empty_entry_branch_pc": address(0x08008E08),
            "empty_entry_target": address(0x08008E2A),
            "consumer": address(EXPECTED_CONSUMER),
            "consumer_callsite": address(0x08008E1C),
            "cleanup": address(EXPECTED_CLEANUP),
            "cleanup_callsite": address(0x08008E22),
            "entry_clear_pc": address(0x08008E28),
            "entry_clear_after_consumer": True,
            "loop_index_register": "r6",
            "loop_index_upper_inclusive": EXPECTED_QUEUE_ENTRY_COUNT - 1,
            "loop_back_pc": address(0x08008E30),
        },
        "argument_layout": {
            "r0": "entry+0x08",
            "r1": "[entry+0x04]",
            "r2": "byte[entry+0x46]",
            "r3": "[entry+0x00]",
            "stack_0": 1,
            "source_payload_identity": "unproven; r0 is a queue-entry-derived pointer, not assumed static text",
            "field_semantics": "opaque",
        },
    }


def _previous_contract(layout_report: Mapping[str, Any]) -> dict[str, Any]:
    corpus = layout_report.get("corpus_boundary")
    gate = layout_report.get("gate")
    semantic = layout_report.get("semantic_status")
    if not isinstance(corpus, Mapping) or not isinstance(gate, Mapping) or not isinstance(semantic, Mapping):
        raise QueueBoundaryReject("m128_contract_shape_missing")
    if int(corpus.get("record_count", -1)) != EXPECTED_RECORD_COUNT:
        raise QueueBoundaryReject("m128_record_count_mismatch")
    if int(corpus.get("source_no_op_count", -1)) != EXPECTED_RECORD_COUNT:
        raise QueueBoundaryReject("m128_no_op_count_mismatch")
    if gate.get("source_records_2325") is not True or gate.get("source_token_encode_no_op_2325") is not True:
        raise QueueBoundaryReject("m128_source_gate_mismatch")
    return {
        "record_count": EXPECTED_RECORD_COUNT,
        "source_no_op_count": int(corpus["source_no_op_count"]),
        "target_encoder_admissible_count": int(corpus.get("target_encoder_admissible_count", -1)),
        "opaque_unit_count": int(corpus.get("opaque_unit_count", -1)),
        "semantic_status": {str(key): str(value) for key, value in sorted(semantic.items())},
        "translation_started": bool(gate.get("translation_started", False)),
    }


def _runtime_boundary(
    manifest: Mapping[str, Any],
    identity_report: Mapping[str, Any],
    session_report: Mapping[str, Any],
) -> dict[str, Any]:
    if manifest.get("case_id") != "m131-queue-caller-boundary":
        raise QueueBoundaryReject("manifest_case_mismatch")
    manifest_rom = manifest.get("rom")
    if not isinstance(manifest_rom, Mapping) or manifest_rom.get("sha256") != EXPECTED_PATCHED_SHA256:
        raise QueueBoundaryReject("manifest_patched_rom_mismatch")
    if identity_report.get("status") != "pass":
        raise QueueBoundaryReject("common_rom_identity_not_pass")
    identity_rom = identity_report.get("rom")
    if not isinstance(identity_rom, Mapping) or identity_rom.get("sha256") != EXPECTED_PATCHED_SHA256:
        raise QueueBoundaryReject("common_rom_identity_hash_mismatch")
    preflight = session_report.get("preflight")
    ownership = session_report.get("ownership")
    cleanup = session_report.get("cleanup")
    if not isinstance(preflight, Mapping) or preflight.get("status") != "free":
        raise QueueBoundaryReject("common_session_preflight_not_free")
    if not isinstance(ownership, Mapping):
        raise QueueBoundaryReject("common_session_ownership_missing")
    if ownership.get("process_matches_rom") is not True:
        raise QueueBoundaryReject("common_session_rom_ownership_mismatch")
    if ownership.get("identity_changed") is not False:
        raise QueueBoundaryReject("common_session_identity_changed")
    if not isinstance(cleanup, Mapping) or cleanup.get("status") not in {
        "terminated", "killed_after_timeout", "already_exited"
    }:
        raise QueueBoundaryReject("common_session_cleanup_not_owned")
    listener_ready = ownership.get("ready") is True
    runner_started = session_report.get("runtime_exit") is not None
    return {
        "tool": "scripts/gba-runtime-session.py",
        "manifest_case_id": manifest["case_id"],
        "session_status": session_report.get("status"),
        "preflight_status": preflight.get("status"),
        "process_matches_manifest_rom": ownership.get("process_matches_rom"),
        "identity_changed": ownership.get("identity_changed"),
        "listener_ready": listener_ready,
        "listener_matches_exact_pid": ownership.get("listener_matches_exact_pid"),
        "runtime_runner_started": runner_started,
        "queue_callsite_observed": False,
        "natural_caller_status": "not_observed",
        "cleanup_status": cleanup.get("status"),
        "owned_process_cleanup_verified": True,
        "negative_reason": "listener_readiness_negative_before_manifest_runner" if not listener_ready else "runner_not_configured_for_queue_semantics",
    }


def build_report(
    rom: bytes,
    manifest: Mapping[str, Any],
    identity_report: Mapping[str, Any],
    session_report: Mapping[str, Any],
    layout_report: Mapping[str, Any],
) -> dict[str, Any]:
    for value, label in (
        (manifest, "manifest"),
        (identity_report, "identity_report"),
        (session_report, "session_report"),
        (layout_report, "layout_report"),
    ):
        _assert_source_safe(value, label)
    if sha256(rom) != EXPECTED_BASE_SHA256:
        raise QueueBoundaryReject("base_rom_hash_mismatch")
    previous = _previous_contract(layout_report)
    queue = _rom_queue_context(rom)
    runtime = _runtime_boundary(manifest, identity_report, session_report)
    return {
        "schema": "super-robot-taisen-d-m131-queue-producer-boundary-v1",
        "milestone": "M1.31",
        "game_code": "A6SJ",
        "source_policy": {
            "source_text_emitted": False,
            "raw_memory_emitted": False,
            "pixels_emitted": False,
            "semantic_labels_inferred": False,
            "pointer_report_rescanned": False,
            "translation_started": False,
        },
        "rom": {
            "base_sha256": sha256(rom),
            "expected_base_sha256": EXPECTED_BASE_SHA256,
            "base_hash_match": True,
            "patched_manifest_sha256": EXPECTED_PATCHED_SHA256,
        },
        "queue_context": queue,
        "inherited_layout_contract": previous,
        "control_layout_boundary": {
            "source_terminator": "NUL proven by inherited M1.28 contract",
            "glyph_unit": "two-byte glyph loop proven by inherited M1.28 contract",
            "newline": "unconfirmed; queue entry fields do not identify newline semantics",
            "speaker": "unconfirmed; queue entry fields do not identify speaker semantics",
            "branch": "unconfirmed; queue entry fields do not identify branch semantics",
            "maximum_width": "unconfirmed; observed width is not an engine limit",
            "line_count": "unconfirmed; no producer/layout screen state observed",
            "opaque_field_policy": "preserve opaque; reject translation until semantic identity is proven",
        },
        "runtime_boundary": runtime,
        "gate": {
            "common_rom_identity_exit_0": True,
            "common_manifest_validated": True,
            "common_session_owned_cleanup": True,
            "base_rom_hash_match": True,
            "queue_window_disassembly_verified": True,
            "queue_table_literal_verified": True,
            "consumer_callsite_verified": True,
            "post_consumer_clear_verified": True,
            "source_records_2325": previous["record_count"] == EXPECTED_RECORD_COUNT,
            "source_no_op_2325": previous["source_no_op_count"] == EXPECTED_RECORD_COUNT,
            "natural_queue_callsite_observed": False,
            "newline_semantics_proven": False,
            "speaker_semantics_proven": False,
            "branch_semantics_proven": False,
            "engine_width_limit_proven": False,
            "translation_started": False,
            "release_ready": False,
        },
        "next_condition": "bind a queue entry payload to a verified source record and layout/screen state before naming scene or control semantics",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity-report", type=Path, required=True)
    parser.add_argument("--session-report", type=Path, required=True)
    parser.add_argument("--layout-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_report(
            args.rom.read_bytes(),
            _read_json(args.manifest),
            _read_json(args.identity_report),
            _read_json(args.session_report),
            _read_json(args.layout_report),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, QueueBoundaryReject, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"m131_queue_producer_boundary_rejected={exc}", flush=True)
        return 2
    print(
        "m131_queue_producer_boundary=accepted window={} queue_entries={} runtime={} queue_hit={}".format(
            result["queue_context"]["window"]["bytes_sha256"][:12],
            result["queue_context"]["queue_table"]["entry_count"],
            result["runtime_boundary"]["session_status"],
            result["runtime_boundary"]["queue_callsite_observed"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
