# Changelog

## Unreleased

- Add shallow project discovery across explicit workspace roots.
- Keep discovered absolute paths confined to a private, reviewable configuration.
- Reject cloud-synced config targets, directory links, reparse points, root escapes, and accidental overwrite.
- Omit automatically derived absolute paths from summaries while continuing to fail closed on likely secrets.
- Add bounded filename-only entry-point and test inventory with no source-body reads.
- Add coarse Git change categories and 30-day activity facts without publishing changed filenames.
- Apply link and Windows reparse-point protection to manually configured project roots and Git metadata.
- Extract at most five open checklist items from approved metadata with relative line evidence; source TODO comments remain unread.
- Derive graded declared-dependency and document-reference edges from reviewed structured metadata.
- Suppress generic project IDs, ambiguous package identities, ordinary prose matches, and repeated template references.
- Bind snapshot changes with an independent hash while keeping the fact hash stable across comparison baselines.
- Add deterministic question-directed briefings for priority, change, relationship, overview, and named-project discussions.
- Extract bounded project constraints from explicitly approved contract sections without reading source bodies.
- Add an explicit opt-in code-path relationship adapter with bounded local reads and no source-text or absolute-root publication.

## 0.2.0 - 2026-08-12

- Add an allowlist-only local workspace scanner.
- Generate a private review report and candidate manifest before publishing.
- Add deterministic fact hashes and previous-snapshot change summaries.
- Keep local paths out of candidate manifests and generated bundles.
- Preserve a two-step human approval gate with zero required model calls.
- Verify fact hashes at publish time and reject sensitive observed-path names.
- Disable Git filesystem monitors and submodule recursion during metadata collection.
- Reject private review output paths that visibly target common cloud-sync folders.

## 0.1.0 - 2026-08-12

- Add a strict approved-manifest compiler for AI-readable project briefings.
- Generate deterministic Markdown and a derived relationship graph.
- Reject unsupported fields, likely secrets, absolute local paths, and dangling relationships.
- Publish an open JSON Schema, synthetic examples, and an optional agent Skill.
- Add privacy documentation, contribution guidance, security reporting, and CI.
