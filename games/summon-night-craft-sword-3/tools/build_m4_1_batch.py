#!/usr/bin/env python3
"""Build the first post-M2.5 bounded zh-TW batch cumulatively.

This builder is deliberately narrow: it consumes the fixed M2.5 build first,
then patches one opaque-free resource-22 record and two new glyphs in the
remaining allowed slots.  It never writes source text to a tracked path and
rejects source, control, glyph, length, capacity, or cumulative re-extraction
drift.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
import subprocess
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = GAME_ROOT.parents[1]
M25_PATH = GAME_ROOT / "tools" / "build_m2_5_batch.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M25 = _load_module("b3cj_build_m2_5_for_m4_1", M25_PATH)
M23 = M25.M23
INSPECT_FONT = M25.INSPECT_FONT
EXTRACT_STATIC = M25.EXTRACT_STATIC

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_FONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
EXPECTED_BATCH_ID = "m4.1-wood-chopping-rank"
M25_TARGET_ID = "b3cj:t2:024:0x0064"
M4_TARGET_ID = "b3cj:t2:022:0x004e"
ALLOWED_SLOT_FIRST = 0x845
ALLOWED_SLOT_LAST = 0x85F
TARGET_LOCALE = "zh-TW"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must not be boolean")
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
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _source_offset(row: Mapping[str, object]) -> int:
    provenance = row.get("provenance")
    _require(isinstance(provenance, dict), f"source row {row.get('string_id')} has no provenance")
    return parse_int(provenance.get("decompressed_offset"), f"{row.get('string_id')}.decompressed_offset")


def load_plan(path: pathlib.Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(plan, dict), "M4.1 plan root must be an object")
    _require(plan.get("plan_version") == 1, "unsupported M4.1 plan version")
    _require(plan.get("batch_id") == EXPECTED_BATCH_ID, "unexpected M4.1 batch id")
    _require(plan.get("game") == EXPECTED_GAME and plan.get("revision") == EXPECTED_REVISION, "M4.1 identity mismatch")
    _require(plan.get("source_table_sha256") == EXPECTED_SOURCE_TABLE_SHA256, "M4.1 source table hash mismatch")
    _require(plan.get("clean_rom_sha256") == EXPECTED_ROM_SHA256, "M4.1 clean ROM hash mismatch")
    _require(plan.get("font_source_sha256") == EXPECTED_FONT_SOURCE_SHA256, "M4.1 font source hash mismatch")
    _require(plan.get("target_locale") == TARGET_LOCALE and plan.get("status") == "ai_draft", "M4.1 target/status contract mismatch")

    context = plan.get("context")
    _require(isinstance(context, dict), "M4.1 context is missing")
    _require(context.get("max_width") == 6 and context.get("max_lines") == 1, "M4.1 layout contract mismatch")
    _require(context.get("control_codes") == ["0x0308", "0x0000"], "M4.1 text control contract mismatch")

    controls = plan.get("control_contract")
    _require(isinstance(controls, dict), "M4.1 control contract is missing")
    _require(controls.get("following_opcodes") == ["0x0003", "0x0002", "0x0308"], "M4.1 following controls changed")
    _require(controls.get("opaque_control_count") == 0, "M4.1 cannot contain opaque controls")

    targets = plan.get("targets")
    _require(isinstance(targets, dict), "M4.1 targets are missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets.get(locale)
        _require(isinstance(target, dict) and isinstance(target.get("text"), str), f"M4.1 {locale} target is malformed")
        _require(target.get("utf8_sha256") == sha256_bytes(str(target["text"]).encode("utf-8")), f"M4.1 {locale} hash mismatch")

    contract = plan.get("target_contract")
    _require(isinstance(contract, dict), "M4.1 target contract is missing")
    expected_units = ["ec67", "ec6c", "9056", "8ee8", "8140", "8140"]
    _require(contract.get("byte_length") == 12 and contract.get("code_units") == expected_units, "M4.1 code-unit contract mismatch")
    _require(contract.get("extension_units") == ["ec67", "ec6c"] and contract.get("record_terminator") == "0x0000", "M4.1 extension contract mismatch")

    allocations = plan.get("allocations")
    _require(isinstance(allocations, list) and len(allocations) == 2, "M4.1 requires exactly two allocations")
    seen_units: set[str] = set()
    seen_slots: set[int] = set()
    expected_allocations = {"ec67": ("劈", 0x84A), "ec6c": ("柴", 0x84B)}
    for index, value in enumerate(allocations):
        _require(isinstance(value, dict), f"allocations[{index}] is not an object")
        unit = value.get("code_unit")
        char = value.get("unicode")
        slot = parse_int(value.get("glyph_id"), f"allocations[{index}].glyph_id")
        _require(isinstance(unit, str) and unit in expected_allocations, f"unexpected allocation at {index}")
        expected_char, expected_slot = expected_allocations[unit]
        _require(char == expected_char and slot == expected_slot, f"allocation mismatch for {unit}")
        _require(value.get("codepoint") == f"U+{ord(str(char)):04X}", f"codepoint mismatch for {unit}")
        _require(value.get("code_unit_kind") == "opaque_extension" and value.get("status") == "m4.1_ai_draft", f"allocation metadata mismatch for {unit}")
        raw = bytes.fromhex(unit)
        _require(len(raw) == 2 and not INSPECT_FONT.is_strict_shift_jis_pair(raw), f"allocation {unit} is addressable Shift-JIS")
        _require(ALLOWED_SLOT_FIRST <= slot <= ALLOWED_SLOT_LAST, f"allocation slot 0x{slot:x} is outside allowed range")
        _require(unit not in seen_units and slot not in seen_slots, "M4.1 allocation is duplicated")
        seen_units.add(unit)
        seen_slots.add(slot)

    records = plan.get("records")
    _require(isinstance(records, list) and len(records) == 1, "M4.1 requires exactly one record")
    record = records[0]
    _require(isinstance(record, dict), "M4.1 record is malformed")
    _require(record.get("string_id") == M4_TARGET_ID and record.get("resource_id") == 22, "M4.1 record identity mismatch")
    _require(record.get("decompressed_offset") == "0x004e" and record.get("raw_length") == 12, "M4.1 record layout mismatch")
    for field in ("source_hash", "source_raw_sha256", "source_record_sha256"):
        _require(isinstance(record.get(field), str) and len(record[field]) == 64, f"M4.1 {field} is malformed")
    _require(plan.get("adjacent_untouched_records") == ["b3cj:t2:022:0x0072", "b3cj:t2:022:0x0098"], "M4.1 adjacent records changed")
    _require(plan.get("adjacent_untouched_glyph_id") == "0x84c", "M4.1 adjacent glyph changed")
    return plan


def load_source_rows(path: pathlib.Path) -> dict[str, dict[str, object]]:
    _require(sha256_file(path) == EXPECTED_SOURCE_TABLE_SHA256, "source table SHA-256 mismatch")
    rows = M23.load_source_table(path, EXPECTED_SOURCE_TABLE_SHA256)
    return {str(key): value for key, value in rows.items()}


def validate_source_selection(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    record = plan["records"][0]
    assert isinstance(record, dict)
    row = source_rows.get(M4_TARGET_ID)
    _require(row is not None, "M4.1 selected source row is missing")
    _require(canonical_source_hash(str(row.get("source_text"))) == record["source_hash"], "M4.1 source hash mismatch")
    _require(row.get("raw_sha256") == record["source_raw_sha256"] and row.get("record_sha256") == record["source_record_sha256"], "M4.1 source byte hash mismatch")
    _require(int(row["provenance"]["resource_id"]) == 22 and _source_offset(row) == 0x4E, "M4.1 source provenance mismatch")
    _require(row.get("raw_length") == 12 and row.get("control_tokens") == ["0x0308", "0x0000"], "M4.1 source length/control mismatch")
    following = row.get("following_controls")
    _require(isinstance(following, list), "M4.1 following controls missing")
    _require([item.get("opcode") for item in following if isinstance(item, dict)] == ["0x0003", "0x0002", "0x0308"], "M4.1 following opcode mismatch")
    _require(not _contains_opaque(row.get("control_structure")) and not _contains_opaque(following), "M4.1 selected row contains opaque control")
    return dict(row)


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


def make_seed_ledger(plan: Mapping[str, object], source_row: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    context = plan["context"]
    targets = plan["targets"]
    assert isinstance(context, dict) and isinstance(targets, dict)
    target_values = {
        locale: {"text": targets[locale]["text"], "author": "Codex", "model": "gpt-5.6-luna"}
        for locale in ("zh-Hans", TARGET_LOCALE)
    }
    ledger = {
        "game": EXPECTED_GAME,
        "revision": EXPECTED_REVISION,
        "string_id": M4_TARGET_ID,
        "source_locale": str(source_row["locale"]),
        "source_hash": canonical_source_hash(str(source_row["source_text"])),
        "targets": target_values,
        "context": context,
        "terms": [],
        "status": "ai_draft",
        "review_notes": plan["review_notes"],
    }
    adapter = {
        "string_id": M4_TARGET_ID,
        "locale": str(source_row["locale"]),
        "text": str(source_row["source_text"]),
        "provenance": "B3CJ M4.1 local extractor adapter; temporary only",
    }
    return [ledger], [adapter]


def validate_working(plan: Mapping[str, object], source_row: Mapping[str, object], path: pathlib.Path) -> None:
    rows = load_jsonl(path)
    _require(len(rows) == 1 and rows[0].get("string_id") == M4_TARGET_ID, "M4.1 working file must contain exactly the selected record")
    row = rows[0]
    source = row.get("source")
    _require(isinstance(source, dict) and source.get("text") == source_row.get("source_text"), "M4.1 working source was not restored from local table")
    _require(row.get("game") == EXPECTED_GAME and row.get("revision") == EXPECTED_REVISION and row.get("status") == "ai_draft", "M4.1 working identity/status mismatch")
    targets = row.get("targets")
    expected = plan["targets"]
    _require(isinstance(targets, dict) and isinstance(expected, dict), "M4.1 working targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        _require(targets.get(locale, {}).get("text") == expected[locale]["text"], f"M4.1 working {locale} target mismatch")


def _target_payload(plan: Mapping[str, object], rom_data: bytes, font: Mapping[str, object]) -> bytes:
    allocations = {str(item["unicode"]): bytes.fromhex(str(item["code_unit"])) for item in plan["allocations"] if isinstance(item, dict)}
    units: list[bytes] = []
    target_text = str(plan["targets"][TARGET_LOCALE]["text"])
    for char in target_text:
        if char in allocations:
            units.append(allocations[char])
            continue
        raw = char.encode("shift_jis")
        _require(len(raw) == 2 and INSPECT_FONT.is_strict_shift_jis_pair(raw), f"M4.1 target char {char!r} is not a strict mapped code unit")
        lookup = INSPECT_FONT.lookup_code_unit(rom_data, raw, slot_count=int(font["slot_count"]), font_base_file_offset=int(font["font_base_file_offset"]))
        _require(lookup.get("status") == "mapped", f"M4.1 target char {char!r} has no existing mapped glyph")
        units.append(raw)
    expected = list(plan["target_contract"]["code_units"])
    _require([unit.hex() for unit in units] == expected, "M4.1 target code units drifted")
    payload = b"".join(units)
    _require(len(payload) == int(plan["target_contract"]["byte_length"]), "M4.1 target payload length drifted")
    return payload


def _apply_new_font(rom_data: bytes, patched: bytearray, plan: Mapping[str, object], font_source: pathlib.Path, source_units: set[bytes], font: Mapping[str, object]) -> list[dict[str, object]]:
    _require(sha256_file(font_source) == EXPECTED_FONT_SOURCE_SHA256, "M4.1 font source hash mismatch")
    codepoints = [ord(str(item["unicode"])) for item in plan["allocations"] if isinstance(item, dict)]
    glyphs = INSPECT_FONT.load_unifont_glyphs(font_source, codepoints)
    reports: list[dict[str, object]] = []
    for item in plan["allocations"]:
        assert isinstance(item, dict)
        raw = bytes.fromhex(str(item["code_unit"]))
        slot = parse_int(item["glyph_id"], f"{raw.hex()}.glyph_id")
        _require(raw not in source_units, f"M4.1 extension code unit {raw.hex()} collides with source corpus")
        lookup = INSPECT_FONT.lookup_code_unit(rom_data, raw, slot_count=int(font["slot_count"]), font_base_file_offset=int(font["font_base_file_offset"]))
        _require(lookup.get("status") == "fallback" and lookup.get("table_value") == "0x0000", f"M4.1 code unit {raw.hex()} is not an unused fallback")
        cell_offset = int(font["font_base_file_offset"]) + slot * INSPECT_FONT.FONT_CELL_SIZE
        old_cell = rom_data[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE]
        _require(old_cell == bytes(INSPECT_FONT.FONT_CELL_SIZE), f"M4.1 slot 0x{slot:x} is not blank")
        cell = INSPECT_FONT.unifont_bitmap_to_cell(glyphs[ord(str(item["unicode"]))])
        table_offset = int(str(lookup["table_entry_file_offset"]), 16)
        struct.pack_into("<H", patched, table_offset, slot + 1)
        patched[cell_offset : cell_offset + INSPECT_FONT.FONT_CELL_SIZE] = cell
        reports.append({"code_unit": raw.hex(), "unicode": str(item["unicode"]), "glyph_id": f"0x{slot:03x}", "table_entry_file_offset": f"0x{table_offset:x}", "cell_file_offset": f"0x{cell_offset:x}", "cell_sha256": sha256_bytes(cell)})
    return reports


def _reextract(
    clean_rom: bytes,
    final_rom: bytes,
    source_rows: Mapping[str, Mapping[str, object]],
    expected_targets: Mapping[str, bytes],
    adjacent_ids: set[str] | None = None,
) -> dict[str, object]:
    resource_ids = sorted({int(row["provenance"]["resource_id"]) for row in source_rows.values() if isinstance(row.get("provenance"), dict)})
    clean_resources = M25._decode_resources(clean_rom, resource_ids)
    final_resources = M25._decode_resources(final_rom, resource_ids)
    if adjacent_ids is None:
        adjacent_ids = {"b3cj:t2:024:0x0046", "b3cj:t2:024:0x0078", "b3cj:t2:022:0x0072", "b3cj:t2:022:0x0098"}
    reports: list[dict[str, object]] = []
    target_reports: list[dict[str, object]] = []
    adjacent_reports: list[dict[str, object]] = []
    total = 0
    untouched = 0
    for resource_id in resource_ids:
        _clean_resolved, clean_decoded, clean_consumed = clean_resources[resource_id]
        _final_resolved, final_decoded, final_consumed = final_resources[resource_id]
        reports.append({"resource_id": resource_id, "clean_stream_sha256": sha256_bytes(clean_decoded[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]), "final_stream_sha256": sha256_bytes(final_decoded[EXTRACT_STATIC.SCRIPT_HEADER_SIZE:]), "clean_compressed_size": clean_consumed, "final_compressed_size": final_consumed, "unchanged": clean_decoded == final_decoded})
        for string_id, source_row in source_rows.items():
            if int(source_row["provenance"]["resource_id"]) != resource_id:
                continue
            offset = _source_offset(source_row)
            raw_length = int(source_row["raw_length"])
            clean_record = M25._record_region(clean_decoded, offset, raw_length)
            final_record = M25._record_region(final_decoded, offset, raw_length)
            total += 1
            if string_id in expected_targets:
                _require(final_record == expected_targets[string_id], f"target re-extract mismatch for {string_id}")
                target_reports.append({"string_id": string_id, "resource_id": resource_id, "record_sha256": sha256_bytes(final_record), "payload_sha256": sha256_bytes(final_record[2:-2]), "record_byte_length": len(final_record)})
            else:
                _require(final_record == clean_record, f"untouched record changed for {string_id}")
                untouched += 1
            if string_id in adjacent_ids:
                adjacent_reports.append({"string_id": string_id, "record_sha256": sha256_bytes(final_record), "byte_identical_to_clean": final_record == clean_record})
    _require(total == 361 and len(target_reports) == len(expected_targets) and untouched == 361 - len(expected_targets), "cumulative re-extraction count mismatch")
    _require(len(adjacent_reports) == len(adjacent_ids) and all(item["byte_identical_to_clean"] for item in adjacent_reports), "adjacent untouched record proof incomplete")
    return {"records_total": total, "target_records": len(target_reports), "untouched_records": untouched, "target": target_reports, "adjacent_untouched": adjacent_reports, "resources": reports}


def build_batch(clean_rom: bytes, source_path: pathlib.Path, plan: Mapping[str, object], working_path: pathlib.Path, m25_working_path: pathlib.Path, font_source: pathlib.Path) -> tuple[bytes, dict[str, object]]:
    identity = INSPECT_FONT.verify_rom(clean_rom)
    _require(identity["sha256"] == EXPECTED_ROM_SHA256, "M4.1 clean ROM identity mismatch")
    INSPECT_FONT.verify_static_evidence(clean_rom)
    source_rows = load_source_rows(source_path)
    source_row = validate_source_selection(plan, source_rows)
    validate_working(plan, source_row, working_path)

    m25_plan = M25.load_plan(GAME_ROOT / "research" / "m2.5-batch-plan.json")
    m25_patched, m25_summary = M25.build_batch(clean_rom, source_path, font_source, m25_plan, m25_working_path)
    font = INSPECT_FONT.parse_font_resource(m25_patched)
    source_units, _metadata = INSPECT_FONT.source_code_units_from_jsonl(source_path)
    patched = bytearray(m25_patched)
    allocations = _apply_new_font(m25_patched, patched, plan, font_source, set(source_units), font)
    target_payload = _target_payload(plan, m25_patched, font)

    resolved = EXTRACT_STATIC.resolve_script_resource(m25_patched, 22)
    original_decoded, original_compressed_size = EXTRACT_STATIC.decode_lz77(m25_patched, int(resolved["payload_file_offset"]))
    offset = _source_offset(source_row)
    raw_length = int(source_row["raw_length"])
    original_record = M25._record_region(original_decoded, offset, raw_length)
    _require(sha256_bytes(original_record) == str(plan["records"][0]["source_record_sha256"]), "M4.1 source record bytes drifted")
    target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
    _require(len(target_record) == len(original_record), "M4.1 same-length record contract failed")
    decoded = bytearray(original_decoded)
    decoded[offset : offset + len(target_record)] = target_record
    compressed = M23.lz77_compress(bytes(decoded))
    span_bytes = int(resolved["span_units"]) * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
    _require(len(compressed) <= span_bytes, f"M4.1 resource 22 compressed output {len(compressed)} exceeds span {span_bytes}")
    payload_offset = int(resolved["payload_file_offset"])
    patched[payload_offset : payload_offset + span_bytes] = compressed + bytes(span_bytes - len(compressed))
    final_rom = bytes(patched)

    baseline_changed = {index for index, (before, after) in enumerate(zip(clean_rom, m25_patched)) if before != after}
    allowed = set(baseline_changed)
    for item in allocations:
        for start, size in ((int(item["table_entry_file_offset"], 16), 2), (int(item["cell_file_offset"], 16), INSPECT_FONT.FONT_CELL_SIZE)):
            allowed.update(range(start, start + size))
    allowed.update(range(payload_offset, payload_offset + span_bytes))
    changed = {index for index, (before, after) in enumerate(zip(clean_rom, final_rom)) if before != after}
    _require(changed.issubset(allowed), "M4.1 changed a byte outside cumulative font/resource spans")

    expected_targets: dict[str, bytes] = {}
    m25_resources = M25._decode_resources(m25_patched, [24])
    _m25_resolved, m25_decoded, _m25_consumed = m25_resources[24]
    m25_source_rows = [row for row in source_rows.values() if str(row["string_id"]) == M25_TARGET_ID]
    _require(len(m25_source_rows) == 1, "M2.5 target source row is missing from current table")
    m25_row = m25_source_rows[0]
    expected_targets[M25_TARGET_ID] = M25._record_region(m25_decoded, _source_offset(m25_row), int(m25_row["raw_length"]))
    expected_targets[M4_TARGET_ID] = target_record
    reextract = _reextract(clean_rom, final_rom, source_rows, expected_targets)

    post_font = INSPECT_FONT.parse_font_resource(final_rom)
    post_allocations: list[dict[str, object]] = []
    for item in plan["allocations"]:
        assert isinstance(item, dict)
        raw = bytes.fromhex(str(item["code_unit"]))
        expected_slot = parse_int(item["glyph_id"], f"{raw.hex()}.glyph_id")
        lookup = INSPECT_FONT.lookup_code_unit(final_rom, raw, slot_count=int(post_font["slot_count"]), font_base_file_offset=int(post_font["font_base_file_offset"]))
        _require(lookup.get("status") == "mapped" and int(lookup["glyph_id"]) == expected_slot, f"M4.1 post-build mapping failed for {raw.hex()}")
        post_allocations.append({"code_unit": raw.hex(), "unicode": str(item["unicode"]), "glyph_id": f"0x{expected_slot:03x}", "cell_sha256": lookup["cell_sha256"]})
    adjacent_glyph = parse_int(str(plan["adjacent_untouched_glyph_id"]), "adjacent_untouched_glyph_id")
    adjacent_clean = INSPECT_FONT.render_glyph(clean_rom, INSPECT_FONT.parse_font_resource(clean_rom), adjacent_glyph)
    adjacent_final = INSPECT_FONT.render_glyph(final_rom, post_font, adjacent_glyph)
    _require(adjacent_clean["cell_sha256"] == adjacent_final["cell_sha256"] and adjacent_clean["render_sha256"] == adjacent_final["render_sha256"], "M4.1 adjacent glyph changed")

    summary: dict[str, object] = {
        "batch_id": EXPECTED_BATCH_ID,
        "base_batch_id": "m2.5-prize-ui",
        "static_only": True,
        "runtime_qa": "pending",
        "translation_status": "ai_draft",
        "translated_string_ids": sorted(expected_targets),
        "new_translated_string_ids": [M4_TARGET_ID],
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "clean_rom_sha256": EXPECTED_ROM_SHA256,
        "target_sha256": sha256_bytes(final_rom),
        "target": {"locale": TARGET_LOCALE, "utf8_sha256": plan["targets"][TARGET_LOCALE]["utf8_sha256"], "byte_length": len(target_payload), "code_units": list(plan["target_contract"]["code_units"])},
        "font": {"new_allocations": allocations, "post_allocations": post_allocations, "adjacent_untouched_glyph": {"glyph_id": f"0x{adjacent_glyph:03x}", "cell_sha256": adjacent_final["cell_sha256"], "render_sha256": adjacent_final["render_sha256"]}, "font_base_file_offset": f"0x{int(post_font['font_base_file_offset']):x}", "cell_size": INSPECT_FONT.FONT_CELL_SIZE},
        "resource": {"resource_id": 22, "payload_file_offset": f"0x{payload_offset:x}", "span_bytes": span_bytes, "original_compressed_size": original_compressed_size, "new_compressed_size": len(compressed), "original_compressed_sha256": sha256_bytes(m25_patched[payload_offset : payload_offset + original_compressed_size]), "new_compressed_sha256": sha256_bytes(compressed), "repacked_in_original_span": True},
        "reextract": reextract,
        "m2_5_reextract": m25_summary["reextract"],
        "byte_level": {"changed_byte_count": len(changed), "changed_outside_cumulative_ranges": False, "all_361_records_reextracted": True},
        "boundary": "Cumulative static build only; no runtime screen/readability or release-patch claim.",
    }
    return final_rom, summary


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-jsonl", type=pathlib.Path, required=True)
    prepare.add_argument("--plan", type=pathlib.Path, required=True)
    prepare.add_argument("--ledger-output", type=pathlib.Path, required=True)
    prepare.add_argument("--source-adapter-output", type=pathlib.Path, required=True)
    build = subparsers.add_parser("build")
    build.add_argument("rom", type=pathlib.Path)
    build.add_argument("--source-jsonl", type=pathlib.Path, required=True)
    build.add_argument("--plan", type=pathlib.Path, required=True)
    build.add_argument("--working", type=pathlib.Path, required=True)
    build.add_argument("--m2-5-working", type=pathlib.Path, required=True)
    build.add_argument("--font-source", type=pathlib.Path, required=True)
    build.add_argument("--output", type=pathlib.Path, required=True)
    build.add_argument("--summary-output", type=pathlib.Path, required=True)
    build.add_argument("--bps-output", type=pathlib.Path)
    build.add_argument("--bps-applied-output", type=pathlib.Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        plan = load_plan(args.plan)
        if args.command == "prepare":
            source_rows = load_source_rows(args.source_jsonl)
            row = validate_source_selection(plan, source_rows)
            ledger, adapter = make_seed_ledger(plan, row)
            write_jsonl(args.ledger_output, ledger)
            write_jsonl(args.source_adapter_output, adapter)
            print(f"B3CJ_M4_1_PREPARE_OK records=1 ledger={args.ledger_output} source_adapter={args.source_adapter_output}")
            return 0
        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        patched, summary = build_batch(args.rom.read_bytes(), args.source_jsonl, plan, args.working, args.m2_5_working, args.font_source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = M25.run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M4_1_BUILD_OK records={len(summary['translated_string_ids'])} new_records={len(summary['new_translated_string_ids'])} changed_bytes={summary['byte_level']['changed_byte_count']} target_sha256={summary['target_sha256']}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"build_m4_1_batch.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
