"""Deterministic ROM identity, relocation, record, and layout checks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .manifest import ManifestError, integer
from .result import Report


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _intervals(rows: Iterable[Any], field: str) -> list[tuple[int, int]]:
    output = []
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 2:
            raise ManifestError(f"{field}[{index}] must be [start, end]")
        start = integer(row[0], f"{field}[{index}][0]")
        end = integer(row[1], f"{field}[{index}][1]")
        if start < 0 or end < start:
            raise ManifestError(f"{field}[{index}] is an invalid inclusive range")
        output.append((start, end))
    return output


def _inside(value: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= value <= end for start, end in ranges)


def _span(data: bytes, offset: int, length: int, field: str) -> bytes:
    if offset < 0 or length <= 0 or offset + length > len(data):
        raise ManifestError(
            f"{field} span 0x{offset:X}+0x{length:X} is outside ROM size 0x{len(data):X}"
        )
    return data[offset:offset + length]


def _identity(report: Report, base: bytes, rom_spec: dict[str, Any]) -> None:
    expected_hash = rom_spec["sha256"]
    actual_hash = _sha(base)
    report.evidence["rom"] = {
        "sha256": actual_hash,
        "size": len(base),
        "game_code_hex": base[0xAC:0xB0].hex() if len(base) >= 0xB0 else None,
    }
    report.add(
        "pass" if actual_hash == expected_hash else "fail",
        "rom.identity.sha256",
        "base ROM identity matches manifest" if actual_hash == expected_hash else "base ROM SHA-256 mismatch",
        expected=expected_hash,
        actual=actual_hash,
    )
    if "size" in rom_spec:
        expected_size = integer(rom_spec["size"], "rom.size")
        report.add(
            "pass" if len(base) == expected_size else "fail",
            "rom.identity.size",
            "base ROM size matches manifest" if len(base) == expected_size else "base ROM size mismatch",
            expected=expected_size,
            actual=len(base),
        )
    if "game_code_hex" in rom_spec:
        expected_code = str(rom_spec["game_code_hex"]).lower()
        actual_code = base[0xAC:0xB0].hex() if len(base) >= 0xB0 else ""
        report.add(
            "pass" if actual_code == expected_code else "fail",
            "rom.identity.game_code",
            "GBA header game code matches manifest" if actual_code == expected_code else "GBA header game code mismatch",
            expected=expected_code,
            actual=actual_code,
        )


def _check_change_policy(
    report: Report,
    base: bytes,
    candidate: bytes,
    spec: dict[str, Any],
) -> None:
    if len(base) != len(candidate) and not spec.get("allow_size_change", False):
        report.add(
            "fail",
            "static.relocation.size_change",
            "candidate ROM size changed without allow_size_change",
            base_size=len(base),
            candidate_size=len(candidate),
        )
    allowed = _intervals(spec.get("allowed_changed_ranges", []), "static.change_policy.allowed_changed_ranges")
    changed = [index for index, pair in enumerate(zip(base, candidate)) if pair[0] != pair[1]]
    if len(base) != len(candidate):
        changed.extend(range(min(len(base), len(candidate)), max(len(base), len(candidate))))
    outside = [offset for offset in changed if not _inside(offset, allowed)]
    report.evidence["change_policy"] = {
        "changed_byte_count": len(changed),
        "outside_allowed_count": len(outside),
        "first_outside_allowed": None if not outside else f"0x{outside[0]:X}",
    }
    report.add(
        "pass" if not outside else "fail",
        "static.relocation.allowed_ranges",
        "all changed bytes are inside declared ranges" if not outside else "candidate changed bytes outside declared ranges",
        outside_count=len(outside),
        first_outside=None if not outside else f"0x{outside[0]:X}",
    )
    if spec.get("require_change", False):
        report.add(
            "pass" if changed else "fail",
            "static.relocation.required_change",
            "candidate contains an intended change" if changed else "candidate is byte-identical but a change is required",
        )


def _check_regions(
    report: Report,
    base: bytes,
    candidate: bytes,
    rows: list[dict[str, Any]],
) -> None:
    evidence: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        offset = integer(row.get("offset"), f"static.regions[{index}].offset")
        length = integer(row.get("length"), f"static.regions[{index}].length")
        before = _span(base, offset, length, f"static.regions[{index}]")
        after = _span(candidate, offset, length, f"static.regions[{index}]")
        changed = sum(left != right for left, right in zip(before, after))
        region_id = str(row.get("id", f"region-{index}"))
        policy = row.get("policy", "observe")
        role = row.get("role", "other")
        evidence.append({
            "id": region_id,
            "offset": f"0x{offset:X}",
            "length": length,
            "policy": policy,
            "role": role,
            "base_sha256": _sha(before),
            "candidate_sha256": _sha(after),
            "changed_bytes": changed,
        })
        if policy == "unchanged":
            report.add(
                "pass" if not changed else "fail",
                "static.region.unchanged",
                f"region {region_id} is unchanged" if not changed else f"region {region_id} was polluted",
                region=region_id,
                changed_bytes=changed,
            )
        elif policy == "changed":
            report.add(
                "pass" if changed else "fail",
                "static.region.changed",
                f"region {region_id} changed" if changed else f"region {region_id} did not change",
                region=region_id,
            )
        elif policy != "observe":
            raise ManifestError(f"static.regions[{index}].policy is unknown: {policy!r}")
    report.evidence["regions"] = evidence


def _read_pointer(data: bytes, row: dict[str, Any], field: str) -> int:
    offset = integer(row.get("offset"), f"{field}.offset")
    encoding = row.get("encoding", "gba32le")
    if encoding != "gba32le":
        raise ManifestError(f"{field}.encoding only supports gba32le")
    raw = _span(data, offset, 4, field)
    return int.from_bytes(raw, "little")


def _check_pointers(
    report: Report,
    candidate: bytes,
    rows: list[dict[str, Any]],
) -> None:
    targets: dict[int, list[tuple[str, str | None]]] = {}
    groups: dict[str, set[int]] = {}
    evidence: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        field = f"static.pointers[{index}]"
        pointer_id = str(row.get("id", f"pointer-{index}"))
        target = _read_pointer(candidate, row, field)
        ranges = _intervals(row.get("target_ranges", []), f"{field}.target_ranges")
        alignment = integer(row.get("alignment", 1), f"{field}.alignment")
        in_range = bool(ranges) and _inside(target, ranges)
        aligned = alignment > 0 and target % alignment == 0
        expected_target = row.get("expected_target")
        exact_match = expected_target is None or target == integer(expected_target, f"{field}.expected_target")
        group = row.get("alias_group")
        if group is not None and not isinstance(group, str):
            raise ManifestError(f"{field}.alias_group must be a string")
        targets.setdefault(target, []).append((pointer_id, group))
        if group:
            groups.setdefault(group, set()).add(target)
        evidence.append({
            "id": pointer_id,
            "target": f"0x{target:08X}",
            "in_range": in_range,
            "aligned": aligned,
            "expected_target": None if expected_target is None else f"0x{integer(expected_target, f'{field}.expected_target'):08X}",
            "exact_match": exact_match,
            "alias_group": group,
        })
        report.add(
            "pass" if in_range else "fail",
            "static.pointer.range",
            f"pointer {pointer_id} target is in range" if in_range else f"pointer {pointer_id} target is outside declared ranges",
            pointer=pointer_id,
            target=f"0x{target:08X}",
        )
        report.add(
            "pass" if aligned else "fail",
            "static.pointer.alignment",
            f"pointer {pointer_id} is aligned" if aligned else f"pointer {pointer_id} is misaligned",
            pointer=pointer_id,
            alignment=alignment,
        )
        if expected_target is not None:
            report.add(
                "pass" if exact_match else "fail",
                "static.pointer.expected_target",
                f"pointer {pointer_id} resolves to the expected target" if exact_match else f"pointer {pointer_id} resolves to the wrong in-range target",
                pointer=pointer_id,
                expected=f"0x{integer(expected_target, f'{field}.expected_target'):08X}",
                actual=f"0x{target:08X}",
            )
    for target, aliases in targets.items():
        if len(aliases) < 2:
            continue
        declared = {group for _, group in aliases}
        if None in declared or len(declared) != 1:
            report.add(
                "fail",
                "static.pointer.unexpected_alias",
                "multiple pointer records alias without one shared alias_group",
                target=f"0x{target:08X}",
                pointers=[pointer_id for pointer_id, _ in aliases],
            )
    for group, group_targets in groups.items():
        report.add(
            "pass" if len(group_targets) == 1 else "fail",
            "static.pointer.alias_group",
            f"alias group {group} resolves consistently" if len(group_targets) == 1 else f"alias group {group} split across targets",
            targets=[f"0x{target:08X}" for target in sorted(group_targets)],
        )
    report.evidence["pointers"] = evidence


def _tokens(raw: bytes, unit_bytes: int) -> list[int]:
    if len(raw) % unit_bytes:
        raise ManifestError("record allocation is not divisible by unit_bytes")
    return [
        int.from_bytes(raw[index:index + unit_bytes], "little")
        for index in range(0, len(raw), unit_bytes)
    ]


def _control_stream(
    tokens: list[int],
    specs: dict[int, tuple[int, list[tuple[int, int]]]],
) -> tuple[list[int], set[int], list[dict[str, Any]]]:
    """Return preserved control+argument units, argument indexes, and errors."""
    preserved: list[int] = []
    argument_indexes: set[int] = set()
    errors: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        value = tokens[index]
        spec = specs.get(value)
        if spec is None:
            index += 1
            continue
        argument_units, ranges = spec
        available = len(tokens) - index - 1
        if available < argument_units:
            errors.append({"control": f"0x{value:X}", "index": index, "reason": "truncated", "expected_argument_units": argument_units, "available_argument_units": available})
            preserved.extend(tokens[index:])
            break
        arguments = tokens[index + 1:index + 1 + argument_units]
        preserved.extend([value, *arguments])
        argument_indexes.update(range(index + 1, index + 1 + argument_units))
        if ranges:
            invalid = [argument for argument in arguments if not _inside(argument, ranges)]
            if invalid:
                errors.append({"control": f"0x{value:X}", "index": index, "reason": "argument-range", "invalid_values": [f"0x{argument:X}" for argument in invalid]})
        index += 1 + argument_units
    return preserved, argument_indexes, errors


def _preserved_controls(
    tokens: list[int],
    specs: dict[int, tuple[int, list[tuple[int, int]]]],
    simple_controls: set[int],
) -> list[int]:
    output: list[int] = []
    index = 0
    while index < len(tokens):
        value = tokens[index]
        if value in specs:
            argument_units = specs[value][0]
            output.extend(tokens[index:min(len(tokens), index + 1 + argument_units)])
            index += 1 + argument_units
            continue
        if value in simple_controls:
            output.append(value)
        index += 1
    return output


def _terminator_index(
    tokens: list[int],
    terminator: int,
    specs: dict[int, tuple[int, list[tuple[int, int]]]],
) -> int | None:
    """Find a record terminator without mistaking control arguments for it."""
    index = 0
    while index < len(tokens):
        value = tokens[index]
        if value == terminator:
            return index
        if value in specs:
            index += 1 + specs[value][0]
        else:
            index += 1
    return None


def _check_records(
    report: Report,
    base: bytes,
    candidate: bytes,
    rows: list[dict[str, Any]],
) -> None:
    evidence: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        field = f"static.records[{index}]"
        record_id = str(row.get("id", f"record-{index}"))
        offset = integer(row.get("offset"), f"{field}.offset")
        allocated = integer(row.get("allocated_length"), f"{field}.allocated_length")
        unit_bytes = integer(row.get("unit_bytes", 1), f"{field}.unit_bytes")
        if unit_bytes not in (1, 2, 4):
            raise ManifestError(f"{field}.unit_bytes must be 1, 2, or 4")
        base_raw = _span(base, offset, allocated, field)
        candidate_raw = _span(candidate, offset, allocated, field)
        base_tokens = _tokens(base_raw, unit_bytes)
        candidate_tokens = _tokens(candidate_raw, unit_bytes)
        terminator = integer(row.get("terminator", 0), f"{field}.terminator")
        allowed = _intervals(row.get("allowed_values", []), f"{field}.allowed_values")
        controls = {integer(value, f"{field}.control_values") for value in row.get("control_values", [])}
        control_specs: dict[int, tuple[int, list[tuple[int, int]]]] = {}
        for control_index, control in enumerate(row.get("control_codes", [])):
            control_field = f"{field}.control_codes[{control_index}]"
            value = integer(control.get("value"), f"{control_field}.value")
            argument_units = integer(control.get("argument_units"), f"{control_field}.argument_units")
            ranges = _intervals(control.get("argument_values", []), f"{control_field}.argument_values")
            control_specs[value] = (argument_units, ranges)
            controls.add(value)
        end = _terminator_index(candidate_tokens, terminator, control_specs)
        if end is None:
            report.add("fail", "static.record.terminator", f"record {record_id} has no in-range terminator", record=record_id)
            end = len(candidate_tokens)
        content = candidate_tokens[:end]
        base_end = _terminator_index(base_tokens, terminator, control_specs)
        if base_end is None:
            base_end = len(base_tokens)
        newlines = {integer(value, f"{field}.newline_values") for value in row.get("newline_values", [])}
        _, control_argument_indexes, control_errors = _control_stream(content, control_specs)
        invalid = [value for token_index, value in enumerate(content) if token_index not in control_argument_indexes and value not in controls | newlines and not _inside(value, allowed)]
        report.add(
            "pass" if not invalid else "fail",
            "static.record.encoding",
            f"record {record_id} tokens are allowed" if not invalid else f"record {record_id} contains disallowed tokens",
            record=record_id,
            invalid_values=[f"0x{value:X}" for value in sorted(set(invalid))[:16]],
        )
        report.add(
            "pass" if not control_errors else "fail",
            "static.record.control_arity",
            f"record {record_id} control codes are structurally complete" if not control_errors else f"record {record_id} has malformed control-code arguments",
            record=record_id,
            errors=control_errors,
        )
        if row.get("preserve_controls", False):
            simple_controls = (controls - set(control_specs)) | newlines
            before_controls = _preserved_controls(base_tokens[:base_end], control_specs, simple_controls)
            after_controls = _preserved_controls(content, control_specs, simple_controls)
            report.add(
                "pass" if before_controls == after_controls else "fail",
                "static.record.controls",
                f"record {record_id} preserves control-code sequence" if before_controls == after_controls else f"record {record_id} changed control-code sequence",
                record=record_id,
                before=[f"0x{value:X}" for value in before_controls],
                after=[f"0x{value:X}" for value in after_controls],
            )
        layout = row.get("layout")
        line_widths: list[int] | None = None
        if layout is not None:
            if not isinstance(layout, dict):
                raise ManifestError(f"{field}.layout must be an object")
            widths = {
                integer(key, f"{field}.layout.glyph_widths key"): integer(value, f"{field}.layout.glyph_widths[{key}]")
                for key, value in layout.get("glyph_widths", {}).items()
            }
            default_width = layout.get("default_width")
            if default_width is not None:
                default_width = integer(default_width, f"{field}.layout.default_width")
            line_widths = [0]
            unknown_widths: list[int] = []
            for token_index, value in enumerate(content):
                if value in newlines:
                    line_widths.append(0)
                elif value in controls or token_index in control_argument_indexes:
                    continue
                elif value in widths:
                    line_widths[-1] += widths[value]
                elif default_width is not None:
                    line_widths[-1] += default_width
                else:
                    unknown_widths.append(value)
            report.add(
                "pass" if not unknown_widths else "unknown",
                "static.record.glyph_width",
                f"record {record_id} has widths for every glyph" if not unknown_widths else f"record {record_id} has glyphs with unknown width",
                record=record_id,
                unknown_values=[f"0x{value:X}" for value in sorted(set(unknown_widths))[:16]],
            )
            max_width = integer(layout.get("max_width"), f"{field}.layout.max_width")
            max_lines = integer(layout.get("max_lines"), f"{field}.layout.max_lines")
            report.add(
                "pass" if max(line_widths, default=0) <= max_width else "fail",
                "static.record.line_width",
                f"record {record_id} fits line width" if max(line_widths, default=0) <= max_width else f"record {record_id} overflows line width",
                record=record_id,
                widths=line_widths,
                max_width=max_width,
            )
            report.add(
                "pass" if len(line_widths) <= max_lines else "fail",
                "static.record.line_count",
                f"record {record_id} fits line count" if len(line_widths) <= max_lines else f"record {record_id} exceeds line count",
                record=record_id,
                lines=len(line_widths),
                max_lines=max_lines,
            )
        evidence.append({
            "id": record_id,
            "offset": f"0x{offset:X}",
            "allocated_length": allocated,
            "content_units": len(content),
            "terminator_unit_index": None if end == len(candidate_tokens) else end,
            "candidate_sha256": _sha(candidate_raw),
            "line_widths": line_widths,
        })
    report.evidence["records"] = evidence


def run_static(
    manifest: dict[str, Any],
    base_path: Path,
    candidate_path: Path | None = None,
) -> Report:
    report = Report("static")
    report.evidence["case_id"] = manifest["case_id"]
    try:
        base = base_path.read_bytes()
        candidate = base if candidate_path is None else candidate_path.read_bytes()
        _identity(report, base, manifest["rom"])
        spec = manifest.get("static", {})
        _check_change_policy(report, base, candidate, spec.get("change_policy", {}))
        _check_regions(report, base, candidate, spec.get("regions", []))
        _check_pointers(report, candidate, spec.get("pointers", []))
        _check_records(report, base, candidate, spec.get("records", []))
    except (OSError, ManifestError, ValueError) as exc:
        report.add("unknown", "static.execution", str(exc))
    return report
