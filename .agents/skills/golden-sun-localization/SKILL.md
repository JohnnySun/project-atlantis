---
name: golden-sun-localization
description: Safely extend Project Atlantis localization work for the GBA Golden Sun games. Use whenever work touches Golden Sun text extraction, Japanese codepages, translation JSONL, control codes, context Huffman rebuilding, Chinese glyph insertion, ROM delta validation, or BPS round-trip QA, even when the request only says to continue a translation batch.
---

# Golden Sun localization

Use this workflow to make localization batches reproducible while preventing unrelated ROM text from changing.

## Establish scope

1. Read the workspace `AGENTS.md` and the selected game's `README.md` and `ROADMAP.md`.
2. Inspect `git status --short`. Preserve unrelated and user-owned changes.
3. Treat ROMs, extracted scripts, rendered text, OCR output, and build artifacts as local research data. Do not add them to Git.
4. Keep game-specific revisions, offsets, pointers, hashes, and terminology in the selected game's documentation rather than this skill.

## Prepare a translation batch

1. Rebuild or inspect the ignored decoded Japanese JSONL produced by `core/golden-sun/decode-text-ids.rb`.
2. Confirm each source string against the strict codepage decoder. Use OCR only as candidate evidence; do not copy OCR output directly into translation records.
3. Select a coherent, reachable batch such as save UI, combat commands, or configuration labels.
4. Preserve the order and exact multiplicity of control codes. Delay records with unknown internal controls or dynamic interpolation until their semantics are understood.
5. Write `zh-TW` explicitly. Keep noun and verb terminology consistent, and mark unreviewed work as draft.

## Build safely

1. Run the game-specific data-driven builder using the clean verified ROM, extracted text IDs, game codepage, translation JSONL, licensed BDF, and an ignored output path.
2. Let the builder reject source mismatches, duplicate IDs, missing glyphs, and control-code mismatches. Fix the data rather than weakening these checks.
3. Re-extract all strings from the rebuilt ROM using the new pointer locations printed by the builder.
4. Run `scripts/verify_text_delta.rb SOURCE.tsv BUILT.tsv TRANSLATIONS.jsonl [MORE_TRANSLATIONS.jsonl ...]`. The changed IDs must exactly equal the union of IDs declared by every translation batch.
5. When generated glyph IDs cross a `0x100` boundary, confirm the context Huffman writer emits the additional tree group and that the generic extractor still decodes all strings.

## Verify the patch

1. Generate a BPS patch from the verified clean ROM and rebuilt ROM.
2. Apply the BPS patch to the clean ROM into a second ignored output.
3. Compare rebuilt and reapplied ROMs byte for byte, then record CRC32, patch size, and SHA-256 in the game README.
4. Run the shared Ruby tests and compile-check any platform-specific OCR helper that changed.
5. Perform mGBA runtime QA for reachable screens. Preserve test save data, and report screens that remain untested instead of inferring success.

## Commit boundary

Stage explicit paths only. Include reusable core changes, game documentation, codepages, tools, tests, and translation records. Exclude ROMs, patches, extracted scripts, screenshots, OCR output, `HANDOFF.md`, and unrelated game changes.

Report the translated ID set, glyph count and highest glyph ID, reverse-extraction result, BPS round-trip result, runtime coverage, remaining risks, and commit hash.
