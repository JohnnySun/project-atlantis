---
name: gba-runtime-validation
description: Validate GBA ROM boot, input, menus, localized text, memory, registers, VRAM, OAM, palettes, tilemaps, pointers, adjacent records, clipping, and rendering with deterministic mGBA/GDB evidence. Use whenever work needs runtime ROM QA, breakpoint/watchpoint probes, save-state or controlled-consumer reachability, machine-readable case manifests, or fail-closed reports; do not rely on OCR or screenshots alone.
---

# GBA Runtime Validation

Build reproducible evidence that a patched GBA ROM boots, reacts to input, reaches the intended menu or text consumer, and preserves both the target record and its neighbours.

## Read before acting

1. Read the repository `AGENTS.md` and `.agents/skills/gba-localization/SKILL.md`.
2. Read `core/gba/runtime_validation/README.md`, `docs/technical/gba-runtime-validation.md`, and [references/manifest-guide.md](references/manifest-guide.md).
3. Read the target game's extraction, reinsertion, encoding, and runtime-probe documentation.
4. Inspect `git status` and preserve all unrelated dirty work. Treat game directories as read-only unless the task explicitly owns them.

Never commit ROMs, save states, screenshots containing full copyrighted text, raw memory dumps, or complete source strings. Store live artifacts under `/private/tmp` or ignored game paths and commit only hashes, bounded metadata, verdicts, and reproducible manifests with no copyrighted payload.

## Choose an evidence level

Label every case with the strongest level actually demonstrated:

- `natural`: fresh boot plus normal injected input reaches the case.
- `state-assisted`: a provenance-checked save state reaches the case; record ROM hash, emulator build, state hash, and creation recipe outside version control when copyrighted.
- `controlled-consumer`: a bounded register/RAM setup or consumer hook invokes the real render/decoder path without claiming natural reachability.
- `static-only`: ROM structure is checked but runtime behavior is unproven.

Do not upgrade controlled injection or a screenshot into natural reachability. A missed breakpoint, unsupported capability, ambiguous state, or missing adjacent check is `unknown`, never `pass`.

## Define the case

Create a JSON manifest conforming to `schemas/gba-runtime-case.schema.json`. Keep ROM paths outside committed manifests; pass the ROM with `--rom` at runtime. Pin its SHA-256 and size in the manifest.

Declare:

- the exact target bytes and at least one adjacent record or guard region;
- pointer source, permitted target range, alignment, and relocation expectations;
- terminator, control-code, encoding, glyph coverage, line-width, line-count, and alias rules;
- required runtime capabilities and every boot, input, breakpoint, watchpoint, capture, write, or assertion action;
- explicit timeouts and deterministic frame counts.

If glyph metrics are incomplete, omit guessed defaults so width becomes `unknown`. Do not hide uncertainty behind a permissive fallback.

## Run static gates first

Use the repository runner rather than ad-hoc parsing:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-qa.py static CASE.json --base-rom GAME.gba --output /private/tmp/CASE-static.json
```

Resolve every `fail` and understand every `unknown` before live execution. Preserve existing re-extract, translation-ledger, pointer, BPS, and repository-safety checks; this framework supplements them.

## Own the emulator process

Probe an independent high local port before launch. Start one emulator instance, record its exact PID, connect one runner, and terminate only that PID. Never use broad `pkill`, shared ports, or another session's process. If the local mGBA build fixes its GDB port in source, verify the actual listen port instead of assuming a CLI setting overrides it.

Treat the bind probe and launch as separate, raceable events. Before connecting the runner, verify that the listener PID on the selected port is exactly the PID just started. Record a child identity token immediately after launch (at least PID, parent PID, process start time, and executable/command), and revalidate that token before every signal; a numeric PID alone is vulnerable to PID reuse. If another PID wins the port, stop only your still-identity-matching child and choose another port or build; never let the runner connect based on port number alone.

Use the shared owner rather than writing another per-game launcher. It performs
the pre-launch bind probe, launches an absolute executable and ROM path,
requires the sole listener PID to equal the child PID, records PID/PPID/start
time/command immediately after launch, requires readiness to match that exact
initial token before connecting the runner, revalidates identity before cleanup, preserves runner exit
`0/1/2`, and emits a separate session receipt:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-session.py preflight \
  --port PORT --session-report /private/tmp/CASE-preflight.json

PYTHONDONTWRITEBYTECODE=1 python3 scripts/gba-runtime-session.py run CASE.json \
  --rom GAME.gba --mgba /absolute/path/to/mgba-headless --port PORT \
  --runtime-report /private/tmp/CASE-runtime.json \
  --session-report /private/tmp/CASE-session.json \
  --log /private/tmp/CASE-mgba.log
```

Pass emulator-specific switches with repeated `--mgba-arg`; for example,
`--mgba-arg=-C --mgba-arg=ports.qt.gdbPort=PORT`. These switches are not proof
that the port moved: the post-launch listener check remains authoritative. For
a source-fixed GDB port, use the port actually compiled into that executable.
An ownership receipt with `status=pass` proves only process/listener ownership;
the runtime report independently determines whether the game case passed.
If the numeric PID, ROM token, and listener still match but PID/PPID/start time
or command differs from the launch token, ownership is `unknown` with
`initial_identity_changed`; the runtime runner must not start.

## Exercise real runtime surfaces

- Prove boot with a bounded wait on a stable register or memory predicate.
- Inject input through the game's observed KEYINPUT read path. Prefer the repository's read-watchpoint hook over directly writing read-only MMIO.
- Use breakpoints/watchpoints to identify the real consumer and capture bounded register regions.
- Use controlled register or RAM writes only when declared by the case; state which natural progression they replace.
- Capture bounded memory hashes plus decoded BG/tilemap, OAM, palette, or Mode 3 evidence as appropriate.
- Assert both target behavior and adjacent stability. A changed framebuffer hash alone does not prove the intended string rendered.

Prefer existing components: `core/gba/gdbstub_client.py`, `capture_runtime.py`, `render_vram.py`, `render_oam.py`, and game-specific probes. Add shared behavior to `core/gba/runtime_validation/`, not a copied one-off harness.

## Interpret and verify

Runner exits are contractual:

- `0`: all required checks passed and required capabilities were exercised.
- `1`: a definite validation failure occurred.
- `2`: evidence is incomplete, unsupported, or ambiguous.

Validate report shape and copyright boundaries:

```bash
python3 .agents/skills/gba-runtime-validation/scripts/check_report.py /private/tmp/CASE-runtime.json
```

The report must list required, exercised, and unproven capabilities; action-level results; hashes or structured render metadata; and a top-level `pass`, `fail`, or `unknown`. Reject raw byte/text fields and any `pass` with an unproven required capability.
The checker's own exit `0` means the report is structurally consistent and copyright-safe; it does not turn a structurally valid `fail` or `unknown` report into a case pass. Read the report status (or the runner's `0/1/2`) separately.

## Finish the localization QA chain

Rerun the target game's extraction/re-extraction comparison, ledger validation, deterministic patch/BPS build, clean-base apply, static manifest, runtime manifest, tests, and repository-safety check. Record emulator identity, ROM hash, manifest hash or committed path, evidence level, commands, and report digest in a copyright-safe receipt.

Commit only owned paths with explicit pathspecs and repository author identity. Do not stage broadly, reset, stash, rebase, or overwrite other agents' work.
