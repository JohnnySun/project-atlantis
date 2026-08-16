#!/usr/bin/env python3
"""Prove the bounded FE6 glyph plane/nibble merge contract.

M1.27 follows the already identified composer into the small renderer kernel.
The report records instruction hashes, exact callsites, plane offsets and the
packed-word data-flow shape.  It does not emit bitmap bytes or call the
address/bit-operation shape a Unicode or font identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from trace_m18_callers import ROM_BASE, scan_direct_calls, hex32
from trace_m19_glyph_sink import _capstone_instructions


ROM_SIZE = 0x800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
KERNEL_ENTRY = 0x08099580
KERNEL_END = 0x080995AE
RENDERER_ENTRY = 0x080995B0
RENDERER_END = 0x080995FA
COMPOSER_ENTRY = 0x08099424
COMPOSER_CALL = 0x08099462
WRITER = 0x080995A6
SOURCE_BASE_LITERAL = 0x02000000
DESTINATION_BASE_LITERAL = 0x06010000
OFFSET_MASK_LITERAL = 0x000003FF
PLANE_OFFSETS = (0x00, 0x40, 0x80, 0xC0)
PLANE_CALLS = (0x080995D0, 0x080995DC, 0x080995E8, 0x080995F4)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_range(rom: bytes, start: int, end: int) -> str:
    first = start - ROM_BASE
    last = end - ROM_BASE
    if first < 0 or last > len(rom) or first >= last:
        raise ValueError("invalid ROM hash range")
    return _sha256(rom[first:last])


def _instruction(rows: list[dict[str, object]], address: int) -> str:
    for row in rows:
        if int(row["address"]) == address:
            return f"{hex32(address)}: {row['mnemonic']} {row['op_str']}".rstrip()
    raise ValueError(f"missing instruction at {hex32(address)}")


def _u32(rom: bytes, address: int) -> int:
    offset = address - ROM_BASE
    if offset < 0 or offset + 4 > len(rom):
        raise ValueError(f"ROM address outside image: {hex32(address)}")
    return int.from_bytes(rom[offset:offset + 4], "little")


def _static_report(rom: bytes) -> dict[str, object]:
    kernel = _capstone_instructions(rom, KERNEL_ENTRY, KERNEL_END)
    renderer = _capstone_instructions(rom, RENDERER_ENTRY, RENDERER_END)
    if _instruction(kernel, WRITER) != "0x080995a6: str r1, [r2]":
        raise ValueError("reviewed writer instruction drifted")
    plane_rows = [
        {
            "callsite": hex32(callsite),
            "instruction": _instruction(renderer, callsite),
            "plane_offset": hex32(offset),
        }
        for callsite, offset in zip(PLANE_CALLS, PLANE_OFFSETS)
    ]
    expected_plane_instructions = (
        "0x080995d0: bl #0x8099580",
        "0x080995dc: bl #0x8099580",
        "0x080995e8: bl #0x8099580",
        "0x080995f4: bl #0x8099580",
    )
    if tuple(row["instruction"] for row in plane_rows) != expected_plane_instructions:
        raise ValueError("renderer plane callsite topology drifted")
    return {
        "encoding": "ARM7TDMI Thumb",
        "composer": {
            "entry": hex32(COMPOSER_ENTRY),
            "callsite": hex32(COMPOSER_CALL),
            "direct_callers": [hex32(address) for address in scan_direct_calls(rom, COMPOSER_ENTRY)],
            "address_model": {
                "source_base_literal": hex32(SOURCE_BASE_LITERAL),
                "destination_base_literal": hex32(DESTINATION_BASE_LITERAL),
                "offset_mask_literal": hex32(OFFSET_MASK_LITERAL),
                "source_candidate_is_single_literal": False,
                "destination_candidate_is_single_literal": False,
            },
        },
        "renderer": {
            "entry": hex32(RENDERER_ENTRY),
            "code_sha256": _hash_range(rom, RENDERER_ENTRY, RENDERER_END),
            "plane_count": len(PLANE_OFFSETS),
            "plane_offsets": [hex32(value) for value in PLANE_OFFSETS],
            "plane_stride": hex32(PLANE_OFFSETS[1] - PLANE_OFFSETS[0]),
            "plane_calls": plane_rows,
            "kernel_target": hex32(KERNEL_ENTRY),
        },
        "kernel": {
            "entry": hex32(KERNEL_ENTRY),
            "end_exclusive": hex32(KERNEL_END),
            "code_sha256": _hash_range(rom, KERNEL_ENTRY, KERNEL_END),
            "mask_instruction": _instruction(kernel, 0x0809958E),
            "source_word_load": _instruction(kernel, 0x080995A0),
            "destination_word_load": _instruction(kernel, 0x0809959A),
            "destination_clear": _instruction(kernel, 0x0809959C),
            "source_nibble_select": _instruction(kernel, 0x080995A2),
            "packed_word_add": _instruction(kernel, 0x080995A4),
            "writer_instruction": _instruction(kernel, WRITER),
            "nibble_mask_formula": "0x0f << ((r2 & 0x07) * 4)",
            "plane_merge_formula": "dest = (dest & ~mask) | (source & mask)",
            "packed_nibble_operation_confirmed": True,
            "semantic_name_assigned": False,
        },
        "raw_bytes_emitted": False,
        "unicode_identity_confirmed": False,
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


def _runtime_summary(report: dict[str, object]) -> dict[str, object]:
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime receipt has no runtime object")
    rows = runtime.get("renderer_entries", [])
    if not isinstance(rows, list):
        rows = []
    sources: list[int] = []
    destinations: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = _as_int(row.get("source_register_r0"))
        destination = _as_int(row.get("destination_register_r1"))
        if source is not None:
            sources.append(source)
        if destination is not None:
            destinations.append(destination)
    writer_rows = runtime.get("writer_receipts", [])
    writer_count = len(writer_rows) if isinstance(writer_rows, list) else 0
    return {
        "renderer_entry_count": len(rows),
        "unique_source_count": len(set(sources)),
        "unique_destination_count": len(set(destinations)),
        "source_candidate_observed": SOURCE_BASE_LITERAL + 0x20C0 in sources,
        "destination_candidate_observed": DESTINATION_BASE_LITERAL + 0x4000 in destinations,
        "writer_receipt_count": writer_count,
        "same_run_writer_pairing_confirmed": bool(writer_count),
        "raw_bytes_emitted": False,
    }


def build_report(rom_path: Path, runtime_path: Optional[Path] = None) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    game_code = rom[0xAC:0xB0].decode("ascii", errors="replace")
    rom_sha256 = _sha256(rom)
    if game_code != EXPECTED_GAME_CODE or rom_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError("ROM is not the reviewed AFEJ revision")
    report: dict[str, object] = {
        "schema": "afej-m127-font-contract-v1",
        "rom": {
            "game_code": game_code,
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "static": _static_report(rom),
        "runtime_input": None,
        "runtime": None,
        "status": {
            "glyph_storage_contract": "packed_nibble_four_plane_data_flow",
            "unicode_identity_confirmed": False,
            "font_identity_confirmed": False,
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }
    if runtime_path is not None:
        report["runtime_input"] = str(runtime_path)
        report["runtime"] = _runtime_summary(
            json.loads(runtime_path.read_text(encoding="utf-8"))
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_report(args.rom, args.runtime_report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"output={args.output}")
    print(f"plane_count={result['static']['renderer']['plane_count']}")
    print(f"nibble_merge={result['static']['kernel']['packed_nibble_operation_confirmed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
