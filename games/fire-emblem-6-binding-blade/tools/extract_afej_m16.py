#!/usr/bin/env python3
"""Extract a bounded AFEJ compressed-text cohort into opaque tokens.

The worker at 0x0300323c is a small bitstream/tree expander copied to IWRAM
from the ROM boot image.  This module mirrors that worker literally: bits are
consumed LSB first, the tree node survives flag-byte boundaries, and the root
is restored only after a leaf is emitted.  It intentionally does not apply a
Unicode codepage or infer control-code meanings.

The generated JSONL is a local research corpus.  It contains code-unit bytes,
opaque marker bytes, addresses, and hashes, but no decoded Japanese text.  The
source ROM and corpus output are expected to remain under ignored paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROM_BASE = 0x08000000
ROM_SIZE = 0x00800000
EXPECTED_GAME_CODE = "AFEJ"
EXPECTED_ROM_SHA256 = (
    "e62288883544705b18f1a0753896fdd865a628fb4589135813b16a972a4c1557"
)

# The actual Thumb entry begins at 0x08013ad0.  0x08013acc is the requested
# loader region and contains two literal/data halfwords immediately before it.
LOADER_ENTRY = 0x08013AD0
POINTER_TABLE = 0x080F635C
TABLE_END_INDEX = 3342
TREE_BASE = 0x080F300C
ROOT_NODE = 0x080F6354
WORKER = 0x0300323C
BUFFER = 0x02029404
BUFFER_LENGTH = 0x400

COHORT_START = 3080
COHORT_COUNT = 16
RUNTIME_RECEIPT_INDEX = 3087
RUNTIME_RECEIPT_BUFFER_SHA256 = (
    "792667cef3da14699e533dd04573bb90c7f53a79546519d60a0c328023d5359f"
)

KNOWN_MARKERS = (0x00, 0x01, 0x04, 0xFF)


class AfejFormatError(ValueError):
    """Raised when the ROM does not match the proven M1.6 structure."""


@dataclass(frozen=True)
class Leaf:
    """One worker leaf and the bytes it writes to the output buffer."""

    output_offset: int
    node_address: int
    value: int
    output: bytes
    path_bits: tuple[int, ...]


@dataclass(frozen=True)
class DecodedRecord:
    index: int
    source_pointer: int
    source_end: int
    source_bytes: bytes
    output: bytes
    buffer: bytes
    leaves: tuple[Leaf, ...]

    @property
    def source_length(self) -> int:
        return len(self.source_bytes)

    @property
    def payload_length(self) -> int:
        return len(self.output)


class AfejRom:
    """Read-only ROM view with GBA-addressed accessors."""

    def __init__(self, data: bytes, *, strict_identity: bool = True) -> None:
        if len(data) != ROM_SIZE:
            raise AfejFormatError(
                f"expected {ROM_SIZE} byte AFEJ ROM, got {len(data)}"
            )
        if strict_identity:
            game_code = data[0xAC:0xB0].decode("ascii", errors="replace")
            digest = hashlib.sha256(data).hexdigest()
            if game_code != EXPECTED_GAME_CODE:
                raise AfejFormatError(f"expected game code AFEJ, got {game_code!r}")
            if digest != EXPECTED_ROM_SHA256:
                raise AfejFormatError(
                    "ROM SHA-256 does not match the reviewed AFEJ revision: "
                    f"{digest}"
                )
        self.data = data

    def _offset(self, address: int, length: int = 1) -> int:
        offset = address - ROM_BASE
        if offset < 0 or offset + length > len(self.data):
            raise AfejFormatError(f"ROM address out of range: 0x{address:08x}")
        return offset

    def read(self, address: int, length: int) -> bytes:
        offset = self._offset(address, length)
        return self.data[offset:offset + length]

    def u16(self, address: int) -> int:
        return int.from_bytes(self.read(address, 2), "little")

    def u32(self, address: int) -> int:
        return int.from_bytes(self.read(address, 4), "little")


def load_rom(path: Path, *, strict_identity: bool = True) -> AfejRom:
    return AfejRom(path.read_bytes(), strict_identity=strict_identity)


def is_rom_pointer(value: int) -> bool:
    return ROM_BASE <= value < ROM_BASE + ROM_SIZE


def table_entry(rom: AfejRom, index: int) -> int:
    if not 0 <= index < TABLE_END_INDEX:
        raise AfejFormatError(
            f"index {index} is outside proven table domain [0, {TABLE_END_INDEX})"
        )
    value = rom.u32(POINTER_TABLE + index * 4)
    if not is_rom_pointer(value):
        raise AfejFormatError(
            f"table entry {index} is not a ROM pointer: 0x{value:08x}"
        )
    return value


def prove_table_end(rom: AfejRom) -> int:
    """Confirm the static contiguous pointer run and its first non-pointer.

    The loader's `table + index * 4` instruction gives entry semantics.  This
    scan records the separately observed first non-ROM value so callers do not
    silently widen the table merely because a nearby word looks plausible.
    """

    index = 0
    while is_rom_pointer(rom.u32(POINTER_TABLE + index * 4)):
        index += 1
        if index > 10000:
            raise AfejFormatError("pointer-table scan exceeded safety bound")
    if index != TABLE_END_INDEX:
        raise AfejFormatError(
            f"pointer-table boundary drifted: expected {TABLE_END_INDEX}, got {index}"
        )
    return index


def leaf_output(value: int) -> bytes:
    """Mirror the worker's two stores and its one-byte terminator test."""

    low = value & 0xFF
    high = (value >> 8) & 0xFF
    if high:
        return bytes((low, high))
    return bytes((low,))


