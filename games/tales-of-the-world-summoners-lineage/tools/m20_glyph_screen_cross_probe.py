#!/usr/bin/env python3
"""Metadata-only cross-check for the M1.7 font consumer receipt.

The private M1.7 receipt records an immediate post-store tile hash, while the
later core capture contains the final VRAM and BG0 tilemap.  This probe joins
those two observations without emitting tile bytes, pixels, source text, or
code-unit sequences.  It deliberately keeps the identity gate closed when a
later VRAM hash differs from the immediate post-store hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from m20_text_record_probe import (
    EXPECTED_ROM_SHA256,
    FONT_RECORD_BUS_BASE,
    FONT_RECORD_FILE_BASE,
    FONT_RECORD_STRIDE,
)


ROM_BASE = 0x08000000
VRAM_BASE = 0x06000000
VRAM_LENGTH = 0x18000
SCREENBLOCK_LENGTH = 0x800

TARGETS: dict[int, dict[str, Any]] = {
    0x005E: {
        "keyboard_slot": "a-row-1",
        "keyboard_label": "あ",
        "input_path": "first A at the known first kana slot",
        "screen_positions": ((14, 4), (14, 5)),
        "store_addresses": (0x060020E0, 0x06002320),
    },
    0x0066: {
        "keyboard_slot": "a-row-3",
        "keyboard_label": "う",
        "input_path": "RIGHT then A at observed row-0 selection 2",
        "screen_positions": ((15, 4), (15, 5)),
        "store_addresses": (0x06002100, 0x06002340),
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_hex(value: object) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise ValueError(f"expected integer-like value, got {type(value).__name__}")
    return int(value, 0)


def tile_id_from_address(address: int, *, charbase: int = 0) -> int:
    base = VRAM_BASE + charbase
    if address < base or address >= base + VRAM_LENGTH:
        raise ValueError("VRAM tile address is outside the supplied VRAM image")
    offset = address - base
    if offset % 0x20:
        raise ValueError("VRAM tile address is not 32-byte aligned")
    return offset // 0x20


def gba_4bpp_ink_mask(tile: bytes) -> bytes:
    """Return one byte per pixel, without returning the packed tile data."""

    if len(tile) != 0x20:
        raise ValueError("a GBA 4bpp tile must be 32 bytes")
    return bytes(
        1 if ((tile[pixel // 2] >> (4 * (pixel & 1))) & 0xF) else 0
        for pixel in range(64)
    )


def tile_metadata(vram: bytes, address: int, *, charbase: int = 0) -> dict[str, object]:
    tile_id = tile_id_from_address(address, charbase=charbase)
    offset = address - VRAM_BASE
    tile = vram[offset:offset + 0x20]
    if len(tile) != 0x20:
        raise ValueError("tile is outside the supplied VRAM image")
    mask = gba_4bpp_ink_mask(tile)
    return {
        "address": f"0x{address:08X}",
        "tile_id": tile_id,
        "tile_sha256": sha256(tile),
        "ink_pixel_count": sum(mask),
        "ink_mask_sha256": sha256(mask),
    }


def screen_entry(vram: bytes, x: int, y: int, *, screenbase: int = 0) -> dict[str, int | bool]:
    if not 0 <= x < 32 or not 0 <= y < 32:
        raise ValueError("screenblock coordinate must be 0..31")
    offset = screenbase + 2 * (y * 32 + x)
    entry = int.from_bytes(vram[offset:offset + 2], "little")
    return {
        "x": x,
        "y": y,
        "entry": entry,
        "tile_id": entry & 0x03FF,
        "hflip": bool(entry & 0x0400),
        "vflip": bool(entry & 0x0800),
        "palette_bank": entry >> 12,
    }


def _store_receipts(summary: dict[str, object], code_unit: int) -> dict[int, dict[str, object]]:
    trace = summary.get("trace")
    if not isinstance(trace, dict):
        raise ValueError("M1.7 summary has no trace object")
    hits = trace.get("store_hits")
    if not isinstance(hits, list):
        raise ValueError("M1.7 summary has no store_hits list")
    wanted = f"0x{code_unit:08X}"
    receipts: dict[int, dict[str, object]] = {}
    for hit in hits:
        if not isinstance(hit, dict) or hit.get("code_unit") != wanted:
            continue
        address_value = hit.get("store_address")
        if address_value is None:
            continue
        address = parse_hex(address_value)
        receipts.setdefault(address, hit)
    return receipts


def record_metadata(rom: bytes, code_unit: int) -> dict[str, object]:
    offset = FONT_RECORD_FILE_BASE + code_unit * FONT_RECORD_STRIDE
    record = rom[offset:offset + FONT_RECORD_STRIDE]
    if len(record) != FONT_RECORD_STRIDE:
        raise ValueError("font record is outside the supplied ROM")
    bus_address = FONT_RECORD_BUS_BASE + code_unit * FONT_RECORD_STRIDE
    return {
        "code_unit": f"0x{code_unit:04X}",
        "record_bus_address": f"0x{bus_address:08X}",
        "record_file_offset": f"0x{offset:X}",
        "record_sha256": sha256(record),
        "arithmetic_confirmed": bus_address == ROM_BASE + offset,
    }


def cross_target(
    rom: bytes,
    vram: bytes,
    summary: dict[str, object],
    code_unit: int,
    *,
    charbase: int = 0,
    screenbase: int = 0,
) -> dict[str, object]:
    target = TARGETS[code_unit]
    if len(vram) < VRAM_LENGTH:
        raise ValueError("VRAM image is shorter than the standard GBA VRAM window")

    receipts = _store_receipts(summary, code_unit)
    stores: list[dict[str, object]] = []
    screen_position_ok = True
    immediate_hashes_present = True
    final_hash_matches_immediate = True
    cpu_store_receipts = True

    for address, (x, y) in zip(target["store_addresses"], target["screen_positions"]):
        tile = tile_metadata(vram, address, charbase=charbase)
        entry = screen_entry(vram, x, y, screenbase=screenbase)
        receipt = receipts.get(address)
        post_store = receipt.get("post_store_tile") if receipt else None
        immediate_hash = (
            post_store.get("tile_sha256")
            if isinstance(post_store, dict)
            else None
        )
        map_matches = entry["tile_id"] == tile["tile_id"]
        screen_position_ok = screen_position_ok and bool(map_matches)
        immediate_hashes_present = immediate_hashes_present and isinstance(immediate_hash, str)
        final_matches = immediate_hash == tile["tile_sha256"]
        final_hash_matches_immediate = final_hash_matches_immediate and final_matches
        if receipt is None:
            cpu_store_receipts = False
        else:
            cpu_store_receipts = cpu_store_receipts and receipt.get("writer_class") == "cpu-game-rom"

        stores.append(
            {
                "store_address": tile["address"],
                "tile_id": tile["tile_id"],
                "screen_position": entry,
                "screen_tilemap_match": map_matches,
                "final_vram_tile_sha256": tile["tile_sha256"],
                "final_vram_ink_pixel_count": tile["ink_pixel_count"],
                "final_vram_ink_mask_sha256": tile["ink_mask_sha256"],
                "immediate_post_store_tile_sha256": immediate_hash,
                "final_hash_matches_immediate_post_store": final_matches,
                "writer_class": receipt.get("writer_class") if receipt else None,
                "store_pc": receipt.get("store_pc") if receipt else None,
                "store_lr": receipt.get("lr") if receipt else None,
                "record_pointer_from_r12": receipt.get("font_record_pointer_from_r12") if receipt else None,
            }
        )

    combined_mask = b"".join(
        gba_4bpp_ink_mask(vram[address - VRAM_BASE:address - VRAM_BASE + 0x20])
        for address in target["store_addresses"]
    )
    keyboard_gate = bool(summary.get("keyboard_gate", {}).get("confirmed")) if isinstance(summary.get("keyboard_gate"), dict) else False
    runtime_store_confirmed = bool(stores) and cpu_store_receipts and immediate_hashes_present
    final_screen_cross_confirmed = screen_position_ok and final_hash_matches_immediate
    identity_gate = (
        sha256(rom) == EXPECTED_ROM_SHA256
        and record_metadata(rom, code_unit)["arithmetic_confirmed"]
        and runtime_store_confirmed
        and keyboard_gate
        and final_screen_cross_confirmed
    )
    return {
        "code_unit": f"0x{code_unit:04X}",
        "keyboard_slot": target["keyboard_slot"],
        "keyboard_label": target["keyboard_label"],
        "input_path": target["input_path"],
        "record": record_metadata(rom, code_unit),
        "stores": stores,
        "combined_column_mask": {
            "width": 8,
            "height": 16,
            "ink_pixel_count": sum(combined_mask),
            "ink_mask_sha256": sha256(combined_mask),
        },
        "evidence": {
            "keyboard_gate_confirmed": keyboard_gate,
            "cpu_store_receipts_confirmed": runtime_store_confirmed,
            "screen_tilemap_positions_confirmed": screen_position_ok,
            "final_screen_bytes_equal_immediate_post_store": final_hash_matches_immediate,
            "dma_or_bios_copy_receipt": False,
            "identity_gate": identity_gate,
        },
        "status": "confirmed" if identity_gate else "provisional",
        "negative_boundary": None
        if final_screen_cross_confirmed
        else "final VRAM tile hash differs from immediate post-store hash; same-time screen bytes are not proven",
    }


def probe(rom_path: Path, vram_path: Path, summary_path: Path) -> dict[str, object]:
    rom = rom_path.read_bytes()
    vram = vram_path.read_bytes()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return {
        "probe_version": "m20-glyph-screen-cross-probe-20260816.v1",
        "rom": {
            "sha256": sha256(rom),
            "expected_a9pj_sha256_match": sha256(rom) == EXPECTED_ROM_SHA256,
            "source_text_emitted": False,
        },
        "capture": {
            "summary_path": str(summary_path),
            "vram_path": str(vram_path),
            "vram_sha256": sha256(vram),
            "charbase": "0x0000",
            "screenbase": "0x0000",
            "bg_layer": "BG0",
            "raw_bytes_emitted": False,
            "image_emitted": False,
        },
        "targets": [cross_target(rom, vram, summary, code_unit) for code_unit in TARGETS],
        "source_text_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("summary", type=Path, help="private M1.7 summary.json")
    parser.add_argument("vram", type=Path, help="private core capture vram.bin")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(probe(args.rom, args.vram, args.summary), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
