#!/usr/bin/env python3
"""Bounded A6SJ pointer/literal-pool and caller classification.

This scanner is deliberately narrower than a whole-ROM decompiler.  It scans
ARM/Thumb PC-relative literal loads in a caller-supplied code range, resolves
only literals whose values point into the bounded Shift-JIS bank, and labels
the literal slot as either an ordinary literal pool or a member of a dense
ROM-pointer run.  A nearby prologue and a following BL are evidence for a
caller-shaped instruction stream, not proof of reachability.

The report contains offsets, addresses, instruction mnemonics, and scores;
it never emits decoded game text.  Raw JSON reports belong under ignored
games/<game>/work/ or /private/tmp.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
from collections import Counter
from typing import Iterable, Optional

try:
    import capstone
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit("capstone is required; use the repository Python environment") from exc


ROM_BASE = 0x08000000


def source_offsets(path: Optional[pathlib.Path]) -> set[int]:
    if path is None:
        return set()
    result: set[int] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                result.add(int(json.loads(line)["string_id"]))
    return result


def pointer_runs(
    data: bytes, target_start: int, target_end: int, minimum: int
) -> tuple[list[tuple[int, int]], list[dict[str, object]]]:
    """Return all aligned pointer refs and dense consecutive-word runs."""
    refs: list[tuple[int, int]] = []
    low = ROM_BASE + target_start
    high = ROM_BASE + target_end
    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if low <= value < high:
            refs.append((offset, value))

    runs: list[dict[str, object]] = []
    if not refs:
        return refs, runs
    begin = 0
    for index in range(1, len(refs) + 1):
        split = index == len(refs) or refs[index][0] != refs[index - 1][0] + 4
        if not split:
            continue
        group = refs[begin:index]
        if len(group) >= minimum:
            values = [value for _, value in group]
            runs.append(
                {
                    "start": group[0][0],
                    "words": len(group),
                    "end_exclusive": group[0][0] + len(group) * 4,
                    "target_min": min(values) - ROM_BASE,
                    "target_max": max(values) - ROM_BASE,
                    "ascending": all(values[n] <= values[n + 1] for n in range(len(values) - 1)),
                }
            )
        begin = index
    runs.sort(key=lambda row: (-int(row["words"]), int(row["start"])))
    return refs, runs


def in_pointer_run(offset: int, runs: Iterable[dict[str, object]]) -> Optional[dict[str, object]]:
    for row in runs:
        if int(row["start"]) <= offset < int(row["end_exclusive"]):
            return row
    return None


def thumb_literal_candidates(
    data: bytes, code_start: int, code_end: int, target_start: int, target_end: int
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    low = ROM_BASE + target_start
    high = ROM_BASE + target_end
    for offset in range(max(0, code_start) & ~1, min(code_end, len(data) - 1), 2):
        halfword = struct.unpack_from("<H", data, offset)[0]
        if halfword & 0xF800 != 0x4800:
            continue
        literal_offset = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        if literal_offset < 0 or literal_offset + 4 > len(data):
            continue
        value = struct.unpack_from("<I", data, literal_offset)[0]
        if low <= value < high:
            candidates.append(
                {
                    "mode": "thumb",
                    "instruction_offset": offset,
                    "literal_offset": literal_offset,
                    "target_offset": value - ROM_BASE,
                    "target_address": value,
                    "target_register": (halfword >> 8) & 7,
                }
            )
    return candidates


def arm_literal_candidates(
    data: bytes, code_start: int, code_end: int, target_start: int, target_end: int
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    low = ROM_BASE + target_start
    high = ROM_BASE + target_end
    # ARM LDR (word, immediate, PC-relative): cond 01 0 P U 0 W L, Rn=PC.
    for offset in range(max(0, code_start) & ~3, min(code_end, len(data) - 3), 4):
        word = struct.unpack_from("<I", data, offset)[0]
        if word & 0x0F7F0000 != 0x051F0000:
            continue
        imm = word & 0xFFF
        literal_offset = offset + 8 + (imm if word & (1 << 23) else -imm)
        if literal_offset < 0 or literal_offset + 4 > len(data):
            continue
        value = struct.unpack_from("<I", data, literal_offset)[0]
        if low <= value < high:
            candidates.append(
                {
                    "mode": "arm",
                    "instruction_offset": offset,
                    "literal_offset": literal_offset,
                    "target_offset": value - ROM_BASE,
                    "target_address": value,
                    "target_register": (word >> 12) & 0xF,
                }
            )
    return candidates


def parse_branch_target(op_str: str) -> Optional[int]:
    match = re.search(r"#?(0x[0-9a-fA-F]+|[0-9]+)", op_str)
    return int(match.group(1), 0) if match else None


def disassemble_context(
    data: bytes, mode: str, instruction_offset: int, window: int
) -> tuple[Optional[int], list[object]]:
    if mode == "thumb":
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        alignment = 2
        prologue_mnemonics = {"push"}
    else:
        md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        alignment = 4
        prologue_mnemonics = {"push", "stmdb"}
    md.detail = True

    anchor: Optional[int] = None
    for candidate in range(
        max(0, instruction_offset - window) & ~(alignment - 1),
        instruction_offset,
        alignment,
    )[::-1]:
        decoded = list(md.disasm(data[candidate:candidate + 4], ROM_BASE + candidate))
        if not decoded:
            continue
        insn = decoded[0]
        if insn.mnemonic in prologue_mnemonics and "lr" in insn.op_str:
            anchor = candidate
            break

    start = anchor if anchor is not None else max(0, instruction_offset - window) & ~(alignment - 1)
    end = min(len(data), instruction_offset + window)
    insns = list(md.disasm(data[start:end], ROM_BASE + start))
    return anchor, insns


def classify_candidate(
    data: bytes,
    candidate: dict[str, object],
    runs: list[dict[str, object]],
    source: set[int],
    window: int,
) -> dict[str, object]:
    instruction_offset = int(candidate["instruction_offset"])
    literal_offset = int(candidate["literal_offset"])
    mode = str(candidate["mode"])
    anchor, insns = disassemble_context(data, mode, instruction_offset, window)
    instruction_address = ROM_BASE + instruction_offset
    decoded = [insn for insn in insns if insn.address == instruction_address]
    target_insn = decoded[0] if decoded else None
    target_reg = f"r{candidate['target_register']}"
    following = [
        insn for insn in insns
        if instruction_address <= insn.address <= instruction_address + 0x20
    ]
    calls: list[dict[str, object]] = []
    for insn in following:
        if insn.address <= instruction_address or insn.mnemonic not in {"bl", "blx"}:
            continue
        branch = parse_branch_target(insn.op_str)
        calls.append(
            {
                "address": insn.address,
                "target": branch,
                "mnemonic": insn.mnemonic,
            }
        )

    stack_buffer = any(
        insn.mnemonic in {"mov", "adds", "add"}
        and re.search(r"\br0,\s*(?:sp|r\d+)", insn.op_str)
        for insn in following[1:6]
    )
    length_setup = any(
        insn.mnemonic in {"movs", "mov", "ldr"}
        and re.search(r"\br2,", insn.op_str)
        for insn in following[1:8]
    )
    pool_run = in_pointer_run(literal_offset, runs)
    score = 0
    if anchor is not None:
        score += 3
    if target_insn is not None:
        score += 2
    if calls:
        score += 2
    if target_reg in {"r0", "r1"}:
        score += 1
    if stack_buffer:
        score += 2
    if length_setup:
        score += 1
    confidence = "high" if score >= 8 else "medium" if score >= 5 else "low"
    result = {
        **candidate,
        "literal_kind": "pointer_table_member" if pool_run else "literal_pool",
        "source_offset_exact": int(candidate["target_offset"]) in source,
        "pointer_table_start": None if pool_run is None else pool_run["start"],
        "function_start": anchor,
        "decoded_at_instruction": target_insn is not None,
        "following_calls": calls,
        "stack_buffer_shape": stack_buffer,
        "length_setup_shape": length_setup,
        "score": score,
        "confidence": confidence,
    }
    if target_insn is not None:
        result["instruction"] = f"{target_insn.mnemonic} {target_insn.op_str}".strip()
    if following:
        result["context"] = [
            {
                "offset": insn.address - ROM_BASE,
                "mnemonic": insn.mnemonic,
                "op_str": insn.op_str,
            }
            for insn in following[:12]
        ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("--target-start", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--target-end", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--code-start", type=lambda value: int(value, 0), default=0x100)
    parser.add_argument("--code-end", type=lambda value: int(value, 0))
    parser.add_argument("--minimum-pointer-run", type=int, default=4)
    parser.add_argument("--source-table", type=pathlib.Path)
    parser.add_argument("--window", type=lambda value: int(value, 0), default=0x100)
    parser.add_argument("--top", type=int, default=60)
    parser.add_argument("--json-output", type=pathlib.Path)
    args = parser.parse_args()

    data = args.rom.read_bytes()
    code_end = args.target_start if args.code_end is None else args.code_end
    source = source_offsets(args.source_table)
    refs, runs = pointer_runs(data, args.target_start, args.target_end, args.minimum_pointer_run)
    raw_candidates = thumb_literal_candidates(
        data, args.code_start, code_end, args.target_start, args.target_end
    ) + arm_literal_candidates(data, args.code_start, code_end, args.target_start, args.target_end)
    candidates = [classify_candidate(data, item, runs, source, args.window) for item in raw_candidates]
    candidates.sort(key=lambda row: (-int(row["score"]), int(row["instruction_offset"])))
    summary = {
        "target_file_start": args.target_start,
        "target_file_end": args.target_end,
        "code_file_start": args.code_start,
        "code_file_end": code_end,
        "aligned_pointer_refs": len(refs),
        "pointer_runs": len(runs),
        "literal_candidates": len(candidates),
        "by_mode": dict(Counter(str(row["mode"]) for row in candidates)),
        "by_literal_kind": dict(Counter(str(row["literal_kind"]) for row in candidates)),
        "by_confidence": dict(Counter(str(row["confidence"]) for row in candidates)),
        "exact_source_targets": sum(bool(row["source_offset_exact"]) for row in candidates),
    }
    report = {"summary": summary, "pointer_runs": runs, "candidates": candidates}
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {args.json_output}")
    print("=== bounded pointer/caller summary ===")
    for key, value in summary.items():
        print(f"{key}={value}")
    print(f"=== top {min(args.top, len(candidates))} caller-shaped literal loads ===")
    for row in candidates[: args.top]:
        function = (
            "?"
            if row["function_start"] is None
            else f"0x{int(row['function_start']):06x}"
        )
        calls = ",".join(
            f"0x{int(call['address']) - ROM_BASE:06x}->"
            f"0x{(int(call['target']) - ROM_BASE):06x}"
            if call["target"] is not None else f"0x{int(call['address']) - ROM_BASE:06x}->?"
            for call in row["following_calls"]
        ) or "-"
        print(
            f"  mode={row['mode']} insn=0x{int(row['instruction_offset']):06x} "
            f"literal=0x{int(row['literal_offset']):06x} "
            f"target=0x{int(row['target_offset']):06x} "
            f"kind={row['literal_kind']} confidence={row['confidence']} score={row['score']} "
            f"function={function} "
            f"stack_buffer={row['stack_buffer_shape']} calls={calls}"
        )
        for insn in row.get("context", []):
            print(f"    0x{int(insn['offset']):06x}: {insn['mnemonic']} {insn['op_str']}")


if __name__ == "__main__":
    main()