def decode_record(rom: AfejRom, index: int) -> DecodedRecord:
    """Decode one table entry using the proven IWRAM worker semantics."""

    source = table_entry(rom, index)
    cursor = source
    node = ROOT_NODE
    flag = 0
    bits_remaining = 0
    output = bytearray()
    leaves: list[Leaf] = []
    path_bits: list[int] = []
    source_limit = ROM_BASE + ROM_SIZE

    for _step in range(1_000_000):
        if bits_remaining == 0:
            if cursor >= source_limit:
                raise AfejFormatError(f"index {index} ran off the ROM bitstream")
            flag = rom.read(cursor, 1)[0]
            cursor += 1
            bits_remaining = 8

        bit = flag & 1
        flag >>= 1
        bits_remaining -= 1
        path_bits.append(bit)

        child_index = rom.u16(node + (2 if bit else 0))
        node = TREE_BASE + child_index * 4
        value = rom.u32(node)
        if not (value & 0x80000000):
            continue

        emitted = leaf_output(value)
        output_offset = len(output)
        output.extend(emitted)
        leaves.append(
            Leaf(
                output_offset=output_offset,
                node_address=node,
                value=value,
                output=emitted,
                path_bits=tuple(path_bits),
            )
        )
        path_bits.clear()
        node = ROOT_NODE

        # The worker tests r6,#0xff after the one-byte store.  A two-byte leaf
        # is never a terminator even when its low byte happens to be zero.
        if emitted == b"\x00":
            if len(output) > BUFFER_LENGTH:
                raise AfejFormatError(
                    f"index {index} output exceeds 0x400-byte EWRAM buffer"
                )
            source_bytes = rom.read(source, cursor - source)
            padded = output + bytes(BUFFER_LENGTH - len(output))
            return DecodedRecord(
                index=index,
                source_pointer=source,
                source_end=cursor,
                source_bytes=source_bytes,
                output=bytes(output),
                buffer=padded,
                leaves=tuple(leaves),
            )

        if len(output) >= BUFFER_LENGTH:
            raise AfejFormatError(f"index {index} has no terminator before buffer limit")

    raise AfejFormatError(f"index {index} exceeded decoder step bound")


