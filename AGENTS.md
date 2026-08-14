# Project Atlantis workspace guidance

## Reusable skills

- When development produces a stable, repeatable workflow or body of knowledge, consider extracting it into a workspace skill under `.agents/skills/<skill-name>/`.
- Use the workspace-installed Anthropic `skill-creator` skill when creating, revising, evaluating, or packaging those skills.
- Create a skill only when the material is reusable across future tasks; keep game-specific facts in the relevant game's documentation.
- Prefer small, focused skills with explicit trigger descriptions, deterministic scripts for repetitive work, and source or license attribution for imported material.
- Validate a new skill before treating it as part of the normal workflow, and commit its files with the work that motivated it when practical.

## Project scope

- Project Atlantis is a device-independent, general GBA localization project. Do not introduce KONKR, Project Advance, ADB, or device deployment concerns into its project identity or core architecture.
- Traditional Chinese output targets `zh-TW`; do not silently treat it as an unspecified generic `zh-Hant` target.
- Repository-authored commits use `JohnnySun <bmy001@gmail.com>`.
