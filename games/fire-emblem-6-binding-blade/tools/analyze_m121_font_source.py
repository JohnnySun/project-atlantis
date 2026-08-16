#!/usr/bin/env python3
"""Prove the AFEJ glyph-source address formula without emitting source bytes.

M1.21 follows the already observed ``0x020020c0`` -> ``0x06014000``
renderer receipt back to the two composer variants.  The ROM does not contain
those candidate addresses as one literal: the code combines literal RAM/VRAM
bases with a computed offset and a small global configuration value.  This
tool records that static provenance and can summarize an ignored runtime
receipt's address pairs.  It never emits ROM slices, RAM bytes, bitmaps or
decoded Japanese text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Optional

from trace_m18_callers import ROM_BASE, scan_direct_calls, hex32
from trace_m19_glyph_sink import _capstone_instructions


ROM_SIZE = 0x800000
COMPOSER_ENTRY = 0x08099424
COMPOSER_VARIANT = 0x0809947C
RENDERER_ENTRY = 0x080995B0
RENDERER_KERNEL = 0x08099580
RENDERER_WRITE = 0x080995A6

SOURCE_BASE_VALUES = (0x02000000,)
DESTINATION_BASE_VALUES = (0x06010000,)
CONFIG_VALUES = (0x02002800,)
SOURCE_CANDIDATE = 0x020020C0
DESTINATION_CANDIDATE = 0x06014000

# PC-relative literal addresses resolved from the ARM7TDMI Thumb instructions.
LITERAL_PROVENANCE = (
    (0x08099428, 0x0809946C, "composer_config"),
    (0x08099442, 0x08099470, "composer_offset_mask"),
    (0x08099448, 0x08099474, "composer_destination_base"),
    (0x0809945C, 0x08099478, "composer_source_base"),
    (0x0809948A, 0x080994EC, "variant_config"),
    (0x080994AC, 0x080994F0, "variant_offset_mask"),
    (0x080994B4, 0x080994F4, "variant_destination_base"),
    (0x080994CA, 0x080994F8, "variant_source_base"),
)


def _u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError(f"address outside ROM: {hex32(address)}")
    return int.from_bytes(rom[offset:offset + 4], "little")


def _hash_range(rom: bytes, start: int, end: int) -> str:
    first = start - ROM_BASE
    last = end - ROM_BASE
    if first < 0 or last > len(rom) or first >= last:
        raise ValueError("invalid ROM hash range")
    return hashlib.sha256(rom[first:last]).hexdigest()


def _instruction(rows: Iterable[dict[str, object]], address: int) -> str:
    for row in rows:
        if int(row["address"]) == address:
            return f"{hex32(address)}: {row['mnemonic']} {row['op_str']}".rstrip()
    raise ValueError(f"missing instruction at {hex32(address)}")


def _literal_receipts(rom: bytes, rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    by_address = {int(row["address"]): row for row in rows}
    receipts = []
    for instruction_address, literal_address, role in LITERAL_PROVENANCE:
        receipts.append({
            "instruction": _instruction(by_address.values(), instruction_address),
            "literal_address": hex32(literal_address),
            "literal_value": hex32(_u32(rom, literal_address)),
            "role": role,
        })
    return receipts


def _static_report(rom: bytes) -> dict[str, object]:
    composer_rows = _capstone_instructions(rom, COMPOSER_ENTRY, 0x0809946C)
    variant_rows = _capstone_instructions(rom, COMPOSER_VARIANT, 0x0809951C)
    renderer_rows = _capstone_instructions(rom, RENDERER_ENTRY, RENDERER_ENTRY + 2)
    kernel_rows = _capstone_instructions(rom, RENDERER_KERNEL, RENDERER_WRITE + 4)
    literal_rows = composer_rows + variant_rows
    literal_values = {_u32(rom, address) for _, address, _ in LITERAL_PROVENANCE}
    expected_values = set(SOURCE_BASE_VALUES + DESTINATION_BASE_VALUES + CONFIG_VALUES + (0x3FF,))
    if not expected_values.issubset(literal_values):
        raise ValueError("composer literal provenance does not match reviewed AFEJ")

    return {
        "encoding": "ARM7TDMI Thumb",
        "composer": {
            "entry": hex32(COMPOSER_ENTRY),
            "variant_entry": hex32(COMPOSER_VARIANT),
            "entry_code_sha256": _hash_range(rom, COMPOSER_ENTRY, 0x0809946C),
            "variant_code_sha256": _hash_range(rom, COMPOSER_VARIANT, 0x0809951C),
            "literal_provenance": _literal_receipts(rom, literal_rows),
            "direct_callers_of_entry": [hex32(address) for address in scan_direct_calls(rom, COMPOSER_ENTRY)],
            "direct_callers_of_renderer": [hex32(address) for address in scan_direct_calls(rom, RENDERER_ENTRY)],
            "renderer_entry": _instruction(renderer_rows, RENDERER_ENTRY),
            "renderer_kernel": _instruction(kernel_rows, RENDERER_KERNEL),
            "renderer_writer": _instruction(kernel_rows, RENDERER_WRITE),
        },
        "address_model": {
            "source": "literal 0x02000000 + computed source offset",
            "destination": "literal 0x06010000 + computed destination offset",
            "config_literal": "0x02002800",
            "offset_mask_literal": "0x000003ff",
            "source_candidate": hex32(SOURCE_CANDIDATE),
            "source_candidate_offset": hex32(SOURCE_CANDIDATE - SOURCE_BASE_VALUES[0]),
            "destination_candidate": hex32(DESTINATION_CANDIDATE),
            "destination_candidate_offset": hex32(DESTINATION_CANDIDATE - DESTINATION_BASE_VALUES[0]),
            "candidate_addresses_are_single_literals": False,
            "semantic_name_assigned": False,
            "unicode_identity_confirmed": False,
        },
        "raw_bytes_emitted": False,
    }


def _as_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            return None
    return None


def _rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = runtime.get("renderer_entries")
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    events = runtime.get("renderer_events")
    if not isinstance(events, list):
        return []
    return [
        row for row in events
        if isinstance(row, dict) and row.get("pc") == hex32(RENDERER_ENTRY)
    ]


def _runtime_report(report: dict[str, Any]) -> dict[str, object]:
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime report has no runtime object")
    rows = _rows(runtime)
    pairs: list[dict[str, str]] = []
    source_hash_count = 0
    for row in rows:
        source = _as_int(row.get("source_register_r0"))
        destination = _as_int(row.get("destination_register_r1"))
        if source is None or destination is None:
            continue
        if isinstance(row.get("source_hash_window"), dict) and row["source_hash_window"].get("sha256"):
            source_hash_count += 1
        pairs.append({
            "source": hex32(source),
            "source_offset_from_literal_base": hex32(source - SOURCE_BASE_VALUES[0]),
            "destination": hex32(destination),
            "destination_offset_from_literal_base": hex32(destination - DESTINATION_BASE_VALUES[0]),
        })
    writer_rows = runtime.get("writer_receipts")
    writer_count = len(writer_rows) if isinstance(writer_rows, list) else 0
    pair_bytes = json.dumps(pairs, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "renderer_entry_count": len(rows),
        "address_pair_count": len(pairs),
        "unique_source_count": len({row["source"] for row in pairs}),
        "unique_destination_count": len({row["destination"] for row in pairs}),
        "source_candidate_observed": any(row["source"] == hex32(SOURCE_CANDIDATE) for row in pairs),
        "destination_candidate_observed": any(row["destination"] == hex32(DESTINATION_CANDIDATE) for row in pairs),
        "address_pair_sha256": hashlib.sha256(pair_bytes).hexdigest(),
        "source_hash_receipt_count": source_hash_count,
        "writer_receipt_count": writer_count,
        "same_run_writer_hash_pairing_confirmed": bool(source_hash_count and writer_count),
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_path: Optional[Path] = None) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    report: dict[str, object] = {
        "schema": "afej-m121-font-source-provenance-v1",
        "rom": {
            "game_code": rom[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "static": _static_report(rom),
        "runtime_input": None,
        "runtime": None,
        "raw_bytes_emitted": False,
    }
    if runtime_path is not None:
        report["runtime_input"] = str(runtime_path)
        report["runtime"] = _runtime_report(json.loads(runtime_path.read_text(encoding="utf-8")))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.rom, args.runtime_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
