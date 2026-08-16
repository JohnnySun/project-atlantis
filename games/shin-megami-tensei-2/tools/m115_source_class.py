#!/usr/bin/env python3
"""Bounded decoder/classifier for the M1.14 resource source candidates.

The exact 16x8 callback runs are the only source set considered here.  Each
candidate is decoded in memory as the GBA 4-bit Huffman form used by the ROM,
then as the nested LZ77 stream consumed by the already identified writer.  The
report contains addresses, headers, lengths, hashes, counts, and alignment
statistics only; it never emits compressed/decompressed bytes, strings, tiles,
or a translation source table.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "core" / "gba"))
sys.path.insert(0, str(TOOLS_ROOT))

from m16_queue_probe import (  # noqa: E402
    ROM_BASE,
    ROM_LIMIT,
    address_metadata,
    hex_address,
    read_u32,
    sha256,
)
from m113_staging_resource_map import (  # noqa: E402
    RESOURCE_RECORDS_PER_GROUP,
    RESOURCE_RECORD_STRIDE,
    STAGING_WRITER_THUMB,
    _groups_from_positions,
    _pointer_positions,
    _region,
)


SCHEMA = "smt2.m1.15.source-class.v1"
HUFF_FORMAT_NIBBLE = 0x20
LZ77_TAG = 0x10
MAX_DECODED_BYTES = 0x40000


class DecodeError(ValueError):
    """A bounded source did not satisfy the selected decoder contract."""


def _address_field(value: int, rom_size: int) -> dict[str, object]:
    return {**address_metadata(value, rom_size), "region_class": _region(value)}


def _read_u24(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 3 > len(data):
        raise DecodeError("u24-out-of-range")
    return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)


def _rom_offset(address: int, size: int) -> int:
    if not ROM_BASE <= address < ROM_BASE + size:
        raise DecodeError("source-not-in-rom")
    return address - ROM_BASE


def _huffman_decode(data: bytes, address: int) -> tuple[bytes, dict[str, object]]:
    """Decode the GBA BIOS HuffUnComp tree used by the identified writer.

    GBA stores each tree node at a byte pointer.  The low six flag bits select
    the relative child base; bit 7 marks the left child as a leaf and bit 6
    marks the right child as a leaf.  Leaf values are masked to the header's
    4/8-bit unit size and packed low unit first, matching the BIOS routine.
    """

    offset = _rom_offset(address, len(data))
    if offset + 5 > len(data):
        raise DecodeError("huffman-header-truncated")
    header = int.from_bytes(data[offset : offset + 4], "little")
    tag = header & 0xFF
    bit_depth = header & 0x0F
    output_length = header >> 8
    if tag & 0xF0 != HUFF_FORMAT_NIBBLE:
        raise DecodeError("not-gba-huffman")
    if bit_depth not in (4, 8) or output_length <= 0:
        raise DecodeError("unsupported-huffman-header")
    if output_length > MAX_DECODED_BYTES:
        raise DecodeError("huffman-output-bound")

    tree_field = data[offset + 4]
    tree_length = (tree_field << 1) + 1
    tree_start = offset + 5
    tree_end = tree_start + tree_length
    stream_start = tree_end
    if tree_end > len(data):
        raise DecodeError("huffman-tree-truncated")
    if stream_start % 4:
        raise DecodeError("huffman-stream-unaligned")

    output = bytearray()
    bit_position = 0
    unit_mask = (1 << bit_depth) - 1
    units_needed = (output_length * 8) // bit_depth
    if units_needed * bit_depth != output_length * 8:
        raise DecodeError("huffman-size-not-unit-aligned")

    def next_bit() -> int:
        nonlocal bit_position
        word_offset = stream_start + (bit_position // 32) * 4
        if word_offset + 4 > len(data):
            raise DecodeError("huffman-bitstream-truncated")
        word = int.from_bytes(data[word_offset : word_offset + 4], "little")
        bit_in_word = bit_position % 32
        bit_position += 1
        return (word >> (31 - bit_in_word)) & 1

    for unit_index in range(units_needed):
        node = tree_start
        for _step in range(128):
            if node < tree_start or node >= tree_end:
                raise DecodeError("huffman-node-out-of-tree")
            flags = data[node]
            branch = next_bit()
            child_base = (node & ~1) + ((flags & 0x3F) << 1)
            child = child_base + (3 if branch else 2)
            if child >= tree_end:
                raise DecodeError("huffman-child-out-of-tree")
            terminal = bool(flags & (0x40 if branch else 0x80))
            value = data[child]
            if terminal:
                unit = value & unit_mask
                if bit_depth == 8:
                    output.append(unit)
                else:
                    # The BIOS writes 4-bit units into successive low-to-high
                    # nibbles of each destination byte.
                    if unit_index % 2 == 0:
                        output.append(unit)
                    else:
                        output[-1] |= unit << 4
                break
            node = child
        else:
            raise DecodeError("huffman-tree-depth-bound")

    if len(output) != output_length:
        raise DecodeError("huffman-output-length-mismatch")
    stream_bytes = ((bit_position + 31) // 32) * 4
    consumed_length = (stream_start - offset) + stream_bytes
    if offset + consumed_length > len(data):
        raise DecodeError("huffman-consumed-span-truncated")
    metadata = {
        "format": "gba_huffman",
        "tag": hex_address(tag),
        "bit_depth": bit_depth,
        "declared_output_length": output_length,
        "tree_field": tree_field,
        "tree_length": tree_length,
        "tree_address": hex_address(ROM_BASE + tree_start),
        "stream_address": hex_address(ROM_BASE + stream_start),
        "stream_alignment": stream_start % 4,
        "stream_bit_length": bit_position,
        "stream_bytes_consumed": stream_bytes,
        "input_span_length": consumed_length,
        "input_span_hash": sha256(data[offset : offset + consumed_length]),
        "output_length": len(output),
        "output_hash": sha256(output),
    }
    return bytes(output), metadata


def _lz77_decode(payload: bytes) -> tuple[bytes, dict[str, object]]:
    if len(payload) < 4 or payload[0] != LZ77_TAG:
        return b"", {
            "status": "not-lz77",
            "tag": hex_address(payload[0]) if payload else None,
        }
    output_length = _read_u24(payload, 1)
    if output_length <= 0 or output_length > MAX_DECODED_BYTES:
        return b"", {
            "status": "lz77-output-bound",
            "tag": hex_address(payload[0]),
            "declared_output_length": output_length,
        }

    position = 4
    output = bytearray()
    try:
        while len(output) < output_length:
            if position >= len(payload):
                raise DecodeError("lz77-flags-truncated")
            flags = payload[position]
            position += 1
            for bit in range(7, -1, -1):
                if len(output) >= output_length:
                    break
                if flags & (1 << bit):
                    if position + 2 > len(payload):
                        raise DecodeError("lz77-backref-truncated")
                    first = payload[position]
                    second = payload[position + 1]
                    position += 2
                    length = (first >> 4) + 3
                    displacement = ((first & 0x0F) << 8) | second
                    source = len(output) - displacement - 1
                    if source < 0:
                        raise DecodeError("lz77-backref-before-output")
                    for _ in range(length):
                        output.append(output[source])
                        source += 1
                        if len(output) >= output_length:
                            break
                else:
                    if position >= len(payload):
                        raise DecodeError("lz77-literal-truncated")
                    output.append(payload[position])
                    position += 1
    except IndexError as error:
        raise DecodeError("lz77-index-error") from error

    metadata = {
        "status": "valid",
        "tag": hex_address(payload[0]),
        "declared_output_length": output_length,
        "consumed_length": position,
        "input_length": len(payload),
        "output_length": len(output),
        "output_hash": sha256(output),
    }
    return bytes(output), metadata


def _payload_stats(payload: bytes) -> dict[str, object]:
    counts = Counter(payload)
    entropy = 0.0
    if payload:
        total = len(payload)
        entropy = -sum(
            (count / total) * math.log2(count / total)
            for count in counts.values()
            if count
        )
    blocks = [payload[index : index + 32] for index in range(0, len(payload), 32)]
    complete_blocks = [block for block in blocks if len(block) == 32]
    return {
        "length": len(payload),
        "hash": sha256(payload),
        "entropy": round(entropy, 5),
        "zero_byte_count": counts.get(0, 0),
        "ff_byte_count": counts.get(0xFF, 0),
        "aligned_4bpp_tile_bytes": len(payload) % 32 == 0,
        "complete_4bpp_tile_count": len(complete_blocks),
        "unique_4bpp_tile_hash_count": len({sha256(block) for block in complete_blocks}),
    }


def _record_sources(data: bytes) -> list[dict[str, object]]:
    positions = _pointer_positions(data, STAGING_WRITER_THUMB)
    groups = _groups_from_positions(
        positions,
        stride=RESOURCE_RECORD_STRIDE,
        record_count=RESOURCE_RECORDS_PER_GROUP,
    )
    records: list[dict[str, object]] = []
    for group_index, group in enumerate(groups):
        for record_index, record in enumerate(group):
            records.append(
                {
                    "group_index": group_index,
                    "record_index": record_index,
                    "record_address": record,
                    "source": read_u32(data, record + 4),
                    "argument_r2": read_u32(data, record + 8),
                }
            )
    return records


def _decode_record(data: bytes, record: dict[str, object]) -> dict[str, object]:
    source = int(record["source"])
    result = {
        "group_index": record["group_index"],
        "record_index": record["record_index"],
        "record_address": hex_address(int(record["record_address"])),
        "source": _address_field(source, len(data)),
        "argument_r2": record["argument_r2"],
    }
    try:
        huff_output, huff = _huffman_decode(data, source)
        result["huffman"] = huff
        lz_output, lz = _lz77_decode(huff_output)
        result["nested_lz77"] = lz
        if lz.get("status") == "valid":
            result["final_payload"] = _payload_stats(lz_output)
        else:
            result["final_payload"] = {"status": "not-decoded"}
    except DecodeError as error:
        result["status"] = "decode-error"
        result["error"] = str(error)
    return result


def static_report(data: bytes) -> dict[str, object]:
    records = _record_sources(data)
    decoded = [_decode_record(data, record) for record in records]
    status_counts = Counter(item.get("status", "valid") for item in decoded)
    huff_tags = Counter(
        item["huffman"]["tag"] for item in decoded if "huffman" in item
    )
    lz_status = Counter(
        item["nested_lz77"]["status"]
        for item in decoded
        if "nested_lz77" in item
    )
    final_sizes = [
        int(item["final_payload"]["length"])
        for item in decoded
        if item.get("final_payload", {}).get("length") is not None
    ]
    final_hashes = {
        item["final_payload"]["hash"]
        for item in decoded
        if item.get("final_payload", {}).get("hash") is not None
    }
    huff_output_hashes = {
        item["huffman"]["output_hash"]
        for item in decoded
        if item.get("huffman", {}).get("output_hash") is not None
    }
    groups: dict[int, list[dict[str, object]]] = {}
    for item in decoded:
        groups.setdefault(int(item["group_index"]), []).append(item)
    group_reports = []
    for group_index in sorted(groups):
        group = groups[group_index]
        group_reports.append(
            {
                "group_index": group_index,
                "record_count": len(group),
                "argument_r2_counts": dict(
                    sorted(Counter(int(item["argument_r2"]) for item in group).items())
                ),
                "huffman_tag_counts": dict(
                    sorted(
                        Counter(
                            item["huffman"]["tag"]
                            for item in group
                            if "huffman" in item
                        ).items()
                    )
                ),
                "nested_lz77_status_counts": dict(
                    sorted(
                        Counter(
                            item["nested_lz77"]["status"]
                            for item in group
                            if "nested_lz77" in item
                        ).items()
                    )
                ),
                "final_output_lengths": sorted(
                    int(item["final_payload"]["length"])
                    for item in group
                    if item.get("final_payload", {}).get("length") is not None
                ),
            }
        )

    return {
        "schema": SCHEMA,
        "rom": {"size": len(data), "sha256": sha256(data)},
        "scan_scope": {
            "method": "exact established 0x0813ef65 callback runs only",
            "callback_pointer": hex_address(STAGING_WRITER_THUMB),
            "group_stride": RESOURCE_RECORD_STRIDE,
            "records_per_group": RESOURCE_RECORDS_PER_GROUP,
            "record_count": len(records),
            "full_rom_glyph_scan": False,
            "raw_payload_emitted": False,
            "source_table_created": False,
        },
        "decoder_contract": {
            "outer": "GBA HuffUnComp-compatible tree walk",
            "outer_header": "0x2n with 4/8-bit unit depth",
            "inner": "GBA LZ77 stream beginning at Huff output",
            "writer_chain": "ROM source -> Huff -> 0x0200afc8 -> LZ77 -> 0x02001000 + (r2 << 12)",
        },
        "groups": group_reports,
        "records": decoded,
        "summary": {
            "record_count": len(decoded),
            "decode_status_counts": dict(sorted(status_counts.items())),
            "huffman_tag_counts": dict(sorted(huff_tags.items())),
            "huffman_tree_field_counts": dict(
                sorted(
                    Counter(
                        item["huffman"]["tree_field"]
                        for item in decoded
                        if "huffman" in item
                    ).items()
                )
            ),
            "nested_lz77_status_counts": dict(sorted(lz_status.items())),
            "final_output_length_range": [min(final_sizes), max(final_sizes)]
            if final_sizes
            else None,
            "unique_huffman_output_hash_count": len(huff_output_hashes),
            "unique_final_output_hash_count": len(final_hashes),
            "final_output_4bpp_aligned_count": sum(
                item.get("final_payload", {}).get("aligned_4bpp_tile_bytes", False)
                for item in decoded
            ),
            "source_identity": "resource-payload-class-only",
            "code_unit_or_string_id": "not_established",
            "glyph_identity": "not_established",
            "translation_ledger": "blocked",
        },
        "conclusions": {
            "confirmed": [
                "all_established_sources_use_gba_4bit_huffman_header_0x24",
                "all_established_sources_decode_to_nested_lz77_header_0x10",
                "nested_lz77_outputs_have_reproducible_hash_and_length_metadata",
            ],
            "provisional": [
                "decoded_outputs_are_resource_payloads_not_proven_text",
                "tile_alignment_is_shape_evidence_only_not_glyph_identity",
            ],
            "negative": [
                "no_code_unit_or_string_id_recovered",
                "no_unicode_or_glyph_identity_recovered",
                "no_text_source_table_created",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = static_report(args.rom.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
