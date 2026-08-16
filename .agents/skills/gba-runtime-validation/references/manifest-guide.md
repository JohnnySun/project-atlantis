# Runtime case manifest guide

Use `schemas/gba-runtime-case.schema.json` as the machine contract and `examples/gba-runtime-validation/` for copyright-free fixtures. This guide describes the evidence intent, not a second schema.

## Identity and policy

Pin `rom.sha256` and `rom.size`. Select `evidence_level` from `natural`, `state-assisted`, `controlled-consumer`, or `static-only`. Set `unknown_policy` to `fail-closed`; an unsupported or unexercised required capability must produce `unknown` and exit 2.

## Static checks

- `allowed_changes`: patched ranges must stay inside declared regions.
- `pointers`: decode the stored pointer, then check GBA address range, alignment, and `expected_target` when relocation must be exact.
- `regions`: hash or compare bounded target and adjacent regions without placing their payload in reports. Give them explicit `role: target` and `role: adjacent`; declaring either role without the other is invalid.
- `records`: prove bounded termination and neighbouring-record boundaries.
- `encoding`: enumerate valid bytes, multibyte forms, control codes, and forbidden sequences. Use `control_codes` with `argument_units` and optional `argument_values` when an introducer consumes following units; truncated or out-of-range arguments fail.
- `layout`: supply actual glyph widths, line breaks, pixel width, and line capacity. Missing metrics remain unknown.
- `aliases`: identify records expected to share or not share storage.

## Runtime actions

Actions execute in order and each carries a stable `id`.

- `wait_until`: bounded boot/state predicate.
- `run`: bounded free-running interval followed by an interrupt.
- `keys`: buttons and deterministic hold/release reads through the KEYINPUT consumer hook.
- `breakpoint` / `watchpoint`: stop at a real consumer or access.
- `write_register` / `write_memory`: declared controlled setup, never hidden natural progression.
- `capture`: hash bounded `regions`, derive `register_regions`, and produce structured BG, OAM, or Mode 3 `renders`.

Put cross-snapshot comparisons in `runtime.assertions`; use stable capture IDs and paths.

Require only capabilities the case truly needs, but never delete a requirement merely to turn an unknown result green.

For `state-assisted`, pin the local state file hash and size in `runtime.savestate`, require at least one state-specific live memory predicate, pass the file with `--savestate`, and require `savestate-load-at-launch`. File identity without a matching live predicate remains unproven.

## Minimum menu/text receipt

A convincing non-playthrough text case records ROM identity, boot predicate, input or declared controlled reachability, consumer breakpoint, source-region hash, destination/render evidence, target and adjacent checks, required/exercised capabilities, and the final tri-state verdict. Screenshots may aid review but cannot replace these fields.
