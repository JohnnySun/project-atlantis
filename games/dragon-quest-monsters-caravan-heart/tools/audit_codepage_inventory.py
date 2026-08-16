#!/usr/bin/env python3
"""Audit clean A9HJ code-unit usage without emitting source text.

The input is the ignored raw-token JSONL produced by ``extract_text.py``.
This tool intentionally emits only aggregate counts, hexadecimal code-unit
frequencies, and the set of used alternate-glyph indexes.  It is an evidence
receipt for narrowing the codepage; it is not a decoder and never writes a
translation source table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from build_source_table import direct_map, pair_text  # noqa: E402


ROM_SIZE = 0x800000
EXPECTED_CRC32 = 0x3C24ABCC
EXPECTED_SHA256 = "fb388539b95fdaf6009bad879e9bbb25955daf8d4d438486a9213d407b2b48ce"
EXTRACTOR_SCHEMA = "dqmch-clean-script-bytes-v1"


def validate_rom(data: bytes) -> dict[str, str | int]:
    """Accept only the formally approved clean A9HJ ROM."""

    crc32 = zlib.crc32(data) & 0xFFFFFFFF
    sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != ROM_SIZE:
        raise ValueError(f"expected 8 MiB clean ROM, got {len(data)} bytes")
    if crc32 != EXPECTED_CRC32 or sha256 != EXPECTED_SHA256:
        raise ValueError(f"refusing non-clean A9HJ ROM: CRC32={crc32:08X}, SHA256={sha256}")
    return {"size": len(data), "crc32": f"{crc32:08X}", "sha256": sha256}


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load and validate extractor records without retaining source strings."""

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at line {line_number}: {error}") from error
        if record.get("schema") != EXTRACTOR_SCHEMA:
            raise ValueError(f"unexpected extractor schema at line {line_number}")
        if record.get("rom_sha256") != EXPECTED_SHA256:
            raise ValueError(f"record at line {line_number} is not from the clean ROM")
        tokens = record.get("tokens")
        if not isinstance(tokens, list):
            raise ValueError(f"record at line {line_number} has no token list")
        records.append(record)
    return records


def hex_counts(counter: Counter[int]) -> dict[str, int]:
    return {f"0x{value:02X}": count for value, count in sorted(counter.items())}


def pair_counts(counter: Counter[tuple[int, int]]) -> dict[str, int]:
    return {
        f"0x{lead:02X}{trail:02X}": count
        for (lead, trail), count in sorted(counter.items())
    }


def alt_counts(counter: Counter[tuple[int, int]]) -> dict[str, int]:
    return {
        f"0x{lead:02X}:{index:02X}": count
        for (lead, index), count in sorted(counter.items())
    }


