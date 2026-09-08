# 2026-09-08 maintenance and product iteration

## Outcome and baseline

Keep the local, zero-runtime-dependency context compiler small and trustworthy.
The current user authorizes code review, refactoring, bug fixes and useful small
product iterations. Preserve existing uncommitted work. Release locally; remote
publication and real project-state approval are separate operations.

Before edits: 350 tests pass, both synthetic gold suites pass, and synthetic
scan/build/slice plus 34 documentation links pass. Exact source bytes, dirty
state and outputs are frozen in the private maintenance evidence directory.

## System and ownership

Discovery writes private deny-by-default project configuration. Scanner reads
approved metadata/state and optional bounded architecture, resolves lifecycle
against an approved predecessor, and produces a candidate and semantic changes.
Manifest validation guards all publishable facts. Build renders an entry, cards
and graph; slice selects facts for a question. Approval history remains separate.
SOL Context is an independently tested private product, not a runtime dependency.

## Iterations

1. Correct evidence: distinguish development/build dependencies from runtime
   dependencies; remove guessed cross-module calls and imports inside JS prose.
   Correct missing-file handling so source disappearance reaches lifecycle review.
2. Preserve refresh meaning: report edits to stable state records, retain explicit
   architecture policy during rediscovery, and re-evaluate future-dated records
   when their observation time is reached without reopening closed records.
3. Make complete bundles time-aware: optional `build --as-of` follows the existing
   slice contract, preserves original facts/hashes and makes expiry visible in
   both the entry and project cards. Default snapshot replay stays deterministic.
4. Cleanup after three iterations: merge duplicate atomic writers, avoid copying
   entire architecture payloads for state resolution, remove redundant dispatch
   and helpers where proven unused. Do not expand the schema or add frameworks.

## Verification and stop rule

Reproduce each logic bug before its fix; use synthetic fixtures in source control.
Compare unchanged baseline output byte-for-byte. Run focused regressions per
logical change, then one final frozen candidate including installed-wheel smoke.
Review actual CLI output and a private read-only real-input run when available.
Keep validation, private output, user acceptance, remote CI and replacement
claims distinct. Stop when remaining opportunities need actual user feedback,
approved current action facts or real same-model evaluation rather than more code.

## Completion checkpoint

The planned correctness, refresh and cleanup changes are implemented. Independent
review additionally identified and fixed permission inheritance through a new
project-name collision in Linker, and preflight now preserves an existing entry
when a project-card target is a directory. No framework or runtime dependency was
added. Existing manifests, approval boundaries and independent product entrypoints
remain supported. Exact final tests, installed artifact hashes, real private CLI
observations and the complete evolution report are retained outside the repository.
