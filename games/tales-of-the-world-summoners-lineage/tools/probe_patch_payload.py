#!/usr/bin/env python3
"""Summarize an external IPS patch's appended payload without exporting text.

The existing v0.20 patch grows the ROM.  This probe follows valid GBA LZ77
blocks from the appended start and reports boundaries, sizes, and aggregate
word statistics only; the patch itself remains a local reference artifact.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

from probe_resource_pointer_table import lz77


def probe(path: Path, start: int, end: int | None) -> dict[str, object]:
    data = path.read_bytes()
    limit = len(data) if end is None else min(end, len(data))
    position = start
    blocks: list[tuple[int, int, int]] = []
    failure: dict[str, object] | None = None

    while position + 4 <= limit and data[position] == 0x10:
        decoded, next_position, error = lz77(data, position)
        if error or decoded is None or next_position is None:
            failure = {"offset": f"0x{position:x}", "error": error}
            break
        blocks.append((position, len(decoded), next_position - position))
        aligned = (next_position + 3) & ~3
        if aligned < limit and data[aligned] == 0x10 and all(
            value == 0 for value in data[next_position:aligned]
        ):
            position = aligned
        else:
            position = next_position

    word_counts = collections.Counter(
        int.from_bytes(data[offset : offset + 2], "little")
        for offset in range(start, limit - 1, 2)
    )
    return {
        "rom_path": str(path),
        "region": [f"0x{start:x}", f"0x{limit:x}"],
        "sequential_lz77_blocks": len(blocks),
        "sequential_lz77_end": f"0x{position:x}",
        "failure": failure,
        "decoded_size_counts": dict(
            sorted(collections.Counter(size for _, size, _ in blocks).items())
        ),
        "compressed_size_counts": dict(
            sorted(collections.Counter(size for _, _, size in blocks).items())
        ),
        "first_blocks": [
            {
                "offset": f"0x{offset:x}",
                "decoded_size": decoded_size,
                "compressed_size": compressed_size,
            }
            for offset, decoded_size, compressed_size in blocks[:20]
        ],
        "last_blocks": [
            {
                "offset": f"0x{offset:x}",
                "decoded_size": decoded_size,
                "compressed_size": compressed_size,
            }
            for offset, decoded_size, compressed_size in blocks[-20:]
        ],
        "most_common_16_bit_values": [
            {"value": f"0x{value:04x}", "count": count}
            for value, count in word_counts.most_common(20)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--start", type=lambda value: int(value, 0), default=0x800000)
    parser.add_argument("--end", type=lambda value: int(value, 0))
    args = parser.parse_args()
    json.dump(probe(args.rom, args.start, args.end), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