def inventory(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return a source-free aggregate inventory for extractor records."""

    direct = direct_map()
    single = Counter()
    direct_mapped = Counter()
    direct_unresolved = Counter()
    pairs = Counter()
    pairs_resolved = Counter()
    pairs_unresolved = Counter()
    alternates = Counter()
    controls = Counter()
    kinds = Counter()
    boundaries = Counter()
    pointers: set[str] = set()
    groups: set[int] = set()
    variants: set[tuple[int, int]] = set()
    unresolved_by_group_variant: dict[tuple[int, int], dict[str, Any]] = {}
    terminated = 0
    truncated = 0
    record_count = 0

    for record in records:
        record_count += 1
        pointer = record.get("pointer_cpu")
        if isinstance(pointer, str):
            pointers.add(pointer)
        group = int(record.get("group", 0))
        variant = int(record.get("variant", 0))
        groups.add(group)
        variants.add((group, variant))
        context_key = (group, variant)
        context = unresolved_by_group_variant.setdefault(
            context_key,
            {
                "group": group,
                "variant": variant,
                "records": 0,
                "records_with_unresolved": 0,
                "unresolved_total": 0,
                "unresolved_units": Counter(),
            },
        )
        context["records"] += 1
        boundaries[str(record.get("boundary", "unknown"))] += 1
        if record.get("truncated_pair"):
            truncated += 1
        control_values = record.get("control_values", [])
        if isinstance(control_values, list) and 0xFF in [int(value) for value in control_values]:
            terminated += 1

        record_unresolved = Counter()
        for token in record["tokens"]:
            kind = str(token.get("kind"))
            kinds[kind] += 1
            if kind == "single-byte-candidate":
                value = int(token["value"])
                single[value] += 1
                if value in direct:
                    direct_mapped[value] += 1
                else:
                    direct_unresolved[value] += 1
                    record_unresolved[value] += 1
            elif kind == "pair":
                lead = int(token["lead"])
                trail = int(token["trail"])
                pairs[(lead, trail)] += 1
                _, resolved = pair_text(lead, trail, direct)
                (pairs_resolved if resolved else pairs_unresolved)[(lead, trail)] += 1
            elif kind == "alt-glyph":
                alternates[(int(token["lead"]), int(token["value"]))] += 1
            elif kind == "control-candidate":
                controls[int(token["value"])] += 1
            elif kind in {"pair-truncated", "alt-glyph-truncated"}:
                pass
            else:
                raise ValueError(f"unknown token kind: {kind!r}")

        if record_unresolved:
            context["records_with_unresolved"] += 1
            context["unresolved_total"] += sum(record_unresolved.values())
            context["unresolved_units"].update(record_unresolved)

    alternate_leads = Counter()
    for (lead, _), count in alternates.items():
        alternate_leads[lead] += count
    alternate_indexes = {
        f"0x{lead:02X}": sorted(index for (current_lead, index) in alternates if current_lead == lead)
        for lead in sorted({lead for lead, _ in alternates})
    }
    unresolved_context = []
    for key in sorted(unresolved_by_group_variant):
        context = unresolved_by_group_variant[key]
        if not context["unresolved_total"]:
            continue
        unresolved_context.append(
            {
                "group": context["group"],
                "variant": context["variant"],
                "records": context["records"],
                "records_with_unresolved": context["records_with_unresolved"],
                "unresolved_total": context["unresolved_total"],
                "unresolved_units": hex_counts(context["unresolved_units"]),
            }
        )
    return {
        "schema": "dqmch-codepage-inventory-v2",
        "rom_sha256": EXPECTED_SHA256,
        "records": record_count,
        "unique_pointers": len(pointers),
        "groups": sorted(groups),
        "variants": len(variants),
        "terminated_records_with_ff": terminated,
        "truncated_pair_records": truncated,
        "boundaries": dict(sorted(boundaries.items())),
        "token_kinds": dict(sorted(kinds.items())),
        "single_byte": {
            "total": sum(single.values()),
            "mapped_total": sum(direct_mapped.values()),
            "unresolved_total": sum(direct_unresolved.values()),
            "used_units": hex_counts(single),
            "mapped_units": hex_counts(direct_mapped),
            "unresolved_units": hex_counts(direct_unresolved),
            "unresolved_by_group_variant": unresolved_context,
        },
        "pair": {
            "total": sum(pairs.values()),
            "resolved_total": sum(pairs_resolved.values()),
            "unresolved_total": sum(pairs_unresolved.values()),
            "used_units": pair_counts(pairs),
            "resolved_units": pair_counts(pairs_resolved),
            "unresolved_units": pair_counts(pairs_unresolved),
        },
        "alternate_glyph": {
            "total": sum(alternates.values()),
            "lead_counts": hex_counts(alternate_leads),
            "used_slots": alt_counts(alternates),
            "used_indexes": alternate_indexes,
            "unique_slots": len(alternates),
        },
        "control_candidate": {
            "total": sum(controls.values()),
            "used_values": hex_counts(controls),
        },
        "direct_map": {
            "defined_units": len(direct),
            "used_defined_units": len(direct_mapped),
            "used_undefined_units": len(direct_unresolved),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("decoded", type=Path, help="ignored raw-token JSONL from extract_text.py")
    parser.add_argument("--out", type=Path, help="optional source-free JSON receipt")
    args = parser.parse_args()

    try:
        identity = validate_rom(args.rom.read_bytes())
        records = load_records(args.decoded)
        receipt = inventory(records)
        receipt["rom"] = identity
        payload = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(payload, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"audit_codepage_inventory: {error}", file=sys.stderr)
        return 2

    sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
