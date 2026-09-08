# Changelog

## 0.2.5 — 2026-09-08

Selected-evidence release. Public availability is recorded by the GitHub release.

- Let `slice --include-document PROJECT:PATH` include complete, explicitly selected manifest attachments with original line numbers and redaction markers. Reuse the existing document renderer; default slices remain unchanged.
- Keep document selection independent from heuristic project ranking. Reject unknown or non-allowed projects, missing attachments, and a combined selection over eight documents or 256 KiB; never open source files or truncate failure conditions.
- Add a synthetic behavior-note template distinguishing inspected implementation, tests and unknowns. An exploratory High Chat comparison found better detail coverage with a small reviewed note; this is not automatic code understanding or SOL replacement acceptance.

## 0.2.4 — 2026-09-08

Local evidence-cleanup release.

- Keep complete attached contracts as the rule source instead of also extracting truncated, duplicate constraint bullets. Metadata-only scans and explicit configured records remain supported.
- Reuse the same configuration-aware constraint label in full briefings, project cards and question slices; shortened output no longer promotes configured records to confirmed facts.
- Verify document refreshes replace previous rules in the new briefing while keeping the old snapshot reproducible. Explicitly distinguish direct evidence from inferred behavior.

## 0.2.3 — 2026-09-08

- Expose which project briefing fields contain existing configuration, retaining their values while warning that collection time does not establish configuration freshness. Apply the warning to full cards and question slices.
- Label mixed configuration/document constraints as records requiring current-document review, and distinguish attached historical plans and changes from current capabilities.
- Expand the maintainer's new private attachment selection to allowed business projects; preserve previous comparison inputs and do not enable attachments for denied or summary-only projects.

## 0.2.2 — 2026-09-08

- Add explicit `attach_files` for selected allowlisted metadata documents, including README and AGENTS. Preserve relative provenance and line positions, visibly redact sensitive lines and private-key blocks, and reject missing or oversized documents.
- Include all project cards and selected document bodies in `ai_context.md` when attachments are enabled, supporting follow-up reasoning without local-disk access. Keep the existing default bundle unchanged.
- Include document changes in fact hashes and semantic review; preserve attachment choices during rediscovery. Mark attached instructions as untrusted project data and abbreviated slices as incomplete.

Local release only; online same-model comparison and SOL replacement remain unverified.

## 0.2.1 — 2026-09-08

Local maintenance release; public publication is tracked separately.

- Preserve reviewed workspace configuration, private state sources and architecture policy during rediscovery; reserve existing project IDs so new folders cannot inherit another project's permissions.
- Add optional `build --as-of` using the same lifecycle clock as question slices. Expired actions leave the entry, remain labeled in project history, and do not mutate the source snapshot or graph.
- Restore future-dated record freshness when its timestamp is reached, without reopening closed records; allow missing state files to reach lifecycle review.
- Distinguish JavaScript/Cargo development and build dependencies from runtime dependencies. Reject malformed dependency tables as parse errors.
- Remove guessed cross-module and out-of-scope calls, preserve imported class members, and ignore JavaScript imports inside comments or strings.
- Report text, expiry and other semantic edits to existing stable state records.
- Merge four atomic writers, avoid full architecture deep copies and duplicate priority selection, and preflight invalid output files before replacing an existing briefing.

### Previously unreleased changes

- Add optional timezone-aware `slice --as-of` action-expiry re-evaluation, preserve deterministic snapshot replay, and disclose capture/evaluation times without mutating approved inputs or renewing approvals.

