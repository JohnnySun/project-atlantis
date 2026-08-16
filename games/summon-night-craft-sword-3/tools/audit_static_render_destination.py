#!/usr/bin/env python3
"""Audit the B3CJ text writer through the static DMA/render chain.

The mGBA/GDB listener is a separate runtime gate.  This read-only audit is
useful when that transport is unavailable: it verifies the local B3CJ bytes
for the reviewed glyph writer, its DMA queue, the text-window callsite, the
fixed VRAM character destination, the text-tile address formula, and the OAM
copy callsite.  It also records the palette shadow path without pretending
that a live text cache, tilemap, or screen has been observed.

The report contains only hashes, addresses, formulas, and bounded metadata.
It never writes a ROM or emits decoded source text/raw memory.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any, Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
INSPECT_FONT_PATH = GAME_ROOT / "tools" / "inspect_font.py"


def _load_inspector() -> Any:
    spec = importlib.util.spec_from_file_location("b3cj_inspect_font_render_audit", INSPECT_FONT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {INSPECT_FONT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSPECT_FONT = _load_inspector()

EXPECTED_CSM3_COMMIT = "7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2"

# File ranges are GBA addresses minus 0x08000000.  Each range is bounded by
# the next reviewed function entry in csm3's assembly and is independently
# checked against the local B3CJ ROM bytes.
REVIEWED_FUNCTIONS = (
    ("sub_08001BC0", 0x00001BC0, 0x00001BF6, "db6aeb2ceae31a50c9428fc3f14d63b9716598c9621e9135d435e0df48fb66f7"),
    ("sub_08001C00", 0x00001C00, 0x00001C30, "11e49e947411f5f978996bd1ae569a04348d9fbb3764cc100a1ec7d4566fe8ff"),
    ("sub_08002CB4", 0x00002CB4, 0x000031E8, "7ea0b0df799259d52eee5b818d7abcfa8fe51ddbdc0456fe202489769f67ee1b"),
    ("sub_080036C4", 0x000036C4, 0x000036F8, "1f747a03c51832819aab72c06c50b2a18613eb82a7a2e8019c4706ab3ee041b7"),
    ("sub_080036F8", 0x000036F8, 0x0000382E, "8593bbedfbfa610d0411f09ac808ccb4191ab7ff8b570f66168b94ddd639ee35"),
    ("DmaCopyBufferToOam.local_sub_080092CC", 0x000092CC, 0x000092E0, "adaf453e707c3d45b76099c0213ee8ab5efc2438e3f1d5f6dcd1ce7088b7b110"),
    ("sub_08009654", 0x00009654, 0x00009678, "63081b9bbd76ddb96ceb4236ae499c796edbaff2058cf648a366bac5e671d7c4"),
    ("DmaCopyMapAndPltt", 0x00006AC4, 0x00006BA4, "0a6d478733805e022ac1f1bbd781d492adcc561a5203ff6887f55694e56477a1"),
    ("sub_08006BA4", 0x00006BA4, 0x00006C10, "6f94efbb3c1c17caaceed4ee506d94758cfb5d028db0569547c9da3c97cedd2a"),
    ("sub_0800B730", 0x0000B730, 0x0000B7DE, "d4807052a062cb7b57e436f9cf1ffdec0b74ce6537a57fc8e5557845d395fcb0"),
    ("sub_0800D81C", 0x0000D81C, 0x0000D904, "2e9b06a234fefc7b0bed8a82463dd8c3412a1632164c6dd53aa9c18ab302b234"),
    ("sub_0800F224", 0x0000F224, 0x0000F2CC, "122d4f388e8c49d99b08290f4ac8ebd8b9abe4dd06352800747d48b493344a83"),
    ("sub_08010CD4", 0x00010CD4, 0x00010D0C, "fd7d019886f35e1baeb5c0c4373a82ffa59640f4c763bacd3f1df475c84eee1c"),
)

# Literal pools are local-ROM evidence for the reviewed callsites.  They are
# intentionally kept separate from the csm3 names: a name alone is not a
# local-ROM proof.
REVIEWED_LITERALS = (
    ("sub_080036C4.palette_source_table", 0x000036F4, 0x08B6D610),
    ("sub_080092CC.dma_register", 0x000092E0, 0x040000D4),
    ("sub_080092CC.oam_source", 0x000092E4, 0x030038B0),
    ("sub_080092CC.dma_control", 0x000092E8, 0x84000100),
    ("sub_08009654.tile_table_root", 0x00009678, 0x030040C0),
    ("sub_08009654.tile_index_mask", 0x0000967C, 0x000003FF),
    ("sub_08009654.text_vram_base", 0x00009680, 0x06010000),
    ("DmaCopyMapAndPltt.dma_register", 0x00006BA0, 0x040000D4),
    ("sub_08006BA4.queue_count", 0x00006BD0, 0x03003180),
    ("sub_08006BA4.queue_table", 0x00006BD4, 0x03002DC0),
    ("sub_08006BA4.override_state", 0x00006BD8, 0x03003184),
    ("sub_0800B730.source_root", 0x0000B8A0, 0x03005180),
    ("sub_0800B730.text_window_root", 0x0000B8A4, 0x030056C0),
    ("sub_0800D81C.text_char_vram", 0x0000D8F8, 0x06010000),
    ("sub_0800D81C.text_window_root", 0x0000D8FC, 0x030056C0),
    ("sub_08010CD4.palette_shadow_root", 0x00010D08, 0x03005960),
)


def _read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"literal read outside ROM at 0x{offset:x}")
    return int.from_bytes(data[offset : offset + 4], "little")


def _function_checks(data: bytes) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for name, start, end, expected in REVIEWED_FUNCTIONS:
        actual = hashlib.sha256(data[start:end]).hexdigest()
        matched = actual == expected
        checks.append(
            {
                "name": name,
                "file_range": f"0x{start:x}..0x{end:x}",
                "sha256": actual,
                "matched": matched,
            }
        )
        if not matched:
            raise ValueError(f"reviewed function hash mismatch: {name}")
    return checks


def _literal_checks(data: bytes) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for name, offset, expected in REVIEWED_LITERALS:
        actual = _read_u32(data, offset)
        matched = actual == expected
        checks.append(
            {
                "name": name,
                "file_offset": f"0x{offset:x}",
                "expected_gba_value": f"0x{expected:08x}",
                "actual_value": f"0x{actual:08x}",
                "matched": matched,
            }
        )
        if not matched:
            raise ValueError(f"reviewed literal mismatch: {name}")
    return checks


def audit_rom(path: pathlib.Path) -> dict[str, object]:
    """Return a fail-closed, no-raw static render-chain report."""

    data = path.read_bytes()
    identity = INSPECT_FONT.verify_rom(data)
    function_checks = _function_checks(data)
    literal_checks = _literal_checks(data)

    return {
        "audit_version": "b3cj-static-render-destination-v3",
        "evidence_level": "confirmed-static-writer-dma-vram-palette-oam-copy-and-text-tile-address",
        "rom_identity": identity,
        "csm3_commit": EXPECTED_CSM3_COMMIT,
        "function_checks": function_checks,
        "literal_checks": literal_checks,
        "writer": {
            "lookup": "sub_0800348C",
            "caller": "sub_080036F8",
            "glyph_writer": "sub_08002CB4",
            "destination_register": "r1",
            "per_glyph_stride": "0x80",
            "output_span": "0x80 per glyph",
            "boundary": "writer output is a RAM/output buffer until the reviewed DMA queue consumes it",
        },
        "dma_queue": {
            "queue_function": "sub_08006BA4",
            "descriptor_fields": ["source", "destination", "length"],
            "descriptor_table_runtime": "0x03002dc0",
            "count_runtime": "0x03003180",
            "hardware_dma_register": "0x040000d4",
            "length_contract": "sub_0800B730 passes glyph_count << 7 bytes",
            "evidence": "local function hashes and literal pools; no live DMA register read",
        },
        "text_vram_destination": {
            "runtime_pointer_field": "gUnk_030056C0 + 0x194",
            "initialized_by": "sub_0800D81C",
            "callsite": "sub_0800D81C sets window index r0=0 then calls sub_0800B730",
            "gba_address": "0x06010000",
            "memory_region": "VRAM character/tile data region",
            "evidence": "local literal 0x06010000 plus writer -> DMA descriptor callsite chain",
        },
        "text_tile_address": {
            "function": "sub_08009654",
            "table_root_runtime": "0x030040c0",
            "formula": "(((var->unk2 & 0x3ff) + var3->unk2) * 0x20) + 0x06010000",
            "tile_index_mask": "0x3ff",
            "tile_stride": "0x20 bytes (4bpp)",
            "base": "0x06010000",
            "evidence": "local function hash and literal guards cross-checked with csm3 copy.c formula; this proves tile-data addressing, not tilemap placement",
        },
        "palette": {
            "source_table_gba": "0x08b6d610",
            "loader": "sub_080036C4",
            "shadow_writer": "sub_0800F224",
            "shadow_formula": "gUnk_03005960 + variant*0x0c + palette_index*0x20",
            "palette_indices_used_by_loader": ["0x0e", "0x0f"],
            "hardware_copy": "sub_08010CD4",
            "hardware_copy_caller": "sub_08001C00",
            "hardware_copy_source": "gUnk_03005960 + 0x400 = 0x03005d60",
            "hardware_palette_destination": "0x05000000",
            "hardware_copy_length": "0x400 bytes",
            "evidence_level": "confirmed-static-shadow-to-hardware-destination",
        },
        "tilemap": {
            "destination": "unknown",
            "evidence_level": "not proven by this bounded chain",
        },
        "oam": {
            "caller": "sub_08001BC0",
            "local_transfer": "DmaCopyBufferToOam.local_sub_080092CC",
            "source": "0x030038b0",
            "destination": "0x07000000",
            "dma_register": "0x040000d4",
            "length": "0x400 bytes",
            "control": "0x84000100",
            "evidence_level": "confirmed-static-oam-dma",
            "boundary": "OAM buffer copy is confirmed as a display metadata transfer; it is not evidence that text glyphs use OAM or that a live screen was rendered",
        },
        "runtime": {
            "handshake": "blocked-transport-only",
            "consumer_hit": False,
            "writer_hit": False,
            "vram_read": False,
            "screen_readability": False,
        },
        "boundary": "Static writer -> queued DMA -> 0x06010000, text tile address formula, OAM buffer -> 0x07000000, and palette shadow -> queued DMA -> 0x05000000 evidence is confirmed; live text cache, tilemap, natural reachability, VRAM readback, and screen readability remain unconfirmed.",
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path, help="clean B3CJ ROM")
    parser.add_argument("--output", type=pathlib.Path, help="ignored JSON summary path")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = audit_rom(args.rom)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_STATIC_RENDER_AUDIT_OK "
            f"functions={len(report['function_checks'])} "
            f"literals={len(report['literal_checks'])} "
            f"vram={report['text_vram_destination']['gba_address']}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"audit_static_render_destination.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