def build_codebook(rom: AfejRom) -> dict[bytes, tuple[int, ...]]:
    """Build the inverse of the ROM tree and reject ambiguous leaf outputs."""

    codebook: dict[bytes, tuple[int, ...]] = {}
    stack: list[tuple[int, tuple[int, ...]]] = [(ROOT_NODE, ())]
    visited: set[tuple[int, tuple[int, ...]]] = set()

    while stack:
        node, path = stack.pop()
        visit_key = (node, path)
        if visit_key in visited:
            continue
        visited.add(visit_key)
        value = rom.u32(node)
        if value & 0x80000000:
            emitted = leaf_output(value)
            previous = codebook.get(emitted)
            if previous is not None:
                raise AfejFormatError(
                    "tree has duplicate output leaves; safe inverse encoding is"
                    f" ambiguous for {emitted.hex()}"
                )
            codebook[emitted] = path
            continue

        for bit in (0, 1):
            child_index = rom.u16(node + (2 if bit else 0))
            child = TREE_BASE + child_index * 4
            rom._offset(child, 4)
            stack.append((child, path + (bit,)))

        if len(visited) > 100_000:
            raise AfejFormatError("tree traversal exceeded safety bound")

    if not codebook:
        raise AfejFormatError("tree inverse is empty")
    return codebook


