#!/usr/bin/env python3
"""Bounded A5TJ OBJ glyph-source analysis.

The inputs are local ROM/VRAM/OAM captures.  The report deliberately contains
only hashes, offsets, counts, and OAM metadata; it never writes tile bytes or
decoded game text.  It checks the exact 4bpp OBJ tile/sprite bytes against the
ROM, a small set of reversible pixel transforms, and bounded standard GBA
LZ77/RL streams.  A match is evidence about bytes, not proof of a string
table or Unicode codepage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


OBJ_DIMS = {
    (0, 0): (1, 1),
    (0, 1): (2, 2),
    (0, 2): (4, 4),
    (0, 3): (8, 8),
    (1, 0): (2, 1),
    (1, 1): (4, 1),
    (1, 2): (4, 2),
    (1, 3): (8, 4),
    (2, 0): (1, 2),
    (2, 1): (1, 4),
    (2, 2): (2, 4),
    (2, 3): (4, 8),
}


def load_rom(path: Path) -> bytes:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and info.filename.lower().endswith((".gba", ".agb", ".rom"))
            ]
            if len(members) != 1:
                raise ValueError(f"expected one GBA member, found {len(members)}")
            return archive.read(members[0])
    return path.read_bytes()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return offsets
        offsets.append(offset)
        start = offset + 1


def sprite_dimensions(shape: int, size: int) -> tuple[int, int]:
    try:
        return OBJ_DIMS[(shape, size)]
    except KeyError as exc:
        raise ValueError(f"unsupported OBJ shape/size: {shape}/{size}") from exc


def active_sprites(
    oam: bytes,
    *,
    max_y: int,
    mapping: str,
    bpp: int,
) -> list[dict[str, object]]:
    if len(oam) < 0x400:
        raise ValueError("OAM capture must contain 0x400 bytes")
    index_scale = 2 if bpp == 8 else 1
    sprites: list[dict[str, object]] = []
    for index in range(128):
        attr0, attr1, attr2, _ = struct.unpack_from("<HHHH", oam, index * 8)
        y = attr0 & 0xFF
        obj_mode = (attr0 >> 8) & 3
        shape = (attr0 >> 14) & 3
        size = (attr1 >> 14) & 3
        x = attr1 & 0x1FF
        if x >= 256:
            x -= 512
        # This matches the shared renderer's bounded active-screen rule and
        # the A5TJ capture: mode 2 and y>=160 are not part of this frame.
        if obj_mode == 2 or y >= max_y:
            continue
        tile_width, tile_height = sprite_dimensions(shape, size)
        tile_start = attr2 & 0x3FF
        tile_numbers: list[int] = []
        for tile_y in range(tile_height):
            for tile_x in range(tile_width):
                if mapping == "1d":
                    delta = (tile_y * tile_width + tile_x) * index_scale
                else:
                    delta = (tile_y * 32 + tile_x * index_scale)
                tile_numbers.append(tile_start + delta)
        sprites.append(
            {
                "index": index,
                "x": x,
                "y": y,
                "shape": shape,
                "size": size,
                "width_tiles": tile_width,
                "height_tiles": tile_height,
                "tile_start": tile_start,
                "tile_numbers": tile_numbers,
                "palette_bank": (attr2 >> 12) & 0xF,
                "hflip": bool(attr1 & 0x1000),
                "vflip": bool(attr1 & 0x2000),
            }
        )
    return sprites


def tile_bytes(vram: bytes, tile_number: int, *, obj_base: int, bpp: int) -> bytes:
    tile_size = 64 if bpp == 8 else 32
    offset = obj_base + tile_number * tile_size
    if offset < 0 or offset + tile_size > len(vram):
        raise ValueError(f"OBJ tile {tile_number} is outside VRAM capture")
    return vram[offset : offset + tile_size]


def decode_4bpp_tile(raw: bytes) -> list[list[int]]:
    pixels: list[list[int]] = []
    for row in range(8):
        output: list[int] = []
        for value in raw[row * 4 : row * 4 + 4]:
            output.extend((value & 0xF, value >> 4))
        pixels.append(output)
    return pixels


def encode_4bpp_tile(pixels: list[list[int]]) -> bytes:
    output = bytearray()
    for row in pixels:
        for column in range(0, 8, 2):
            output.append((row[column] & 0xF) | ((row[column + 1] & 0xF) << 4))
    return bytes(output)


def sprite_pixels(raw_tiles: list[bytes], width_tiles: int, height_tiles: int) -> list[list[int]]:
    canvas = [[0 for _ in range(width_tiles * 8)] for _ in range(height_tiles * 8)]
    for tile_index, raw in enumerate(raw_tiles):
        tile = decode_4bpp_tile(raw)
        tile_x = tile_index % width_tiles
        tile_y = tile_index // width_tiles
        for y in range(8):
            for x in range(8):
                canvas[tile_y * 8 + y][tile_x * 8 + x] = tile[y][x]
    return canvas


def transformed_sprite_bytes(
    raw_tiles: list[bytes], width_tiles: int, height_tiles: int
) -> dict[str, bytes]:
    """Return a deliberately small 4bpp transform family for one sprite."""
    if not raw_tiles:
        return {}
    pixels = sprite_pixels(raw_tiles, width_tiles, height_tiles)
    variants = {
        "hflip": [list(reversed(row)) for row in pixels],
        "vflip": list(reversed(pixels)),
        "rotate180": [list(reversed(row)) for row in reversed(pixels)],
    }
    output: dict[str, bytes] = {}
    for name, matrix in variants.items():
        height = len(matrix)
        width = len(matrix[0])
        encoded = bytearray()
        for tile_y in range(0, height, 8):
            for tile_x in range(0, width, 8):
                tile = [row[tile_x : tile_x + 8] for row in matrix[tile_y : tile_y + 8]]
                encoded.extend(encode_4bpp_tile(tile))
        output[name] = bytes(encoded)
    output["nibble_swap"] = bytes(
        ((value & 0xF) << 4) | (value >> 4) for value in b"".join(raw_tiles)
    )
    return output


def match_record(rom: bytes, value: bytes, *, limit: int = 12) -> dict[str, object]:
    offsets = find_all(rom, value)
    return {"count": len(offsets), "offsets": [f"0x{x:x}" for x in offsets[:limit]]}


def add_bus_offsets(record: dict[str, object], base: int) -> dict[str, object]:
    offsets = [int(value, 16) for value in record["offsets"]]
    return {
        **record,
        "bus_offsets": [f"0x{base + value:08x}" for value in offsets],
    }


def gcd_stride(offsets: Iterable[int]) -> dict[str, object] | None:
    unique = sorted(set(offsets))
    if len(unique) < 2:
        return None
    deltas = [right - left for left, right in zip(unique, unique[1:])]
    return {
        "matched_offsets": [f"0x{x:x}" for x in unique],
        "delta_gcd": math.gcd(*deltas),
        "delta_counts": {
            f"0x{delta:x}": count for delta, count in Counter(deltas).most_common()
        },
    }


def lz77_decompress(data: bytes, offset: int, max_output: int) -> bytes | None:
    if offset + 4 > len(data) or data[offset] != 0x10:
        return None
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0 or size > max_output:
        return None
    cursor = offset + 4
    output = bytearray()
    try:
        while len(output) < size:
            flags = data[cursor]
            cursor += 1
            for bit in range(8):
                if len(output) >= size:
                    break
                if flags & (1 << (7 - bit)):
                    first, second = data[cursor], data[cursor + 1]
                    cursor += 2
                    length = (first >> 4) + 3
                    distance = (((first & 0xF) << 8) | second) + 1
                    if distance > len(output):
                        return None
                    for _ in range(length):
                        output.append(output[-distance])
                        if len(output) >= size:
                            break
                else:
                    output.append(data[cursor])
                    cursor += 1
    except IndexError:
        return None
    return bytes(output) if len(output) == size else None


def rl_decompress(data: bytes, offset: int, max_output: int) -> bytes | None:
    if offset + 4 > len(data) or data[offset] != 0x30:
        return None
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    if size <= 0 or size > max_output:
        return None
    cursor = offset + 4
    output = bytearray()
    try:
        while len(output) < size:
            header = data[cursor]
            cursor += 1
            if header & 0x80:
                count = (header & 0x7F) + 3
                value = data[cursor]
                cursor += 1
                output.extend([value] * min(count, size - len(output)))
            else:
                count = (header & 0x7F) + 1
                output.extend(data[cursor : cursor + min(count, size - len(output))])
                cursor += count
    except IndexError:
        return None
    return bytes(output) if len(output) == size else None


def scan_compressed(
    rom: bytes,
    targets: dict[bytes, list[dict[str, object]]],
    *,
    alignment: int,
    max_output: int,
    max_candidates: int,
) -> dict[str, object]:
    candidates = Counter()
    valid = Counter()
    match_reference_counts = Counter()
    matches: list[dict[str, object]] = []
    examined = 0
    limit_hit = False
    for offset in range(0, len(rom) - 4, alignment):
        kind = {0x10: "lz77", 0x30: "rl"}.get(rom[offset])
        if kind is None:
            continue
        size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
        if size <= 0 or size > max_output:
            continue
        candidates[kind] += 1
        examined += 1
        if examined > max_candidates:
            limit_hit = True
            break
        unpacked = (
            lz77_decompress(rom, offset, max_output)
            if kind == "lz77"
            else rl_decompress(rom, offset, max_output)
        )
        if unpacked is None:
            continue
        valid[kind] += 1
        # Prefer the full sprite glyph (128 bytes for A5TJ's 2x2 sprites)
        # before sparse individual tiles.  This keeps the bounded evidence
        # useful even when a decompressed graphics block contains many blank
        # tiles.
        for needle, refs in sorted(targets.items(), key=lambda item: -len(item[0])):
            output_offset = unpacked.find(needle)
            if output_offset < 0:
                continue
            for ref in refs[:4]:
                match_reference_counts[f"{ref['kind']}:{ref['transform']}"] += 1
                if len(matches) >= 128:
                    break
                matches.append(
                    {
                        "kind": kind,
                        "rom_offset": f"0x{offset:x}",
                        "output_size": len(unpacked),
                        "output_offset": f"0x{output_offset:x}",
                        "match_length": len(needle),
                        "reference": ref,
                    }
                )
    return {
        "alignment": alignment,
        "max_output": max_output,
        "max_candidates": max_candidates,
        "candidate_limit_hit": limit_hit,
        "candidates_examined": examined,
        "candidate_counts": dict(candidates),
        "valid_stream_counts": dict(valid),
        "match_reference_counts": dict(match_reference_counts),
        "matches_capped_at": 128,
        "matches": matches,
    }


def analyze(
    rom: bytes,
    vram: bytes,
    oam: bytes,
    iwram: bytes | None = None,
    ewram: bytes | None = None,
    *,
    max_y: int,
    obj_base: int,
    bpp: int,
    mapping: str,
    compression_alignment: int,
    compression_max_output: int,
    compression_max_candidates: int,
    compression_glyphs_only: bool,
    skip_compression: bool,
) -> dict[str, object]:
    if bpp != 4:
        raise ValueError("A5TJ M1.5 analysis currently requires 4bpp OBJ data")
    sprites = active_sprites(oam, max_y=max_y, mapping=mapping, bpp=bpp)
    tile_cache: dict[int, bytes] = {}
    byte_match_cache: dict[bytes, dict[str, object]] = {}
    target_refs: defaultdict[bytes, list[dict[str, object]]] = defaultdict(list)
    sprite_results: list[dict[str, object]] = []
    glyph_bytes_by_index: dict[int, bytes] = {}
    duplicate_groups: defaultdict[str, list[int]] = defaultdict(list)

    for sprite in sprites:
        numbers = [int(value) for value in sprite["tile_numbers"]]
        raw_tiles = []
        for tile_number in numbers:
            raw = tile_cache.setdefault(
                tile_number, tile_bytes(vram, tile_number, obj_base=obj_base, bpp=bpp)
            )
            raw_tiles.append(raw)
        glyph = b"".join(raw_tiles)
        glyph_bytes_by_index[int(sprite["index"])] = glyph
        glyph_hash = sha256(glyph)
        duplicate_groups[glyph_hash].append(int(sprite["index"]))
        target_refs[glyph].append(
            {
                "kind": "sprite",
                "sprite_index": sprite["index"],
                "tile_start": f"0x{int(sprite['tile_start']):x}",
                "transform": "exact",
            }
        )
        variants = transformed_sprite_bytes(
            raw_tiles, int(sprite["width_tiles"]), int(sprite["height_tiles"])
        )
        variant_results: dict[str, dict[str, object]] = {}
        for name, value in [("exact", glyph), *variants.items()]:
            if value not in byte_match_cache:
                byte_match_cache[value] = match_record(rom, value)
            variant_results[name] = byte_match_cache[value]
            if name != "exact":
                target_refs[value].append(
                    {
                        "kind": "sprite",
                        "sprite_index": sprite["index"],
                        "tile_start": f"0x{int(sprite['tile_start']):x}",
                        "transform": name,
                    }
                )
        sprite_results.append(
            {
                "index": sprite["index"],
                "x": sprite["x"],
                "y": sprite["y"],
                "shape": sprite["shape"],
                "size": sprite["size"],
                "width_tiles": sprite["width_tiles"],
                "height_tiles": sprite["height_tiles"],
                "tile_start": f"0x{int(sprite['tile_start']):x}",
                "tile_count": len(numbers),
                "tile_sha256": [sha256(raw) for raw in raw_tiles],
                "glyph_nonzero_bytes": sum(value != 0 for value in glyph),
                "glyph_sha256": glyph_hash,
                "rom_matches": variant_results,
            }
        )

    unique_tiles = []
    for tile_number, raw in sorted(tile_cache.items()):
        if raw not in byte_match_cache:
            byte_match_cache[raw] = match_record(rom, raw)
        # Blank tiles have millions of irrelevant matches in both raw and
        # decompressed ROM data.  Keep them in the exact report as a negative
        # counterexample, but do not use them as compression needles.
        if any(raw):
            target_refs[raw].append(
                {
                    "kind": "tile",
                    "tile_number": f"0x{tile_number:x}",
                    "transform": "exact",
                }
            )
        unique_tiles.append(
            {
                "tile_number": f"0x{tile_number:x}",
                "nonzero_bytes": sum(value != 0 for value in raw),
                "distinct_bytes": len(set(raw)),
                "sha256": sha256(raw),
                "rom_matches": byte_match_cache[raw],
            }
        )

    exact_glyph_offsets = []
    for result in sprite_results:
        exact_glyph_offsets.extend(
            int(value, 16) for value in result["rom_matches"]["exact"]["offsets"]
        )
    duplicate_groups_out = [
        {"glyph_sha256": glyph, "sprite_indices": indices, "count": len(indices)}
        for glyph, indices in sorted(duplicate_groups.items())
        if len(indices) > 1
    ]
    report: dict[str, object] = {
        "rom": {"size": len(rom), "sha256": sha256(rom)},
        "capture": {
            "vram_size": len(vram),
            "oam_size": len(oam),
            "iwram_size": None if iwram is None else len(iwram),
            "max_y": max_y,
            "obj_base": f"0x{obj_base:x}",
            "bpp": bpp,
            "mapping": mapping,
            "active_sprite_count": len(sprites),
            "unique_tile_count": len(unique_tiles),
        },
        "font_table_candidate": gcd_stride(exact_glyph_offsets),
        "duplicate_glyph_groups": duplicate_groups_out,
        "sprites": sprite_results,
        "tiles": unique_tiles,
        "exact_match_summary": {
            "sprites_with_exact_match": sum(
                bool(result["rom_matches"]["exact"]["count"])
                for result in sprite_results
            ),
            "tiles_with_exact_match": sum(
                bool(result["rom_matches"]["count"]) for result in unique_tiles
            ),
            "nonblank_tiles_with_exact_match": sum(
                bool(result["rom_matches"]["count"]) and result["nonzero_bytes"] > 0
                for result in unique_tiles
            ),
            "transform_sprite_match_counts": {
                name: sum(
                    bool(result["rom_matches"][name]["count"])
                    for result in sprite_results
                )
                for name in ["hflip", "vflip", "rotate180", "nibble_swap"]
            },
            "transform_family": ["hflip", "vflip", "rotate180", "nibble_swap"],
        },
    }
    if iwram is None:
        report["runtime_ram_matches"] = {"skipped": True}
    else:
        sprite_ram_matches = []
        for result in sprite_results:
            record = match_record(iwram, glyph_bytes_by_index[int(result["index"])])
            sprite_ram_matches.append(
                {
                    "sprite_index": result["index"],
                    "glyph_sha256": result["glyph_sha256"],
                    "matches": add_bus_offsets(record, 0x03000000),
                }
            )
        tile_ram_matches = []
        for tile_number, raw in sorted(tile_cache.items()):
            record = match_record(iwram, raw)
            tile_ram_matches.append(
                {
                    "tile_number": f"0x{tile_number:x}",
                    "nonzero_bytes": sum(value != 0 for value in raw),
                    "distinct_bytes": len(set(raw)),
                    "sha256": sha256(raw),
                    "matches": add_bus_offsets(record, 0x03000000),
                }
            )
        oam_record = add_bus_offsets(match_record(iwram, oam), 0x03000000)
        report["runtime_ram_matches"] = {
            "region": "IWRAM",
            "base": "0x03000000",
            "size": len(iwram),
            "sha256": sha256(iwram),
            "oam_exact": oam_record,
            "sprites": sprite_ram_matches,
            "tiles": tile_ram_matches,
            "summary": {
                "oam_exact_count": oam_record["count"],
                "sprites_with_exact_match": sum(
                    item["matches"]["count"] > 0 for item in sprite_ram_matches
                ),
                "tiles_with_exact_match": sum(
                    item["matches"]["count"] > 0 for item in tile_ram_matches
                ),
                "nonblank_tiles_with_exact_match": sum(
                    item["matches"]["count"] > 0 and item["nonzero_bytes"] > 0
                    for item in tile_ram_matches
                ),
            },
        }
    if ewram is None:
        report["runtime_ewram_matches"] = {"skipped": True}
    else:
        sprite_ram_matches = []
        for result in sprite_results:
            record = match_record(ewram, glyph_bytes_by_index[int(result["index"])])
            sprite_ram_matches.append(
                {
                    "sprite_index": result["index"],
                    "glyph_sha256": result["glyph_sha256"],
                    "matches": add_bus_offsets(record, 0x02000000),
                }
            )
        tile_ram_matches = []
        for tile_number, raw in sorted(tile_cache.items()):
            record = match_record(ewram, raw)
            tile_ram_matches.append(
                {
                    "tile_number": f"0x{tile_number:x}",
                    "nonzero_bytes": sum(value != 0 for value in raw),
                    "distinct_bytes": len(set(raw)),
                    "sha256": sha256(raw),
                    "matches": add_bus_offsets(record, 0x02000000),
                }
            )
        oam_record = add_bus_offsets(match_record(ewram, oam), 0x02000000)
        report["runtime_ewram_matches"] = {
            "region": "EWRAM",
            "base": "0x02000000",
            "size": len(ewram),
            "sha256": sha256(ewram),
            "oam_exact": oam_record,
            "sprites": sprite_ram_matches,
            "tiles": tile_ram_matches,
            "summary": {
                "oam_exact_count": oam_record["count"],
                "sprites_with_exact_match": sum(
                    item["matches"]["count"] > 0 for item in sprite_ram_matches
                ),
                "tiles_with_exact_match": sum(
                    item["matches"]["count"] > 0 for item in tile_ram_matches
                ),
                "nonblank_tiles_with_exact_match": sum(
                    item["matches"]["count"] > 0 and item["nonzero_bytes"] > 0
                    for item in tile_ram_matches
                ),
            },
        }
    if skip_compression:
        report["compressed_scan"] = {"skipped": True}
    else:
        compression_targets = dict(target_refs)
        if compression_glyphs_only:
            compression_targets = {
                value: [ref for ref in refs if ref["kind"] == "sprite"]
                for value, refs in compression_targets.items()
            }
            compression_targets = {
                value: refs for value, refs in compression_targets.items() if refs
            }
        report["compressed_scan"] = scan_compressed(
            rom,
            compression_targets,
            alignment=compression_alignment,
            max_output=compression_max_output,
            max_candidates=compression_max_candidates,
        )
        report["compressed_scan"]["glyphs_only"] = compression_glyphs_only
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="raw GBA ROM or one-member ZIP")
    parser.add_argument("vram", type=Path)
    parser.add_argument("oam", type=Path)
    parser.add_argument(
        "--iwram",
        type=Path,
        help="optional IWRAM capture for runtime-source exact-match checks",
    )
    parser.add_argument(
        "--ewram",
        type=Path,
        help="optional EWRAM capture for runtime-source exact-match checks",
    )
    parser.add_argument("--max-y", type=int, default=160)
    parser.add_argument("--obj-base", type=lambda value: int(value, 0), default=0x10000)
    parser.add_argument("--bpp", type=int, choices=(4, 8), default=4)
    parser.add_argument("--mapping", choices=("1d", "2d"), default="1d")
    parser.add_argument("--compression-alignment", type=int, default=4)
    parser.add_argument("--compression-max-output", type=lambda value: int(value, 0), default=0x40000)
    parser.add_argument("--compression-max-candidates", type=int, default=4096)
    parser.add_argument(
        "--compression-glyphs-only",
        action="store_true",
        help="search only full active-sprite glyph variants, not individual tiles",
    )
    parser.add_argument("--skip-compression", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.compression_alignment <= 0:
        parser.error("--compression-alignment must be positive")
    report = analyze(
        load_rom(args.rom),
        args.vram.read_bytes(),
        args.oam.read_bytes(),
        None if args.iwram is None else args.iwram.read_bytes(),
        None if args.ewram is None else args.ewram.read_bytes(),
        max_y=args.max_y,
        obj_base=args.obj_base,
        bpp=args.bpp,
        mapping=args.mapping,
        compression_alignment=args.compression_alignment,
        compression_max_output=args.compression_max_output,
        compression_max_candidates=args.compression_max_candidates,
        compression_glyphs_only=args.compression_glyphs_only,
        skip_compression=args.skip_compression,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
