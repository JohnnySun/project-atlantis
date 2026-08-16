#!/usr/bin/env python3
"""Cross-check a bounded AFEJ codepage candidate without emitting Japanese.

The M1.19 natural receipt supplies opaque input-code-unit hashes, map indices
and glyph-field values.  This tool cross-checks those facts against the ROM
map and the ignored M1.6 corpus, then measures whether strict Shift-JIS can
decode the bounded map/corpus.  The result remains a *candidate*: it never
writes source bytes or decoded text into the report and does not create a
translation ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


ROM_BASE = 0x08000000
MAP_BASE = 0x08691644
MAP_ENTRY_COUNT = 121
RUNTIME_MAP_INDEX_LIMIT = 32


def _map_pairs(rom: bytes) -> list[bytes]:
    start = MAP_BASE - ROM_BASE
    pairs = [rom[start + index * 2:start + index * 2 + 2] for index in range(MAP_ENTRY_COUNT)]
    if any(len(pair) != 2 for pair in pairs):
        raise ValueError("AFEJ map span is truncated")
    return pairs


def _hex_bytes(value: Any) -> bytes:
    if not isinstance(value, str) or len(value) % 2 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("expected bounded hexadecimal byte token")
    return bytes.fromhex(value)


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _map_codepage_candidate(pairs: list[bytes]) -> dict[str, object]:
    decoded: list[str] = []
    invalid_indices: list[int] = []
    for index, pair in enumerate(pairs):
        try:
            decoded.append(pair.decode("shift_jis"))
        except UnicodeDecodeError:
            invalid_indices.append(index)
    decoded_text = "".join(decoded)
    return {
        "encoding_tested": "shift_jis",
        "entry_count": len(pairs),
        "strictly_decodable_count": len(decoded),
        "invalid_entry_count": len(invalid_indices),
        "invalid_entry_indices_sha256": _hash_bytes(
            json.dumps(invalid_indices, separators=(",", ":")).encode("ascii")
        ),
        "decoded_map_utf8_sha256": _hash_bytes(decoded_text.encode("utf-8")),
        "semantic_name_assigned": False,
        "candidate_only": True,
        "raw_bytes_emitted": False,
    }


def _corpus_record(corpus_path: Path, table_index: int) -> dict[str, Any]:
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        provenance = record.get("provenance", {})
        if provenance.get("table_index") == table_index:
            return record
    raise ValueError(f"corpus record not found: {table_index}")


def _corpus_candidate(record: dict[str, Any]) -> dict[str, object]:
    code_units: list[bytes] = []
    opaque_count = 0
    for token in record.get("tokens", []):
        if not isinstance(token, dict):
            continue
        if token.get("kind") == "code_unit":
            code_units.append(_hex_bytes(token.get("bytes_hex")))
        elif token.get("kind") == "opaque_control_byte":
            opaque_count += 1
    payload = b"".join(code_units)
    code_unit_hashes = [_hash_bytes(unit) for unit in code_units]
    try:
        decoded = payload.decode("shift_jis")
        invalid = False
    except UnicodeDecodeError:
        decoded = ""
        invalid = True
    return {
        "table_index": record.get("provenance", {}).get("table_index"),
        "string_id": record.get("string_id"),
        "code_unit_count": len(code_units),
        "opaque_control_count": opaque_count,
        "code_unit_bytes_sha256": _hash_bytes(payload),
        "code_unit_hashes": code_unit_hashes,
        "strict_shift_jis_decode": not invalid,
        "decoded_utf8_sha256": _hash_bytes(decoded.encode("utf-8")) if not invalid else None,
        "decoded_character_count": len(decoded) if not invalid else None,
        "candidate_only": True,
        "raw_bytes_emitted": False,
    }


def _runtime_candidate(runtime_path: Path, pairs: list[bytes], corpus: dict[str, object]) -> dict[str, object]:
    report = json.loads(runtime_path.read_text(encoding="utf-8"))
    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("runtime report has no runtime object")
    lookups = runtime.get("lookup_receipts", [])
    fields = runtime.get("glyph_field_receipts", [])
    if not isinstance(lookups, list):
        lookups = []
    if not isinstance(fields, list):
        fields = []

    lookup_hashes: list[str] = []
    map_matches = 0
    for row in lookups[:RUNTIME_MAP_INDEX_LIMIT]:
        if not isinstance(row, dict):
            continue
        input_row = row.get("input", {})
        if not isinstance(input_row, dict):
            continue
        try:
            unit = _hex_bytes(input_row.get("input_code_unit"))
            map_index = int(row["map_index"])
            glyph_index = int(row["glyph_index"])
        except (KeyError, TypeError, ValueError):
            continue
        lookup_hashes.append(_hash_bytes(unit))
        if 0 <= map_index < len(pairs) and pairs[map_index] == unit and glyph_index == map_index:
            map_matches += 1

    field_hashes: list[str] = []
    field_map_matches = 0
    for row in fields[:RUNTIME_MAP_INDEX_LIMIT]:
        if not isinstance(row, dict):
            continue
        input_row = row.get("input_lookup", {})
        if not isinstance(input_row, dict):
            continue
        try:
            unit = _hex_bytes(input_row.get("input_code_unit"))
            map_index = int(input_row["map_index"] if "map_index" in input_row else row["glyph_index"])
            glyph_index = int(row["glyph_index"])
        except (KeyError, TypeError, ValueError):
            continue
        field_hashes.append(_hash_bytes(unit))
        if 0 <= map_index < len(pairs) and pairs[map_index] == unit and glyph_index == map_index:
            field_map_matches += 1

    corpus_prefix = corpus.get("code_unit_hashes")
    prefix_bytes = json.dumps(lookup_hashes, separators=(",", ":")).encode("ascii")
    field_bytes = json.dumps(field_hashes, separators=(",", ":")).encode("ascii")
    prefix_match_count = 0
    if isinstance(corpus_prefix, list):
        for runtime_hash, corpus_hash in zip(lookup_hashes, corpus_prefix):
            if runtime_hash != corpus_hash:
                break
            prefix_match_count += 1
    return {
        "lookup_receipt_count_bounded": len(lookup_hashes),
        "glyph_field_receipt_count_bounded": len(field_hashes),
        "lookup_map_pair_and_glyph_equal_count": map_matches,
        "glyph_field_map_pair_and_glyph_equal_count": field_map_matches,
        "lookup_input_hash_sequence_sha256": _hash_bytes(prefix_bytes),
        "glyph_field_input_hash_sequence_sha256": _hash_bytes(field_bytes),
        "corpus_record_code_unit_hash_sequence_sha256": _hash_bytes(
            json.dumps(corpus_prefix, separators=(",", ":")).encode("ascii")
        ) if isinstance(corpus_prefix, list) else None,
        "natural_runtime_map_correspondence": bool(lookup_hashes and map_matches == len(lookup_hashes)),
        "natural_runtime_glyph_correspondence": bool(field_hashes and field_map_matches == len(field_hashes)),
        "natural_runtime_corpus_prefix_match_count": prefix_match_count,
        "natural_runtime_corpus_prefix_observed": prefix_match_count >= 4,
        "candidate_only": True,
        "raw_bytes_emitted": False,
    }


def build_report(
    rom_path: Path,
    corpus_path: Path,
    runtime_path: Optional[Path] = None,
    *,
    table_index: int = 3087,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    if len(rom) < MAP_BASE - ROM_BASE + MAP_ENTRY_COUNT * 2:
        raise ValueError("ROM is too short for the reviewed map span")
    pairs = _map_pairs(rom)
    corpus_record = _corpus_record(corpus_path, table_index)
    corpus_candidate = _corpus_candidate(corpus_record)
    result: dict[str, object] = {
        "schema": "afej-m122-codepage-candidate-v1",
        "rom": {
            "game_code": rom[0xAC:0xB0].decode("ascii", errors="replace"),
            "size": len(rom),
            "sha256": hashlib.sha256(rom).hexdigest(),
        },
        "map": {
            "base": f"0x{MAP_BASE:08x}",
            "entry_count": len(pairs),
            "pair_span_sha256": _hash_bytes(b"".join(pairs)),
            "codepage_candidate": _map_codepage_candidate(pairs),
        },
        "corpus": corpus_candidate,
        "runtime_input": None,
        "runtime": None,
        "status": {
            "codepage": "shift_jis_candidate_with_runtime_map_correspondence",
            "unicode_identity_confirmed": False,
            "scene_or_content_category": "natural_start_a_context_unconfirmed",
            "translation_ready": False,
            "raw_bytes_emitted": False,
        },
        "raw_bytes_emitted": False,
    }
    if runtime_path is not None:
        result["runtime_input"] = str(runtime_path)
        result["runtime"] = _runtime_candidate(runtime_path, pairs, corpus_candidate)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--runtime-report", type=Path)
    parser.add_argument("--table-index", type=int, default=3087)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.rom, args.corpus, args.runtime_report, table_index=args.table_index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
