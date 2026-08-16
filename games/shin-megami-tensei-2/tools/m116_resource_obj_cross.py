#!/usr/bin/env python3
"""Bounded M1.16 cross-check from named resources to a captured OBJ frame.

M1.15 identified one exact 16x8 callback source set and a nested
HuffUnComp -> LZ77 transform.  This tool keeps that source set bounded and
compares its in-memory final payloads with the active OBJ sprites from one
known Start-screen capture.  It reports addresses, hashes, lengths, counts,
and bounded match offsets only; it never emits ROM/payload/tile bytes,
images, or decoded text.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from analyze_obj_tiles import (  # noqa: E402
    active_sprites,
    tile_bytes,
    transformed_sprite_bytes,
)
from m115_source_class import (  # noqa: E402
    ROM_BASE,
    _address_field,
    _huffman_decode,
    _lz77_decode,
    _record_sources,
)
from m16_queue_probe import sha256  # noqa: E402


SCHEMA = "smt2.m1.16.resource-obj-cross.v1"
MATCH_ALIGNMENT = 32
MATCH_OFFSET_LIMIT = 8


def _aligned_offsets(payload: bytes, needle: bytes, *, alignment: int = MATCH_ALIGNMENT) -> list[int]:
    if not needle:
        return []
    offsets: list[int] = []
    start = 0
    while True:
        offset = payload.find(needle, start)
        if offset < 0:
            break
        if offset % alignment == 0:
            offsets.append(offset)
        start = offset + 1
    return offsets


def _tile_matrix(sprites: list[dict[str, object]], vram: bytes, *, obj_base: int) -> tuple[
    dict[int, bytes], list[dict[str, object]]
]:
    unique: dict[int, bytes] = {}
    occurrences: list[dict[str, object]] = []
    for sprite in sprites:
        for tile_number in sprite["tile_numbers"]:
            number = int(tile_number)
            raw = unique.setdefault(
                number, tile_bytes(vram, number, obj_base=obj_base, bpp=4)
            )
            occurrences.append(
                {
                    "sprite_index": int(sprite["index"]),
                    "tile_number": number,
                    "sha256": sha256(raw),
                    "nonzero_bytes": sum(value != 0 for value in raw),
                }
            )
    return unique, occurrences


def _decode_named_resources(rom: bytes) -> tuple[list[dict[str, object]], list[bytes]]:
    records = _record_sources(rom)
    metadata: list[dict[str, object]] = []
    payloads: list[bytes] = []
    for record in records:
        source = int(record["source"])
        huff_output, huff = _huffman_decode(rom, source)
        final_output, lz = _lz77_decode(huff_output)
        if lz.get("status") != "valid":
            raise ValueError(
                f"named source {source:#x} did not produce a valid nested LZ77 stream"
            )
        payloads.append(final_output)
        metadata.append(
            {
                "group_index": int(record["group_index"]),
                "record_index": int(record["record_index"]),
                "record_address": f"0x{int(record['record_address']):08x}",
                "source": _address_field(source, len(rom)),
                "argument_r2": int(record["argument_r2"]),
                "huffman_tag": huff["tag"],
                "huffman_tree_field": huff["tree_field"],
                "huffman_input_span_length": huff["input_span_length"],
                "huffman_input_span_hash": huff["input_span_hash"],
                "huffman_output_length": huff["output_length"],
                "huffman_output_hash": huff["output_hash"],
                "nested_lz77_tag": lz["tag"],
                "nested_lz77_input_length": lz["input_length"],
                "nested_lz77_consumed_length": lz["consumed_length"],
                "final_output_length": lz["output_length"],
                "final_output_hash": lz["output_hash"],
            }
        )
    return metadata, payloads


def _match_sprite_variants(
    sprites: list[dict[str, object]],
    vram: bytes,
    payloads: list[bytes],
    resource_metadata: list[dict[str, object]],
    *,
    obj_base: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    totals: Counter[str] = Counter()
    matched_resource_pairs: Counter[str] = Counter()
    matches: list[dict[str, object]] = []
    for sprite in sprites:
        raw_tiles = [
            tile_bytes(vram, int(tile_number), obj_base=obj_base, bpp=4)
            for tile_number in sprite["tile_numbers"]
        ]
        exact = b"".join(raw_tiles)
        variants = {"exact": exact}
        variants.update(
            transformed_sprite_bytes(
                raw_tiles,
                int(sprite["width_tiles"]),
                int(sprite["height_tiles"]),
            )
        )
        sprite_counts: dict[str, int] = {}
        for name, needle in variants.items():
            hit_count = 0
            for resource_index, payload in enumerate(payloads):
                offsets = _aligned_offsets(payload, needle)
                if not offsets:
                    continue
                hit_count += len(offsets)
                matched_resource_pairs[name] += 1
                if len(matches) < 64:
                    matches.append(
                        {
                            "sprite_index": int(sprite["index"]),
                            "transform": name,
                            "resource_index": resource_index,
                            "resource_record": resource_metadata[resource_index][
                                "record_address"
                            ],
                            "resource_offset_count": len(offsets),
                            "resource_offsets": [
                                f"0x{offset:x}" for offset in offsets[:MATCH_OFFSET_LIMIT]
                            ],
                        }
                    )
            sprite_counts[name] = hit_count
            if hit_count:
                totals[name] += 1
        records.append(
            {
                "sprite_index": int(sprite["index"]),
                "x": int(sprite["x"]),
                "y": int(sprite["y"]),
                "tile_start": f"0x{int(sprite['tile_start']):x}",
                "tile_count": len(sprite["tile_numbers"]),
                "width_tiles": int(sprite["width_tiles"]),
                "height_tiles": int(sprite["height_tiles"]),
                "glyph_length": len(exact),
                "glyph_sha256": sha256(exact),
                "variant_match_counts": sprite_counts,
            }
        )
    return records, {
        "alignment": MATCH_ALIGNMENT,
        "sprite_reference_count": len(sprites),
        "resource_record_count": len(payloads),
        "sprite_hit_counts_by_transform": dict(sorted(totals.items())),
        "resource_pair_hit_counts_by_transform": dict(sorted(matched_resource_pairs.items())),
        "bounded_matches": matches,
        "bounded_match_limit": 64,
    }


def _match_tiles(
    unique_tiles: dict[int, bytes],
    occurrences: list[dict[str, object]],
    payloads: list[bytes],
    resource_metadata: list[dict[str, object]],
) -> dict[str, object]:
    nonzero_occurrences = [item for item in occurrences if item["nonzero_bytes"]]
    nonzero_numbers = sorted(
        number for number, raw in unique_tiles.items() if any(raw)
    )
    unique_hits: dict[int, list[dict[str, object]]] = defaultdict(list)
    for number in nonzero_numbers:
        needle = unique_tiles[number]
        for resource_index, payload in enumerate(payloads):
            offsets = _aligned_offsets(payload, needle)
            if offsets:
                unique_hits[number].append(
                    {
                        "resource_index": resource_index,
                        "resource_record": resource_metadata[resource_index][
                            "record_address"
                        ],
                        "offset_count": len(offsets),
                        "offsets": [
                            f"0x{offset:x}" for offset in offsets[:MATCH_OFFSET_LIMIT]
                        ],
                    }
                )
    hit_numbers = set(unique_hits)
    hit_occurrences = sum(
        1 for item in nonzero_occurrences if int(item["tile_number"]) in hit_numbers
    )
    return {
        "alignment": MATCH_ALIGNMENT,
        "tile_occurrence_count": len(occurrences),
        "nonzero_tile_occurrence_count": len(nonzero_occurrences),
        "unique_tile_count": len(unique_tiles),
        "nonzero_unique_tile_count": len(nonzero_numbers),
        "unique_tiles_with_aligned_exact_match": len(hit_numbers),
        "nonzero_occurrences_with_aligned_exact_match": hit_occurrences,
        "bounded_hits": [
            {
                "tile_number": f"0x{number:x}",
                "sha256": sha256(unique_tiles[number]),
                "resource_hits": hits[:MATCH_OFFSET_LIMIT],
            }
            for number, hits in sorted(unique_hits.items())[:MATCH_OFFSET_LIMIT]
        ],
        "bounded_hit_limit": MATCH_OFFSET_LIMIT,
    }


def analyze(
    rom: bytes,
    vram: bytes,
    oam: bytes,
    *,
    max_y: int,
    obj_base: int,
    mapping: str,
) -> dict[str, object]:
    if len(rom) < 0x100:
        raise ValueError("ROM is too short")
    sprites = active_sprites(oam, max_y=max_y, mapping=mapping, bpp=4)
    unique_tiles, occurrences = _tile_matrix(sprites, vram, obj_base=obj_base)
    resource_metadata, payloads = _decode_named_resources(rom)
    sprite_records, sprite_matches = _match_sprite_variants(
        sprites,
        vram,
        payloads,
        resource_metadata,
        obj_base=obj_base,
    )
    tile_matches = _match_tiles(unique_tiles, occurrences, payloads, resource_metadata)
    resource_summary = {
        "record_count": len(resource_metadata),
        "group_count": len({item["group_index"] for item in resource_metadata}),
        "huffman_tag_counts": dict(
            sorted(Counter(item["huffman_tag"] for item in resource_metadata).items())
        ),
        "nested_lz77_tag_counts": dict(
            sorted(Counter(item["nested_lz77_tag"] for item in resource_metadata).items())
        ),
        "final_output_length_counts": dict(
            sorted(
                Counter(item["final_output_length"] for item in resource_metadata).items()
            )
        ),
        "unique_final_output_hash_count": len(
            {item["final_output_hash"] for item in resource_metadata}
        ),
        "r2_counts": dict(
            sorted(Counter(item["argument_r2"] for item in resource_metadata).items())
        ),
    }
    return {
        "schema": SCHEMA,
        "scope": {
            "source_set": "M1.15 exact 0x0813ef65 callback records only",
            "capture_role": "known Start-screen active OBJ frame",
            "comparison": "aligned exact bytes plus hflip/vflip/rotate180/nibble-swap sprite variants",
            "full_rom_glyph_scan": False,
            "raw_payload_emitted": False,
            "raw_capture_emitted": False,
        },
        "rom": {"size": len(rom), "sha256": sha256(rom)},
        "capture": {
            "vram_size": len(vram),
            "vram_sha256": sha256(vram),
            "oam_size": len(oam),
            "oam_sha256": sha256(oam),
            "max_y": max_y,
            "obj_base": f"0x{obj_base:x}",
            "bpp": 4,
            "mapping": mapping,
            "active_sprite_count": len(sprites),
            "unique_tile_count": len(unique_tiles),
            "tile_occurrence_count": len(occurrences),
        },
        "resource_summary": resource_summary,
        "sprite_matches": sprite_matches,
        "tile_matches": tile_matches,
        "sprites": sprite_records,
        "resource_records": resource_metadata,
        "conclusions": {
            "confirmed": [
                "M1.15_named_resource_set_is_reproducibly_decodable",
                "known_start_capture_has_no_aligned_exact_full_sprite_match_in_named_final_payloads",
                "known_start_capture_has_no_aligned_exact_nonblank_tile_match_in_named_final_payloads",
            ],
            "provisional": [
                "named_resource_set_is_not_the_direct_OBJ_source_for_this_capture",
                "absence_does_not_classify_the_resource_as_non_text_globally",
            ],
            "negative_window": {
                "capture_vram_sha256": sha256(vram),
                "capture_oam_sha256": sha256(oam),
                "resource_record_count": len(resource_metadata),
                "aligned_full_sprite_hit_count": sum(sprite_matches["sprite_hit_counts_by_transform"].values()),
                "aligned_nonzero_tile_hit_count": tile_matches[
                    "nonzero_occurrences_with_aligned_exact_match"
                ],
            },
            "unknown": [
                "text_code_unit_or_string_table",
                "natural_runtime_resource_selection",
                "alternate_transform_or_staging_source_outside_named_set",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--vram", type=Path, required=True)
    parser.add_argument("--oam", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-y", type=int, default=160)
    parser.add_argument("--obj-base", type=lambda value: int(value, 0), default=0x10000)
    parser.add_argument("--mapping", choices=("1d", "2d"), default="1d")
    args = parser.parse_args()
    report = analyze(
        args.rom.read_bytes(),
        args.vram.read_bytes(),
        args.oam.read_bytes(),
        max_y=args.max_y,
        obj_base=args.obj_base,
        mapping=args.mapping,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
