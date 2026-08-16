#!/usr/bin/env python3
"""Build the first real B3CJ zh-TW batch from the local ledger workflow.

The bounded M2.5 plan covers four repeated resource-24 prize-header records.
This tool has two explicit phases:

* ``prepare`` creates an ignored bootstrap ledger and a source adapter whose
  ``text`` field matches the generic core ledger contract.  The caller must
  then run ``restore_translations.rb`` and ``strip_translations.rb``.
* ``build`` consumes the restored local working file, allocates only the three
  M2.5 extension glyphs, patches the four same-length records, repacks only
  the original resource span, and optionally runs the shared BPS tools.

The tool never writes a clean ROM, source table, or patch outside explicit
output arguments.  Reports contain hashes, IDs, and target-side evidence; no
source text is copied into tracked files.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import struct
import subprocess
import sys
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
M23_PATH = GAME_ROOT / "tools" / "encode_m2_3_poc.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M23 = _load_module("b3cj_encode_m2_3_for_m2_5", M23_PATH)
INSPECT_FONT = M23.INSPECT_FONT
EXTRACT_STATIC = M23.EXTRACT_STATIC

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_FONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
EXPECTED_BATCH_ID = "m2.5-prize-ui"
ALLOWED_SLOT_FIRST = 0x845
ALLOWED_SLOT_LAST = 0x85F
TARGET_LOCALE = "zh-TW"
LEDGER_ALLOWED_CONTEXT_KEYS = {"scene", "speaker", "notes", "max_width", "max_lines", "control_codes"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"{field} is not an integer: {value!r}") from exc
    raise ValueError(f"{field} must be an integer or 0x string")


def load_jsonl(path: pathlib.Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        rows.append(value)
    return rows


def write_jsonl(path: pathlib.Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def canonical_source_hash(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def _contains_opaque(value: object) -> bool:
    if isinstance(value, dict):
        if value.get("kind") == "opaque":
            return True
        opaque_ops = value.get("opaque_ops")
        if isinstance(opaque_ops, list) and opaque_ops:
            return True
        return any(_contains_opaque(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_opaque(item) for item in value)
    return False


def _source_offset(row: Mapping[str, object]) -> int:
    provenance = row.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError(f"source row {row.get('string_id')} has no provenance object")
    return parse_int(provenance.get("decompressed_offset"), f"{row.get('string_id')}.decompressed_offset")


def load_plan(path: pathlib.Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("M2.5 plan root must be an object")
    plan = value
    if parse_int(plan.get("plan_version"), "plan_version") != 1:
        raise ValueError("unsupported M2.5 plan version")
    if plan.get("game") != EXPECTED_GAME or plan.get("revision") != EXPECTED_REVISION:
        raise ValueError("M2.5 plan is not for B3CJ")
    if plan.get("batch_id") != EXPECTED_BATCH_ID:
        raise ValueError("unexpected M2.5 batch id")
    if plan.get("source_table_sha256") != EXPECTED_SOURCE_TABLE_SHA256:
        raise ValueError("M2.5 source-table hash is not fixed B3CJ")
    if plan.get("clean_rom_sha256") != EXPECTED_ROM_SHA256:
        raise ValueError("M2.5 clean-ROM hash is not fixed B3CJ")
    if plan.get("font_source_sha256") != EXPECTED_FONT_SOURCE_SHA256:
        raise ValueError("M2.5 font-source hash is not fixed Unifont")
    if plan.get("target_locale") != TARGET_LOCALE or plan.get("status") != "ai_draft":
        raise ValueError("M2.5 target locale/status contract changed")

    context = plan.get("context")
    if not isinstance(context, dict):
        raise ValueError("M2.5 plan context must be an object")
    if not isinstance(context.get("max_width"), int) or context["max_width"] != 7:
        raise ValueError("M2.5 width contract must remain seven cells")
    if not isinstance(context.get("max_lines"), int) or context["max_lines"] != 1:
        raise ValueError("M2.5 line contract must remain one line")
    if context.get("control_codes") != ["0x0308", "0x0000"]:
        raise ValueError("M2.5 record control contract changed")

    control_contract = plan.get("control_contract")
    if not isinstance(control_contract, dict):
        raise ValueError("M2.5 control contract is missing")
    if control_contract.get("following_opcodes") != ["0x0309", "0x0308"]:
        raise ValueError("M2.5 following-control contract changed")
    if control_contract.get("opaque_control_count") != 0:
        raise ValueError("M2.5 batch must have zero opaque controls")

    targets = plan.get("targets")
    if not isinstance(targets, dict):
        raise ValueError("M2.5 targets are missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets.get(locale)
        if not isinstance(target, dict) or not isinstance(target.get("text"), str):
            raise ValueError(f"M2.5 {locale} target is malformed")
        if target.get("utf8_sha256") != sha256_bytes(target["text"].encode("utf-8")):
            raise ValueError(f"M2.5 {locale} target hash mismatch")

    target_contract = plan.get("target_contract")
    expected_units = ["ec64", "8e9f", "9349", "ec65", "9569", "ec66", "8163"]
    if not isinstance(target_contract, dict):
        raise ValueError("M2.5 target contract is missing")
    if parse_int(target_contract.get("byte_length"), "target_contract.byte_length") != 14:
        raise ValueError("M2.5 target length must remain 14 bytes")
    if target_contract.get("code_units") != expected_units:
        raise ValueError("M2.5 target code-unit contract changed")
    if target_contract.get("extension_units") != ["ec64", "ec65", "ec66"]:
        raise ValueError("M2.5 extension-unit contract changed")
    if target_contract.get("record_terminator") != "0x0000":
        raise ValueError("M2.5 record terminator changed")

    allocations_value = plan.get("allocations")
    if not isinstance(allocations_value, list) or len(allocations_value) != 3:
        raise ValueError("M2.5 requires exactly three new glyph allocations")
    allocations: list[dict[str, object]] = []
    seen_units: set[str] = set()
    seen_slots: set[int] = set()
    expected_allocations = {
        "ec64": ("這", 0x847),
        "ec65": ("獎", 0x848),
        "ec66": ("是", 0x849),
    }
    for index, raw_item in enumerate(allocations_value):
        if not isinstance(raw_item, dict):
            raise ValueError(f"allocations[{index}] must be an object")
        item = dict(raw_item)
        unit = item.get("code_unit")
        char = item.get("unicode")
        slot = parse_int(item.get("glyph_id"), f"allocations[{index}].glyph_id")
        if not isinstance(unit, str) or not isinstance(char, str) or unit not in expected_allocations:
            raise ValueError(f"unexpected M2.5 allocation at index {index}")
        expected_char, expected_slot = expected_allocations[unit]
        if char != expected_char or slot != expected_slot:
            raise ValueError(f"M2.5 allocation mapping mismatch for {unit}")
        if item.get("code_unit_kind") != "opaque_extension" or item.get("status") != "m2.5_ai_draft":
            raise ValueError(f"M2.5 allocation metadata mismatch for {unit}")
        if unit in seen_units or slot in seen_slots:
            raise ValueError("M2.5 allocation units and slots must be unique")
        seen_units.add(unit)
        seen_slots.add(slot)
        if not ALLOWED_SLOT_FIRST <= slot <= ALLOWED_SLOT_LAST:
            raise ValueError(f"M2.5 slot 0x{slot:x} is outside fail-closed range")
        if item.get("codepoint") != f"U+{ord(char):04X}":
            raise ValueError(f"M2.5 codepoint mismatch for {unit}")
        try:
            code_unit = bytes.fromhex(unit)
        except ValueError as exc:
            raise ValueError(f"M2.5 allocation {unit} is not hex") from exc
        if len(code_unit) != 2 or INSPECT_FONT.is_strict_shift_jis_pair(code_unit):
            raise ValueError(f"M2.5 allocation {unit} must remain opaque/non-Shift-JIS")
        allocations.append(item)

    records_value = plan.get("records")
    if not isinstance(records_value, list) or not 1 <= len(records_value) <= 4:
        raise ValueError("M2.5 must contain one to four records")
    records: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_offsets: set[int] = set()
    for index, raw_item in enumerate(records_value):
        if not isinstance(raw_item, dict):
            raise ValueError(f"records[{index}] must be an object")
        item = dict(raw_item)
        string_id = item.get("string_id")
        if not isinstance(string_id, str) or not string_id.startswith("b3cj:t2:024:"):
            raise ValueError(f"records[{index}] is outside the resource-24 batch")
        if string_id in seen_ids:
            raise ValueError(f"duplicate M2.5 string_id {string_id}")
        seen_ids.add(string_id)
        offset = parse_int(item.get("decompressed_offset"), f"{string_id}.decompressed_offset")
        if offset in seen_offsets:
            raise ValueError(f"duplicate M2.5 offset 0x{offset:x}")
        seen_offsets.add(offset)
        if parse_int(item.get("resource_id"), f"{string_id}.resource_id") != 24:
            raise ValueError(f"{string_id} is not resource 24")
        if parse_int(item.get("raw_length"), f"{string_id}.raw_length") != 14:
            raise ValueError(f"{string_id} does not have the 14-byte contract")
        for field in ("source_hash", "source_raw_sha256", "source_record_sha256"):
            if not isinstance(item.get(field), str) or len(item[field]) != 64:
                raise ValueError(f"{string_id} has malformed {field}")
        if item["source_hash"] != "c10caff6b389dc1506d1879cdac4e21111ead7eb8b41e05eca6aed3d73873ddc":
            raise ValueError(f"{string_id} source hash is not the selected repeated group")
        records.append(item)
    if not seen_offsets.issubset({0x64, 0x12C, 0x1F0, 0x2BE}):
        raise ValueError("M2.5 record offset is outside the fixed repeated group")

    adjacent = plan.get("adjacent_untouched_records")
    if adjacent != ["b3cj:t2:024:0x0046", "b3cj:t2:024:0x0078"]:
        raise ValueError("M2.5 adjacent-record contract changed")
    return plan


def load_source_rows(path: pathlib.Path) -> dict[str, dict[str, object]]:
    if sha256_file(path) != EXPECTED_SOURCE_TABLE_SHA256:
        raise ValueError("source table SHA-256 mismatch")
    rows = M23.load_source_table(path, EXPECTED_SOURCE_TABLE_SHA256)
    return {str(key): value for key, value in rows.items()}


def validate_source_selection(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> None:
    records = plan["records"]
    assert isinstance(records, list)
    control_contract = plan["control_contract"]
    assert isinstance(control_contract, dict)
    expected_following = control_contract["following_opcodes"]
    assert isinstance(expected_following, list)
    for spec in records:
        assert isinstance(spec, dict)
        string_id = str(spec["string_id"])
        row = source_rows.get(string_id)
        if row is None:
            raise ValueError(f"M2.5 source row is missing: {string_id}")
        if canonical_source_hash(str(row.get("source_text"))) != spec["source_hash"]:
            raise ValueError(f"source hash mismatch for {string_id}")
        if row.get("raw_sha256") != spec["source_raw_sha256"] or row.get("record_sha256") != spec["source_record_sha256"]:
            raise ValueError(f"source raw/record hash mismatch for {string_id}")
        provenance = row.get("provenance")
        if not isinstance(provenance, dict) or int(provenance.get("resource_id")) != 24:
            raise ValueError(f"source provenance mismatch for {string_id}")
        if _source_offset(row) != parse_int(spec["decompressed_offset"], f"{string_id}.decompressed_offset"):
            raise ValueError(f"source offset mismatch for {string_id}")
        if parse_int(row.get("raw_length"), f"{string_id}.raw_length") != 14:
            raise ValueError(f"source length mismatch for {string_id}")
        source_text = row.get("source_text")
        if not isinstance(source_text, str):
            raise ValueError(f"source text missing for {string_id}")
        try:
            source_payload = source_text.encode("shift_jis")
        except UnicodeEncodeError as exc:
            raise ValueError(f"source Shift-JIS encode failed for {string_id}") from exc
        if len(source_payload) != 14 or sha256_bytes(source_payload) != spec["source_raw_sha256"]:
            raise ValueError(f"source payload mismatch for {string_id}")
        if row.get("control_tokens") != ["0x0308", "0x0000"]:
            raise ValueError(f"source control token mismatch for {string_id}")
        following = row.get("following_controls")
        if not isinstance(following, list) or [node.get("opcode") for node in following if isinstance(node, dict)] != expected_following:
            raise ValueError(f"source following-control mismatch for {string_id}")
        if _contains_opaque(row.get("control_structure")) or _contains_opaque(row.get("following_controls")):
            raise ValueError(f"opaque control present in selected source row {string_id}")


def make_seed_ledger(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    validate_source_selection(plan, source_rows)
    context_value = plan["context"]
    assert isinstance(context_value, dict)
    context = {key: context_value[key] for key in LEDGER_ALLOWED_CONTEXT_KEYS if key in context_value}
    targets = plan["targets"]
    assert isinstance(targets, dict)
    target_records: dict[str, dict[str, object]] = {}
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets[locale]
        assert isinstance(target, dict)
        target_records[locale] = {
            "text": target["text"],
            "author": "Codex",
            "model": "gpt-5.6-luna",
        }
    records: list[dict[str, object]] = []
    source_adapter: list[dict[str, object]] = []
    plan_records = plan["records"]
    assert isinstance(plan_records, list)
    for spec in plan_records:
        assert isinstance(spec, dict)
        string_id = str(spec["string_id"])
        row = source_rows[string_id]
        source_text = str(row["source_text"])
        records.append(
            {
                "game": EXPECTED_GAME,
                "revision": EXPECTED_REVISION,
                "string_id": string_id,
                "source_locale": str(row["locale"]),
                "source_hash": canonical_source_hash(source_text),
                "targets": target_records,
                "context": context,
                "terms": [],
                "status": "ai_draft",
                "review_notes": plan["review_notes"],
            }
        )
        source_adapter.append(
            {
                "string_id": string_id,
                "locale": str(row["locale"]),
                "text": source_text,
                "provenance": "B3CJ extract_static.py M2.1 local source adapter",
            }
        )
    return records, source_adapter


def validate_working_rows(
    plan: Mapping[str, object],
    source_rows: Mapping[str, Mapping[str, object]],
    working_rows: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    plan_records = plan["records"]
    assert isinstance(plan_records, list)
    expected_ids = {str(item["string_id"]) for item in plan_records if isinstance(item, dict)}
    actual_ids = {str(item.get("string_id")) for item in working_rows}
    if actual_ids != expected_ids or len(working_rows) != len(expected_ids):
        raise ValueError("working file must contain exactly the planned one-to-four records")
    targets = plan["targets"]
    assert isinstance(targets, dict)
    expected_tw = targets[TARGET_LOCALE]
    expected_hans = targets["zh-Hans"]
    assert isinstance(expected_tw, dict) and isinstance(expected_hans, dict)
    rows_by_id: dict[str, dict[str, object]] = {}
    for working in working_rows:
        string_id = str(working.get("string_id"))
        source = working.get("source")
        if not isinstance(source, dict) or not isinstance(source.get("text"), str):
            raise ValueError(f"working record {string_id} must come from restore_translations.rb")
        source_row = source_rows[string_id]
        if source["text"] != source_row.get("source_text") or source.get("locale") != source_row.get("locale"):
            raise ValueError(f"working source mismatch for {string_id}")
        if working.get("game") != EXPECTED_GAME or working.get("revision") != EXPECTED_REVISION:
            raise ValueError(f"working identity mismatch for {string_id}")
        if working.get("status") != "ai_draft":
            raise ValueError(f"M2.5 requires ai_draft status for {string_id}")
        working_targets = working.get("targets")
        if not isinstance(working_targets, dict):
            raise ValueError(f"working targets missing for {string_id}")
        for locale, expected in ((TARGET_LOCALE, expected_tw), ("zh-Hans", expected_hans)):
            actual = working_targets.get(locale)
            if not isinstance(actual, dict) or actual.get("text") != expected.get("text"):
                raise ValueError(f"working {locale} target differs from the fixed M2.5 plan for {string_id}")
        rows_by_id[string_id] = working
    return rows_by_id


def _record_region(decoded: bytes, offset: int, raw_length: int) -> bytes:
    return M23._record_region(decoded, offset, raw_length)


def _target_payload(
    target_text: str,
    plan: Mapping[str, object],
    rom_data: bytes,
    font: Mapping[str, object],
) -> tuple[bytes, list[bytes]]:
    allocations = plan["allocations"]
    assert isinstance(allocations, list)
    by_char: dict[str, bytes] = {}
    for item in allocations:
        assert isinstance(item, dict)
        by_char[str(item["unicode"])] = bytes.fromhex(str(item["code_unit"]))
    units: list[bytes] = []
    for char in target_text:
        extension = by_char.get(char)
        if extension is not None:
            units.append(extension)
            continue
        try:
            raw = char.encode("shift_jis")
        except UnicodeEncodeError as exc:
            raise ValueError(f"target character {char!r} is not encodable in the fixed codepage") from exc
        if len(raw) != 2 or not INSPECT_FONT.is_strict_shift_jis_pair(raw):
            raise ValueError(f"target character {char!r} is not a supported two-byte code unit")
        lookup = INSPECT_FONT.lookup_code_unit(
            rom_data,
            raw,
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        if lookup.get("status") != "mapped":
            raise ValueError(f"target character {char!r} has no existing mapped glyph")
        units.append(raw)
    expected_units = plan["target_contract"]["code_units"]
    assert isinstance(expected_units, list)
    if [unit.hex() for unit in units] != expected_units:
        raise ValueError("target code units differ from the fixed M2.5 plan")
    payload = b"".join(units)
    expected_length = parse_int(plan["target_contract"]["byte_length"], "target_contract.byte_length")
    if len(payload) != expected_length:
        raise ValueError(f"target payload length {len(payload)} != {expected_length}")
    return payload, units


def _apply_font_allocations(
    rom_data: bytes,
    patched: bytearray,
    plan: Mapping[str, object],
    font_source_path: pathlib.Path,
    source_units: set[bytes],
    font: Mapping[str, object],
) -> list[dict[str, object]]:
    allocations = plan["allocations"]
    assert isinstance(allocations, list)
    codepoints = [ord(str(item["unicode"])) for item in allocations if isinstance(item, dict)]
    source_hash = INSPECT_FONT.verify_unifont_source(font_source_path)
    if source_hash != EXPECTED_FONT_SOURCE_SHA256:
        raise ValueError("font source SHA-256 mismatch")
    glyphs = INSPECT_FONT.load_unifont_glyphs(font_source_path, codepoints)
    reports: list[dict[str, object]] = []
    seen_slots: set[int] = set()
    for item in allocations:
        assert isinstance(item, dict)
        raw = bytes.fromhex(str(item["code_unit"]))
        glyph_id = parse_int(item["glyph_id"], f"allocation {raw.hex()}.glyph_id")
        if raw in source_units:
            raise ValueError(f"extension code unit {raw.hex()} already occurs in source corpus")
        if glyph_id in seen_slots:
            raise ValueError(f"duplicate M2.5 slot 0x{glyph_id:x}")
        seen_slots.add(glyph_id)
        lookup = INSPECT_FONT.lookup_code_unit(
            rom_data,
            raw,
            slot_count=int(font["slot_count"]),
            font_base_file_offset=int(font["font_base_file_offset"]),
        )
        if lookup.get("status") != "fallback" or lookup.get("table_value") != "0x0000":
            raise ValueError(f"extension code unit {raw.hex()} is not an unused zero mapping")
        cell_offset = int(font["font_base_file_offset"]) + glyph_id * INSPECT_FONT.FONT_CELL_SIZE
        old_cell = rom_data[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE]
        if old_cell != bytes(INSPECT_FONT.FONT_CELL_SIZE):
            raise ValueError(f"M2.5 slot 0x{glyph_id:x} is not physically blank")
        cell = INSPECT_FONT.unifont_bitmap_to_cell(glyphs[ord(str(item["unicode"]))])
        table_offset = int(str(lookup["table_entry_file_offset"]), 16)
        old_table_value = struct.unpack_from("<H", rom_data, table_offset)[0]
        struct.pack_into("<H", patched, table_offset, glyph_id + 1)
        patched[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE] = cell
        reports.append(
            {
                "code_unit": raw.hex(),
                "unicode": str(item["unicode"]),
                "codepoint": str(item["codepoint"]),
                "glyph_id": f"0x{glyph_id:03x}",
                "table_entry_file_offset": f"0x{table_offset:x}",
                "old_table_value": f"0x{old_table_value:04x}",
                "new_table_value": f"0x{glyph_id + 1:04x}",
                "cell_file_offset": f"0x{cell_offset:x}",
                "cell_sha256": sha256_bytes(cell),
            }
        )
    return reports


def _source_record_map(source_rows: Mapping[str, Mapping[str, object]]) -> dict[str, dict[str, object]]:
    return {str(key): dict(value) for key, value in source_rows.items()}


def _decode_resources(rom_data: bytes, resource_ids: Iterable[int]) -> dict[int, tuple[dict[str, int], bytes, int]]:
    decoded: dict[int, tuple[dict[str, int], bytes, int]] = {}
    for resource_id in sorted(set(resource_ids)):
        resolved = EXTRACT_STATIC.resolve_script_resource(rom_data, resource_id)
        payload, consumed = EXTRACT_STATIC.decode_lz77(rom_data, int(resolved["payload_file_offset"]))
        decoded[resource_id] = (resolved, payload, consumed)
    return decoded


def _verify_reextract(
    clean_rom: bytes,
    patched_rom: bytes,
    plan: Mapping[str, object],
    source_rows: Mapping[str, Mapping[str, object]],
    target_records: Mapping[str, bytes],
) -> dict[str, object]:
    source_record_rows = _source_record_map(source_rows)
    resource_ids = [int(row["provenance"]["resource_id"]) for row in source_rows.values() if isinstance(row.get("provenance"), dict)]
    clean_resources = _decode_resources(clean_rom, resource_ids)
    patched_resources = _decode_resources(patched_rom, resource_ids)
    selected_ids = set(target_records)
    record_count = 0
    untouched_count = 0
    target_reports: list[dict[str, object]] = []
    adjacent_reports: list[dict[str, object]] = []
    adjacent_ids = set(str(item) for item in plan["adjacent_untouched_records"])
    resource_reports: list[dict[str, object]] = []
    for resource_id in sorted(clean_resources):
        clean_resolved, clean_decoded, clean_consumed = clean_resources[resource_id]
        patched_resolved, patched_decoded, patched_consumed = patched_resources[resource_id]
        if resource_id != 24 and patched_decoded != clean_decoded:
            raise ValueError(f"resource {resource_id} changed outside M2.5 batch")
        resource_reports.append(
            {
                "resource_id": resource_id,
                "decoded_size": len(patched_decoded),
                "clean_stream_sha256": sha256_bytes(clean_decoded[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]),
                "patched_stream_sha256": sha256_bytes(patched_decoded[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]),
                "lz77_consumed_size": patched_consumed,
                "unchanged": patched_decoded == clean_decoded,
            }
        )
        for string_id, row in source_record_rows.items():
            provenance = row.get("provenance")
            if not isinstance(provenance, dict) or int(provenance.get("resource_id")) != resource_id:
                continue
            offset = _source_offset(row)
            raw_length = parse_int(row.get("raw_length"), f"{string_id}.raw_length")
            clean_record = _record_region(clean_decoded, offset, raw_length)
            patched_record = _record_region(patched_decoded, offset, raw_length)
            record_count += 1
            if string_id in selected_ids:
                expected = target_records[string_id]
                if patched_record != expected:
                    raise ValueError(f"target re-extract mismatch for {string_id}")
                target_reports.append(
                    {
                        "string_id": string_id,
                        "resource_id": resource_id,
                        "decompressed_offset": f"0x{offset:04x}",
                        "target_record_sha256": sha256_bytes(patched_record),
                        "target_payload_sha256": sha256_bytes(patched_record[2:-2]),
                        "record_byte_length": len(patched_record),
                    }
                )
            else:
                if patched_record != clean_record:
                    raise ValueError(f"untouched record changed for {string_id}")
                untouched_count += 1
            if string_id in adjacent_ids:
                if string_id in selected_ids:
                    raise ValueError(f"adjacent record is unexpectedly selected: {string_id}")
                adjacent_reports.append(
                    {
                        "string_id": string_id,
                        "resource_id": resource_id,
                        "record_sha256": sha256_bytes(patched_record),
                        "byte_identical_to_clean": patched_record == clean_record,
                    }
                )
    if record_count != len(source_record_rows) or record_count != 361:
        raise ValueError(f"re-extract verified {record_count} records, expected 361")
    if len(target_reports) != len(selected_ids) or untouched_count != record_count - len(selected_ids):
        raise ValueError("M2.5 target/untouched record count mismatch")
    if len(adjacent_reports) != 2 or not all(item["byte_identical_to_clean"] for item in adjacent_reports):
        raise ValueError("M2.5 adjacent untouched-record proof is incomplete")
    return {
        "records_total": record_count,
        "target_records": len(target_reports),
        "untouched_records": untouched_count,
        "target": target_reports,
        "adjacent_untouched": adjacent_reports,
        "resources": resource_reports,
    }


def build_batch(
    rom_data: bytes,
    source_path: pathlib.Path,
    font_source_path: pathlib.Path,
    plan: Mapping[str, object],
    working_path: pathlib.Path,
) -> tuple[bytes, dict[str, object]]:
    identity = INSPECT_FONT.verify_rom(rom_data)
    if identity["sha256"] != EXPECTED_ROM_SHA256:
        raise ValueError("clean ROM is not the fixed B3CJ input")
    INSPECT_FONT.verify_static_evidence(rom_data)
    source_rows = load_source_rows(source_path)
    validate_source_selection(plan, source_rows)
    working_rows = load_jsonl(working_path)
    working_by_id = validate_working_rows(plan, source_rows, working_rows)
    font_source_hash = INSPECT_FONT.verify_unifont_source(font_source_path)
    if font_source_hash != EXPECTED_FONT_SOURCE_SHA256:
        raise ValueError("font source is not fixed GNU Unifont 17.0.05")
    font = INSPECT_FONT.parse_font_resource(rom_data)
    source_units, _source_metadata = INSPECT_FONT.source_code_units_from_jsonl(source_path)
    patched = bytearray(rom_data)
    allocation_reports = _apply_font_allocations(rom_data, patched, plan, font_source_path, set(source_units), font)

    targets = plan["targets"]
    assert isinstance(targets, dict)
    target_tw = targets[TARGET_LOCALE]
    assert isinstance(target_tw, dict)
    target_text = str(target_tw["text"])
    if len(target_text) > int(plan["context"]["max_width"]):
        raise ValueError("target exceeds bounded static cell width")
    target_payload, target_units = _target_payload(target_text, plan, rom_data, font)
    resolved = EXTRACT_STATIC.resolve_script_resource(rom_data, 24)
    original_decoded, original_compressed_size = EXTRACT_STATIC.decode_lz77(rom_data, int(resolved["payload_file_offset"]))
    decoded = bytearray(original_decoded)
    target_records: dict[str, bytes] = {}
    plan_records = plan["records"]
    assert isinstance(plan_records, list)
    for spec in plan_records:
        assert isinstance(spec, dict)
        string_id = str(spec["string_id"])
        row = source_rows[string_id]
        offset = _source_offset(row)
        raw_length = parse_int(row["raw_length"], f"{string_id}.raw_length")
        original_record = _record_region(original_decoded, offset, raw_length)
        if sha256_bytes(original_record) != spec["source_record_sha256"]:
            raise ValueError(f"source record bytes mismatch for {string_id}")
        target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
        if len(target_record) != len(original_record):
            raise ValueError(f"same-length record contract failed for {string_id}")
        decoded[offset : offset + len(target_record)] = target_record
        target_records[string_id] = target_record
    compressed = M23.lz77_compress(bytes(decoded))
    span_bytes = int(resolved["span_units"]) * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
    if len(compressed) > span_bytes:
        raise ValueError(f"resource 24 compressed output {len(compressed)} exceeds span {span_bytes}")
    payload_offset = int(resolved["payload_file_offset"])
    patched[payload_offset : payload_offset + span_bytes] = compressed + bytes(span_bytes - len(compressed))

    patched_rom = bytes(patched)
    changed_ranges = [
        (int(report["table_entry_file_offset"], 16), int(report["table_entry_file_offset"], 16) + 2)
        for report in allocation_reports
    ] + [
        (int(report["cell_file_offset"], 16), int(report["cell_file_offset"], 16) + INSPECT_FONT.FONT_CELL_SIZE)
        for report in allocation_reports
    ] + [(payload_offset, payload_offset + span_bytes)]
    changed_offsets = [index for index, (before, after) in enumerate(zip(rom_data, patched_rom)) if before != after]
    if any(not any(start <= offset < end for start, end in changed_ranges) for offset in changed_offsets):
        raise ValueError("M2.5 changed a byte outside font allocations/resource 24 span")

    post_font = INSPECT_FONT.parse_font_resource(patched_rom)
    post_allocations: list[dict[str, object]] = []
    for item in plan["allocations"]:
        assert isinstance(item, dict)
        raw = bytes.fromhex(str(item["code_unit"]))
        lookup = INSPECT_FONT.lookup_code_unit(
            patched_rom,
            raw,
            slot_count=int(post_font["slot_count"]),
            font_base_file_offset=int(post_font["font_base_file_offset"]),
        )
        expected_slot = parse_int(item["glyph_id"], f"{raw.hex()}.glyph_id")
        if lookup.get("status") != "mapped" or int(lookup["glyph_id"]) != expected_slot:
            raise ValueError(f"post-patch glyph mapping failed for {raw.hex()}")
        post_allocations.append(
            {
                "code_unit": raw.hex(),
                "unicode": str(item["unicode"]),
                "glyph_id": f"0x{expected_slot:03x}",
                "cell_sha256": lookup["cell_sha256"],
            }
        )
    adjacent_id = min(parse_int(item["glyph_id"], "glyph_id") for item in plan["allocations"]) - 1
    if adjacent_id in {parse_int(item["glyph_id"], "glyph_id") for item in plan["allocations"]}:
        raise ValueError("M2.5 has no untouched adjacent glyph")
    adjacent_render = INSPECT_FONT.render_glyph(patched_rom, post_font, adjacent_id)
    if adjacent_render["cell_sha256"] != INSPECT_FONT.render_glyph(rom_data, font, adjacent_id)["cell_sha256"]:
        raise ValueError("adjacent untouched glyph changed")
    changed_renders = [
        INSPECT_FONT.render_glyph(patched_rom, post_font, parse_int(item["glyph_id"], "glyph_id"))
        for item in plan["allocations"]
    ]
    reextract = _verify_reextract(rom_data, patched_rom, plan, source_rows, target_records)
    summary: dict[str, object] = {
        "batch_id": EXPECTED_BATCH_ID,
        "static_only": True,
        "runtime_qa": "pending",
        "translation_status": "ai_draft",
        "translated_string_ids": sorted(target_records),
        "plan_sha256": sha256_file(GAME_ROOT / "research" / "m2.5-batch-plan.json"),
        "working_sha256": sha256_file(working_path),
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "font_source_sha256": font_source_hash,
        "clean_rom_identity": identity,
        "target": {
            "locale": TARGET_LOCALE,
            "utf8_sha256": target_tw["utf8_sha256"],
            "byte_length": len(target_payload),
            "code_units": [unit.hex() for unit in target_units],
        },
        "font": {
            "resource_type": 3,
            "resource_id": 2,
            "font_base_file_offset": f"0x{int(post_font['font_base_file_offset']):x}",
            "cell_size": INSPECT_FONT.FONT_CELL_SIZE,
            "allocations": allocation_reports,
            "post_allocations": post_allocations,
            "adjacent_untouched_glyph_id": f"0x{adjacent_id:03x}",
            "adjacent_untouched_cell_sha256": adjacent_render["cell_sha256"],
            "changed_static_renders": [
                {
                    "glyph_id": render["glyph_id"],
                    "cell_sha256": render["cell_sha256"],
                    "render_sha256": render["render_sha256"],
                    "rows": render["rows"],
                }
                for render in changed_renders
            ],
        },
        "resource": {
            "resource_id": 24,
            "payload_file_offset": f"0x{payload_offset:x}",
            "span_bytes": span_bytes,
            "decoded_size": len(decoded),
            "original_compressed_size": original_compressed_size,
            "new_compressed_size": len(compressed),
            "original_compressed_sha256": sha256_bytes(rom_data[payload_offset : payload_offset + original_compressed_size]),
            "new_compressed_sha256": sha256_bytes(compressed),
            "decoded_stream_sha256": sha256_bytes(bytes(decoded)[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]),
            "repacked_in_original_span": True,
        },
        "reextract": reextract,
        "byte_level": {
            "changed_byte_count": len(changed_offsets),
            "changed_outside_font_or_resource24": False,
            "font_mapping_and_cell": "byte_verified",
            "record_and_resource24_stream": "byte_verified",
            "all_361_records_reextracted": True,
        },
        "boundary": "Static build only; no runtime screen/readability or release-patch claim.",
    }
    return patched_rom, summary


def run_bps(source_path: pathlib.Path, target_path: pathlib.Path, bps_path: pathlib.Path, applied_path: pathlib.Path) -> dict[str, object]:
    if source_path.resolve() == target_path.resolve() or source_path.resolve() == applied_path.resolve():
        raise ValueError("refusing to overwrite or apply over the clean ROM")
    bps_path.parent.mkdir(parents=True, exist_ok=True)
    applied_path.parent.mkdir(parents=True, exist_ok=True)
    create = REPO_ROOT / "core" / "patches" / "bps_create.rb"
    apply = REPO_ROOT / "core" / "patches" / "bps_apply.rb"
    subprocess.run(["ruby", str(create), str(source_path), str(target_path), str(bps_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["ruby", str(apply), str(source_path), str(bps_path), str(applied_path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    target = target_path.read_bytes()
    applied = applied_path.read_bytes()
    if applied != target:
        raise ValueError("BPS applied output is not byte-identical to the built ROM")
    bps = bps_path.read_bytes()
    return {
        "source_crc32": f"{binascii.crc32(source_path.read_bytes()) & 0xffffffff:08x}",
        "target_crc32": f"{binascii.crc32(target) & 0xffffffff:08x}",
        "target_sha256": sha256_bytes(target),
        "bps_size": len(bps),
        "bps_sha256": sha256_bytes(bps),
        "applied_sha256": sha256_bytes(applied),
        "applied_byte_identical": True,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="create ignored bootstrap ledger and source adapter")
    prepare.add_argument("--source-jsonl", type=pathlib.Path, required=True)
    prepare.add_argument("--plan", type=pathlib.Path, required=True)
    prepare.add_argument("--ledger-output", type=pathlib.Path, required=True)
    prepare.add_argument("--source-adapter-output", type=pathlib.Path, required=True)

    build = subparsers.add_parser("build", help="build static ROM and optional BPS from restored work file")
    build.add_argument("rom", type=pathlib.Path)
    build.add_argument("--source-jsonl", type=pathlib.Path, required=True)
    build.add_argument("--plan", type=pathlib.Path, required=True)
    build.add_argument("--working", type=pathlib.Path, required=True)
    build.add_argument("--font-source", type=pathlib.Path, required=True)
    build.add_argument("--output", type=pathlib.Path, required=True)
    build.add_argument("--summary-output", type=pathlib.Path, required=True)
    build.add_argument("--bps-output", type=pathlib.Path)
    build.add_argument("--bps-applied-output", type=pathlib.Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = load_plan(args.plan)
        if args.command == "prepare":
            source_rows = load_source_rows(args.source_jsonl)
            seed, adapter = make_seed_ledger(plan, source_rows)
            write_jsonl(args.ledger_output, seed)
            write_jsonl(args.source_adapter_output, adapter)
            print(f"B3CJ_M2_5_PREPARE_OK records={len(seed)} ledger={args.ledger_output} source_adapter={args.source_adapter_output}")
            return 0

        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite the clean ROM")
        patched, summary = build_batch(args.rom.read_bytes(), args.source_jsonl, args.font_source, plan, args.working)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            "B3CJ_M2_5_BUILD_OK "
            f"records={len(summary['translated_string_ids'])} "
            f"allocations={len(summary['font']['allocations'])} "
            f"changed_bytes={summary['byte_level']['changed_byte_count']} "
            f"target_sha256={sha256_bytes(patched)}"
        )
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"build_m2_5_batch.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
