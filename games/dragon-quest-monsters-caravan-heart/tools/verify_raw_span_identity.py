#!/usr/bin/env python3
"""Verify clean A9HJ pointer-span raw identity without decoding source text.

This closes the token-preserving byte portion of the clean-ROM rebuild gate:
each ignored extractor row must describe the exact bytes at its pointer span,
and the explicit pair/alternate/single/control token stream must re-encode to
those bytes before a rebuilt copy is hashed.  It does not prove record
boundaries, control semantics, glyph identity, or a semantic translation
encoder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


EXPECTED_SIZE = 8 * 1024 * 1024
EXPECTED_CRC32 = "3c24abcc"
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"


def validate_rom(data: bytes) -> dict[str, object]:
    if len(data) != EXPECTED_SIZE:
        raise ValueError(f"unexpected ROM size: {len(data)}")
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"unexpected ROM SHA-256: {digest}")
    import zlib

    crc32 = f"{zlib.crc32(data) & 0xFFFFFFFF:08x}"
    if crc32 != EXPECTED_CRC32:
        raise ValueError(f"unexpected ROM CRC32: {crc32}")
    return {"size": len(data), "crc32": crc32, "sha256": digest}


def _offset(value: object, field: str) -> int:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a hex string")
    try:
        result = int(value, 0)
    except ValueError as error:
        raise ValueError(f"invalid {field}: {value!r}") from error
    if result < 0:
        raise ValueError(f"negative {field}: {value!r}")
    return result


def _byte(value: object, field: str) -> int:
    if not isinstance(value, int) or not 0 <= value <= 0xFF:
        raise ValueError(f"{field} must be an 8-bit integer")
    return value


def encode_tokens(tokens: object) -> bytes:
    """Re-encode the extractor's lossless token vocabulary to bytes."""

    if not isinstance(tokens, list):
        raise ValueError("decoded record is missing token list")
    output = bytearray()
    for index, token in enumerate(tokens):
        if not isinstance(token, dict):
            raise ValueError(f"token {index} is not an object")
        kind = token.get("kind")
        if kind in {"single-byte-candidate", "control-candidate"}:
            output.append(_byte(token.get("value"), f"token {index} value"))
        elif kind == "pair":
            output.extend(
                (
                    _byte(token.get("lead"), f"token {index} lead"),
                    _byte(token.get("trail"), f"token {index} trail"),
                )
            )
        elif kind == "alt-glyph":
            output.extend(
                (
                    _byte(token.get("lead"), f"token {index} lead"),
                    _byte(token.get("value"), f"token {index} value"),
                )
            )
        elif kind in {"pair-truncated", "alt-glyph-truncated"}:
            output.append(_byte(token.get("lead"), f"token {index} lead"))
        else:
            raise ValueError(f"unknown token kind: {kind!r}")
    return bytes(output)


def verify_records(data: bytes, records: list[dict[str, object]]) -> dict[str, object]:
    rebuilt = bytearray(data)
    seen_pointers: set[int] = set()
    span_digest = hashlib.sha256()
    mismatches = 0
    overlap_bytes = 0
    covered: set[int] = set()
    token_records = 0
    token_reencode_mismatches = 0
    token_reencode_bytes = 0
    for record in records:
        start = _offset(record.get("pointer_file"), "pointer_file")
        end = _offset(record.get("span_end_file"), "span_end_file")
        raw_hex = record.get("raw_hex")
        if not isinstance(raw_hex, str):
            raise ValueError("decoded record is missing raw_hex")
        try:
            raw = bytes.fromhex(raw_hex)
        except ValueError as error:
            raise ValueError(f"invalid raw_hex at 0x{start:06X}") from error
        if end < start or end - start != len(raw):
            raise ValueError(f"span length mismatch at 0x{start:06X}")
        if end > len(data):
            raise ValueError(f"span exceeds ROM at 0x{start:06X}")
        if data[start:end] != raw:
            mismatches += 1
        tokens = record.get("tokens")
        if tokens is not None:
            token_records += 1
            reencoded = encode_tokens(tokens)
            token_reencode_bytes += len(reencoded)
            if reencoded != raw:
                token_reencode_mismatches += 1
            replay = reencoded
        else:
            # Small unit-test fixtures may exercise the raw-span layer alone;
            # clean extractor output is required to carry tokens.
            replay = raw
        for offset, value in enumerate(raw, start):
            if offset in covered:
                overlap_bytes += 1
            covered.add(offset)
            rebuilt[offset] = replay[offset - start]
        seen_pointers.add(start)
        span_digest.update(start.to_bytes(4, "little"))
        span_digest.update(end.to_bytes(4, "little"))
        span_digest.update(raw)
    if mismatches:
        raise ValueError(f"raw span mismatches: {mismatches}")
    rebuilt_sha256 = hashlib.sha256(rebuilt).hexdigest()
    clean_sha256 = hashlib.sha256(data).hexdigest()
    if rebuilt_sha256 != clean_sha256:
        raise ValueError("raw-span rebuild changed the clean ROM")
    if token_reencode_mismatches:
        raise ValueError(f"token re-encode mismatches: {token_reencode_mismatches}")
    return {
        "record_count": len(records),
        "unique_pointer_count": len(seen_pointers),
        "covered_byte_count": len(covered),
        "overlap_byte_count": overlap_bytes,
        "raw_span_mismatches": 0,
        "raw_span_digest": span_digest.hexdigest(),
        "token_record_count": token_records,
        "token_reencode_bytes": token_reencode_bytes,
        "token_reencode_mismatches": token_reencode_mismatches,
        "token_encoder": "proven" if token_records == len(records) else "not-run",
        "clean_sha256": clean_sha256,
        "rebuilt_sha256": rebuilt_sha256,
        "changed_byte_count": 0,
        "semantic_encoder": "not-proven; token-preserving only",
        "runtime_qa": "not-run",
    }


def load_records(path: pathlib.Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON at line {line_number}") from error
        if not isinstance(record, dict):
            raise ValueError(f"record at line {line_number} is not an object")
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=pathlib.Path)
    parser.add_argument("decoded", type=pathlib.Path)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    try:
        data = args.rom.read_bytes()
        identity = validate_rom(data)
        report = {"rom": identity, **verify_records(data, load_records(args.decoded))}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError) as error:
        print(f"verify_raw_span_identity: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
