#!/usr/bin/env python3
"""Render one local clean script record through the proven glyph model.

This is a research renderer, not a decoder: it preserves unknown code units
and control positions visually, and writes only to an explicitly supplied
local image path.  The JSONL input and rendered image are source-bearing
research artifacts and must remain ignored or outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import zlib

from PIL import Image, ImageDraw


ROM_SIZE = 0x800000
GLYPH_TABLE_FILE = 0x2DF3D4
ALT_GLYPH_TABLE_FILE = 0x2E0BD4
GLYPH_STRIDE = 32
ALT_GLYPH_BANK_BIAS = 0x4000
ALT_GLYPH_CONTROLS = {0xE0, 0xE1}
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"


def validate_rom(data: bytes) -> None:
    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean ROM: CRC32={crc32:08X}, SHA256={sha256}")


def load_record(path: pathlib.Path, pointer_cpu: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("pointer_cpu") == pointer_cpu:
            return record
    raise ValueError(f"script pointer not found: {pointer_cpu}")


def table_tile(rom: bytes, index: int) -> bytes:
    start = GLYPH_TABLE_FILE + index * GLYPH_STRIDE
    return rom[start:start + GLYPH_STRIDE]


def alt_table_tile(rom: bytes, index: int, lead: int = 0xE0) -> bytes:
    if lead not in ALT_GLYPH_CONTROLS:
        raise ValueError(f"unsupported alternate glyph lead: 0x{lead:02X}")
    bank_bias = ALT_GLYPH_BANK_BIAS if lead == 0xE1 else 0
    start = ALT_GLYPH_TABLE_FILE + bank_bias + index * GLYPH_STRIDE
    return rom[start:start + GLYPH_STRIDE]


def apply_pair_mask(tile: bytes, lead: int, trail: int) -> bytes:
    if lead == 0x93:
        mask = 0xF1FFFFFF
    elif lead == 0x92 and trail == 0x30:
        mask = 0xF1F1FFFF
    else:
        mask = 0xFF1FFFFF
    second = int.from_bytes(tile[4:8], "little") & mask
    return tile[:4] + second.to_bytes(4, "little") + tile[8:]


def tile_image(tile: bytes, scale: int) -> Image.Image:
    image = Image.new("RGB", (8, 8), (0, 0, 0))
    pixels = image.load()
    for y in range(8):
        for x in range(8):
            packed = tile[y * 4 + x // 2]
            # GBA 4bpp tiles store the low nibble at the even x coordinate;
            # keep this aligned with core/gba/render_vram.py.
            value = (packed >> (0 if x % 2 == 0 else 4)) & 0x0F
            # Palette index 1 is the menu background in the clean capture;
            # retain all higher indices as visible glyph coverage.
            pixels[x, y] = (255, 255, 255) if value > 1 else (0, 0, 0)
    return image.resize((8 * scale, 8 * scale), Image.Resampling.NEAREST)


def render_record(rom: bytes, record: dict[str, object], scale: int, skip_controls: bool) -> tuple[Image.Image, int]:
    tokens = record["tokens"]
    images: list[Image.Image] = []
    controls = 0
    index = 0
    while index < len(tokens):  # type: ignore[arg-type]
        token = tokens[index]  # type: ignore[index]
        kind = token["kind"]
        if kind == "single-byte-candidate":
            images.append(tile_image(table_tile(rom, int(token["value"])), scale))
        elif kind == "pair":
            lead = int(token["lead"])
            trail = int(token["trail"])
            combined = bytes(
                left | right
                for left, right in zip(table_tile(rom, lead), table_tile(rom, trail))
            )
            images.append(tile_image(apply_pair_mask(combined, lead, trail), scale))
        elif kind == "control-candidate" and int(token["value"]) in ALT_GLYPH_CONTROLS:
            # 0xE0/0xE1 are proven one-byte consumers which render the
            # following code unit through the alternate glyph pool.  This is
            # deliberately narrower than a full control decoder: the pool
            # bank and every other control remain explicit research markers.
            if index + 1 < len(tokens) and tokens[index + 1]["kind"] == "single-byte-candidate":  # type: ignore[index]
                parameter = int(tokens[index + 1]["value"])  # type: ignore[index]
                images.append(tile_image(alt_table_tile(rom, parameter, int(token["value"])), scale))
                index += 1
            else:
                controls += 1
                if not skip_controls:
                    marker = Image.new("RGB", (8 * scale, 8 * scale), (120, 0, 0))
                    ImageDraw.Draw(marker).rectangle(
                        (scale, scale, 7 * scale, 7 * scale), outline=(255, 255, 0), width=max(1, scale // 2)
                    )
                    images.append(marker)
        else:
            controls += 1
            if not skip_controls:
                marker = Image.new("RGB", (8 * scale, 8 * scale), (120, 0, 0))
                ImageDraw.Draw(marker).rectangle(
                    (scale, scale, 7 * scale, 7 * scale), outline=(255, 255, 0), width=max(1, scale // 2)
                )
                images.append(marker)
        index += 1
    width = max(1, len(images) * (8 * scale + scale))
    canvas = Image.new("RGB", (width, 8 * scale), (0, 0, 0))
    for index, image in enumerate(images):
        canvas.paste(image, (index * (8 * scale + scale), 0))
    return canvas, controls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("decoded", type=pathlib.Path)
    parser.add_argument("--pointer-cpu", required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--scale", type=int, default=8)
    parser.add_argument("--skip-controls", action="store_true")
    args = parser.parse_args()
    if args.scale < 1:
        parser.error("--scale must be positive")
    try:
        rom = args.rom.read_bytes()
        validate_rom(rom)
        record = load_record(args.decoded, args.pointer_cpu)
        image, controls = render_record(rom, record, args.scale, args.skip_controls)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.out)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"render_script_record: {error}", file=sys.stderr)
        return 2

    print("rom-sha256", EXPECTED_SHA256)
    print("pointer", args.pointer_cpu, "glyph-images", image.width // (8 * args.scale + args.scale))
    print("controls", controls)
    print("output", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
