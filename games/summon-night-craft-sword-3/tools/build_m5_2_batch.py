#!/usr/bin/env python3
"""Build the cumulative B3CJ M5.2 resource-24 relocation batch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
M43_PATH = GAME_ROOT / "tools" / "build_m4_3_batch.py"
M51_PATH = GAME_ROOT / "tools" / "relocate_resource_poc.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M43 = _load_module("b3cj_build_m4_3_for_m5_2", M43_PATH)
M51 = _load_module("b3cj_relocate_for_m5_2", M51_PATH)
M41 = M43.M41
M25 = M43.M25
M23 = M43.M23
INSPECT_FONT = M43.INSPECT_FONT
EXTRACT_STATIC = M43.EXTRACT_STATIC

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_FONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
EXPECTED_BATCH_ID = "m5.2-reward-relocation"
M25_TARGET_ID = "b3cj:t2:024:0x0064"
M41_TARGET_ID = "b3cj:t2:022:0x004e"
M42_TARGET_ID = "b3cj:t2:016:0x001e"
M43_TARGET_ID = "b3cj:t2:025:0x0b6e"
M52_TARGET_ID = "b3cj:t2:024:0x0078"
TARGET_LOCALE = "zh-TW"
DESTINATION = 0x1FBB1FC
DESTINATION_SPAN_UNITS = 0x60
ALLOWED_SLOT_FIRST = 0x845
ALLOWED_SLOT_LAST = 0x85F


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_int(value: object, field: str) -> int:
    return M43.parse_int(value, field)


def load_jsonl(path: pathlib.Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not an object")
        rows.append(value)
    return rows


def write_jsonl(path: pathlib.Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _source_offset(row: Mapping[str, object]) -> int:
    return M43._source_offset(row)


def _contains_opaque(value: object) -> bool:
    return M43._contains_opaque(value)


def load_plan(path: pathlib.Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(plan, dict), "M5.2 plan root is not an object")
    _require(plan.get("plan_version") == 1 and plan.get("batch_id") == EXPECTED_BATCH_ID, "M5.2 plan version/batch mismatch")
    _require(plan.get("game") == EXPECTED_GAME and plan.get("revision") == EXPECTED_REVISION, "M5.2 identity mismatch")
    _require(plan.get("source_table_sha256") == EXPECTED_SOURCE_TABLE_SHA256 and plan.get("clean_rom_sha256") == EXPECTED_ROM_SHA256 and plan.get("font_source_sha256") == EXPECTED_FONT_SOURCE_SHA256, "M5.2 fixed hash contract changed")
    _require(plan.get("target_locale") == TARGET_LOCALE and plan.get("status") == "ai_draft", "M5.2 target/status contract changed")
    context = plan.get("context")
    _require(isinstance(context, dict) and context.get("max_width") == 6 and context.get("max_lines") == 1 and context.get("control_codes") == ["0x0308", "0x0000"], "M5.2 layout/control contract changed")
    controls = plan.get("control_contract")
    _require(isinstance(controls, dict) and controls.get("following_opcodes") == ["0x0308"] and controls.get("opaque_control_count") == 0, "M5.2 following control contract changed")
    targets = plan.get("targets")
    _require(isinstance(targets, dict), "M5.2 targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets.get(locale)
        _require(isinstance(target, dict) and isinstance(target.get("text"), str), f"M5.2 {locale} target malformed")
        _require(target.get("utf8_sha256") == sha256_bytes(str(target["text"]).encode("utf-8")), f"M5.2 {locale} target hash drifted")
    contract = plan.get("target_contract")
    _require(isinstance(contract, dict) and contract.get("byte_length") == 12 and contract.get("code_units") == ["93c1", "ec65", "8140", "8f64", "8be0", "ec6e"], "M5.2 target code-unit contract changed")
    _require(contract.get("extension_units") == ["ec65", "ec6e"] and contract.get("inherited_extension_units") == ["ec65"] and contract.get("record_terminator") == "0x0000", "M5.2 extension contract changed")
    allocations = plan.get("allocations")
    _require(isinstance(allocations, list) and len(allocations) == 1, "M5.2 requires one allocation")
    item = allocations[0]
    _require(isinstance(item, dict) and item.get("code_unit") == "ec6e" and item.get("unicode") == "礦" and item.get("glyph_id") == "0x84d" and item.get("status") == "m5.2_ai_draft", "M5.2 allocation changed")
    _require(ALLOWED_SLOT_FIRST <= parse_int(item["glyph_id"], "glyph_id") <= ALLOWED_SLOT_LAST and not INSPECT_FONT.is_strict_shift_jis_pair(bytes.fromhex("ec6e")), "M5.2 allocation is not fail-closed")
    inherited = plan.get("inherited_mappings")
    _require(inherited == [{"code_unit": "ec65", "unicode": "獎", "glyph_id": "0x848", "source_batch": "m2.5-prize-ui"}], "M5.2 inherited mapping changed")
    records = plan.get("records")
    _require(isinstance(records, list) and len(records) == 1, "M5.2 requires one record")
    record = records[0]
    _require(isinstance(record, dict) and record.get("string_id") == M52_TARGET_ID and record.get("resource_id") == 24 and record.get("decompressed_offset") == "0x0078" and record.get("raw_length") == 12, "M5.2 record layout changed")
    for field in ("source_hash", "source_raw_sha256", "source_record_sha256"):
        _require(isinstance(record.get(field), str) and len(record[field]) == 64, f"M5.2 {field} malformed")
    _require(plan.get("adjacent_untouched_records") == ["b3cj:t2:024:0x0046", "b3cj:t2:024:0x0088"] and plan.get("adjacent_untouched_glyph_id") == "0x048", "M5.2 adjacent proof changed")
    relocation = plan.get("relocation")
    _require(isinstance(relocation, dict) and relocation.get("destination_file_offset") == "0x1fbb1fc" and relocation.get("span_units") == "0x60" and relocation.get("span_bytes") == 1536 and relocation.get("pointer_unit_bytes") == 16, "M5.2 relocation contract changed")
    return plan


def load_source_rows(path: pathlib.Path) -> dict[str, dict[str, object]]:
    _require(sha256_file(path) == EXPECTED_SOURCE_TABLE_SHA256, "source table SHA-256 mismatch")
    rows = M23.load_source_table(path, EXPECTED_SOURCE_TABLE_SHA256)
    return {str(key): value for key, value in rows.items()}


def validate_source_selection(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    spec = plan["records"][0]
    assert isinstance(spec, dict)
    row = source_rows.get(M52_TARGET_ID)
    _require(row is not None, "M5.2 source row missing")
    _require(M43.M41.canonical_source_hash(str(row.get("source_text"))) == spec["source_hash"], "M5.2 source hash mismatch")
    _require(row.get("raw_sha256") == spec["source_raw_sha256"] and row.get("record_sha256") == spec["source_record_sha256"], "M5.2 source byte hashes mismatch")
    provenance = row.get("provenance")
    _require(isinstance(provenance, dict) and int(provenance.get("resource_id")) == 24 and _source_offset(row) == 0x78, "M5.2 source provenance mismatch")
    _require(row.get("raw_length") == 12 and row.get("control_tokens") == ["0x0308", "0x0000"], "M5.2 source length/control mismatch")
    following = row.get("following_controls")
    _require(isinstance(following, list) and [item.get("opcode") for item in following if isinstance(item, dict)] == ["0x0308"], "M5.2 following opcode mismatch")
    _require(not _contains_opaque(row.get("control_structure")) and not _contains_opaque(following), "M5.2 selected row contains opaque control")
    return dict(row)


def make_seed_ledger(plan: Mapping[str, object], source_row: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    context = plan["context"]
    targets = plan["targets"]
    assert isinstance(context, dict) and isinstance(targets, dict)
    target_values = {locale: {"text": targets[locale]["text"], "author": "Codex", "model": "gpt-5.6-luna"} for locale in ("zh-Hans", TARGET_LOCALE)}
    ledger = {"game": EXPECTED_GAME, "revision": EXPECTED_REVISION, "string_id": M52_TARGET_ID, "source_locale": str(source_row["locale"]), "source_hash": M43.M41.canonical_source_hash(str(source_row["source_text"])), "targets": target_values, "context": context, "terms": [], "status": "ai_draft", "review_notes": plan["review_notes"]}
    adapter = {"string_id": M52_TARGET_ID, "locale": str(source_row["locale"]), "text": str(source_row["source_text"]), "provenance": "B3CJ M5.2 local extractor adapter; temporary only"}
    return [ledger], [adapter]


def validate_working(plan: Mapping[str, object], source_row: Mapping[str, object], path: pathlib.Path) -> None:
    rows = load_jsonl(path)
    _require(len(rows) == 1 and rows[0].get("string_id") == M52_TARGET_ID, "M5.2 working record mismatch")
    row = rows[0]
    _require(isinstance(row.get("source"), dict) and row["source"].get("text") == source_row.get("source_text"), "M5.2 working source was not restored")
    _require(row.get("game") == EXPECTED_GAME and row.get("revision") == EXPECTED_REVISION and row.get("status") == "ai_draft", "M5.2 working identity/status mismatch")
    targets = row.get("targets")
    expected = plan["targets"]
    _require(isinstance(targets, dict) and isinstance(expected, dict), "M5.2 working targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        _require(targets.get(locale, {}).get("text") == expected[locale]["text"], f"M5.2 working {locale} target mismatch")


def _target_payload(plan: Mapping[str, object], rom_data: bytes, font: Mapping[str, object]) -> bytes:
    local_alloc = {"礦": bytes.fromhex("ec6e")}
    inherited = {"獎": bytes.fromhex("ec65")}
    units: list[bytes] = []
    for char in str(plan["targets"][TARGET_LOCALE]["text"]):
        if char in local_alloc:
            units.append(local_alloc[char])
        elif char in inherited:
            unit = inherited[char]
            lookup = INSPECT_FONT.lookup_code_unit(rom_data, unit, slot_count=int(font["slot_count"]), font_base_file_offset=int(font["font_base_file_offset"]))
            _require(lookup.get("status") == "mapped" and int(lookup["glyph_id"]) == 0x848, "M5.2 inherited glyph mapping is not present")
            units.append(unit)
        else:
            raw = char.encode("shift_jis")
            _require(len(raw) == 2 and INSPECT_FONT.is_strict_shift_jis_pair(raw), f"M5.2 target char {char!r} is not strict Shift-JIS")
            lookup = INSPECT_FONT.lookup_code_unit(rom_data, raw, slot_count=int(font["slot_count"]), font_base_file_offset=int(font["font_base_file_offset"]))
            _require(lookup.get("status") == "mapped", f"M5.2 target char {char!r} is not mapped")
            units.append(raw)
    _require([unit.hex() for unit in units] == list(plan["target_contract"]["code_units"]), "M5.2 target code units drifted")
    payload = b"".join(units)
    _require(len(payload) == 12, "M5.2 target payload length drifted")
    return payload


def _record_from_rom(rom_data: bytes, row: Mapping[str, object]) -> bytes:
    return M43._record_from_rom(rom_data, row)


def _adjacent_proof(clean_rom: bytes, final_rom: bytes, source_rows: Mapping[str, Mapping[str, object]], plan: Mapping[str, object]) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for string_id in plan["adjacent_untouched_records"]:
        row = source_rows[str(string_id)]
        before = _record_from_rom(clean_rom, row)
        after = _record_from_rom(final_rom, row)
        _require(before == after, f"M5.2 adjacent record changed: {string_id}")
        records.append({"string_id": string_id, "record_sha256": sha256_bytes(after), "byte_identical_to_clean": True})
    glyph_id = parse_int(plan["adjacent_untouched_glyph_id"], "adjacent_untouched_glyph_id")
    before_glyph = INSPECT_FONT.render_glyph(clean_rom, INSPECT_FONT.parse_font_resource(clean_rom), glyph_id)
    after_glyph = INSPECT_FONT.render_glyph(final_rom, INSPECT_FONT.parse_font_resource(final_rom), glyph_id)
    _require(before_glyph["cell_sha256"] == after_glyph["cell_sha256"] and before_glyph["render_sha256"] == after_glyph["render_sha256"], "M5.2 adjacent glyph changed")
    return {"records": records, "glyph": {"glyph_id": f"0x{glyph_id:03x}", "cell_sha256": after_glyph["cell_sha256"], "render_sha256": after_glyph["render_sha256"], "byte_identical_to_clean": True}}


def _font_proof(clean_rom: bytes, final_rom: bytes, plan: Mapping[str, object]) -> dict[str, object]:
    clean_font = INSPECT_FONT.parse_font_resource(clean_rom)
    final_font = INSPECT_FONT.parse_font_resource(final_rom)
    raw = bytes.fromhex("ec6e")
    clean_lookup = INSPECT_FONT.lookup_code_unit(clean_rom, raw, slot_count=int(clean_font["slot_count"]), font_base_file_offset=int(clean_font["font_base_file_offset"]))
    final_lookup = INSPECT_FONT.lookup_code_unit(final_rom, raw, slot_count=int(final_font["slot_count"]), font_base_file_offset=int(final_font["font_base_file_offset"]))
    _require(clean_lookup.get("status") == "fallback" and clean_lookup.get("table_value") == "0x0000", "M5.2 clean extension unit is not fallback")
    _require(final_lookup.get("status") == "mapped" and int(final_lookup["glyph_id"]) == 0x84D, "M5.2 new glyph did not map to 0x84d")
    existing: list[dict[str, object]] = []
    for unit_hex in ("93c1", "ec65", "8140", "8f64", "8be0"):
        unit = bytes.fromhex(unit_hex)
        before = INSPECT_FONT.lookup_code_unit(clean_rom, unit, slot_count=int(clean_font["slot_count"]), font_base_file_offset=int(clean_font["font_base_file_offset"]))
        after = INSPECT_FONT.lookup_code_unit(final_rom, unit, slot_count=int(final_font["slot_count"]), font_base_file_offset=int(final_font["font_base_file_offset"]))
        _require(before.get("status") == "mapped" and after.get("glyph_id") == before.get("glyph_id") and after.get("cell_sha256") == before.get("cell_sha256"), f"M5.2 inherited/existing glyph changed for {unit_hex}")
        existing.append({"code_unit": unit_hex, "glyph_id": f"0x{int(after['glyph_id']):03x}", "cell_sha256": after["cell_sha256"], "mapping_unchanged": True})
    return {"new_allocation": {"code_unit": "ec6e", "unicode": "礦", "glyph_id": "0x84d", "cell_sha256": final_lookup["cell_sha256"], "mapping_unchanged_from_clean_fallback": True}, "existing_mapped_glyphs": existing}


def build_batch(clean_rom: bytes, source_path: pathlib.Path, plan: Mapping[str, object], working_path: pathlib.Path, m43_working_path: pathlib.Path, m42_working_path: pathlib.Path, m41_working_path: pathlib.Path, m25_working_path: pathlib.Path, font_source: pathlib.Path) -> tuple[bytes, dict[str, object]]:
    identity = INSPECT_FONT.verify_rom(clean_rom)
    _require(identity["sha256"] == EXPECTED_ROM_SHA256, "M5.2 clean ROM identity mismatch")
    INSPECT_FONT.verify_static_evidence(clean_rom)
    _require(sha256_file(font_source) == EXPECTED_FONT_SOURCE_SHA256, "M5.2 font source hash mismatch")
    source_rows = load_source_rows(source_path)
    source_row = validate_source_selection(plan, source_rows)
    validate_working(plan, source_row, working_path)

    m43_plan = M43.load_plan(GAME_ROOT / "research" / "m4.3-ellipsis-label-plan.json")
    m43_rom, m43_summary = M43.build_batch(clean_rom, source_path, m43_plan, m43_working_path, m42_working_path, m41_working_path, m25_working_path, font_source)
    font = INSPECT_FONT.parse_font_resource(m43_rom)
    source_units, _metadata = INSPECT_FONT.source_code_units_from_jsonl(source_path)
    patched = bytearray(m43_rom)
    allocations = M41._apply_new_font(m43_rom, patched, plan, font_source, set(source_units), font)
    font_rom = bytes(patched)
    target_payload = _target_payload(plan, font_rom, INSPECT_FONT.parse_font_resource(font_rom))

    resolved = EXTRACT_STATIC.resolve_script_resource(font_rom, 24)
    original_decoded, original_compressed_size = EXTRACT_STATIC.decode_lz77(font_rom, int(resolved["payload_file_offset"]))
    offset = _source_offset(source_row)
    original_record = M25._record_region(original_decoded, offset, int(source_row["raw_length"]))
    _require(sha256_bytes(original_record) == str(plan["records"][0]["source_record_sha256"]), "M5.2 source record bytes drifted")
    target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
    _require(len(target_record) == len(original_record) == 16, "M5.2 same-length record contract failed")
    decoded = bytearray(original_decoded)
    decoded[offset : offset + len(target_record)] = target_record
    compressed = M23.lz77_compress(bytes(decoded))
    span_units = DESTINATION_SPAN_UNITS
    span_bytes = span_units * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
    _require(len(compressed) <= span_bytes, f"M5.2 relocated resource compressed output {len(compressed)} exceeds span {span_bytes}")
    destination_report = M51.validate_destination(font_rom, DESTINATION, span_bytes)
    table_offset = int(resolved["directory_file_offset"])
    relative_bytes = DESTINATION - EXTRACT_STATIC.SCRIPT_TABLE_FILE_OFFSET
    _require(relative_bytes % EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE == 0, "M5.2 relocation pointer alignment failed")
    relative_units = relative_bytes // EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
    struct.pack_into("<I", patched, table_offset, relative_units)
    struct.pack_into("<I", patched, table_offset + 4, span_units)
    patched[DESTINATION : DESTINATION + span_bytes] = compressed + bytes(span_bytes - len(compressed))
    final_rom = bytes(patched)
    redirected = EXTRACT_STATIC.resolve_script_resource(final_rom, 24)
    _require(int(redirected["payload_file_offset"]) == DESTINATION and int(redirected["span_units"]) == span_units, "M5.2 directory redirect did not persist")
    redirected_decoded, redirected_size = EXTRACT_STATIC.decode_lz77(final_rom, DESTINATION)
    _require(redirected_decoded == bytes(decoded) and redirected_size == len(compressed), "M5.2 relocated decode mismatch")

    baseline_changed = {index for index, (before, after) in enumerate(zip(clean_rom, m43_rom)) if before != after}
    allowed = set(baseline_changed)
    for item in allocations:
        allowed.update(range(int(item["table_entry_file_offset"], 16), int(item["table_entry_file_offset"], 16) + 2))
        allowed.update(range(int(item["cell_file_offset"], 16), int(item["cell_file_offset"], 16) + INSPECT_FONT.FONT_CELL_SIZE))
    allowed.update(range(table_offset, table_offset + 8))
    allowed.update(range(DESTINATION, DESTINATION + span_bytes))
    changed = {index for index, (before, after) in enumerate(zip(clean_rom, final_rom)) if before != after}
    _require(changed.issubset(allowed), "M5.2 changed a byte outside cumulative font/pointer/resource ranges")

    expected_targets = {target_id: _record_from_rom(final_rom, source_rows[target_id]) for target_id in (M25_TARGET_ID, M41_TARGET_ID, M42_TARGET_ID, M43_TARGET_ID)}
    expected_targets[M52_TARGET_ID] = target_record
    reextract = M41._reextract(
        clean_rom,
        final_rom,
        source_rows,
        expected_targets,
        adjacent_ids={"b3cj:t2:024:0x0046", "b3cj:t2:022:0x0072", "b3cj:t2:022:0x0098"},
    )
    adjacent = _adjacent_proof(clean_rom, final_rom, source_rows, plan)
    font_proof = _font_proof(m43_rom, final_rom, plan)
    summary: dict[str, object] = {
        "batch_id": EXPECTED_BATCH_ID,
        "base_batch_id": "m4.3-ellipsis-label",
        "static_only": True,
        "runtime_qa": "pending",
        "translation_status": "ai_draft",
        "translated_string_ids": sorted(expected_targets),
        "new_translated_string_ids": [M52_TARGET_ID],
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "clean_rom_sha256": EXPECTED_ROM_SHA256,
        "target_sha256": sha256_bytes(final_rom),
        "target": {"locale": TARGET_LOCALE, "utf8_sha256": plan["targets"][TARGET_LOCALE]["utf8_sha256"], "byte_length": len(target_payload), "code_units": list(plan["target_contract"]["code_units"])},
        "font": {"new_allocations": allocations, "proof": font_proof, "adjacent_untouched_glyph": adjacent["glyph"], "font_base_file_offset": f"0x{int(font['font_base_file_offset']):x}", "cell_size": INSPECT_FONT.FONT_CELL_SIZE},
        "resource": {"resource_id": 24, "old_payload_file_offset": f"0x{int(resolved['payload_file_offset']):x}", "new_payload_file_offset": f"0x{DESTINATION:x}", "old_span_bytes": int(resolved["span_units"]) * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE, "new_span_bytes": span_bytes, "original_compressed_size": original_compressed_size, "new_compressed_size": len(compressed), "new_compressed_sha256": sha256_bytes(compressed), "repacked_at_relocated_pointer": True},
        "pointer": {"directory_file_offset": f"0x{table_offset:x}", "old_relative_units": f"0x{int(resolved['relative_units']):x}", "new_relative_units": f"0x{relative_units:x}", "old_span_units": int(resolved["span_units"]), "new_span_units": span_units, "destination_guard": destination_report},
        "reextract": reextract,
        "adjacent_untouched": adjacent,
        "m4_3_reextract": m43_summary["reextract"],
        "byte_level": {"changed_byte_count": len(changed), "changed_outside_cumulative_ranges": False, "all_361_records_reextracted": True},
        "boundary": "Cumulative static translation with one relocated resource; no runtime screen/readability or release-patch claim.",
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
    build.add_argument("--m4-3-working", type=pathlib.Path, required=True)
    build.add_argument("--m4-2-working", type=pathlib.Path, required=True)
    build.add_argument("--m4-1-working", type=pathlib.Path, required=True)
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
            print(f"B3CJ_M5_2_PREPARE_OK records=1 ledger={args.ledger_output} source_adapter={args.source_adapter_output}")
            return 0
        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        patched, summary = build_batch(args.rom.read_bytes(), args.source_jsonl, plan, args.working, args.m4_3_working, args.m4_2_working, args.m4_1_working, args.m2_5_working, args.font_source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = M25.run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M5_2_BUILD_OK records={len(summary['translated_string_ids'])} new_records={len(summary['new_translated_string_ids'])} changed_bytes={summary['byte_level']['changed_byte_count']} target_sha256={summary['target_sha256']}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"build_m5_2_batch.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
