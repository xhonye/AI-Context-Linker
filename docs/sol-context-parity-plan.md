# sol-context capability parity plan

## Objective

Make AI Context Linker the safer and at least equally useful context layer for ordinary ChatGPT Chat when the user asks:

1. What should I advance today?
2. Where is each active project blocked?
3. What is the next concrete action?

The target is not byte-for-byte reproduction of `sol-context`. The target is equal or better decision support with a smaller, reviewable cloud surface and no dependency on model-generated indexing.

## Active execution plan — parity, then superiority

This is the current implementation sequence. The older phases below remain the
design history and completed foundation; new work must follow these three stages
instead of opening another parallel compiler or roadmap.

### Stage 1 — Real action parity

Make the first three fixed questions reliably answerable from approved current
state, while keeping automatic Markdown extraction review-only.

Implementation status (2026-08-29): engineering and synthetic/real-structure
checks are complete. The private same-model Q1-Q3 run remains part of Stage 3
because it requires human-approved current action state.

Deliverables:

- reject completed/status/file-list control lines as current goals or deadlines;
- scope Markdown extraction to explicit semantic heading blocks and preserve
  complete multi-line items;
- provide a private `init-review-state` template command for at most three
  explicitly selected projects without inventing values or approving the file;
- short-circuit the changes slice when no approved baseline exists;
- bound relationship slices and keep scan/document-reference noise collapsed by
  default;
- keep Q1-Q3 at no more than three main projects with exactly one approved next
  action and one minimal blocker endpoint per project.

Acceptance gates:

- completed-to-current-goal and control-line-to-deadline false positives = 0;
- approved next-action transfer = 100%;
- blocker precision/recall >= 90% / 90%;
- resolved blocker false-positive rate <= 5%;
- Q1-Q3 are deterministic, <= 12 KiB each, and explain every selection or
  omission;
- a no-baseline Q5 is <= 2 KiB and explicitly refuses to claim change;
- published path, secret, address, and instruction-injection findings = 0;
- a private same-model run over no more than three approved real projects is no
  worse than SOL Context on Q1-Q3.

### Stage 2 — Privacy-safe architecture superiority

Add one opt-in deterministic Architecture Index adapter to the existing scanner.
Audit and deliberately migrate only the bounded parsing ideas from SOL Context;
do not import it at runtime or add model preprocessing.

Implementation status (2026-08-29): the adapter, strict manifest contract,
sharded bundle, project/module graph, semantic diff, code-question slice, and
synthetic percentage-gated evaluator are implemented. The fixed real
code-navigation comparison against SOL Context remains a Stage 3 acceptance
input and is not inferred from synthetic results.

Published structure may include project-relative module IDs, language, class and
function names, internal imports, external package names, test modules, bounded
internal syntactic-call clues, map hashes, truncation, and parse-failure counts.
It must exclude source bodies, comments, docstrings, literals, default values,
absolute roots, and generic calls such as `append`, `get`, or `str`.

Use a sharded publish bundle:

- `ai_context.md` remains the small workspace/action entry;
- `projects/<project-id>.md` contains reviewed project facts and its bounded
  structure index;
- `ai_context_linker.graph.json` remains the rebuildable cross-project graph.

Acceptance gates:

- Python, JavaScript, and TypeScript synthetic structure gold is deterministic;
- module and symbol recall >= 95%, test-module recall = 100%, and internal-call
  precision >= 95%;
- published structural evidence coverage = 100%;
- excluded/generated/link/reparse trees never enter the index;
- source bodies published = 0 and configured privacy leaks = 0;
- architecture changes enter semantic snapshot diff;
- the fixed code-navigation answer is no worse than SOL Context while retrieving
  materially less context.

### Stage 3 — Two-refresh replacement gate

Capture common-surface and native-product tracks from the same approved project
set, action state, and observation window. Blind generator identity, use the same
ChatGPT Pro model and exact fixed questions in fresh conversations, and run both
candidate orderings.

The second refresh must contain a real lifecycle or semantic change, such as a
resolved/superseded blocker, changed next action or deadline, or approved
relationship change. A duplicate static capture does not count.

Replacement requires two consecutive refreshes where:

- all objective privacy, relationship, diff, lifecycle, and determinism gates
  pass;
- Q1-Q3 are individually no worse than SOL Context;
- Q4-Q6 lose no material relationship, semantic change, or code-navigation fact;
- strategic-discussion usefulness is no worse, while retrieval focus or privacy
  is strictly better;
- Linker keeps zero model preprocessing calls and does not fabricate or reuse
  stale approved state.

Only after this gate passes may the dedicated Linker Drive entry become the
default. Keep SOL Context as a rollback benchmark for one additional release
cycle. Real prompts, answers, manifests, reviewer notes, and approval history
remain outside Git.

## Current verified gap

The 2026-08-27 live comparison found that Linker preserved project identity, approved constraints, Git facts, Skills, snapshot changes, and evidence-graded relationships, but did not preserve enough current project state.

