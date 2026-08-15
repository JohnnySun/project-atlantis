# Project Atlantis workspace guidance

## Reusable skills

- When development produces a stable, repeatable workflow or body of knowledge, consider extracting it into a workspace skill under `.agents/skills/<skill-name>/`.
- Use the workspace-installed Anthropic `skill-creator` skill when creating, revising, evaluating, or packaging those skills.
- Create a skill only when the material is reusable across future tasks; keep game-specific facts in the relevant game's documentation.
- Prefer small, focused skills with explicit trigger descriptions, deterministic scripts for repetitive work, and source or license attribution for imported material.
- Validate a new skill before treating it as part of the normal workflow, and commit its files with the work that motivated it when practical.

## Proper-noun transliteration policy

- When a translation needs to transliterate a proper noun (character/place/item name) and the source has no official localization to follow, do not invent a transliteration first. Check for an existing community-conventional Chinese name first, and default to whatever that convention turns out to be rather than our own judgment.
- Primary sources to check, for zh-TW work: Wikipedia (zh-tw) and 巴哈姆特 (Bahamut, forum.gamer.com.tw) community wikis/walkthroughs. Prefer WebSearch/WebFetch on these before other sources; fetch raw content directly (e.g. `curl` with a browser user-agent, or a wiki's raw/API endpoint) when a fetch tool gets bot-blocked or an AI-summarized fetch looks unreliable — verbatim text beats a paraphrase.
- Never settle on a single source. Check multiple independent ones (at minimum Wikipedia + Bahamut; add others — Baidu Baike, Moegirl, dedicated fan wikis, old walkthrough threads — when the first two disagree) and go with whichever rendering is the actual majority/mainstream across them, not whichever page was checked first or whichever matches our own prior choice.
- Watch for false leads: a page can be about an unrelated same-named entity (e.g. a same-titled character from a different franchise), and a single page can itself be internally inconsistent (typos, mixed variants from different eras of editing) — do not treat one page, or one mention on a page, as decisive.
- When sources genuinely split with no majority (e.g. three sources, three different spellings), do not force a pick — say so explicitly and default to keeping the existing in-repo translation rather than swapping it for an equally arbitrary alternative.
- Only fall back to an original transliteration when no existing community name can be found anywhere.

## Project scope

- Project Atlantis is a device-independent, general GBA localization project. Do not introduce KONKR, Project Advance, ADB, or device deployment concerns into its project identity or core architecture.
- Traditional Chinese output targets `zh-TW`; do not silently treat it as an unspecified generic `zh-Hant` target.
- Repository-authored commits use `JohnnySun <bmy001@gmail.com>`.
