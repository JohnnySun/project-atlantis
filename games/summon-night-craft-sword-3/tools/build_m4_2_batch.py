#!/usr/bin/env python3
"""Build the cumulative B3CJ M4.2 bounded warning-label batch.

M4.2 starts from the clean ROM, rebuilds the already-reviewed static M2.5 and
M4.1 slices in memory, then replaces one opaque-free resource-16 record with
an equal-length zh-TW label using only existing mapped glyphs.  It repacks
only the original resource span and rejects source, identity, control,
length, capacity, re-extraction, and changed-range drift.

ROMs, source tables, working ledgers, summaries, and BPS files are supplied
as ignored paths by the caller; this module never writes them implicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
M41_PATH = GAME_ROOT / "tools" / "build_m4_1_batch.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M41 = _load_module("b3cj_build_m4_1_for_m4_2", M41_PATH)
M25 = M41.M25
M23 = M41.M23
INSPECT_FONT = M41.INSPECT_FONT
EXTRACT_STATIC = M41.EXTRACT_STATIC

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_FONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
EXPECTED_BATCH_ID = "m4.2-warning-label"
M25_TARGET_ID = "b3cj:t2:024:0x0064"
M41_TARGET_ID = "b3cj:t2:022:0x004e"
M42_TARGET_ID = "b3cj:t2:016:0x001e"
TARGET_LOCALE = "zh-TW"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_int(value: object, field: str) -> int:
    return M41.parse_int(value, field)


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
    return M41._source_offset(row)


def _contains_opaque(value: object) -> bool:
    return M41._contains_opaque(value)


def load_plan(path: pathlib.Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "M4.2 plan root must be an object")
    plan = value
    _require(plan.get("plan_version") == 1, "unsupported M4.2 plan version")
    _require(plan.get("batch_id") == EXPECTED_BATCH_ID, "unexpected M4.2 batch id")
    _require(plan.get("game") == EXPECTED_GAME and plan.get("revision") == EXPECTED_REVISION, "M4.2 identity mismatch")
    _require(plan.get("source_table_sha256") == EXPECTED_SOURCE_TABLE_SHA256, "M4.2 source table hash mismatch")
    _require(plan.get("clean_rom_sha256") == EXPECTED_ROM_SHA256, "M4.2 clean ROM hash mismatch")
    _require(plan.get("font_source_sha256") == EXPECTED_FONT_SOURCE_SHA256, "M4.2 font source hash mismatch")
    _require(plan.get("target_locale") == TARGET_LOCALE and plan.get("status") == "ai_draft", "M4.2 target/status contract mismatch")

    context = plan.get("context")
    _require(isinstance(context, dict), "M4.2 context is missing")
    _require(context.get("max_width") == 5 and context.get("max_lines") == 1, "M4.2 layout contract mismatch")
    _require(context.get("control_codes") == ["0x0308", "0x0000"], "M4.2 text control contract mismatch")

    controls = plan.get("control_contract")
    _require(isinstance(controls, dict), "M4.2 control contract is missing")
    _require(controls.get("following_opcodes") == ["0x0308"], "M4.2 following controls changed")
    _require(controls.get("opaque_control_count") == 0, "M4.2 cannot contain opaque controls")

    targets = plan.get("targets")
    _require(isinstance(targets, dict), "M4.2 targets are missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets.get(locale)
        _require(isinstance(target, dict) and isinstance(target.get("text"), str), f"M4.2 {locale} target is malformed")
        _require(target.get("utf8_sha256") == sha256_bytes(str(target["text"]).encode("utf-8")), f"M4.2 {locale} target hash mismatch")

    contract = plan.get("target_contract")
    _require(isinstance(contract, dict), "M4.2 target contract is missing")
    _require(contract.get("byte_length") == 10, "M4.2 target length changed")
    _require(contract.get("code_units") == ["8c78", "8d90", "8149", "8140", "8140"], "M4.2 target code units changed")
    _require(contract.get("extension_units") == [] and contract.get("record_terminator") == "0x0000", "M4.2 extension contract changed")

    _require(plan.get("allocations") == [], "M4.2 must not allocate a new glyph")
    records = plan.get("records")
    _require(isinstance(records, list) and len(records) == 1, "M4.2 requires exactly one record")
    record = records[0]
    _require(isinstance(record, dict), "M4.2 record is malformed")
    _require(record.get("string_id") == M42_TARGET_ID and record.get("resource_id") == 16, "M4.2 record identity mismatch")
    _require(record.get("decompressed_offset") == "0x001e" and record.get("raw_length") == 10, "M4.2 record layout mismatch")
    for field in ("source_hash", "source_raw_sha256", "source_record_sha256"):
        _require(isinstance(record.get(field), str) and len(record[field]) == 64, f"M4.2 {field} is malformed")
    _require(plan.get("adjacent_untouched_records") == ["b3cj:t2:016:0x002c", "b3cj:t2:016:0x004a"], "M4.2 adjacent records changed")
    _require(plan.get("adjacent_untouched_glyph_id") == "0x096", "M4.2 adjacent glyph changed")
    return plan


def load_source_rows(path: pathlib.Path) -> dict[str, dict[str, object]]:
    _require(sha256_file(path) == EXPECTED_SOURCE_TABLE_SHA256, "source table SHA-256 mismatch")
    rows = M23.load_source_table(path, EXPECTED_SOURCE_TABLE_SHA256)
    return {str(key): value for key, value in rows.items()}


def validate_source_selection(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    record = plan["records"][0]
    assert isinstance(record, dict)
    row = source_rows.get(M42_TARGET_ID)
    _require(row is not None, "M4.2 selected source row is missing")
    _require(M41.canonical_source_hash(str(row.get("source_text"))) == record["source_hash"], "M4.2 source hash mismatch")
    _require(row.get("raw_sha256") == record["source_raw_sha256"] and row.get("record_sha256") == record["source_record_sha256"], "M4.2 source byte hash mismatch")
    provenance = row.get("provenance")
    _require(isinstance(provenance, dict) and int(provenance.get("resource_id")) == 16 and _source_offset(row) == 0x1E, "M4.2 source provenance mismatch")
    _require(row.get("raw_length") == 10 and row.get("control_tokens") == ["0x0308", "0x0000"], "M4.2 source control/length mismatch")
    following = row.get("following_controls")
    _require(isinstance(following, list), "M4.2 following controls missing")
    _require([item.get("opcode") for item in following if isinstance(item, dict)] == ["0x0308"], "M4.2 following opcode mismatch")
    _require(not _contains_opaque(row.get("control_structure")) and not _contains_opaque(following), "M4.2 selected row contains opaque control")
    return dict(row)


def make_seed_ledger(plan: Mapping[str, object], source_row: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    context = plan["context"]
    targets = plan["targets"]
    assert isinstance(context, dict) and isinstance(targets, dict)
    target_values = {locale: {"text": targets[locale]["text"], "author": "Codex", "model": "gpt-5.6-luna"} for locale in ("zh-Hans", TARGET_LOCALE)}
    ledger = {
        "game": EXPECTED_GAME,
        "revision": EXPECTED_REVISION,
        "string_id": M42_TARGET_ID,
        "source_locale": str(source_row["locale"]),
        "source_hash": M41.canonical_source_hash(str(source_row["source_text"])),
        "targets": target_values,
        "context": context,
        "terms": [],
        "status": "ai_draft",
        "review_notes": plan["review_notes"],
    }
    adapter = {
        "string_id": M42_TARGET_ID,
        "locale": str(source_row["locale"]),
        "text": str(source_row["source_text"]),
        "provenance": "B3CJ M4.2 local extractor adapter; temporary only",
    }
    return [ledger], [adapter]


def validate_working(plan: Mapping[str, object], source_row: Mapping[str, object], path: pathlib.Path) -> None:
    rows = load_jsonl(path)
    _require(len(rows) == 1 and rows[0].get("string_id") == M42_TARGET_ID, "M4.2 working file must contain exactly the selected record")
    row = rows[0]
    source = row.get("source")
    _require(isinstance(source, dict) and source.get("text") == source_row.get("source_text"), "M4.2 working source was not restored from local table")
    _require(row.get("game") == EXPECTED_GAME and row.get("revision") == EXPECTED_REVISION and row.get("status") == "ai_draft", "M4.2 working identity/status mismatch")
    targets = row.get("targets")
    expected = plan["targets"]
    _require(isinstance(targets, dict) and isinstance(expected, dict), "M4.2 working targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        _require(targets.get(locale, {}).get("text") == expected[locale]["text"], f"M4.2 working {locale} target mismatch")


def _target_payload(plan: Mapping[str, object], rom_data: bytes, font: Mapping[str, object]) -> bytes:
    target_text = str(plan["targets"][TARGET_LOCALE]["text"])
    payload = target_text.encode("shift_jis")
    _require(len(payload) == 10, "M4.2 target Shift-JIS length drifted")
    units = [payload[index : index + 2] for index in range(0, len(payload), 2)]
    _require([unit.hex() for unit in units] == list(plan["target_contract"]["code_units"]), "M4.2 target code units drifted")
    for unit in units:
        _require(INSPECT_FONT.is_strict_shift_jis_pair(unit), f"M4.2 target unit {unit.hex()} is not strict Shift-JIS")
        lookup = INSPECT_FONT.lookup_code_unit(rom_data, unit, slot_count=int(font["slot_count"]), font_base_file_offset=int(font["font_base_file_offset"]))
        _require(lookup.get("status") == "mapped", f"M4.2 target unit {unit.hex()} is not already mapped")
    return payload


def _record_from_rom(rom_data: bytes, source_row: Mapping[str, object]) -> bytes:
    resource_id = int(source_row["provenance"]["resource_id"])
    resolved, decoded, _used = M25._decode_resources(rom_data, [resource_id])[resource_id]
    _ = resolved
    return M25._record_region(decoded, _source_offset(source_row), int(source_row["raw_length"]))


def _adjacent_proof(clean_rom: bytes, final_rom: bytes, source_rows: Mapping[str, Mapping[str, object]], plan: Mapping[str, object]) -> dict[str, object]:
    reports: list[dict[str, object]] = []
    for string_id in plan["adjacent_untouched_records"]:
        assert isinstance(string_id, str)
        row = source_rows[string_id]
        clean_record = _record_from_rom(clean_rom, row)
        final_record = _record_from_rom(final_rom, row)
        reports.append({"string_id": string_id, "record_sha256": sha256_bytes(final_record), "byte_identical_to_clean": final_record == clean_record})
        _require(final_record == clean_record, f"M4.2 adjacent record changed: {string_id}")

    glyph_id = parse_int(plan["adjacent_untouched_glyph_id"], "adjacent_untouched_glyph_id")
    clean_font = INSPECT_FONT.parse_font_resource(clean_rom)
    final_font = INSPECT_FONT.parse_font_resource(final_rom)
    clean_render = INSPECT_FONT.render_glyph(clean_rom, clean_font, glyph_id)
    final_render = INSPECT_FONT.render_glyph(final_rom, final_font, glyph_id)
    _require(clean_render["cell_sha256"] == final_render["cell_sha256"] and clean_render["render_sha256"] == final_render["render_sha256"], "M4.2 adjacent glyph changed")
    return {"records": reports, "glyph": {"glyph_id": f"0x{glyph_id:03x}", "cell_sha256": final_render["cell_sha256"], "render_sha256": final_render["render_sha256"], "byte_identical_to_clean": True}}


def _existing_glyph_proof(clean_rom: bytes, final_rom: bytes, plan: Mapping[str, object]) -> list[dict[str, object]]:
    clean_font = INSPECT_FONT.parse_font_resource(clean_rom)
    final_font = INSPECT_FONT.parse_font_resource(final_rom)
    reports: list[dict[str, object]] = []
    for unit_hex in plan["target_contract"]["code_units"]:
        unit = bytes.fromhex(str(unit_hex))
        before = INSPECT_FONT.lookup_code_unit(clean_rom, unit, slot_count=int(clean_font["slot_count"]), font_base_file_offset=int(clean_font["font_base_file_offset"]))
        after = INSPECT_FONT.lookup_code_unit(final_rom, unit, slot_count=int(final_font["slot_count"]), font_base_file_offset=int(final_font["font_base_file_offset"]))
        _require(before.get("status") == "mapped" and after.get("status") == "mapped", f"M4.2 glyph mapping missing for {unit_hex}")
        _require(before.get("glyph_id") == after.get("glyph_id") and before.get("cell_sha256") == after.get("cell_sha256"), f"M4.2 existing glyph changed for {unit_hex}")
        reports.append({"code_unit": unit_hex, "glyph_id": f"0x{int(after['glyph_id']):03x}", "cell_sha256": after["cell_sha256"], "mapping_unchanged": True})
    return reports


def build_batch(clean_rom: bytes, source_path: pathlib.Path, plan: Mapping[str, object], working_path: pathlib.Path, m41_working_path: pathlib.Path, m25_working_path: pathlib.Path, font_source: pathlib.Path) -> tuple[bytes, dict[str, object]]:
    identity = INSPECT_FONT.verify_rom(clean_rom)
    _require(identity["sha256"] == EXPECTED_ROM_SHA256, "M4.2 clean ROM identity mismatch")
    INSPECT_FONT.verify_static_evidence(clean_rom)
    _require(sha256_file(font_source) == EXPECTED_FONT_SOURCE_SHA256, "M4.2 font source hash mismatch")
    source_rows = load_source_rows(source_path)
    source_row = validate_source_selection(plan, source_rows)
    validate_working(plan, source_row, working_path)

    m41_plan = M41.load_plan(GAME_ROOT / "research" / "m4.1-wood-chopping-plan.json")
    m41_patched, m41_summary = M41.build_batch(clean_rom, source_path, m41_plan, m41_working_path, m25_working_path, font_source)
    font = INSPECT_FONT.parse_font_resource(m41_patched)
    target_payload = _target_payload(plan, m41_patched, font)

    resolved = EXTRACT_STATIC.resolve_script_resource(m41_patched, 16)
    original_decoded, original_compressed_size = EXTRACT_STATIC.decode_lz77(m41_patched, int(resolved["payload_file_offset"]))
    offset = _source_offset(source_row)
    raw_length = int(source_row["raw_length"])
    original_record = M25._record_region(original_decoded, offset, raw_length)
    _require(sha256_bytes(original_record) == str(plan["records"][0]["source_record_sha256"]), "M4.2 source record bytes drifted")
    target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
    _require(len(target_record) == len(original_record) == 14, "M4.2 same-length record contract failed")
    decoded = bytearray(original_decoded)
    decoded[offset : offset + len(target_record)] = target_record
    compressed = M23.lz77_compress(bytes(decoded))
    span_bytes = int(resolved["span_units"]) * EXTRACT_STATIC.SCRIPT_TABLE_POINTER_SCALE
    _require(len(compressed) <= span_bytes, f"M4.2 resource 16 compressed output {len(compressed)} exceeds span {span_bytes}")
    payload_offset = int(resolved["payload_file_offset"])
    patched = bytearray(m41_patched)
    patched[payload_offset : payload_offset + span_bytes] = compressed + bytes(span_bytes - len(compressed))
    final_rom = bytes(patched)

    baseline_changed = {index for index, (before, after) in enumerate(zip(clean_rom, m41_patched)) if before != after}
    allowed = set(baseline_changed)
    allowed.update(range(payload_offset, payload_offset + span_bytes))
    changed = {index for index, (before, after) in enumerate(zip(clean_rom, final_rom)) if before != after}
    _require(changed.issubset(allowed), "M4.2 changed a byte outside cumulative font/resource ranges")

    expected_targets: dict[str, bytes] = {}
    for target_id in (M25_TARGET_ID, M41_TARGET_ID):
        expected_targets[target_id] = _record_from_rom(final_rom, source_rows[target_id])
    expected_targets[M42_TARGET_ID] = target_record
    reextract = M41._reextract(clean_rom, final_rom, source_rows, expected_targets)
    adjacent = _adjacent_proof(clean_rom, final_rom, source_rows, plan)
    glyphs = _existing_glyph_proof(clean_rom, final_rom, plan)

    summary: dict[str, object] = {
        "batch_id": EXPECTED_BATCH_ID,
        "base_batch_id": "m4.1-wood-chopping-rank",
        "static_only": True,
        "runtime_qa": "pending",
        "translation_status": "ai_draft",
        "translated_string_ids": sorted(expected_targets),
        "new_translated_string_ids": [M42_TARGET_ID],
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "clean_rom_sha256": EXPECTED_ROM_SHA256,
        "target_sha256": sha256_bytes(final_rom),
        "target": {"locale": TARGET_LOCALE, "utf8_sha256": plan["targets"][TARGET_LOCALE]["utf8_sha256"], "byte_length": len(target_payload), "code_units": list(plan["target_contract"]["code_units"])},
        "font": {"new_allocations": [], "existing_mapped_glyphs": glyphs, "adjacent_untouched_glyph": adjacent["glyph"], "font_base_file_offset": f"0x{int(font['font_base_file_offset']):x}", "cell_size": INSPECT_FONT.FONT_CELL_SIZE},
        "resource": {"resource_id": 16, "payload_file_offset": f"0x{payload_offset:x}", "span_bytes": span_bytes, "original_compressed_size": original_compressed_size, "new_compressed_size": len(compressed), "original_compressed_sha256": sha256_bytes(m41_patched[payload_offset : payload_offset + original_compressed_size]), "new_compressed_sha256": sha256_bytes(compressed), "repacked_in_original_span": True},
        "reextract": reextract,
        "adjacent_untouched": adjacent,
        "m4_1_reextract": m41_summary["reextract"],
        "byte_level": {"changed_byte_count": len(changed), "changed_outside_cumulative_ranges": False, "all_361_records_reextracted": True},
        "rejected_candidate": {"string_id": "b3cj:t2:022:0x0098", "resource_id": 22, "candidate_compressed_size": 500, "span_bytes": 496, "reason": "capacity_guard"},
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
            print(f"B3CJ_M4_2_PREPARE_OK records=1 ledger={args.ledger_output} source_adapter={args.source_adapter_output}")
            return 0
        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        patched, summary = build_batch(args.rom.read_bytes(), args.source_jsonl, plan, args.working, args.m4_1_working, args.m2_5_working, args.font_source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = M25.run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M4_2_BUILD_OK records={len(summary['translated_string_ids'])} new_records={len(summary['new_translated_string_ids'])} changed_bytes={summary['byte_level']['changed_byte_count']} target_sha256={summary['target_sha256']}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"build_m4_2_batch.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
