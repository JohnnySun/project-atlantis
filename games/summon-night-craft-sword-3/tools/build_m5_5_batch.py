#!/usr/bin/env python3
"""Build the cumulative B3CJ M5.5 third repeated prize-header batch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
from typing import Any, Iterable, Mapping


GAME_ROOT = pathlib.Path(__file__).resolve().parents[1]
M54_PATH = GAME_ROOT / "tools" / "build_m5_4_batch.py"


def _load_module(name: str, path: pathlib.Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M54 = _load_module("b3cj_build_m5_4_for_m5_5", M54_PATH)
M53 = M54.M53
M52 = M54.M52
M41 = M54.M41
M25 = M54.M25
EXTRACT_STATIC = M54.EXTRACT_STATIC
INSPECT_FONT = M54.INSPECT_FONT

EXPECTED_GAME = "summon-night-craft-sword-3"
EXPECTED_REVISION = "B3CJ"
EXPECTED_SOURCE_TABLE_SHA256 = "a050790267679a35b1300f8ed3056271b6c481124790e9249484ce9d1d7966e3"
EXPECTED_ROM_SHA256 = "39bc4cf448106aa4b8cdde235632ffb57432c4b1919c8843510b70b3787fad2d"
EXPECTED_FONT_SOURCE_SHA256 = "2ae5311c8e123e9e85f5331cd012aa99757071df23243f1487fdbf8f3acd86be"
EXPECTED_BATCH_ID = "m5.5-repeated-prize-header"
M55_TARGET_ID = "b3cj:t2:024:0x01f0"
TARGET_LOCALE = "zh-TW"
DESTINATION = 0x1FBB1FC
DESTINATION_SPAN_UNITS = 0x60
DESTINATION_SPAN_BYTES = DESTINATION_SPAN_UNITS * 16


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_int(value: object, field: str) -> int:
    return M54.parse_int(value, field)


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


def load_plan(path: pathlib.Path) -> dict[str, object]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(plan, dict), "M5.5 plan root is not an object")
    _require(plan.get("plan_version") == 1 and plan.get("batch_id") == EXPECTED_BATCH_ID, "M5.5 plan version/batch mismatch")
    _require(plan.get("game") == EXPECTED_GAME and plan.get("revision") == EXPECTED_REVISION, "M5.5 identity mismatch")
    _require(plan.get("source_table_sha256") == EXPECTED_SOURCE_TABLE_SHA256 and plan.get("clean_rom_sha256") == EXPECTED_ROM_SHA256 and plan.get("font_source_sha256") == EXPECTED_FONT_SOURCE_SHA256, "M5.5 fixed hash contract changed")
    _require(plan.get("target_locale") == TARGET_LOCALE and plan.get("status") == "ai_draft", "M5.5 target/status contract changed")
    context = plan.get("context")
    _require(isinstance(context, dict) and context.get("max_width") == 7 and context.get("max_lines") == 1 and context.get("control_codes") == ["0x0308", "0x0000"], "M5.5 layout/control contract changed")
    controls = plan.get("control_contract")
    _require(isinstance(controls, dict) and controls.get("following_opcodes") == ["0x0309", "0x0308"] and controls.get("opaque_control_count") == 0, "M5.5 following control contract changed")
    targets = plan.get("targets")
    _require(isinstance(targets, dict), "M5.5 targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        target = targets.get(locale)
        _require(isinstance(target, dict) and isinstance(target.get("text"), str), f"M5.5 {locale} target malformed")
        _require(target.get("utf8_sha256") == sha256_bytes(str(target["text"]).encode("utf-8")), f"M5.5 {locale} target hash drifted")
    contract = plan.get("target_contract")
    _require(isinstance(contract, dict) and contract.get("byte_length") == 14 and contract.get("code_units") == ["ec64", "8e9f", "9349", "ec65", "9569", "ec66", "8163"], "M5.5 target code-unit contract changed")
    _require(contract.get("inherited_extension_units") == ["ec64", "ec65", "ec66"] and contract.get("record_terminator") == "0x0000", "M5.5 inherited extension contract changed")
    _require(plan.get("allocations") == [], "M5.5 must not allocate a new glyph")
    _require(plan.get("inherited_mappings") == [{"code_unit": "ec64", "unicode": "這", "glyph_id": "0x847", "source_batch": "m2.5-prize-ui"}, {"code_unit": "ec65", "unicode": "獎", "glyph_id": "0x848", "source_batch": "m2.5-prize-ui"}, {"code_unit": "ec66", "unicode": "是", "glyph_id": "0x849", "source_batch": "m2.5-prize-ui"}], "M5.5 inherited mapping changed")
    records = plan.get("records")
    _require(isinstance(records, list) and len(records) == 1, "M5.5 requires one record")
    record = records[0]
    _require(isinstance(record, dict) and record.get("string_id") == M55_TARGET_ID and record.get("resource_id") == 24 and record.get("decompressed_offset") == "0x01f0" and record.get("raw_length") == 14, "M5.5 record layout changed")
    for field in ("source_hash", "source_raw_sha256", "source_record_sha256"):
        _require(isinstance(record.get(field), str) and len(record[field]) == 64, f"M5.5 {field} malformed")
    _require(plan.get("adjacent_untouched_records") == ["b3cj:t2:024:0x01cc", "b3cj:t2:024:0x0204"] and plan.get("adjacent_untouched_glyph_id") == "0x048", "M5.5 adjacent proof changed")
    relocation = plan.get("relocation")
    _require(isinstance(relocation, dict) and relocation.get("destination_file_offset") == "0x1fbb1fc" and relocation.get("span_units") == "0x60" and relocation.get("span_bytes") == 1536 and relocation.get("pointer_unit_bytes") == 16 and relocation.get("inherited_from") == "m5.4-lottery-question", "M5.5 relocation contract changed")
    return plan


def load_source_rows(path: pathlib.Path) -> dict[str, dict[str, object]]:
    return M54.load_source_rows(path)


def validate_source_selection(plan: Mapping[str, object], source_rows: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    spec = plan["records"][0]
    assert isinstance(spec, dict)
    row = source_rows.get(M55_TARGET_ID)
    _require(row is not None, "M5.5 source row missing")
    _require(M41.canonical_source_hash(str(row.get("source_text"))) == spec["source_hash"], "M5.5 source hash mismatch")
    _require(row.get("raw_sha256") == spec["source_raw_sha256"] and row.get("record_sha256") == spec["source_record_sha256"], "M5.5 source byte hashes mismatch")
    provenance = row.get("provenance")
    _require(isinstance(provenance, dict) and int(provenance.get("resource_id")) == 24 and M52._source_offset(row) == 0x1F0, "M5.5 source provenance mismatch")
    _require(row.get("raw_length") == 14 and row.get("control_tokens") == ["0x0308", "0x0000"], "M5.5 source length/control mismatch")
    following = row.get("following_controls")
    _require(isinstance(following, list) and [item.get("opcode") for item in following if isinstance(item, dict)] == ["0x0309", "0x0308"], "M5.5 following opcode mismatch")
    _require(not M54.M53.M52._contains_opaque(row.get("control_structure")) and not M54.M53.M52._contains_opaque(following), "M5.5 selected row contains opaque control")
    return dict(row)


def make_seed_ledger(plan: Mapping[str, object], source_row: Mapping[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    context = plan["context"]
    targets = plan["targets"]
    assert isinstance(context, dict) and isinstance(targets, dict)
    target_values = {locale: {"text": targets[locale]["text"], "author": "Codex", "model": "gpt-5.6-luna"} for locale in ("zh-Hans", TARGET_LOCALE)}
    ledger = {"game": EXPECTED_GAME, "revision": EXPECTED_REVISION, "string_id": M55_TARGET_ID, "source_locale": str(source_row["locale"]), "source_hash": M41.canonical_source_hash(str(source_row["source_text"])), "targets": target_values, "context": context, "terms": [], "status": "ai_draft", "review_notes": plan["review_notes"]}
    adapter = {"string_id": M55_TARGET_ID, "locale": str(source_row["locale"]), "text": str(source_row["source_text"]), "provenance": "B3CJ M5.5 local extractor adapter; temporary only"}
    return [ledger], [adapter]


def validate_working(plan: Mapping[str, object], source_row: Mapping[str, object], path: pathlib.Path) -> None:
    rows = load_jsonl(path)
    _require(len(rows) == 1 and rows[0].get("string_id") == M55_TARGET_ID, "M5.5 working record mismatch")
    row = rows[0]
    _require(isinstance(row.get("source"), dict) and row["source"].get("text") == source_row.get("source_text"), "M5.5 working source was not restored")
    _require(row.get("game") == EXPECTED_GAME and row.get("revision") == EXPECTED_REVISION and row.get("status") == "ai_draft", "M5.5 working identity/status mismatch")
    targets = row.get("targets")
    expected = plan["targets"]
    _require(isinstance(targets, dict) and isinstance(expected, dict), "M5.5 working targets missing")
    for locale in ("zh-Hans", TARGET_LOCALE):
        _require(targets.get(locale, {}).get("text") == expected[locale]["text"], f"M5.5 working {locale} target mismatch")


def _record_from_rom(rom_data: bytes, source_row: Mapping[str, object]) -> bytes:
    return M54._record_from_rom(rom_data, source_row)


def _target_payload(rom_data: bytes) -> bytes:
    payload = M53._target_payload(rom_data)
    _require(len(payload) == 14 and payload.hex() == "ec648e9f9349ec659569ec668163", "M5.5 inherited target code units drifted")
    return payload


def _adjacent_proof(clean_rom: bytes, final_rom: bytes, source_rows: Mapping[str, Mapping[str, object]], plan: Mapping[str, object]) -> dict[str, object]:
    records: list[dict[str, object]] = []
    for string_id in plan["adjacent_untouched_records"]:
        row = source_rows[str(string_id)]
        before = _record_from_rom(clean_rom, row)
        after = _record_from_rom(final_rom, row)
        _require(before == after, f"M5.5 adjacent record changed: {string_id}")
        records.append({"string_id": string_id, "record_sha256": sha256_bytes(after), "byte_identical_to_clean": True})
    glyph_id = parse_int(plan["adjacent_untouched_glyph_id"], "adjacent_untouched_glyph_id")
    before_glyph = INSPECT_FONT.render_glyph(clean_rom, INSPECT_FONT.parse_font_resource(clean_rom), glyph_id)
    after_glyph = INSPECT_FONT.render_glyph(final_rom, INSPECT_FONT.parse_font_resource(final_rom), glyph_id)
    _require(before_glyph["cell_sha256"] == after_glyph["cell_sha256"] and before_glyph["render_sha256"] == after_glyph["render_sha256"], "M5.5 adjacent glyph changed")
    return {"records": records, "glyph": {"glyph_id": f"0x{glyph_id:03x}", "cell_sha256": after_glyph["cell_sha256"], "render_sha256": after_glyph["render_sha256"], "byte_identical_to_clean": True}}


def _font_proof(before_rom: bytes, after_rom: bytes) -> dict[str, object]:
    before_font = INSPECT_FONT.parse_font_resource(before_rom)
    after_font = INSPECT_FONT.parse_font_resource(after_rom)
    reports: list[dict[str, object]] = []
    for unit_hex in ("ec64", "ec65", "ec66", "ec6f"):
        raw = bytes.fromhex(unit_hex)
        before = INSPECT_FONT.lookup_code_unit(before_rom, raw, slot_count=int(before_font["slot_count"]), font_base_file_offset=int(before_font["font_base_file_offset"]))
        after = INSPECT_FONT.lookup_code_unit(after_rom, raw, slot_count=int(after_font["slot_count"]), font_base_file_offset=int(after_font["font_base_file_offset"]))
        _require(before.get("status") == "mapped" and after.get("status") == "mapped" and before.get("glyph_id") == after.get("glyph_id") and before.get("cell_sha256") == after.get("cell_sha256"), f"M5.5 inherited glyph changed for {unit_hex}")
        reports.append({"code_unit": unit_hex, "glyph_id": f"0x{int(after['glyph_id']):03x}", "cell_sha256": after["cell_sha256"], "mapping_unchanged": True})
    return {"inherited_mappings": reports}


def build_batch(clean_rom: bytes, source_path: pathlib.Path, plan: Mapping[str, object], working_path: pathlib.Path, m54_working_path: pathlib.Path, m53_working_path: pathlib.Path, m52_working_path: pathlib.Path, m43_working_path: pathlib.Path, m42_working_path: pathlib.Path, m41_working_path: pathlib.Path, m25_working_path: pathlib.Path, font_source: pathlib.Path) -> tuple[bytes, dict[str, object]]:
    identity = INSPECT_FONT.verify_rom(clean_rom)
    _require(identity["sha256"] == EXPECTED_ROM_SHA256, "M5.5 clean ROM identity mismatch")
    INSPECT_FONT.verify_static_evidence(clean_rom)
    _require(sha256_file(font_source) == EXPECTED_FONT_SOURCE_SHA256, "M5.5 font source hash mismatch")
    source_rows = load_source_rows(source_path)
    source_row = validate_source_selection(plan, source_rows)
    validate_working(plan, source_row, working_path)

    m54_plan = M54.load_plan(GAME_ROOT / "research" / "m5.4-lottery-question-plan.json")
    m54_rom, m54_summary = M54.build_batch(clean_rom, source_path, m54_plan, m54_working_path, m53_working_path, m52_working_path, m43_working_path, m42_working_path, m41_working_path, m25_working_path, font_source)
    target_payload = _target_payload(m54_rom)
    resolved = EXTRACT_STATIC.resolve_script_resource(m54_rom, 24)
    _require(int(resolved["payload_file_offset"]) == DESTINATION and int(resolved["span_units"]) == DESTINATION_SPAN_UNITS, "M5.5 inherited relocation is not active")
    decoded, inherited_compressed_size = EXTRACT_STATIC.decode_lz77(m54_rom, DESTINATION)
    offset = M52._source_offset(source_row)
    original_record = M25._record_region(decoded, offset, int(source_row["raw_length"]))
    _require(sha256_bytes(original_record) == str(plan["records"][0]["source_record_sha256"]), "M5.5 source record bytes drifted")
    target_record = struct.pack("<H", EXTRACT_STATIC.TEXT_START_WORD) + target_payload + struct.pack("<H", EXTRACT_STATIC.TEXT_END_WORD)
    _require(len(target_record) == len(original_record) == 18, "M5.5 same-length record contract failed")
    patched_decoded = bytearray(decoded)
    patched_decoded[offset : offset + len(target_record)] = target_record
    compressed = M52.M23.lz77_compress(bytes(patched_decoded))
    _require(len(compressed) <= DESTINATION_SPAN_BYTES, f"M5.5 relocated resource compressed output {len(compressed)} exceeds span {DESTINATION_SPAN_BYTES}")
    destination_report = M52.M51.validate_destination(clean_rom, DESTINATION, DESTINATION_SPAN_BYTES)
    patched = bytearray(m54_rom)
    patched[DESTINATION : DESTINATION + DESTINATION_SPAN_BYTES] = compressed + bytes(DESTINATION_SPAN_BYTES - len(compressed))
    final_rom = bytes(patched)
    redirected_decoded, redirected_size = EXTRACT_STATIC.decode_lz77(final_rom, DESTINATION)
    _require(redirected_decoded == bytes(patched_decoded) and redirected_size == len(compressed), "M5.5 relocated decode mismatch")

    prior_target_ids = list(m54_summary["translated_string_ids"])
    expected_targets = {target_id: _record_from_rom(final_rom, source_rows[target_id]) for target_id in prior_target_ids}
    expected_targets[M55_TARGET_ID] = target_record
    prior_records: list[dict[str, object]] = []
    for target_id in prior_target_ids:
        before = _record_from_rom(m54_rom, source_rows[target_id])
        after = _record_from_rom(final_rom, source_rows[target_id])
        _require(before == after, f"M5.5 prior target changed: {target_id}")
        prior_records.append({"string_id": target_id, "record_sha256": sha256_bytes(after), "byte_identical_to_m5_4": True})
    adjacent_ids = {"b3cj:t2:024:0x0046", "b3cj:t2:022:0x0072", "b3cj:t2:022:0x0098", "b3cj:t2:024:0x00b4", "b3cj:t2:024:0x01cc", "b3cj:t2:024:0x0204", "b3cj:t2:024:0x0898", "b3cj:t2:024:0x08ae"}
    reextract = M41._reextract(clean_rom, final_rom, source_rows, expected_targets, adjacent_ids=adjacent_ids)
    adjacent = _adjacent_proof(clean_rom, final_rom, source_rows, plan)
    baseline_changed = {index for index, (before, after) in enumerate(zip(clean_rom, m54_rom)) if before != after}
    allowed = baseline_changed | set(range(DESTINATION, DESTINATION + DESTINATION_SPAN_BYTES))
    changed = {index for index, (before, after) in enumerate(zip(clean_rom, final_rom)) if before != after}
    _require(changed.issubset(allowed), "M5.5 changed a byte outside cumulative font/relocation ranges")
    summary: dict[str, object] = {
        "batch_id": EXPECTED_BATCH_ID,
        "base_batch_id": "m5.4-lottery-question",
        "static_only": True,
        "runtime_qa": "pending",
        "translation_status": "ai_draft",
        "translated_string_ids": sorted(expected_targets),
        "new_translated_string_ids": [M55_TARGET_ID],
        "source_table_sha256": EXPECTED_SOURCE_TABLE_SHA256,
        "clean_rom_sha256": EXPECTED_ROM_SHA256,
        "target_sha256": sha256_bytes(final_rom),
        "target": {"locale": TARGET_LOCALE, "utf8_sha256": plan["targets"][TARGET_LOCALE]["utf8_sha256"], "byte_length": len(target_payload), "code_units": list(plan["target_contract"]["code_units"])},
        "font": {"new_allocations": [], "proof": _font_proof(m54_rom, final_rom), "adjacent_untouched_glyph": adjacent["glyph"], "font_base_file_offset": f"0x{int(INSPECT_FONT.parse_font_resource(m54_rom)['font_base_file_offset']):x}", "cell_size": INSPECT_FONT.FONT_CELL_SIZE},
        "resource": {"resource_id": 24, "payload_file_offset": f"0x{DESTINATION:x}", "span_bytes": DESTINATION_SPAN_BYTES, "inherited_compressed_size": inherited_compressed_size, "new_compressed_size": len(compressed), "inherited_compressed_sha256": sha256_bytes(m54_rom[DESTINATION : DESTINATION + inherited_compressed_size]), "new_compressed_sha256": sha256_bytes(compressed), "repacked_at_relocated_pointer": True},
        "pointer": {"directory_file_offset": f"0x{int(resolved['directory_file_offset']):x}", "relative_units": f"0x{int(resolved['relative_units']):x}", "span_units": int(resolved["span_units"]), "destination_guard": destination_report, "inherited_from": "m5.4-lottery-question"},
        "prior_target_proof": prior_records,
        "reextract": reextract,
        "adjacent_untouched": adjacent,
        "m5_4_reextract": m54_summary["reextract"],
        "byte_level": {"changed_byte_count": len(changed), "changed_outside_cumulative_ranges": False, "all_361_records_reextracted": True},
        "boundary": "Cumulative static translation with one repeated same-length record; no new glyph, runtime screen/readability or release-patch claim.",
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
    build.add_argument("--m5-4-working", type=pathlib.Path, required=True)
    build.add_argument("--m5-3-working", type=pathlib.Path, required=True)
    build.add_argument("--m5-2-working", type=pathlib.Path, required=True)
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
            print(f"B3CJ_M5_5_PREPARE_OK records=1 ledger={args.ledger_output} source_adapter={args.source_adapter_output}")
            return 0
        if (args.bps_output is None) != (args.bps_applied_output is None):
            raise ValueError("--bps-output and --bps-applied-output must be supplied together")
        if args.output.resolve() == args.rom.resolve():
            raise ValueError("refusing to overwrite clean ROM")
        patched, summary = build_batch(args.rom.read_bytes(), args.source_jsonl, plan, args.working, args.m5_4_working, args.m5_3_working, args.m5_2_working, args.m4_3_working, args.m4_2_working, args.m4_1_working, args.m2_5_working, args.font_source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(patched)
        if args.bps_output is not None and args.bps_applied_output is not None:
            summary["bps"] = M25.run_bps(args.rom, args.output, args.bps_output, args.bps_applied_output)
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"B3CJ_M5_5_BUILD_OK records={len(summary['translated_string_ids'])} new_records=1 changed_bytes={summary['byte_level']['changed_byte_count']} target_sha256={summary['target_sha256']}")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"build_m5_5_batch.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