- Add a private, read-only Chinese review-state preview with exact-byte version hashes, explicit unapproved status, scoped projects, privacy/path guards and a Chinese end-user guide; no state import or approval.
- Preserve valid `why_now` and its evidence in today/next-action slices, separately from selection-rule reasons; expired and unreviewed reasons remain unknown.
- Add repository-only `check` and `candidate` verification profiles with frozen source copies, strict test accounting, both gold suites, private logs, offline installed-wheel checks and shared Linux/Windows CI; no model calls, state approval or release actions.
- Align the build-backend minimum with the existing SPDX license metadata and make offline build dependencies explicit in the development extra.
- Add offline Q1-Q6 blind-run input freezing, raw-response integrity auditing and deterministic double-order aggregates without model calls or automatic replacement approval.
- Keep resolved/superseded state visible as history, recheck explicit-record freshness, apply same-batch supersession, and share priority rules across workspace entry and slices.
- Prevent visibility revocation from restoring old private state or exposing revoked project identities through snapshot differences; reject detailed summary-only manifests and unreviewed blocker edges.
- Preflight output links/reparse points, protect SOL directories for question slices, mark every Markdown surface as untrusted data, and disclose structure-slice omissions and module-level call limits.
- Add an opt-in deterministic Python/JavaScript/TypeScript Architecture Index with project-relative modules, structural symbols, imports, test-module flags, filtered internal calls, map hashes, and fail-closed manifest validation.
- Split the publish bundle into a small `ai_context.md` workspace/action entry, searchable `projects/<project-id>.md` shards, and a project/module/import/call graph.
- Add a generated bundle inventory so rebuilds remove only stale Linker-owned project shards instead of leaving obsolete Drive-searchable cards.
- Add Architecture Index semantic diff coverage plus a synthetic percentage-gated evaluator for recall, precision, evidence, privacy, and determinism.
- Rank architecture question slices by question-matched modules and symbols, incoming internal-call targets, and public entry points before deterministic truncation.
- Stop generated Markdown from claiming that a structurally valid input manifest is approved; approval remains proven only by the external immutable snapshot record.
- Add a safe `init-review-state` command that creates an unapproved, non-actionable seven-day skeleton for one to three explicit projects.
- Stop broad `current` heading matches, checked tasks, status lines, and file-control lines from becoming current goals or deadlines.
- Short-circuit no-baseline change slices and bound relationship slices while collapsing scan and document-reference noise by default.
- Add a binding cross-generator evaluation contract with common-surface, native-product, and optional full-code oracle tracks, blind same-model judging, objective gates, and a two-refresh replacement rule.
- Rename the stable full briefing to `ai_context.md` and fail closed when a build targets the SOL Context directory or a directory already containing `sol_context.md`.
- Add the v0.2 approved action review-state contract with v0.1 migration, complete bounded Markdown extraction, and unknown-by-default status.
- Normalize project action facts into stable lifecycle-aware `StateRecord` objects with explicit resolution, supersession, staleness, and review states.
- Add explicit immutable `approve-snapshot` history; scanning never approves its own candidate.
- Generate path-free `changes.json` and `changes.md` for project, goal, next-action, blocker, deadline, and relationship changes, with Git counts isolated in an appendix.
- Add deterministic Priority Slice v2 with a three-project cap, one minimal blocker endpoint per main project, fixed action fields, and derived-recommendation labeling.
- Add explicit P0-P3 human priority, fail closed on more than three simultaneous P0/P1 projects, and explain why other projects were not selected today.
- Replace ambiguous dependency labels with the layered Relationship Graph v2 contract and isolate AI semantic proposals in a private review queue with zero automatic promotion.
- Add a 13-case synthetic gold evaluation harness and checked-in aggregate report for action transfer, lifecycle, priority, semantic diff, relationship precision, privacy, and determinism gates.
- Add a v0.1-to-v0.2 migration guide plus synthetic v0.2 manifest and review-state examples.
- Add project-level `allow`, `summary-only`, and `deny` cloud visibility with explicit sensitivity and redaction profiles; unclassified projects fail closed to `deny`.
- Stop publishing raw Skill frontmatter descriptions. Publish only names plus explicitly approved neutral summaries, and detect prompt-override or command-like metadata.
- Reuse approved project IDs across path moves through opaque private Git-origin hashes; never persist raw remotes.
- Discover project state files as unapproved candidates and add an opt-in deterministic state adapter with provenance, freshness, and relative line evidence.
- Add a strict neutral JSON session-summary adapter that rejects transcript-shaped fields and reads no raw assistant history.
- Derive `blocked-by` only from explicit non-closed state references to another approved project alias.
- Focus today, blocker, and next-action slices on lifecycle-resolved approved action state and minimal `blocked-by` endpoints instead of all projects or ordinary graph neighbors.
- Apply URL, email, IP endpoint, and UNC-address rejection to every publishable manifest field.
- Add a controlled offline A/B evaluation harness and synthetic scorecard fixtures.

- Add opt-in Skill discovery across Codex/Agent Skills, Claude Code, and Gemini CLI user and workspace roots.
- Read only bounded `SKILL.md` frontmatter names and descriptions for local audit, never instruction bodies or supporting files; raw descriptions are not publication inputs.
- Apply compiler-enforced secret, path, URL, email, IP endpoint, UNC-address, and instruction-like content checks to Skill metadata and approved summaries.
- Add Skill inventory rendering, change detection, and question-directed slicing.
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
- Align the public workspace schema with constraints and opt-in relationship scanning.
- Skip hidden directories during opt-in code relationship discovery.
- Reject bare Windows drive roots such as `D:/` from publishable text.
- Reframe the public README around using ordinary ChatGPT as a project thinking partner.

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
