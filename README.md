🌐 **English** · [简体中文](README.zh-CN.md)

<p align="center">
  <img src="docs/assets/logo.svg" width="96" height="96" alt="AI Context Linker logo: two connected links">
</p>

<h1 align="center">AI Context Linker</h1>

<p align="center"><strong>Help ChatGPT Chat understand all your local projects.</strong></p>

<p align="center">Turn the project details you choose to share into a reviewable briefing.<br>Discuss what each project does, where it is blocked, and what to do next in ordinary Chat.</p>

<p align="center"><strong>Ordinary Chat analysis · No Codex quota used · No whole-repository upload</strong></p>

<p align="center"><a href="#quick-start">Quick start</a> · <a href="#what-changed-in-real-question-tests">See the results</a></p>

<p align="center">
  <a href="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml"><img src="https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
</p>

**Already subscribe to ChatGPT? Use it to discuss your local projects.**

- **Plus:** Choose a higher reasoning effort available in ordinary Chat to analyze your projects without using Codex quota.
- **Pro:** Choose a Pro mode available in ordinary Chat for more complex project questions, without invoking Codex.

Models and reasoning options depend on your account, and ChatGPT plan limits still apply. Separate Codex work to prepare evidence or develop projects still uses Codex quota; [ChatGPT Work shares usage with Codex](https://learn.chatgpt.com/docs/pricing).

**Local, pure Python scripts. Zero third-party Python runtime dependencies.**

- **Prepare data locally:** Core collection and rendering make no network or AI/model API calls and never upload automatically. Git metadata is read through your local Git installation.
- **Control what is read:** New projects are excluded from export by default. Only explicitly allowed material is collected; scanned project code is never executed and business source files are not modified. No whole-repository upload is needed.
- **Review before sharing:** Built-in sensitive-data checks and redaction produce output you can preview and trace to its sources. You choose what to share with Chat; business-sensitive information still needs your review.

Chat reasons from the evidence you share; missing or stale state remains unknown. Deliver only reviewed output through a file upload, a ChatGPT Project, or a dedicated Drive folder supported by your account. See the [security boundary](docs/security-boundary.md).

## What it helps you do

- Ask **“What should I move forward today?”** with the current project map already available.
- Discuss **the next step for every project** without re-explaining each repository in every chat.
- Find **overlap, dependencies, and possible consolidation** across many projects.
- Ask **what changed since the last approved snapshot** instead of relying on stale memory.
- Use ChatGPT for product direction and trade-offs, while reserving Codex or another coding agent for work that truly requires source access and execution.

| Without a context layer | With AI Context Linker |
|---|---|
| ChatGPT starts from almost nothing | ChatGPT receives a current, structured project map |
| You repeatedly paste background into new chats | One stable briefing can support many discussions |
| Advice is generic because evidence is missing | Suggestions can cite approved facts, constraints, and changes |
| The easiest shortcut is uploading too much | The publication surface is deliberately small and reviewable |
| Activity can be mistaken for importance | The briefing tells ChatGPT not to infer value from commits or file counts |

## What changed in real question tests

Missing evidence can make an AI suggest rebuilding something that already exists.
The useful improvement is to supply the few reviewed rules that explain the product,
including failure and recovery behavior, without uploading the repository.

| Evidence supplied | Observed result |
|---|---|
| Briefings with missing business documents | Some existing capabilities were missed; historical records could be confused with current behavior |
| Briefings with complete selected documents | Core answers became comparable to the private baseline; source references exposed stale configuration |
| The same briefing plus a short reviewed behavior note | A later pair answered more previously missing implementation details with 9.4% more input text |

These are limited maintainer experiments, not an independent benchmark or a claim
of complete replacement. The last pair used two fresh ordinary Chat conversations
with High effort; both showed Latest, so the exact backend model is unknown.
The note was checked by an engineering agent, not inferred by the compiler.
See the [anonymized observations and limits](docs/question-test-observations.md).

<details>
<summary>Earlier rounds: anonymized Chinese result cards</summary>

These AI-redrawn cards are anonymized interpretations, not original chat evidence.
Names, internal platforms, paths and specific private business rules are omitted.
The second card includes a corrected evidence assessment.

![Round one: missing evidence can lead to duplicate development advice](docs/assets/round-1-anonymized.png)

![Round two: complete business evidence improves answer grounding](docs/assets/round-2-anonymized.png)

</details>

## How it works

```text
Local project folders
        ↓
Discover project candidates from explicit roots
        ↓
Collect bounded, allowlisted facts on your computer
        ↓
Private candidate manifest + semantic changes + relationship review queue
        ↓  human review
Explicit immutable snapshot approval
        ↓
Small workspace entry + project shards + derived structure graph
        ↓
The file-delivery method supported by your ChatGPT account
        ↓
Grounded project strategy, prioritization, and brainstorming
```

AI Context Linker is a **local context compiler**, not a cloud crawler. The core package has no network or automatic upload behavior.

## Include documents for offline follow-up

When a rule document is attached in full, its rules are not also copied into
truncated constraint bullets. Keep durable owner decisions in configuration;
remove verified stale copies of repository rules from a new private config and
let fresh document captures provide those details. Previous snapshots remain
reproducible. Default question slices omit document bodies; explicit selections can carry the needed attachments.

Scanner manifests identify `configuration_fields`: briefing fields that include
existing configured prose. The briefing keeps those values and warns that their
current validity has not been automatically checked. Collection time is not the
configuration's update time. Conflicts with documents or approved state remain
explicit uncertainties instead of being silently merged into current facts.

When Chat cannot look up local files, select metadata documents to carry with the
briefing. In an allowed project's private workspace configuration:

```json
"allow_files": ["README.md", "AGENTS.md"],
"attach_files": ["README.md", "AGENTS.md"]
```

`attach_files` defaults to empty and must be a subset of `allow_files`. Scan and
review the candidate as usual, then build it. With attachments enabled,
**`ai_context.md` contains all project cards and the selected document bodies**;
sharing this single file delivers those materials. Project shards remain available.
Question slices omit attachments by default. To make one discussion self-contained, select the needed documents already captured in the reviewed manifest:

```powershell
python -m ai_context_linker slice --manifest <reviewed-manifest.json> `
  --question "How does example handle failed restore?" `
  --include-document example:docs/chat-context/README.md `
  --output-dir <private-output-dir>
```

Repeat `--include-document PROJECT:PATH` for each exact attachment. These are manifest references, not local file paths. The selected document is included even if the question's project heuristic does not select its project; this does not change project priority. Unselected attachments stay out. Unknown projects, non-allowed visibility, missing documents and selections over eight unique documents or 256 KiB of UTF-8 body text fail before replacing the output. Selected bodies retain all lines, including failure conditions.

For private projects, prepare a small reviewed behavior note using the [synthetic template](examples/behavior-note/README.md), then explicitly list its path in both `allow_files` and `attach_files`. Do not upload the repository. The compiler collects the note; it does not derive or certify its claims. Keep underlying source hashes privately and re-review the note after source changes. Code inspection, passing tests and real-use acceptance are different evidence grades. A note can itself contain business secrets and must be reviewed before sharing.

Documents retain relative source names and original line numbers. Unsafe lines
and private-key blocks are replaced with visible redaction markers; the filter
cannot detect every business secret. AGENTS text is quoted project evidence, not
instructions for the receiving Chat. Documents reflect the collection time, not
necessarily current or approved project state. Links, images, unselected files,
and arbitrary code details are not included.

Limits: 8 documents per project, 64 KiB per document, 256 KiB per project. Missing
selected documents and oversized input stop the scan instead of silently omitting
content. This feature uses no local AI and adds no upload behavior.

## Privacy model

Discovery does not make a project cloud-readable. Every discovered project defaults to `cloud_visibility: deny`, so it and its relationships stay out of the candidate until a human classifies it. Detailed collection requires explicit `cloud_visibility: allow`, `sensitivity`, and `redaction_profile`. `summary-only` additionally requires an `approved_summary` and publishes no Git, state, constraints, risks, evidence, or automatic relationships.

For explicitly allowed projects, scans may read approved metadata such as README and AGENTS files, Git metadata, conventional entry-point filenames, test-file presence, and explicitly observed paths. They do not read source bodies by default. A separate per-project `architecture_visibility` switch may opt into bounded local syntax parsing; even then, source text never enters the candidate or publish bundle.

Before anything is suitable for sharing, Linker creates private review artifacts. The final compiler then:

- accepts only a strict allowlist schema;
- enforces project-level semantic visibility before metadata, state, or relationships can enter the cloud context;
- rejects unknown fields, common secret patterns, local absolute paths, URLs, email addresses, IP endpoints, and UNC addresses;
- keeps confirmed facts, unknowns, and derived relationships separate;
- verifies deterministic fact and change hashes;
- keeps lifecycle states (`open`, `resolved`, `superseded`, `stale`, `needs_review`) explicit;
- excludes unapproved `ai-candidate` relationships from Markdown, graphs, slices, and semantic diffs;
- writes only to a directory you explicitly select.

An optional per-project `code_relationship_scan` can inspect bounded local code/config files for exact references to another approved project root. It is off by default and publishes neither source lines nor absolute roots. Every derived edge remains a review candidate.

An optional per-project `architecture_visibility` can be set to `modules-only` or `modules-symbols`. It is also off by default and requires detailed `cloud_visibility: allow`; summary-only or denied projects cannot enable it. The deterministic adapter supports Python, JavaScript, and TypeScript and may publish only project-relative module IDs, language, test-module flags, qualified class/function/method names, internal imports, external package names, bounded internal calls, evidence anchors, a map hash, truncation, and parse-failure counts. It excludes source bodies, comments, docstrings, string values, default values, absolute roots, hidden/generated/output/example/fixture/backup trees, and generic calls such as `append`, `get`, `str`, or `map`.

Architecture question slices remain bounded, but they rank question-matched modules and symbols, internal-call targets, and public entry points before truncation. Generated Markdown proves deterministic compilation, not human approval: only the separate immutable `approve-snapshot` record establishes that the input manifest was reviewed for publication.

Read the complete [security boundary](docs/security-boundary.md) before using real projects.

## Quick start

Requirements: Python 3.11 or newer.

```powershell
git clone https://github.com/xhonye/AI-Context-Linker.git
Set-Location AI-Context-Linker
python -m pip install -e .

# 1. Discover direct child projects under explicit roots.
python -m ai_context_linker discover `
  --root "C:/Workspace" `
  --root "C:/Workspace/Projects" `
  --include-skills `
  --config-out "C:/Private/ai-context-linker/workspace.json"

# On later refreshes, preserve approved IDs even if a Git project moved.
python -m ai_context_linker discover `
  --root "C:/Workspace/Projects" `
  --previous-config "C:/Private/ai-context-linker/workspace.json" `
  --config-out "C:/Private/ai-context-linker/workspace-next.json"

# 2. Set each project's sensitivity, visibility, redaction profile, and optional
#    approved summary. Only then review metadata allowlists and scan.
python -m ai_context_linker scan `
  --config "C:/Private/ai-context-linker/workspace.json" `
  --review-dir "C:/Private/ai-context-linker/review"

# 3. Optional: create a safe private skeleton for one to three explicit projects.
#    The skeleton contains no action facts and does not approve itself.
python -m ai_context_linker init-review-state `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --project "sample-project" `
  --output "C:/Private/ai-context-linker/review-state-v0.2.json"

#    Edit the private JSON, add it to review_state_files, then scan again.

# 4. Review candidate-manifest.json, scan-report.json, changes.json,
#    changes.md, and relationship-review-queue.json. Then record approval.
python -m ai_context_linker approve-snapshot `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --history-dir "C:/Private/ai-context-linker/history"

# 5. Build only the reviewed, explicitly approved manifest.
python -m ai_context_linker build `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --output-dir output

# 6. Optional: create a smaller briefing for one discussion.
python -m ai_context_linker slice `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --question "What should I move forward today?" `
  --output-dir output

# On later scans, compare only with the last explicitly approved snapshot.
python -m ai_context_linker scan `
  --config "C:/Private/ai-context-linker/workspace.json" `
  --review-dir "C:/Private/ai-context-linker/review-next" `
  --previous-snapshot "C:/Private/ai-context-linker/history/approved-snapshot-latest.json"
```

Generated files:

- private review: `candidate-manifest.json`, `scan-report.json`, `changes.json`, `changes.md`, and `relationship-review-queue.json`;
- private approval history: immutable `approved-snapshot-*.json` plus `approved-snapshot-latest.json`;
- `ai_context.md` — the small stable workspace/action entry for ordinary ChatGPT conversations;
- `projects/<project-id>.md` — independently searchable reviewed project facts and optional bounded structure index;
- `ai_context_linker.graph.json` — a rebuildable project/module relationship view;
- `ai_context_linker.bundle.json` — the generated project-shard inventory used to remove only stale Linker-owned cards on rebuild;
- `ai_context_linker.question.md` — an optional question-directed briefing.

The root entry deliberately stays small. ChatGPT can retrieve one project shard for a focused discussion instead of loading the entire workspace. Architecture-aware questions can also use the module/import/call nodes in the derived graph without receiving source text.

Discovery records opaque Git-origin or path hashes only in the private config. A unique Git-origin hash lets an approved project keep the same public ID after a folder or drive move; raw remote URLs never enter the config or published bundle. Projects without a unique Git origin require review after a move instead of being guessed.

### Refresh without losing reviewed context

`discover --previous-config` preserves matched projects' policies, the reviewed
workspace description, relationships, state/session sources and approved Skill
summaries. Relative private paths retain their meaning even when the new config
is written elsewhere. New projects remain denied; a coincidentally matching name
cannot inherit an old project's permission. Use `--workspace-name` only when you
want to rename the workspace. Removed source projects or stale configured
relationships may still require explicit review during the next scan.

Both `build` and `slice` accept `--as-of` to recheck action validity at an explicit
timezone-aware timestamp:

```powershell
python -m ai_context_linker build --manifest <reviewed-manifest.json> --output-dir <publish-dir> --as-of "2026-09-08T12:00:00+08:00"
```

Expired actions leave the current-action entry and remain labeled as history in
project cards. This does not collect newer facts or renew approval. Omitting
`--as-of` preserves deterministic replay at the source snapshot time.

### Current project state, without an AI indexing call

Discovery lists root-level `STATUS.md`, `progress.md`, `task_plan.md`, `findings.md`, `ROADMAP.md`, or `DECISIONS.md` under private `state_file_candidates`, but does not approve them. Move reviewed names into `state_files` to opt in. Linker then extracts bounded list items and complete bounded paragraphs under exact semantic heading blocks; a filename, a phase title that merely contains “current,” status/control lines, and completed checklist items cannot silently become a current goal or deadline. Automatically extracted state remains `needs_review` and cannot silently become the current priority.

Current action authority comes from an explicit private v0.2 review-state file, referenced through `review_state_files`. It can approve `priority`, `activity`, `attention`, `why_now`, `current_goal`, `next_action`, `done_when`, `owner`, `due_at`, `blockers`, `updated_at`, and `expires_at`. Approved state outranks automatically extracted state without deleting the original evidence. Missing approved state stays `unknown`; Git activity never fills the gap.

`init-review-state` creates a valid seven-day private skeleton for one to three explicit project IDs. It writes only project IDs and timestamps: no priority, blocker, goal, or next action is guessed, and no snapshot approval is recorded. Add reviewed facts yourself before referencing the file from `review_state_files`.

`preview-review-state --manifest ... --review-state ... --project ... --output ...`
renders an existing draft as a private Chinese review sheet. It preserves original
values, marks every field unapproved, shows expiry and an exact-byte draft hash,
and never imports state or records approval. A local assistant may help fill the
draft from your Chinese instructions; the compiler does not call a model. Keep
the sheet outside repositories and sync/publish folders. See the
[Chinese usage guide](docs/quickstart-zh-CN.md) for a runnable synthetic example.

All v0.2 items compile into stable `StateRecord` entries. Only a stable `record_id` or explicit `supersedes` can close an older record. If a source disappears, the previous record becomes `needs_review`, not `resolved`. A scan writes semantic changes against the previous explicitly approved snapshot; it never approves itself.

Recent AI-assisted work can enter through the neutral [`session-summary.schema.json`](schema/session-summary.schema.json). Add approved JSON files to the private top-level `session_summary_files` list. The adapter accepts only structured completed work, decisions, blockers, next actions, unresolved questions, and optional relative evidence. It has no knowledge of ChatGPT, Codex, Claude, Gemini, or Hermes history locations; transcript-shaped fields are rejected.

For “today” and “next action” questions, v0.2 resolves the complete state lifecycle before selection. It then selects, in order: approved `priority=P0/P1`, approved `attention=today`, a current deadline, an open blocker, and an active project with an approved next action. More than three simultaneous P0/P1 projects fails closed as a human priority conflict. The slice includes at most three main projects, at most one minimal `blocked-by` endpoint for each, and a compact “today not selected” explanation for the remaining workspace. When no human priority exists, the output labels its ordering as a `derived-recommendation`.

Each selected project carries its valid `why_now` and evidence separately from
the deterministic selection reason; an expired or missing reason stays unknown.

### Relationship layers

V0.2 distinguishes observed relationships (`scans-or-indexes`, runtime/build dependency, shared data, blockers, document references), approved semantic relationships (`overlaps-with`, alternatives, replacement, complement, separation, merge decisions), and `ai-candidate` proposals. Exact project-root references are `scans-or-indexes`; they are not runtime-dependency proof. AI proposals go only to the private relationship review queue. A human must add an approved semantic edge before it can enter the formal graph.

Relationship questions expand at most 12 detailed edges across eight projects. `scans-or-indexes` and `document-reference` are counted but collapsed by default. Change questions short-circuit when no previous approved snapshot exists, so a baseline scan cannot masquerade as a workspace-wide change.

### Optional cross-tool Skill inventory

`discover --include-skills` adds detected, private Skill roots for:

- Codex and the shared Agent Skills standard: `~/.agents/skills` and project `.agents/skills`;
- Codex desktop compatibility: `~/.codex/skills`;
- Claude Code: `~/.claude/skills` and project `.claude/skills`;
- Gemini CLI: `~/.gemini/skills`, project `.gemini/skills`, and the shared `.agents/skills` alias.

The scanner reads only the bounded YAML frontmatter in each direct child `SKILL.md`, extracts the declared name and audits the raw description, then stops at the closing `---`. It does not read the instruction body, bundled scripts, references, or assets. The raw description is never published automatically.

By default the Context contains the Skill name plus a neutral withholding notice. To publish a capability summary, add a human-written neutral phrase to that root's private `approved_summaries` map. Both raw and approved summaries are checked for secrets, addresses, and instruction-like language such as attempts to override prompts, require tool calls, upload, send, delete, execute, or silently record. Raw findings stay in the private scan report; unsafe approved summaries fail closed.

See [Skill inventory and privacy](docs/skill-inventory.md) for supported locations, limits, and evidence sources.

Keep the workspace config, candidate manifest, and scan report in a private local directory. Share only an output you have reviewed. Do not connect or synchronize your repository root, workspace root, or private data directory.

## Use it with ChatGPT

Choose the narrowest delivery method available to your account:

1. upload the reviewed Markdown to a conversation;
2. add it to a dedicated ChatGPT Project;
3. if your account or workspace supports a Google Drive connection, synchronize only a dedicated `ai_context_linker` output folder. Do not reuse a `sol_context` folder or mix the two stable entry files.

Then try questions such as:

```text
Read the latest AI Context Linker briefing first.

Which project should I advance this week, and why?
Separate confirmed facts from your inference.
Do not treat commit count or file count as project value.
```

```text
Which projects appear to overlap or depend on one another?
Which relationships are confirmed, which are only document references,
and what is the smallest additional evidence needed?
```

```text
What changed since the previous approved snapshot?
Which earlier recommendation should be reconsidered because of those changes?
```

## Current capabilities

- shallow discovery across one or more explicit workspace roots;
- private project selection and metadata allowlists;
- bounded Git, entry-point, test-presence, open-item, and contract-constraint facts;
- stable private project identity reuse across path moves when a unique Git origin is available;
- opt-in structured project-state and neutral sanitized session-summary facts with freshness and relative evidence;
- cross-tool Skill names plus explicitly approved neutral summaries, with raw descriptions and instruction bodies withheld;
- lifecycle-aware current goal, blocker, next action, deadline, owner, completion criterion, and attention records;
- explicit approved snapshot history plus semantic `changes.json` and `changes.md`;
- layered runtime/build dependency, shared-data, blocker, document-reference, separation, overlap, alternative, replacement, complement, and merge relationships;
- private AI relationship candidate review queue with zero automatic promotion;
- separate SHA-256 identities for the fact snapshot and its comparison view;
- deterministic full and question-directed Markdown;
- action-focused today/next-step slices that exclude projects without selection evidence;
- a derived JSON relationship graph;
- fixed deterministic priority slices capped at three main projects plus minimal dependency endpoints;
- fail-closed schema, secret, absolute-path, link, reparse-point, and root-escape checks;
- project-level `allow` / `summary-only` / `deny` semantic visibility and Skill instruction-injection isolation;
- zero required model calls from local collection to final output.

In a 2026-08-16 private dogfooding audit, Linker covered all 29 approved projects and recovered 130 of 141 agreed core fact instances (92.2%). The generated artifacts contained no source lines, local absolute paths, or common secret-pattern hits. See the aggregate [prototype migration audit](docs/prototype-migration-baseline.md); no private project data is committed here.

## How we evaluate usefulness

We do not treat a smaller file or a successful privacy scan as proof that the resulting ChatGPT conversation is useful.

The acceptance design separates three tracks:

1. **Common-surface:** SOL and Linker briefings use the same approved state, project set, observation window and permitted evidence surface. Fresh, identity-blinded judges answer the same questions in both orders.
2. **Native-product:** each generator follows its normal workflow; extra inputs, AI preprocessing and privacy costs are disclosed separately.
3. **Optional full-workspace oracle:** a code-capable model such as GPT-5.6 Sol inspects permitted local evidence with its available context budget. This high-information reference is checked against direct evidence, never treated as project-state authority or mixed into blind candidate scores.

The fixed questions include:

- What should I advance today, and why?
- Where is each active project blocked?
- What is the next concrete action?
- Which projects depend on, overlap with, or may consolidate into another?
- What changed since the previous approved snapshot?
- Where should an engineer inspect the code, and what cannot be known from a structure-only index?

The full-workspace answer is a high-information reference, not unquestionable ground truth. Claims still need evidence. Linker is considered a real replacement only when it produces no material loss on the action-oriented questions while exposing substantially less local data. Aggregate evaluation results may be published; private projects, prompts, manifests, paths, and raw answers are not committed.

An earlier 2026-08-28 private refresh, before project-level semantic visibility and raw Skill-description isolation were added, produced an 88,757-byte full briefing and an 8,935-byte three-project action slice. That run validated deterministic selection and pattern-based privacy checks only. It is retained as audit evidence, not as proof of current safety or same-model parity.

The offline evaluator accepts a private paired-answer scorecard and emits only a path-free aggregate report:

```powershell
python -m ai_context_linker evaluate `
  --scorecard "C:/Private/ai-context-linker/evaluation/scorecard.json" `
  --output-dir "C:/Private/ai-context-linker/evaluation/report"
```

The legacy scorecard contract is defined in [`schema/evaluation-scorecard.schema.json`](schema/evaluation-scorecard.schema.json), with a runnable synthetic example under [`examples/evaluation/`](examples/evaluation/). It remains a five-question, single-pair diagnostic: `paired_answer_checks_pass` does not establish replacement, and `replacement_ready` stays false. It computes answer size and leakage findings while keeping raw answers and notes out of aggregate reports.

The [local blind-evaluation loop](docs/local-blind-evaluation.md) adds frozen Q1-Q6 inputs, isolated double-order subagent judging, raw-response hashes and regression tests. Local judges accelerate diagnosis; they do not certify ChatGPT Pro behavior. An unknown-only structural excerpt cannot prove action parity, and no score automatically approves project state.

The repository also includes a deterministic v0.2 gold suite covering blocker lifecycle, human priority, deadlines, dependency endpoints, privacy injection, false-positive relationships, approved separation, unapproved AI merge proposals, missing baselines, disappeared sources, and stale approvals:

```powershell
python -m ai_context_linker evaluate-gold `
  --suite examples/evaluation/gold-v02/gold-suite.json `
  --output-dir output/gold-evaluation
```

Architecture Index has a separate Python/JavaScript/TypeScript synthetic gold fixture and percentage gates:

```powershell
python -m ai_context_linker evaluate-architecture `
  --fixture-dir examples/evaluation/architecture-gold/project `
  --expected examples/evaluation/architecture-gold/expected.json `
  --output-dir output/architecture-evaluation
```

It requires at least 95% module and symbol recall, 100% test-module recall, at least 95% internal-call precision, 100% structural evidence coverage and determinism, and zero configured privacy leaks or published source bodies.

Its checked-in synthetic report currently passes every configured release gate. This proves the implementation contract against synthetic facts; it does not prove same-model real-workspace parity with `sol-context`.

## What it is not

AI Context Linker does not replace a coding agent. It does not inspect implementation details by default, run code, edit repositories, or decide priorities for you. It gives ChatGPT enough reviewed context to have a useful strategic conversation and tells it where evidence is still missing.

The graph is a derived navigation view, not a source of truth. Git activity is evidence of activity, not evidence of importance, adoption, or success.

## Project docs

- [Project charter](PROJECT_CHARTER.md)
- [Architecture](docs/architecture.md)
- [Context contract](docs/context-contract.md)
- [V0.1 to V0.2 migration](docs/migration-v0.1-to-v0.2.md)
- [Security boundary](docs/security-boundary.md)
- [Roadmap](docs/roadmap.md)
- [sol-context capability parity plan](docs/sol-context-parity-plan.md)
- [Competitive landscape](docs/competitive-landscape.md)
- [Skill inventory and privacy](docs/skill-inventory.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Open source

AI Context Linker is MIT licensed. The standalone CLI and JSON Schemas are the product core; `skills/ai-context-linker/` is an optional thin interface for compatible agents.

If this solves a context problem you have with ChatGPT, try it on a synthetic or low-risk workspace first, share what was confusing, and consider starring the repository so more people can find it.
