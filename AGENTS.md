# AI Context Linker Agent Contract

## Product boundary

- Product name: AI Context Linker.
- Purpose: prepare a minimal, auditable project briefing for strategic discussion in ChatGPT Chat.
- Never make source code, repository contents, credentials, private runtime data, or absolute local paths part of the default cloud context.
- This project does not execute code, make project decisions, or replace engineering agents.

## Storage boundary

- Code and synthetic fixtures live in the repository.
- Real manifests, review state, logs, and history belong outside the repository in a private data directory.
- Generated output may be written only to an explicit output directory.
- Do not add automatic network or Google Drive upload behavior to the core compiler.

## Evidence contract

- Keep confirmed facts, inference, and unknowns distinct.
- The relationship graph is derived and rebuildable; it is never the source of truth.
- Every future automatic adapter must be allowlisted, fail closed, preserve provenance, and have leakage tests.
- Tests and committed examples must remain synthetic.

## Change discipline

- Preserve the V0.1 manifest-first path until an adapter has an explicit security review.
- Add automated tests for schema changes, privacy filters, and output stability.
- Do not depend on the existing dirty `sol-context` worktree at runtime; migrate only audited logic deliberately.
