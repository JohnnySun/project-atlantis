#!/usr/bin/env python3
"""Apply a bounded fixed-slot patch to one reviewed B3EJ pointer pool.

The reviewed event-system and story-event pools are intentionally bounded.
The patcher validates source hashes, strict Shift-JIS/codepage coverage,
control-byte contracts and NUL spans, and never relocates a record or emits
source text.  Story-event targets can additionally be checked against the
existing four-pool custom-glyph raw-unit map.
Patched ROMs and metadata are caller-owned ignored outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import font_coverage  # noqa: E402
import table_b_common as common  # noqa: E402


ROM_BASE = common.ROM_BASE
POOL_SPECS = {
    "event-system": {"file_offset": 0x0D4D00, "entry_count": 28},
    "story-event": {"file_offset": 0x0CDB64, "entry_count": 33},
}
ENTRY_PATTERN = re.compile(r"^b3ej:(event-system|story-event):(\d{3})$")


def fixed_slot_replacement(original_payload: bytes, encoded_target: bytes) -> bytes:
    if len(encoded_target) > len(original_payload):
        raise ValueError(
            f"translated payload is {len(encoded_target)} bytes, "
            f"original slot is {len(original_payload)} bytes"
        )
    # The writable span includes the original payload and its NUL terminator.
    return encoded_target + b"\0" + b"\0" * (len(original_payload) - len(encoded_target))


def parse_pool_entry(string_id: object, pool: str) -> int:
    match = ENTRY_PATTERN.match(str(string_id))
    if match is None or match.group(1) != pool:
        raise ValueError(f"not a reviewed {pool} string id: {string_id!r}")
    entry = int(match.group(2))
    if entry >= POOL_SPECS[pool]["entry_count"]:
        raise ValueError(f"{pool} entry outside bounded range: {entry}")
    return entry


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _custom_units(path: Path | None) -> set[int]:
    if path is None:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    mappings = payload.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError("custom map has no mappings")
    units = set()
    for mapping in mappings:
        value = str(mapping.get("code_unit", ""))
        if not value.lower().startswith("0x"):
            raise ValueError(f"custom map code unit is not hexadecimal: {value!r}")
        units.add(int(value, 16))
    return units


def _code_units_from_encoded(encoded: bytes) -> list[int]:
    units = []
    cursor = 0
    while cursor < len(encoded):
        lead = encoded[cursor]
        if lead <= 0x7F or 0xA1 <= lead <= 0xDF:
            cursor += 1
            continue
        if cursor + 1 >= len(encoded):
            raise ValueError("translated Shift-JIS payload ends with a lead byte")
        units.append((lead << 8) | encoded[cursor + 1])
        cursor += 2
    return units


def _validate_record_controls(source_payload: bytes, target_payload: bytes) -> None:
    source_known, source_unknown = common.format_sequences(source_payload)
    target_known, target_unknown = common.format_sequences(target_payload)
    if source_known != target_known or source_unknown != target_unknown:
        raise ValueError("format sequence contract changed")
    source_controls = bytes(value for value in source_payload if value < 0x20)
    target_controls = bytes(value for value in target_payload if value < 0x20)
    if source_controls != target_controls:
        raise ValueError("control-byte contract changed")


def patch_pool(
    data: bytes,
    records: list[dict[str, object]],
    pool: str,
    *,
    forbidden_code_units: set[int] | None = None,
) -> tuple[bytes, dict[str, object]]:
    if pool not in POOL_SPECS:
        raise ValueError(f"pool is not explicitly reviewed: {pool}")
    table_offset = POOL_SPECS[pool]["file_offset"]
    entry_count = POOL_SPECS[pool]["entry_count"]
    pointers = []
    for entry in range(entry_count):
        pointer = common.read_u32(data, table_offset + entry * 4)
        if not common.is_rom_pointer(pointer, len(data)):
            raise common.StaticContractError(f"pool pointer outside ROM at entry {entry}")
        pointers.append(pointer)
    pointer_bytes = data[table_offset:table_offset + entry_count * 4]
    patched = bytearray(data)
    seen_target_text: dict[int, str] = {}
    rows = []
    for record in records:
        entry = parse_pool_entry(record.get("string_id"), pool)
        source = record.get("source")
        if not isinstance(source, dict):
            raise ValueError(f"record {entry} is not a restored working record")
        source_text = source.get("text")
        target_text = record.get("targets", {}).get("zh-TW", {}).get("text")
        provenance = source.get("provenance", {})
        if not isinstance(source_text, str) or not isinstance(target_text, str) or not isinstance(provenance, dict):
            raise ValueError(f"record {entry} lacks source, target or provenance")
        target = pointers[entry] - ROM_BASE
        original_payload, terminator = common.read_c_string(data, target)
        if source_text != original_payload.decode("shift_jis"):
            raise ValueError(f"source text mismatch at {pool}:{entry}")
        if provenance.get("source_hash") != hashlib.sha256(original_payload).hexdigest():
            raise ValueError(f"raw source hash mismatch at {pool}:{entry}")
        if provenance.get("source_text_hash") != font_coverage.canonical_text_hash(source_text):
            raise ValueError(f"source text hash mismatch at {pool}:{entry}")
        if target in seen_target_text and seen_target_text[target] != target_text:
            raise ValueError(f"duplicate target has conflicting translations at 0x{target:06X}")
        seen_target_text[target] = target_text
        encoded_target, _ = font_coverage.shift_jis_code_units(target_text)
        _validate_record_controls(original_payload, encoded_target)
        forbidden = forbidden_code_units or set()
        overlap = sorted(set(_code_units_from_encoded(encoded_target)) & forbidden)
        if overlap:
            formatted = ", ".join(f"0x{unit:04X}" for unit in overlap)
            raise ValueError(f"translated target uses forbidden custom raw unit(s): {formatted}")
        coverage = font_coverage.coverage_for_text(data, target_text, max_payload_bytes=len(original_payload))
        if coverage["status"] != "covered" or not coverage["fits_original_record"]:
            raise ValueError(f"font/slot gate failed at {pool}:{entry}: {coverage['status']}")
        patched[target:terminator + 1] = fixed_slot_replacement(original_payload, encoded_target)
        rows.append({
            "entry": entry,
            "record_file_offset": f"0x{target:06X}",
            "original_payload_length": len(original_payload),
            "translated_payload_length": len(encoded_target),
            "original_payload_sha256": hashlib.sha256(original_payload).hexdigest(),
            "translated_payload_sha256": hashlib.sha256(encoded_target).hexdigest(),
            "target_text_hash": font_coverage.canonical_text_hash(target_text),
            "coverage": coverage,
            "relocated": False,
        })
    return bytes(patched), {
        "read_only_source": True,
        "pool": pool,
        "table_file_offset": f"0x{table_offset:06X}",
        "table_entry_count": entry_count,
        "working_record_count": len(records),
        "unique_patched_target_count": len(seen_target_text),
        "relocation": "disabled; fixed-slot only",
        "forbidden_code_unit_count": len(forbidden_code_units or set()),
        "pointer_table_sha256": hashlib.sha256(pointer_bytes).hexdigest(),
        "rows": sorted(rows, key=lambda row: row["entry"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--pool", choices=sorted(POOL_SPECS), default="event-system")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--custom-map", type=Path, help="optional map whose raw units are forbidden in story targets")
    args = parser.parse_args()
    original = args.rom.read_bytes()
    forbidden = _custom_units(args.custom_map)
    if args.pool == "story-event" and args.custom_map is None:
        raise SystemExit("story-event requires --custom-map to enforce the four-pool custom-unit safety gate")
    patched, report = patch_pool(original, _records(args.work), args.pool, forbidden_code_units=forbidden)
    report["original_rom_sha256"] = hashlib.sha256(original).hexdigest()
    report["patched_rom_sha256"] = hashlib.sha256(patched).hexdigest()
    report["changed_byte_count"] = sum(left != right for left, right in zip(original, patched))
    args.output.write_bytes(patched)
    args.metadata_output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("pool", "table_entry_count", "working_record_count", "unique_patched_target_count", "relocation", "changed_byte_count")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