- Linker published 29 previously approved projects; `sol-context` discovered 33.
- Linker had no non-default project statuses, no project risks, and only three open questions belonging to one project.
- `sol-context` also read project-owned `progress.md`, `task_plan.md`, and `findings.md` where present, then produced evidence-bound stage, blocker, opportunity, and unknown judgments for all projects.
- Linker's broad “today” slice remained large because it lacked strong state fields with which to select a small active set.

Therefore deterministic fact coverage and zero-path publication did not establish action-oriented parity. As of 2026-08-28 the missing v0.2 action contract is implemented and passes synthetic gates, but the real same-model comparison still has to be rerun with approved current review state.

## Non-negotiable boundaries

- Keep project absolute roots only in the private workspace configuration and scan report.
- Publish project IDs, stable aliases, relative evidence paths, and line numbers.
- Do not scan raw assistant transcripts, global memory stores, private databases, runtime records, `.env`, credentials, medical records, investment account data, or browser data.
- Do not infer priority from commit count, dirty paths, file count, test count, graph degree, or repository size.
- Any state or session adapter must be opt-in, bounded, schema-validated, provenance-preserving, human-reviewable, and fail closed on secret or absolute-path findings.
- Preserve the model-free `discover -> scan -> review -> build` path. ChatGPT performs the final prioritization from approved facts.

## Phase 0 — Reproducible parity benchmark

Build a local evaluation harness before adding new facts.

The binding protocol is [`context-generation-evaluation-contract.md`](context-generation-evaluation-contract.md).
It controls capture timing, common-surface versus native-product tracks,
blind same-model judging, optional full-code oracle checks, objective metrics,
private artifact handling, and the two-consecutive-refresh replacement gate.
This plan records implementation work; where wording differs, the evaluation
contract governs the comparison.

Implementation status:

- [x] Fixed question IDs and exact question text;
- [x] controlled full-workspace and Linker condition flags;
- [x] 0–4 multidimensional scorecard with private evaluator notes;
- [x] automatic answer-size, absolute-path, and likely-secret measurements;
- [x] path-free aggregate Markdown and JSON reports;
- [x] synthetic regression tests for parity, leakage, missing questions, and path escape;
- [ ] first private GPT-5.6 Sol full-workspace versus Linker evaluation run.

### Fixed questions

- What should I advance today, and why?
- Which active projects are blocked, and by what evidence?
- What is the next concrete action for every active project?
- Which projects depend on, overlap with, or should potentially consolidate into another?
- What changed since the previous approved snapshot, and which earlier recommendation should be reconsidered?

### Scoring dimensions

Score each answer from 0 to 4 for:

- factual grounding;
- current-state freshness;
- blocker recall;
- next-action recall;
- relationship usefulness;
- uncertainty discipline;
- privacy compliance;
- context size and retrieval focus.

Keep the same model, prompt, question, date, and project set for Linker and `sol-context`. Store only aggregate scores and synthetic fixtures in Git; real prompts, manifests, and answers remain private.

### Exit gate

- No fabricated project status, blocker, deadline, or next action.
- Zero secret-pattern and raw absolute-root findings in the publishable bundle.
- Linker is no worse than `sol-context` on the first three questions and better on privacy.

## Phase 1 — Approved project path registry

Turn discovery candidates into a durable private project registry.

### Deliverables

Implementation note (2026-08-28): unique Git origins are stored only as opaque hashes in the private config and may reuse a previously approved ID after a path move. Repositories without a unique origin deliberately require review after moving.

- Stable project ID and display-name mapping across machines and drive letters.
- Explicit approve, reject, rename, and retire decisions for discovered projects.
- Private root aliases that can resolve a project locally without entering the cloud bundle.
- Snapshot changes for added, removed, moved, and renamed projects.

Status: deterministic stable ID reuse is implemented. Approve/reject/retire remains a private configuration review operation rather than a new project-management subsystem.

### Tests

- Moving the same project to another drive does not change its published identity.
- Relative evidence resolves under the approved root and cannot escape it.
- New candidates never enter the publishable manifest without approval.

## Phase 2 — Project-state adapter

Add an opt-in `state_files` adapter for project-owned Markdown at the project root. Initial supported names:

- `STATUS.md`;
- `progress.md`;
- `task_plan.md`;
- `findings.md`;
- `ROADMAP.md`.

### Published schema

Implementation note (2026-08-28): deterministic project-state extraction and the private v0.2 review-state adapter are implemented. Automatically extracted state remains reviewable; approved current action state comes from explicit review JSON.

Each v0.2 StateRecord carries:

- `record_id`, `kind`, and lifecycle `status`;
- bounded text;
- `source_kind`, path-free `source_ref`, and `observed_at`;
- optional `expires_at` and `supersedes`;
- compatibility freshness, provenance, and evidence fields.

