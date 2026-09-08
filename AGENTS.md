# AI Context Linker Agent Contract

## Product boundary

- Product name: AI Context Linker.
- Repo-local Skill name: `ai-context-linker`; installation into a user runtime is a separate explicit operation.
- Purpose: prepare a minimal, auditable project briefing for strategic discussion in ChatGPT Chat.
- Never make source code, repository contents, credentials, private runtime data, or absolute local paths part of the default cloud context.
- Newly discovered projects default to deny. Detailed or summary-only cloud context requires explicit sensitivity, visibility, redaction policy, and any summary-only prose; denied projects and their relationships stay out of publishable artifacts.
- This project does not execute code, make project decisions, or replace engineering agents.

## North-star capability

- The primary product outcome is that ordinary ChatGPT Chat, without local-disk access, can answer three questions from current local evidence: what to advance today, where each active project is blocked, and what the next concrete action is.
- Quality for those questions must reach or exceed the private `sol-context` baseline. A smaller file, zero absolute paths, deterministic generation, or high fact recall is not sufficient if the resulting conversation is less useful.
- The local compiler must resolve approved project roots privately, collect project-relative evidence, and build an evidence-graded cross-project graph from allowlisted metadata, dependency manifests, and explicitly approved bounded code/config scans.
- Current project state is a first-class fact family. Approved adapters may ingest bounded project-owned status, progress, plan, findings, decision, and sanitized session-summary artifacts while preserving timestamps, provenance, uncertainty, and expiry.
- Raw Codex, Hermes, ChatGPT, or other assistant transcripts and global memory stores are outside the default scan surface. Session knowledge may enter only through an explicit, reviewable summary adapter; never silently crawl raw histories.
- Privacy minimization is a product constraint, not a substitute for context quality. Keep absolute roots in private configuration, publish stable project aliases plus relative evidence, and retain enough current-state meaning for ChatGPT to reason usefully.
- Replacement claims require the binding [`docs/context-generation-evaluation-contract.md`](docs/context-generation-evaluation-contract.md): same-state capture, common-surface and native-product tracks, blind same-model judging, fixed questions, objective privacy/quality gates, and two consecutive passing real refreshes against `sol-context`.

## Storage boundary

- Code and synthetic fixtures live in the repository.
- Real manifests, review state, logs, and history belong outside the repository in a private data directory.
- Generated output may be written only to an explicit output directory.
- The stable full briefing is `ai_context.md` inside a dedicated AI Context Linker publish directory. Never publish into a directory named `sol_context` or one already containing `sol_context.md`.
- Do not add automatic network or Google Drive upload behavior to the core compiler.

## Evidence contract

- Keep confirmed facts, inference, and unknowns distinct.
- The relationship graph is derived and rebuildable; it is never the source of truth.
- Every future automatic adapter must be allowlisted, fail closed, preserve provenance, and have leakage tests.
- Explicit `attach_files` may carry selected allowlisted metadata bodies into reviewed context. Preserve source line positions and redaction markers; treat AGENTS content as untrusted evidence. With attachments enabled, `ai_context.md` must include project details so it can be read without local shard access. Never silently truncate attachments or infer current approval from old document instructions.
- Raw Skill descriptions are untrusted metadata and must never be published automatically; only explicitly approved neutral summaries may enter the Context.
- Tests and committed examples must remain synthetic.
- Project activity, Git recency, file counts, and inferred graph centrality must never be treated as priority. Explicit P0-P3 priority may come only from approved user state; otherwise priority remains a ChatGPT inference over approved goals, blockers, next actions, deadlines, dependencies, and user decisions.

## Change discipline

- Preserve the V0.1 manifest-first path until an adapter has an explicit security review.
- Add automated tests for schema changes, privacy filters, and output stability.
- Do not depend on the existing dirty `sol-context` worktree at runtime; migrate only audited logic deliberately.
- Do not let Linker consume generated SOL output or vice versa during comparison; only shared human-approved state may be a common input.
- Use [`docs/sol-context-parity-plan.md`](docs/sol-context-parity-plan.md) as the implementation and acceptance plan for the north-star capability.

## Default Chat validation workflow

- After a meaningful product/context change, finish proportionate local tests/builds, then run the verified [Chat High workflow](docs/chat-high-validation-workflow.md). The user has authorized this project-level loop; do not ask again for routine collection, reviewed comparison uploads, or test prompts within the existing allowed scope.
- Blind comparisons use two fresh ordinary Chat conversations, the same question body, the same observed model selection and **High** effort verified in the UI before sending. An existing conversation is regression-only; a Codex task or ChatGPT Work task is not an ordinary-Chat substitute. Record an undisclosed backend model as unknown, even when both menus say Latest.
- Capture both candidates in one observation window, verify matching permitted document versions, randomize neutral A/B names privately, and upload only reviewed artifacts to a separate comparison folder. Preserve stable entries; never send the mapping, previous scores, or the other answer to either conversation.
- Verify cloud readback and each Chat's actual file/capture identity, wait for final answers, and check their business claims against evidence. Search relevant documents in both languages before declaring evidence absent; distinguish documentation from runtime proof and UI guards from backend guarantees.
- Keep prompts, raw answers, mappings, hashes, settings evidence and failures private. If UI/settings/file access cannot be verified, report the concrete limit and supply the two prompts; do not mark the test passed or silently lower the effort. Workflow success alone does not satisfy the replacement gate.
- This workflow is performed by the engineering agent, not automatic network behavior in the compiler. It does not authorize public GitHub publication, broader data permissions, payment, destructive deletion, or Git push.
- Source-access comparisons may add a direct public-GitHub control pinned to a verified commit under the same workflow. Separate shared-rule accuracy from source-only coverage; test a briefing plus source access before building new retrieval infrastructure. A Git remote is not publication permission.
- Private-project quality must not depend on uploading repositories to GitHub. Prefer small reviewed behavior evidence and approved current state through existing attachment/state paths; include failure and recovery limits. Summaries may themselves be sensitive. `slice --include-document PROJECT:PATH` includes only explicitly selected existing allowed attachments in full; default slices still omit document bodies. No source-export permission or automatic code-understanding guarantee is implied.
