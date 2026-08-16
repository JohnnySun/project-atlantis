#!/usr/bin/env python3
"""Build and verify the five bounded A9HJ translation batches together.

This tool intentionally remains a bounded proof: it merges only the fixed
menu span and four fixed system-message spans plus their authored E1 tiles.  It
does not claim to be the full game's encoder or source-boundary parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import patch_menu
import patch_message_batch_2
import patch_message_batch_3
import patch_message_batch_4
import patch_message_batch_5
import verify_menu_patch
import verify_message_batch_2
import verify_message_batch_3
import verify_message_batch_4
import verify_message_batch_5


def load_entry(path: pathlib.Path, string_id: str) -> dict[str, object]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            if entry.get("string_id") == string_id:
                return entry
    raise ValueError(f"missing {string_id}")


def merge(
    clean: bytes,
    menu: bytes,
    message: bytes,
    message_3: bytes | None = None,
    message_4: bytes | None = None,
    message_5: bytes | None = None,
) -> bytes:
    outputs = [menu, message]
    if message_3 is not None:
        outputs.append(message_3)
    if message_4 is not None:
        outputs.append(message_4)
    if message_5 is not None:
        outputs.append(message_5)
    if any(len(clean) != output_len for output_len in (len(output) for output in outputs)):
        raise ValueError("bounded outputs differ in size")
    result = bytearray(clean)
    for offset, base in enumerate(clean):
        changed = [output[offset] for output in outputs if output[offset] != base]
        if len(set(changed)) > 1:
            raise ValueError(f"bounded batches conflict at file offset 0x{offset:06X}")
        if changed:
            result[offset] = changed[0]
    return bytes(result)


def verify(clean: bytes, combined: bytes) -> dict[str, object]:
    patch_menu.validate_rom(clean)
    if len(clean) != len(combined):
        raise ValueError("combined output differs in size")
    menu = combined[patch_menu.MENU_FILE_OFFSET:patch_menu.MENU_FILE_OFFSET + patch_menu.MENU_SPAN_LENGTH]
    message = combined[patch_message_batch_2.MESSAGE_FILE_OFFSET:patch_message_batch_2.MESSAGE_FILE_OFFSET + patch_message_batch_2.MESSAGE_SPAN_LENGTH]
    if menu != patch_menu.encode_target(patch_menu.TARGET_TEXT):
        raise ValueError("combined menu target mismatch")
    if verify_menu_patch.decode_target(menu) != patch_menu.TARGET_TEXT:
        raise ValueError("combined menu re-extraction mismatch")
    if verify_message_batch_2.decode_target(message) != patch_message_batch_2.TARGET_TEXT:
        raise ValueError("combined message target mismatch")
    message_3 = combined[patch_message_batch_3.MESSAGE_FILE_OFFSET:patch_message_batch_3.MESSAGE_FILE_OFFSET + patch_message_batch_3.MESSAGE_SPAN_LENGTH]
    if verify_message_batch_3.decode_target(message_3) != patch_message_batch_3.TARGET_TEXT:
        raise ValueError("combined message batch 3 re-extraction mismatch")
    message_4 = combined[patch_message_batch_4.MESSAGE_FILE_OFFSET:patch_message_batch_4.MESSAGE_FILE_OFFSET + patch_message_batch_4.MESSAGE_SPAN_LENGTH]
    if verify_message_batch_4.decode_target(message_4) != patch_message_batch_4.TARGET_TEXT:
        raise ValueError("combined message batch 4 re-extraction mismatch")
    message_5 = combined[patch_message_batch_5.MESSAGE_FILE_OFFSET:patch_message_batch_5.MESSAGE_FILE_OFFSET + patch_message_batch_5.MESSAGE_SPAN_LENGTH]
    if verify_message_batch_5.decode_target(message_5) != patch_message_batch_5.TARGET_TEXT:
        raise ValueError("combined message batch 5 re-extraction mismatch")

    ranges = (
        verify_menu_patch.allowed_ranges()
        + verify_message_batch_2.allowed_ranges()
        + verify_message_batch_3.allowed_ranges()
        + verify_message_batch_4.allowed_ranges()
        + verify_message_batch_5.allowed_ranges()
    )
    changed = [offset for offset, (before, after) in enumerate(zip(clean, combined)) if before != after]
    if any(not any(start <= offset < end for start, end in ranges) for offset in changed):
        raise ValueError("combined output changes bytes outside bounded ranges")
    return {
        "clean_sha256": hashlib.sha256(clean).hexdigest(),
        "combined_sha256": hashlib.sha256(combined).hexdigest(),
        "batch_string_ids": [
            patch_menu.MENU_STRING_ID,
            patch_message_batch_2.MESSAGE_STRING_ID,
            patch_message_batch_3.MESSAGE_STRING_ID,
            patch_message_batch_4.MESSAGE_STRING_ID,
            patch_message_batch_5.MESSAGE_STRING_ID,
        ],
        "allowed_range_count": len(ranges),
        "changed_byte_count": len(changed),
        "outside_range_changes": 0,
        "menu_reextract": "ok",
        "message_reextract": "ok",
        "message_batch_3_reextract": "ok",
        "message_batch_4_reextract": "ok",
        "message_batch_5_reextract": "ok",
        "runtime_qa": "not-run",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean", type=pathlib.Path)
    parser.add_argument("menu_ledger", type=pathlib.Path)
    parser.add_argument("message_ledger", type=pathlib.Path)
    parser.add_argument("message_3_ledger", type=pathlib.Path)
    parser.add_argument("message_4_ledger", type=pathlib.Path)
    parser.add_argument("message_5_ledger", type=pathlib.Path)
    parser.add_argument("source_table", type=pathlib.Path)
    parser.add_argument("decoded", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--report", type=pathlib.Path)
    args = parser.parse_args()
    try:
        clean = args.clean.read_bytes()
        ledger_menu = load_entry(args.menu_ledger, patch_menu.MENU_STRING_ID)
        ledger_message = load_entry(args.message_ledger, patch_message_batch_2.MESSAGE_STRING_ID)
        ledger_message_3 = load_entry(args.message_3_ledger, patch_message_batch_3.MESSAGE_STRING_ID)
        ledger_message_4 = load_entry(args.message_4_ledger, patch_message_batch_4.MESSAGE_STRING_ID)
        ledger_message_5 = load_entry(args.message_5_ledger, patch_message_batch_5.MESSAGE_STRING_ID)
        source_menu = load_entry(args.source_table, patch_menu.MENU_STRING_ID)
        source_message = load_entry(args.source_table, patch_message_batch_2.MESSAGE_STRING_ID)
        source_message_3 = load_entry(args.source_table, patch_message_batch_3.MESSAGE_STRING_ID)
        source_message_4 = load_entry(args.source_table, patch_message_batch_4.MESSAGE_STRING_ID)
        source_message_5 = load_entry(args.source_table, patch_message_batch_5.MESSAGE_STRING_ID)
        menu, _ = patch_menu.patch(clean, ledger_menu, source_menu, args.decoded)
        message, _ = patch_message_batch_2.patch(clean, ledger_message, source_message, args.decoded)
        message_3, _ = patch_message_batch_3.patch(clean, ledger_message_3, source_message_3, args.decoded)
        message_4, _ = patch_message_batch_4.patch(clean, ledger_message_4, source_message_4, args.decoded)
        message_5, _ = patch_message_batch_5.patch(clean, ledger_message_5, source_message_5, args.decoded)
        combined = merge(clean, menu, message, message_3, message_4, message_5)
        report = verify(clean, combined)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(combined)
        report["output"] = str(args.out)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"build_bounded_batches: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
