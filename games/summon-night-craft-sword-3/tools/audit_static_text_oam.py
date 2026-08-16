#!/usr/bin/env python3
"""Audit the B3CJ text-object -> OAM-buffer chain.

This is a bounded static supplement to audit_static_render_destination.py.  It
checks the local ROM bytes for the text-window object's per-glyph setup and
the main-loop OAM serializer, then reuses the existing writer/DMA/OAM guards.
It reports only hashes, addresses, and bounded contracts; it never emits text,
raw memory, a ROM, or an image.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Iterable


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_AUDIT_PATH = GAME_ROOT / "tools" / "audit_static_render_destination.py"


def _load_base_audit():
    spec = importlib.util.spec_from_file_location("b3cj_static_render_destination", BASE_AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE_AUDIT = _load_base_audit()
EXPECTED_CSM3_COMMIT = "7e388ac861bbac289b1f86dc5b8fa46d47b1a1a2"

# These ranges are bounded by the next csm3 assembly function entry and are
# independently checked against the local B3CJ ROM.  The first range includes
# the per-glyph object loop after the existing writer prefix audit.
TEXT_OBJECT_FUNCTIONS = (
    (
        "sub_0800B730.text_object_setup",
        0x0000B730,
        0x0000B8F4,
        "59feabb18a62ea301bb7d453dca387fda15076a9f4a8a5b8758a56e73b37df38",
    ),
    (
        "sub_0800901C.main_oam_pack",
        0x0000901C,
        0x00009108,
        "e6d1f338dfb6acf124f197e77f14460a5563480d301900e973522c00b98272b1",
    ),
)

TEXT_OBJECT_LITERALS = (
    ("sub_0800901C.oam_buffer", 0x000090F4, 0x030038B0),
    ("sub_0800901C.oam_priority_links", 0x000090F8, 0x030037A0),
    ("sub_0800901C.oam_object_links", 0x000090FC, 0x03003CC0),
    ("sub_0800901C.oam_count_state", 0x00009100, 0x03003CB0),
    ("sub_0800901C.affine_object_data", 0x00009104, 0x030037B0),
)


def _read_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"literal read outside ROM at 0x{offset:x}")
    return int.from_bytes(data[offset : offset + 4], "little")


def _function_checks(data: bytes) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name, start, end, expected in TEXT_OBJECT_FUNCTIONS:
        actual = hashlib.sha256(data[start:end]).hexdigest()
        result.append(
            {
                "name": name,
                "file_range": f"0x{start:x}..0x{end:x}",
                "sha256": actual,
                "matched": actual == expected,
            }
        )
        if actual != expected:
            raise ValueError(f"reviewed text-object function hash mismatch: {name}")
    return result


def _literal_checks(data: bytes) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name, offset, expected in TEXT_OBJECT_LITERALS:
        actual = _read_u32(data, offset)
        result.append(
            {
                "name": name,
                "file_offset": f"0x{offset:x}",
                "expected_gba_value": f"0x{expected:08x}",
                "actual_value": f"0x{actual:08x}",
                "matched": actual == expected,
            }
        )
        if actual != expected:
            raise ValueError(f"reviewed text-object literal mismatch: {name}")
    return result


def audit_rom(path: pathlib.Path) -> dict[str, object]:
    data = path.read_bytes()
    base = BASE_AUDIT.audit_rom(path)
    function_checks = _function_checks(data)
    literal_checks = _literal_checks(data)

    return {
        "audit_version": "b3cj-static-text-oam-v1",
        "evidence_level": "confirmed-static-text-object-to-oam-buffer-and-oam-dma",
        "rom_identity": base["rom_identity"],
        "csm3_commit": EXPECTED_CSM3_COMMIT,
        "base_audit": {
            "audit_version": base["audit_version"],
            "function_checks": len(base["function_checks"]),
            "literal_checks": len(base["literal_checks"]),
            "tilemap": base["tilemap"],
        },
        "function_checks": function_checks,
        "literal_checks": literal_checks,
        "text_object_chain": {
            "text_entry": "sub_0800D81C -> sub_0800B730",
            "glyph_setup": "sub_0800B730 calls sub_080036F8, then builds one object descriptor per decoded glyph",
            "object_descriptor_stride": "0x28 bytes per glyph in the local sub_0800B730 loop",
            "descriptor_helpers": [
                "sub_08009F0C",
                "sub_08009F50",
                "sub_0800A630",
                "sub_0800A6C0",
                "sub_0800A6CC",
            ],
            "main_loop_serializer": "sub_08001C00 -> sub_0800901C",
            "serializer_inputs": ["gUnk_03003CC0", "gUnk_030037B0", "gUnk_03003CB0"],
            "serializer_output": "gOamBuffer at 0x030038b0",
            "oam_fields": "sub_0800901C writes bounded attr0/attr1/attr2 halfwords for each linked object",
            "hardware_copy": "sub_08001BC0 -> DmaCopyBufferToOam.local_sub_080092CC -> 0x07000000",
            "independent_evidence": "local function hashes/literals plus csm3 callsite/control-flow review",
        },
        "boundary": "This confirms a static text-object to OAM-buffer path and the existing OAM DMA destination; it does not prove live target glyph use, live OAM values, tilemap placement, palette readback, or screen readability.",
        "runtime": {
            "consumer_hit": False,
            "writer_hit": False,
            "live_oam_read": False,
            "tilemap_proven": False,
            "screen_readability": False,
        },
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
            "B3CJ_STATIC_TEXT_OAM_AUDIT_OK "
            f"functions={len(report['function_checks'])} "
            f"literals={len(report['literal_checks'])} "
            f"buffer={report['text_object_chain']['serializer_output']}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"audit_static_text_oam.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