The manifest-level `generated_at` records collection time. Approval is now recorded by a separate immutable `approve-snapshot` command; scan never auto-approves.

### Extraction rules

- Read only explicitly enabled files, with byte and item limits.
- Prefer explicit headings and Markdown task syntax; do not summarize arbitrary prose into confirmed facts.
- Reject or redact secrets, raw absolute paths, URLs and identities according to field policy.
- Mark stale or undated state as stale/unknown rather than current.
- Deduplicate repeated status copied across files.

### Exit gate

- Synthetic tests cover fresh, stale, contradictory, missing, unsafe, oversized, linked, and root-escape inputs.
- The bundle can identify a blocker and next action without a model call when the project has stated them.

## Phase 3 — Sanitized session-summary adapter

Support recent AI-assisted work without crawling raw chat histories.

### Input contract

Implementation note (2026-08-28): the strict neutral JSON adapter is implemented. Unknown transcript-shaped fields are rejected and the scan report records zero raw transcripts read.

Accept an explicitly supplied local JSON summary containing only:

- project ID;
- session date;
- completed work;
- decisions;
- blockers;
- next actions;
- unresolved questions;
- relative evidence references when available.

The adapter must not know Codex, Hermes, ChatGPT, Claude, or Gemini private storage layouts. Tool-specific exporters may generate this neutral format outside the core package.

### Merge rules

- Project-owned state outranks session summaries when they conflict.
- Newer approved summaries may supersede older summaries but never erase history silently.
- Unsupported claims remain session-reported, not confirmed repository facts.
- Apply retention and freshness windows so old sessions do not masquerade as current work.

### Exit gate

- Raw transcript text, tool logs, prompts, user memory, and local session paths never enter the candidate manifest.
- A recent approved summary measurably improves blocker and next-action recall in the fixed benchmark.

## Phase 4 — Action-aware relationship graph

The v0.2 graph distinguishes `contains`, `scans-or-indexes`, runtime/build dependency, shared data, blockers, document references, and intentional separation. Human-approved semantic types cover overlap, alternative, replacement, complement, and merge judgments.

Use project IDs and relative evidence. Do not publish the absolute path used for local matching. Do not derive priority from graph centrality.

AI discussion hypotheses use the `ai-candidate` layer and remain only in the private review queue. Formal output contains observed and approved-semantic layers with evidence. The graph now distinguishes package dependency, document mention, local project-root reference, and AI hypothesis without claiming per-edge freshness that is not available.

## Phase 5 — Action-focused slicing

Replace broad keyword slicing for “today” and “next step” with deterministic state selection.

### Selection order

Implementation note (2026-08-28): Priority Slice v2 resolves lifecycle first, then uses approved P0/P1, `attention=today`, current deadline, open blocker, and active-with-approved-next-action in fixed order. It caps output at three main projects and one minimal blocker endpoint per main project, explains omissions, and rejects more than three simultaneous P0/P1 projects as a human priority conflict.

The first private deterministic refresh, rerun after raw-line safety hardening but before project-level semantic visibility and raw Skill-description isolation, selected three of 34 projects for the fixed “today” question and reduced the briefing from 88,757 bytes to 8,935 bytes. Two projects had current action evidence and one was included as an explicit `blocked-by` endpoint. It is historical implementation evidence, not a current safety claim or the still-pending same-model A/B score.

1. Approved `priority=P0/P1`.
2. Approved `attention=today`.
3. Current deadline.
4. Open blocker.
5. Active project with approved next action.
6. One minimal required blocker endpoint per selected project.

Git activity may describe recency but cannot select or rank projects by itself.

### Exit gate

- A “today” slice excludes unrelated dormant projects.
- Every included project has an explicit selection reason.
- Every omitted project has a specific reason or belongs to an explicit no-approved-action-evidence count.
- The slice is materially smaller than the full bundle while preserving all evidence needed for the answer.

## Phase 6 — Publication and replacement decision

- Generate full and question-directed Linker bundles from the same approved snapshot.
- Run schema, hash, path, secret, stale-state, graph-integrity, and leakage tests.
- Run the 13-case synthetic gold suite and keep every configured gate green.
- Run the fixed same-model A/B evaluation against the latest valid `sol-context` output.
- Publish Linker as the sole default Drive context only after the parity exit gate passes.
- Keep `sol-context` as a private rollback benchmark until two consecutive real refreshes pass the gate.

## Implementation order

1. Benchmark harness and synthetic fixtures.
2. Durable private project registry and approval UX.
3. Project-state schema, adapter, privacy policy, and tests.
4. Neutral session-summary schema and adapter.
5. State-aware relationship edges.
6. Action-focused slice selection.
7. Two live private A/B refreshes and replacement decision.

Do not start with raw session crawling, vector storage, an LLM enrichment pipeline, or a general knowledge graph. Those increase privacy and complexity before the missing current-state facts are solved.
