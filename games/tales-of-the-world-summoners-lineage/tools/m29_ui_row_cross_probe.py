#!/usr/bin/env python3
"""Cross-check one local candidate against the clean A9PJ name-entry screen.

M29 correlates the M27 local row at caller ``0x080526FE``/stream ``0x1FA4B4``
with the M19 runtime keyboard gate and a private BG0 reconstruction.  The
optional M32 inputs add a fixed five-unit ROM-record raster and BG0 tilemap
receipt.  The tool emits only screen hashes, addresses, mapping statuses and
gate fields; it never prints the row's source text or raster bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence


PROBE_VERSION = "m29-ui-row-cross-probe-20260816.v2"
EXPECTED_ROM_SHA256 = "b41c293fc0ed6111b7a37d960d9cd0c685e5d521a4739e0e2eaa7ff6186cfdd3"
EXPECTED_CALLER = "0x080526FE"
EXPECTED_STREAM = "0x1FA4B4"
EXPECTED_BG0_SCREENBLOCK_SHA256 = "e9fda91c66abb64e01c812dc1266520ae8541e1bab78926213a5cbebee995661"
EXPECTED_BG1_SCREENBLOCK_SHA256 = "5098385e2f10559f32aaa4f81dca535d054ba6ebf9e4483749c81f5125358b5b"
EXPECTED_BG0_IMAGE_SHA256 = "72d1bf7271453ee012553c152940847c226d82e4470b43009d41963f63410f91"

# M32 is a deliberately fixed known-screen receipt, not a new corpus scan.
# The five units are the bounded stream at 0x1FA4B4.  Their names are kept out
# of this tracked tool; only the code-unit/table/image relationship is needed
# for the gate.
M32_STREAM_FILE_OFFSET = 0x1FA4B4
M32_STREAM_UNITS = (0x0006, 0x00F6, 0x0090, 0x009C, 0x000C)
M32_STREAM_BYTES = bytes(
    value
    for unit in (*M32_STREAM_UNITS, 0x0000)
    for value in unit.to_bytes(2, "little")
)
M32_STREAM_SHA256 = "ba5fcf40ea248f9662571951de19c7447854d76f069091ed5b6f845d2b149d88"
M32_SOURCE_TEXT_SHA256 = "4055ab372bbb3feadbf21c328f0eb72e9ceb2874c8979383feb193eb722d4c60"
M32_RECORD_BASE = 0x08089E00
M32_RECORD_STRIDE = 0x18
M32_RECORD_HASHES = {
    0x0006: "859f3e53f64e83939b8cc8aa8662bc6ac4c83c177875f5762a66f1cce752534d",
    0x00F6: "11ed35e98e5a20b31a870c1f02c4277aa2c54243c3a3d93636483c1edf8e4b93",
    0x0090: "bf5efd2a4d79d8de5dfde3eb7f5bb9a59196ef94c1cce7d500851907b6eabdea",
    0x009C: "78ac4d2f9cef751746e91d6da6595051ab5d5a27ba7e582a049ceaa47ba096e4",
    0x000C: "37618669f3f6cba37d72a987f95d14d1f2b645159b6c8962482df69f887f5e83",
}

# Coordinates are absolute pixels in the private 256x256 BG0 reconstruction.
# The boxes are metadata for a known screen; the box contents are never stored
# in Git.  The corresponding BG0 tilemap cells are retained below as IDs and
# hashes only.
M32_SCREEN_BOXES = {
    0x0006: (149, 37, 151, 39),
    0x00F6: (158, 33, 166, 43),
    0x0090: (169, 33, 179, 43),
    0x009C: (181, 32, 190, 43),
    0x000C: (192, 36, 203, 38),
}
M32_TILE_RECEIPTS = {
    0x0006: {
        "top": (18, 4, 0x010B, "639e68ff83f92522017047ee43908d903adf5c4a27170adad1dbb8e4843f1f48"),
        "bottom": (18, 5, 0x011D, "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"),
    },
    0x00F6: {
        "top": (19, 4, 0x010C, "0faa10408af62fe0a7f5ee1ddfc97495637ba44cbcd2e76be5dfe3a3ccfbf6cb"),
        "bottom": (19, 5, 0x011E, "bb7f904ce841b6794668f86bfd61625c42e302c05bcc1e3c2ff54a168eaa4f17"),
    },
    0x0090: {
        "top": (21, 4, 0x010E, "26f11b266a8b454c0a3b0fa957d10a9db8977fcb2887ed5a9f4bf7685f643940"),
        "bottom": (21, 5, 0x0120, "9d9a0107cfc086e32864fd0c7cf6b647354acb9b27aa7517c86f6a52055b1e0d"),
    },
    0x009C: {
        "top": (22, 4, 0x010F, "cf6470ff3396e53bf3a35d3b476c4494c14cfa8315421d67eb947ab8de7d5d31"),
        "bottom": (22, 5, 0x0121, "e4c649c8579710250ee36ea925ae01a41d49afce5f6f34f230b5b8747cf60d67"),
    },
    0x000C: {
        "top": (24, 4, 0x0111, "3b74145e3da19679b3c9c6934538832b306dbd56b0da0b754846dff51cbd3fe4"),
        "bottom": (24, 5, 0x0123, "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"),
    },
}
M32_BLANK_TILE_SHA256 = "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"
M32_BG0_VRAM_SHA256 = "6662c7de25340739f352e19f8634dbcd8b2318892481b2599ea1e9b927924da1"

# M34 is a second fixed known-screen cross, using the protagonist-name field
# visible in the same clean BG0 capture.  The code units, hashes, boxes and
# tile receipts are metadata only; no decoded source string is stored here.
M34_PROTAGONIST_UNITS = (0x00C8, 0x00F6, 0x0063, 0x00FE)
M34_SOURCE_FILE_OFFSET = 0x087384
M34_SOURCE_BYTE_LENGTH = 10
M34_SOURCE_STREAM_SHA256 = "a996824161672f240ae4ddf9578ffce192cc5464efea28949f08dead2d0f23e9"
M34_SOURCE_POINTER_LITERAL_FILE_OFFSET = 0x003E34
M34_SOURCE_POINTER_BUS_ADDRESS = 0x08087384
M34_SOURCE_POINTER_LOAD_PC = 0x08003E24
M34_RECORD_HASHES = {
    0x00C8: "2bbd328bba90164ca0b3b10eff1d260f181454f3b305315703931dcfafcfda14",
    0x00F6: "11ed35e98e5a20b31a870c1f02c4277aa2c54243c3a3d93636483c1edf8e4b93",
    0x0063: "4e2a7536070a7a01c9b608753351a68183591899973578678e7ae2b6026f705c",
    0x00FE: "b125b55c7f58c53b3deedc785a79703855a7502e0610e6bac5435014a00877b9",
}
M34_SCREEN_BOXES = {
    0x00C8: (65, 34, 74, 43),
    0x00F6: (78, 33, 86, 43),
    0x0063: (88, 32, 97, 43),
    0x00FE: (101, 34, 110, 43),
}
M34_MASK_HASHES = {
    0x00C8: "ae462e7b71635156eaf20de4c538043a8a1af4d213a882da316b0fd3b44e860c",
    0x00F6: "a6228b8b625dad1d6c55e0b569c5c0a5be759b9f23c0e0dd8820ca4ecb9720d4",
    0x0063: "0b8ca2a33b11b1e28fac69641f5a8ae228ceab5d958d5edc94a74c00da87b774",
    0x00FE: "fd4fee0e0b579fa395ff61687607ac0f3431380d18904a873712b6ef3732e878",
}
M34_TILE_RECEIPTS = {
    0x00C8: {
        "top": (8, 4, 0x0101, "f4d91b583cfcb6ef0551065264d6163a46432639acd6be23f54a2bace0e58526"),
        "bottom": (8, 5, 0x0113, "2bc6c85e4e77f3291411067131f8a4b4bade0ac592e4ae25cf4f29cd74797e9a"),
    },
    0x00F6: {
        "top": (9, 4, 0x0102, "a686db5215765dd5d2470a2b50647c59f9ad50c71309a0752f51810c36caa0ef"),
        "bottom": (9, 5, 0x0114, "bb7f904ce841b6794668f86bfd61625c42e302c05bcc1e3c2ff54a168eaa4f17"),
    },
    0x0063: {
        "top": (11, 4, 0x0104, "ddb252fd6c24a9a54b54e588abf336a7da526debac947eb24f0a773262b58da5"),
        "bottom": (11, 5, 0x0116, "95a34edb0d05a1c4dcb40ac23b89468c7d83c4ecbe9a65f64ac73bf1ebcb945f"),
    },
    0x00FE: {
        "top": (12, 4, 0x0105, "fa69a7b5dc3dc94d8ba998433c9b4a8630a9ceb998eb4a29aa7a1b7da896ca30"),
        "bottom": (12, 5, 0x0117, "3c69cf77c1732a2e8391fc81eff3859801ca6a22a5a0695690d4c2e05c202197"),
    },
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mask_sha256(mask: Sequence[Sequence[int]]) -> str:
    """Hash a cropped 1bpp mask without writing pixels or source text."""

    return hashlib.sha256(
        bytes(pixel for row in mask for pixel in row)
    ).hexdigest()


def crop_mask(pixels: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Trim a non-empty 1bpp mask to its ink bounding box."""

    height = len(pixels)
    width = len(pixels[0]) if height else 0
    points = [
        (x, y)
        for y, row in enumerate(pixels)
        for x, pixel in enumerate(row)
        if pixel
    ]
    if not points:
        return ()
    min_x = min(x for x, _ in points)
    max_x = max(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_y = max(y for _, y in points)
    del height, width
    return tuple(
        tuple(int(pixels[y][x]) for x in range(min_x, max_x + 1))
        for y in range(min_y, max_y + 1)
    )


def font_record_mask(record: bytes) -> tuple[tuple[int, ...], ...]:
    """Decode one 24-byte record as the confirmed 16x12 MSB-first raster."""

    if len(record) != M32_RECORD_STRIDE:
        raise ValueError(f"font record length {len(record)} != {M32_RECORD_STRIDE}")
    rows = [
        int.from_bytes(record[index:index + 2], "little")
        for index in range(0, M32_RECORD_STRIDE, 2)
    ]
    return crop_mask(
        [
            [1 if value & (1 << (15 - x)) else 0 for x in range(16)]
            for value in rows
        ]
    )


def image_component_mask(
    pixels: Sequence[Sequence[tuple[int, int, int]]],
    box: tuple[int, int, int, int],
) -> tuple[tuple[int, ...], ...]:
    """Read an explicitly bounded screen component as a black/non-black mask."""

    left, top, right, bottom = box
    if not pixels or bottom > len(pixels) or right > len(pixels[0]):
        raise ValueError("screen component is outside the supplied image")
    return tuple(
        tuple(1 if pixels[y][x] != (0, 0, 0) else 0 for x in range(left, right))
        for y in range(top, bottom)
    )


def read_u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise ValueError("VRAM read outside supplied dump")
    return int.from_bytes(data[offset:offset + 2], "little")


def bounded_tilemap_receipt(
    vram: bytes,
    expected_tiles: dict[int, dict[str, tuple[int, int, int, str]]],
) -> dict[str, object]:
    """Check an explicitly bounded set of BG0 tilemap cells and tile hashes."""

    rows: dict[str, object] = {}
    all_match = True
    for unit, expected in expected_tiles.items():
        receipt: dict[str, object] = {}
        for side, (x, y, expected_entry, expected_hash) in expected.items():
            entry_offset = (y * 32 + x) * 2
            entry = read_u16(vram, entry_offset)
            tile_id = entry & 0x03FF
            tile_offset = tile_id * 0x20
            tile = vram[tile_offset:tile_offset + 0x20]
            if len(tile) != 0x20:
                raise ValueError("VRAM tile read outside supplied dump")
            actual_hash = hashlib.sha256(tile).hexdigest()
            item = {
                "x": x,
                "y": y,
                "entry": f"0x{entry:04X}",
                "expected_entry": f"0x{expected_entry:04X}",
                "tile_id": tile_id,
                "expected_tile_id": expected_entry & 0x03FF,
                "tile_sha256": actual_hash,
                "expected_tile_sha256": expected_hash,
                "entry_match": entry == expected_entry,
                "tile_hash_match": actual_hash == expected_hash,
            }
            receipt[side] = item
            all_match = all_match and bool(item["entry_match"]) and bool(item["tile_hash_match"])
        rows[f"0x{unit:04X}"] = receipt
    result = {
        "vram_sha256": hashlib.sha256(vram).hexdigest(),
        "expected_vram_sha256_match": hashlib.sha256(vram).hexdigest() == M32_BG0_VRAM_SHA256,
        "screenbase": "0x00000000",
        "charbase": "0x00000000",
        "rows": rows,
        "all_tilemap_and_tile_hashes_match": all_match,
    }
    return result


def tilemap_receipt(vram: bytes) -> dict[str, object]:
    """Check only the five M32 row positions and their two BG0 tile cells."""

    return bounded_tilemap_receipt(vram, M32_TILE_RECEIPTS)


def protagonist_name_raster_cross(
    *,
    rom: bytes | None,
    vram: bytes | None,
    image_pixels: Sequence[Sequence[tuple[int, int, int]]] | None,
    image_sha256: str | None,
    screen_summary: dict[str, object],
) -> dict[str, object]:
    """Cross one fixed protagonist-name source pointer with the known BG0 screen.

    This is deliberately not a source extractor.  It checks one source pointer,
    one terminated halfword span, four record hashes, four cropped raster masks
    and eight BG0 tile hashes.  No decoded name or glyph bytes are serialized.
    """

    screen = screen_summary["starts"][0]["screen"]
    keyboard = screen.get("keyboard_layout", {})
    keyboard_gate = (
        bool(screen.get("gate_confirmed"))
        and screen.get("bg1_screenblock_sha256") == EXPECTED_BG1_SCREENBLOCK_SHA256
        and keyboard.get("position_match_count") == 8
        and len(keyboard.get("selected_positions", [])) == 8
    )
    result: dict[str, object] = {
        "probe_version": "m34-protagonist-name-raster-cross-20260816.v1",
        "method": "known-screen-static-source-pointer-record-raster-and-tilemap-cross",
        "source_text_emitted": False,
        "runtime_reader_breakpoint_hit": False,
        "screen": {
            "bg0_image_sha256": image_sha256,
            "bg0_image_expected_hash_match": image_sha256 == EXPECTED_BG0_IMAGE_SHA256,
            "keyboard_gate": keyboard_gate,
        },
        "source_pointer": {
            "literal_file_offset": f"0x{M34_SOURCE_POINTER_LITERAL_FILE_OFFSET:06X}",
            "load_pc": f"0x{M34_SOURCE_POINTER_LOAD_PC:08X}",
            "expected_bus_address": f"0x{M34_SOURCE_POINTER_BUS_ADDRESS:08X}",
            "expected_file_offset": f"0x{M34_SOURCE_FILE_OFFSET:06X}",
        },
        "source_stream": {
            "file_offset": f"0x{M34_SOURCE_FILE_OFFSET:06X}",
            "byte_length": M34_SOURCE_BYTE_LENGTH,
            "expected_sha256": M34_SOURCE_STREAM_SHA256,
            "expected_code_unit_count": len(M34_PROTAGONIST_UNITS),
            "expected_terminator": "0x0000",
        },
        "records": [],
        "tilemap": None,
        "classification": {
            "scene_role_candidate": "ui-name-entry-protagonist-name-field",
            "runtime_context_proof": "missing",
            "glyph_identity_confirmed_by_this_probe": 0,
            "source_pointer_confirmed": False,
            "general_codepage_confirmed": False,
            "control_schema_confirmed": False,
            "eligible_for_ledger": False,
        },
    }
    if rom is None:
        result["failure_reason"] = "ROM input not supplied"
        return result

    rom_sha256 = hashlib.sha256(rom).hexdigest()
    stream = rom[M34_SOURCE_FILE_OFFSET:M34_SOURCE_FILE_OFFSET + M34_SOURCE_BYTE_LENGTH]
    stream_units = [
        int.from_bytes(stream[index:index + 2], "little")
        for index in range(0, len(stream), 2)
        if len(stream[index:index + 2]) == 2
    ]
    stream_match = (
        len(stream) == M34_SOURCE_BYTE_LENGTH
        and hashlib.sha256(stream).hexdigest() == M34_SOURCE_STREAM_SHA256
        and tuple(stream_units[:-1]) == M34_PROTAGONIST_UNITS
        and stream_units[-1:] == [0x0000]
    )
    literal = int.from_bytes(
        rom[M34_SOURCE_POINTER_LITERAL_FILE_OFFSET:M34_SOURCE_POINTER_LITERAL_FILE_OFFSET + 4],
        "little",
    )
    pointer_match = literal == M34_SOURCE_POINTER_BUS_ADDRESS
    result["rom"] = {
        "sha256": rom_sha256,
        "expected_a9pj_sha256_match": rom_sha256 == EXPECTED_ROM_SHA256,
        "size": len(rom),
    }
    result["source_pointer"].update({
        "literal_value": f"0x{literal:08X}",
        "literal_match": pointer_match,
    })
    result["source_stream"].update({
        "observed_sha256": hashlib.sha256(stream).hexdigest(),
        "observed_code_unit_count": max(0, len(stream_units) - 1),
        "has_terminator": bool(stream_units and stream_units[-1] == 0x0000),
        "units_match": tuple(stream_units[:-1]) == M34_PROTAGONIST_UNITS,
        "bytes_match_expected": stream_match,
    })

    record_results: list[dict[str, object]] = []
    raster_match_count = 0
    for unit in M34_PROTAGONIST_UNITS:
        bus_address = M32_RECORD_BASE + unit * M32_RECORD_STRIDE
        file_offset = bus_address - 0x08000000
        record = rom[file_offset:file_offset + M32_RECORD_STRIDE]
        record_hash = hashlib.sha256(record).hexdigest()
        record_mask = font_record_mask(record) if len(record) == M32_RECORD_STRIDE else ()
        screen_mask = None
        if image_pixels is not None:
            screen_mask = image_component_mask(image_pixels, M34_SCREEN_BOXES[unit])
        mask_match = screen_mask is not None and record_mask == crop_mask(screen_mask)
        if mask_match:
            raster_match_count += 1
        record_results.append({
            "code_unit": f"0x{unit:04X}",
            "record_bus_address": f"0x{bus_address:08X}",
            "record_file_offset": f"0x{file_offset:06X}",
            "record_sha256": record_hash,
            "expected_record_sha256": M34_RECORD_HASHES[unit],
            "record_hash_match": record_hash == M34_RECORD_HASHES[unit],
            "screen_bbox": list(M34_SCREEN_BOXES[unit]),
            "record_mask_sha256": mask_sha256(record_mask) if record_mask else None,
            "expected_mask_sha256": M34_MASK_HASHES[unit],
            "screen_mask_sha256": mask_sha256(screen_mask) if screen_mask else None,
            "mask_equal": mask_match,
        })
    result["records"] = record_results

    tilemap_match = False
    if vram is not None:
        result["tilemap"] = bounded_tilemap_receipt(vram, M34_TILE_RECEIPTS)
        tilemap_match = bool(result["tilemap"]["all_tilemap_and_tile_hashes_match"])
    all_record_hashes = all(bool(row["record_hash_match"]) for row in record_results)
    all_masks = raster_match_count == len(M34_PROTAGONIST_UNITS)
    eligible = (
        keyboard_gate
        and rom_sha256 == EXPECTED_ROM_SHA256
        and pointer_match
        and stream_match
        and all_record_hashes
        and image_sha256 == EXPECTED_BG0_IMAGE_SHA256
        and all_masks
        and tilemap_match
    )
    result["classification"] = {
        "scene_role_candidate": "ui-name-entry-protagonist-name-field",
        "runtime_context_proof": (
            "known-screen-static-source-pointer-record-raster-and-tilemap-correlated"
            if eligible else "partial-known-screen-cross"
        ),
        "glyph_identity_confirmed_by_this_probe": raster_match_count if eligible else 0,
        "source_pointer_confirmed": pointer_match and stream_match,
        "general_codepage_confirmed": False,
        "control_schema_confirmed": False,
        "eligible_for_ledger": eligible,
    }
    result["gate_checks"] = {
        "keyboard_gate": keyboard_gate,
        "rom": rom_sha256 == EXPECTED_ROM_SHA256,
        "source_pointer": pointer_match,
        "source_stream": stream_match,
        "record_hashes": all_record_hashes,
        "image_sha256": image_sha256 == EXPECTED_BG0_IMAGE_SHA256,
        "record_to_image_masks": all_masks,
        "bg0_tilemap_and_tile_hashes": tilemap_match,
    }
    return result


def load_rgb_pixels(path: Path) -> tuple[tuple[int, int], list[list[tuple[int, int, int]]]]:
    """Load a private raster only for mask comparison; never serialize pixels."""

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on local runtime
        raise RuntimeError("--bg0-image requires Pillow for private raster input") from exc
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        return (width, height), [
            [rgb.getpixel((x, y)) for x in range(width)]
            for y in range(height)
        ]


def known_screen_raster_cross(
    *,
    rom: bytes | None,
    vram: bytes | None,
    image_pixels: Sequence[Sequence[tuple[int, int, int]]] | None,
    image_sha256: str | None,
    screen_summary: dict[str, object],
    m17_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run the bounded M32 record→screen→tilemap cross-check.

    The eligibility decision requires all three independent surfaces: the
    clean-ROM record arithmetic, the known final BG0 raster, and the BG0
    tilemap/tile hashes captured at the same known screen.  It deliberately
    does not require or imply a live reader breakpoint or byte-identical
    CPU/DMA source copy.
    """

    screen = screen_summary["starts"][0]["screen"]
    keyboard = screen.get("keyboard_layout", {})
    keyboard_gate = (
        bool(screen.get("gate_confirmed"))
        and screen.get("bg1_screenblock_sha256") == EXPECTED_BG1_SCREENBLOCK_SHA256
        and keyboard.get("position_match_count") == 8
        and len(keyboard.get("selected_positions", [])) == 8
    )
    result: dict[str, object] = {
        "probe_version": PROBE_VERSION,
        "method": "known-screen-record-raster-and-tilemap-cross",
        "source_text_emitted": False,
        "stream": {
            "file_offset": f"0x{M32_STREAM_FILE_OFFSET:06X}",
            "expected_units": [f"0x{unit:04X}" for unit in M32_STREAM_UNITS],
            "terminator": "0x0000",
            "expected_source_text_sha256": M32_SOURCE_TEXT_SHA256,
        },
        "runtime_keyboard_gate": {
            "confirmed": keyboard_gate,
            "bg1_screenblock_sha256": screen.get("bg1_screenblock_sha256"),
            "position_match_count": keyboard.get("position_match_count"),
            "position_count": len(keyboard.get("selected_positions", [])),
        },
        "records": [],
        "tilemap": None,
        "m17": None,
        "classification": {
            "runtime_context_proof": "missing",
            "reader_breakpoint_hit": False,
            "glyph_identity_confirmed_by_this_probe": 0,
            "raw_byte_copy_confirmed": False,
            "general_codepage_confirmed": False,
            "control_schema_confirmed": False,
            "eligible_for_ledger": False,
        },
    }
    if rom is None:
        result["failure_reason"] = "ROM input not supplied"
        return result

    rom_sha256 = hashlib.sha256(rom).hexdigest()
    stream_bytes = rom[M32_STREAM_FILE_OFFSET:M32_STREAM_FILE_OFFSET + len(M32_STREAM_BYTES)]
    stream_match = stream_bytes == M32_STREAM_BYTES
    result["rom"] = {
        "sha256": rom_sha256,
        "expected_a9pj_sha256_match": rom_sha256 == EXPECTED_ROM_SHA256,
        "size": len(rom),
    }
    result["stream"].update({
        "byte_sha256": hashlib.sha256(stream_bytes).hexdigest(),
        "expected_byte_sha256": M32_STREAM_SHA256,
        "bytes_match_expected": stream_match,
        "has_terminator": stream_bytes[-2:] == b"\x00\x00",
    })

    record_results: list[dict[str, object]] = []
    raster_match_count = 0
    for unit in M32_STREAM_UNITS:
        bus_address = M32_RECORD_BASE + unit * M32_RECORD_STRIDE
        file_offset = bus_address - 0x08000000
        record = rom[file_offset:file_offset + M32_RECORD_STRIDE]
        record_sha256 = hashlib.sha256(record).hexdigest()
        record_mask = font_record_mask(record) if len(record) == M32_RECORD_STRIDE else ()
        screen_mask = None
        if image_pixels is not None:
            screen_mask = image_component_mask(image_pixels, M32_SCREEN_BOXES[unit])
        mask_match = screen_mask is not None and record_mask == crop_mask(screen_mask)
        if mask_match:
            raster_match_count += 1
        record_results.append({
            "code_unit": f"0x{unit:04X}",
            "record_bus_address": f"0x{bus_address:08X}",
            "record_file_offset": f"0x{file_offset:06X}",
            "record_sha256": record_sha256,
            "expected_record_sha256": M32_RECORD_HASHES[unit],
            "record_hash_match": record_sha256 == M32_RECORD_HASHES[unit],
            "screen_bbox": list(M32_SCREEN_BOXES[unit]),
            "record_mask_sha256": mask_sha256(record_mask) if record_mask else None,
            "screen_mask_sha256": mask_sha256(screen_mask) if screen_mask else None,
            "mask_equal": mask_match,
        })
    result["records"] = record_results

    tilemap_match = False
    if vram is not None:
        result["tilemap"] = tilemap_receipt(vram)
        tilemap_match = bool(result["tilemap"]["all_tilemap_and_tile_hashes_match"])
    if m17_summary is not None:
        m17_screen = m17_summary.get("post_trace_screen", {})
        result["m17"] = {
            "post_trace_screen_matches_gate": (
                m17_screen.get("bg0_screenblock_sha256") == EXPECTED_BG0_SCREENBLOCK_SHA256
                and m17_screen.get("bg1_screenblock_sha256") == EXPECTED_BG1_SCREENBLOCK_SHA256
                and m17_screen.get("dispcnt") == "0x1B40"
            ),
            "summary_rom_sha256": m17_summary.get("rom", {}).get("sha256"),
            "summary_rom_matches": m17_summary.get("rom", {}).get("sha256") == EXPECTED_ROM_SHA256,
        }

    all_record_hashes = all(bool(row["record_hash_match"]) for row in record_results)
    all_masks = raster_match_count == len(M32_STREAM_UNITS)
    image_match = image_sha256 == EXPECTED_BG0_IMAGE_SHA256
    eligible = (
        keyboard_gate
        and rom_sha256 == EXPECTED_ROM_SHA256
        and stream_match
        and all_record_hashes
        and image_match
        and all_masks
        and tilemap_match
    )
    result["classification"] = {
        "runtime_context_proof": "known-screen-record-raster-and-tilemap-correlated" if eligible else "partial-known-screen-cross",
        "reader_breakpoint_hit": False,
        "glyph_identity_confirmed_by_this_probe": raster_match_count if eligible else 0,
        "raw_byte_copy_confirmed": False,
        "general_codepage_confirmed": False,
        "control_schema_confirmed": False,
        "eligible_for_ledger": eligible,
    }
    result["gate_checks"] = {
        "keyboard_gate": keyboard_gate,
        "rom": rom_sha256 == EXPECTED_ROM_SHA256,
        "stream": stream_match,
        "record_hashes": all_record_hashes,
        "image_sha256": image_match,
        "record_to_image_masks": all_masks,
        "bg0_tilemap_and_tile_hashes": tilemap_match,
    }
    return result


def cross_check(
    rows: list[dict[str, object]],
    screen_summary: dict[str, object],
    *,
    bg0_image_sha256: str | None = None,
    raster_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    matches = [
        row
        for row in rows
        if row.get("caller_bus_address") == EXPECTED_CALLER
        and row.get("stream_file_offset") == EXPECTED_STREAM
    ]
    screen = screen_summary["starts"][0]["screen"]
    keyboard = screen.get("keyboard_layout", {})
    row = matches[0] if matches else None
    result = {
        "probe_version": PROBE_VERSION,
        "candidate_match_count": len(matches),
        "candidate": None
        if row is None
        else {
            "string_id": row.get("string_id"),
            "caller_bus_address": row.get("caller_bus_address"),
            "stream_file_offset": row.get("stream_file_offset"),
            "source_text_sha256": row.get("source_text_sha256"),
            "mapping_status_counts": row.get("mapping_status_counts"),
            "unresolved_code_units": row.get("unresolved_code_units"),
            "control_candidates": row.get("control_candidates"),
            "complete_codepage": row.get("complete_codepage"),
            "raster_gate_eligible": bool(
                raster_receipt
                and raster_receipt.get("classification", {}).get("eligible_for_ledger")
            ),
        },
        "rom": {
            "sha256": screen_summary.get("rom", {}).get("sha256"),
            "expected_a9pj_sha256_match": screen_summary.get("rom", {}).get("sha256") == EXPECTED_ROM_SHA256,
        },
        "runtime_screen": {
            "gate_confirmed": screen.get("gate_confirmed"),
            "dispcnt": screen.get("dispcnt"),
            "bgcnt": screen.get("bgcnt"),
            "bg0_screenblock_sha256": screen.get("bg0_screenblock_sha256"),
            "bg1_screenblock_sha256": screen.get("bg1_screenblock_sha256"),
            "bg0_expected_hash_match": screen.get("bg0_screenblock_sha256") == EXPECTED_BG0_SCREENBLOCK_SHA256,
            "bg1_expected_keyboard_hash_match": screen.get("bg1_screenblock_sha256") == EXPECTED_BG1_SCREENBLOCK_SHA256,
            "keyboard_position_match_count": keyboard.get("position_match_count"),
            "keyboard_position_count": len(keyboard.get("selected_positions", [])),
            "bg0_image_sha256": bg0_image_sha256,
            "bg0_image_expected_hash_match": bg0_image_sha256 == EXPECTED_BG0_IMAGE_SHA256
            if bg0_image_sha256 is not None
            else False,
        },
        "classification": {
            "scene_role_candidate": "ui-name-entry" if row is not None else "unknown",
            "runtime_context_proof": (
                raster_receipt.get("classification", {}).get("runtime_context_proof")
                if row is not None and raster_receipt
                else "screen-and-static-caller-correlated" if row is not None else "missing"
            ),
            "reader_breakpoint_hit": False,
            "glyph_identity_confirmed_by_this_probe": (
                raster_receipt.get("classification", {}).get("glyph_identity_confirmed_by_this_probe", 0)
                if row is not None and raster_receipt
                else 0
            ),
            "raw_byte_copy_confirmed": False,
            "eligible_for_ledger": bool(
                row is not None
                and raster_receipt
                and raster_receipt.get("classification", {}).get("eligible_for_ledger")
            ),
        },
        "source_text_emitted": False,
    }
    if raster_receipt is not None:
        result["raster_cross"] = raster_receipt
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("local_jsonl", type=Path)
    parser.add_argument("screen_summary", type=Path)
    parser.add_argument("--bg0-image", type=Path)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--bg0-vram", type=Path)
    parser.add_argument("--m17-summary", type=Path)
    parser.add_argument(
        "--protagonist-name-cross",
        action="store_true",
        help="also run the fixed M34 protagonist-name source/raster cross",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    image_hash = sha256_file(args.bg0_image) if args.bg0_image else None
    image_pixels = load_rgb_pixels(args.bg0_image)[1] if args.bg0_image else None
    raster_receipt = known_screen_raster_cross(
        rom=args.rom.read_bytes() if args.rom else None,
        vram=args.bg0_vram.read_bytes() if args.bg0_vram else None,
        image_pixels=image_pixels,
        image_sha256=image_hash,
        screen_summary=json.loads(args.screen_summary.read_text(encoding="utf-8")),
        m17_summary=json.loads(args.m17_summary.read_text(encoding="utf-8")) if args.m17_summary else None,
    ) if any((args.rom, args.bg0_vram, args.m17_summary)) else None
    result = cross_check(
        load_rows(args.local_jsonl),
        json.loads(args.screen_summary.read_text(encoding="utf-8")),
        bg0_image_sha256=image_hash,
        raster_receipt=raster_receipt,
    )
    if args.protagonist_name_cross:
        result["protagonist_name_cross"] = protagonist_name_raster_cross(
            rom=args.rom.read_bytes() if args.rom else None,
            vram=args.bg0_vram.read_bytes() if args.bg0_vram else None,
            image_pixels=image_pixels,
            image_sha256=image_hash,
            screen_summary=json.loads(args.screen_summary.read_text(encoding="utf-8")),
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"probe_version": PROBE_VERSION, "output": str(args.output), "source_text_emitted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