def encode_leaves(
    leaves: Iterable[Leaf], codebook: Mapping[bytes, tuple[int, ...]]
) -> bytes:
    """Encode leaf outputs through the inverse tree, packing bits LSB first."""

    bits: list[int] = []
    for leaf in leaves:
        try:
            bits.extend(codebook[leaf.output])
        except KeyError as exc:
            raise AfejFormatError(
                f"no inverse tree path for leaf {leaf.output.hex()}"
            ) from exc

    encoded = bytearray((len(bits) + 7) // 8)
    for bit_index, bit in enumerate(bits):
        encoded[bit_index // 8] |= bit << (bit_index % 8)
    return bytes(encoded)


def token_for_leaf(leaf: Leaf) -> dict[str, object]:
    emitted = leaf.output
    if emitted == b"\x00":
        kind = "terminator"
    elif len(emitted) == 1 and emitted[0] in KNOWN_MARKERS:
        kind = "opaque_control_byte"
    elif len(emitted) == 1:
        kind = "opaque_single_byte"
    else:
        kind = "code_unit"
    return {
        "offset": leaf.output_offset,
        "kind": kind,
        "bytes_hex": emitted.hex(),
        "tree_node": f"0x{leaf.node_address:08x}",
    }


def marker_offsets(output: bytes) -> dict[str, list[int]]:
    return {
        f"0x{marker:02x}": [
            offset for offset, value in enumerate(output) if value == marker
        ]
        for marker in KNOWN_MARKERS
    }


def record_to_json(
    rom: AfejRom,
    record: DecodedRecord,
    *,
    table_end: int,
    codebook: Mapping[bytes, tuple[int, ...]],
) -> dict[str, object]:
    source_hash = hashlib.sha256(record.source_bytes).hexdigest()
    output_hash = hashlib.sha256(record.buffer).hexdigest()
    encoded = encode_leaves(record.leaves, codebook)
    if encoded != record.source_bytes:
        raise AfejFormatError(
            f"index {record.index} decode->encode mismatch at "
            f"0x{record.source_pointer:08x}"
        )
    next_source = (
        table_entry(rom, record.index + 1)
        if record.index + 1 < table_end
        else None
    )
    if next_source is not None and record.source_end != next_source:
        raise AfejFormatError(
            f"index {record.index} source span ends at 0x{record.source_end:08x}, "
            f"not next table pointer 0x{next_source:08x}"
        )
    tokens = [token_for_leaf(leaf) for leaf in record.leaves]
    opaque = [
        token for token in tokens
        if token["kind"] in {"opaque_control_byte", "opaque_single_byte"}
    ]
    entry_address = POINTER_TABLE + record.index * 4
    return {
        "schema": "afej-opaque-text-corpus-v1",
        "game": "fire-emblem-6-binding-blade",
        "revision": EXPECTED_GAME_CODE,
        "string_id": f"afej.ptr.{record.index:04d}",
        "locale": "ja-opaque",
        "provenance": {
            "loader_entry": f"0x{LOADER_ENTRY:08x}",
            "pointer_table": f"0x{POINTER_TABLE:08x}",
            "table_domain": f"[0, {table_end})",
            "table_index": record.index,
            "table_entry": f"0x{entry_address:08x}",
            "source_pointer": f"0x{record.source_pointer:08x}",
            "source_end": f"0x{record.source_end:08x}",
            "next_source_pointer": (
                f"0x{next_source:08x}" if next_source is not None else None
            ),
            "source_span_matches_next_entry": next_source is None
            or record.source_end == next_source,
            "worker": f"0x{WORKER:08x}",
            "destination": f"0x{BUFFER:08x}",
        },
        "source_hash": source_hash,
        "output_hash": output_hash,
        "source_length": record.source_length,
        "payload_length": record.payload_length,
        "buffer_length": len(record.buffer),
        "control_marker_offsets": marker_offsets(record.output),
        "opaque_token_count": len(opaque),
        "tokens": tokens,
        "decode_encode_byte_identical": True,
        "decoder": "afej-tree-worker-v1",
        "rom_sha256": hashlib.sha256(rom.data).hexdigest(),
    }


def extract(
    rom: AfejRom,
    *,
    start: int = COHORT_START,
    count: int = COHORT_COUNT,
    runtime_receipt: Path | None = None,
) -> list[dict[str, object]]:
    if count <= 0:
        raise AfejFormatError("count must be positive")
    table_end = prove_table_end(rom)
    if start < 0 or start + count > table_end:
        raise AfejFormatError(
            f"cohort [{start}, {start + count}) exceeds table domain [0, {table_end})"
        )
    codebook = build_codebook(rom)
    records = [
        record_to_json(
            rom,
            decode_record(rom, index),
            table_end=table_end,
            codebook=codebook,
        )
        for index in range(start, start + count)
    ]

    if runtime_receipt is not None:
        receipt = json.loads(runtime_receipt.read_text(encoding="utf-8"))
        receipt_index = int(receipt.get("table_index", -1))
        if receipt_index != RUNTIME_RECEIPT_INDEX:
            raise AfejFormatError(
                f"runtime receipt index {receipt_index} is not {RUNTIME_RECEIPT_INDEX}"
            )
        match = next((row for row in records if row["provenance"]["table_index"] == receipt_index), None)
        if match is None:
            raise AfejFormatError("runtime receipt index is outside requested cohort")
        runtime_hash = receipt.get("buffer_sha256")
        if runtime_hash != match["output_hash"]:
            raise AfejFormatError(
                "runtime/static buffer SHA-256 mismatch: "
                f"{runtime_hash} != {match['output_hash']}"
            )
        if runtime_hash != RUNTIME_RECEIPT_BUFFER_SHA256:
            raise AfejFormatError("runtime receipt does not match reviewed M1.5 hash")
        match["runtime_buffer_hash_equal"] = True
    return records


def write_jsonl(path: Path, records: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True))
            handle.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    default_rom = Path(__file__).resolve().parents[1] / "roms/base/AFEJ.gba"
    default_output = Path(__file__).resolve().parents[1] / "research/afej-decoded.jsonl"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=default_rom)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--start", type=int, default=COHORT_START)
    parser.add_argument("--count", type=int, default=COHORT_COUNT)
    parser.add_argument("--runtime-receipt", type=Path)
    args = parser.parse_args(argv)

    try:
        rom = load_rom(args.rom)
        records = extract(
            rom,
            start=args.start,
            count=args.count,
            runtime_receipt=args.runtime_receipt,
        )
        write_jsonl(args.output, records)
    except (OSError, json.JSONDecodeError, AfejFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    equal = sum(1 for record in records if record.get("runtime_buffer_hash_equal"))
    print(f"rom={args.rom}")
    print(f"table_domain=[0, {TABLE_END_INDEX})")
    print(f"cohort_start={args.start}")
    print(f"cohort_count={len(records)}")
    print(f"decode_encode_byte_identical={len(records)}/{len(records)}")
    if args.runtime_receipt is not None:
        print(f"runtime_buffer_hash_equal={equal}/1")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
