# AI Context Linker

**Use ChatGPT as a project thinking partner — without uploading your repositories.**

> 让普通 ChatGPT 持续理解你的本地项目，只同步经过审阅的项目认知，不上传整个代码库。

[![CI](https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml/badge.svg)](https://github.com/xhonye/AI-Context-Linker/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

ChatGPT is excellent at strategy, prioritization, and brainstorming. The problem is context: it cannot see what is happening across your local projects, while uploading whole repositories is noisy and can expose code, credentials, private paths, or runtime data.

AI Context Linker builds a small, reviewable project briefing on your computer. You decide what is allowed, inspect the candidate, and share only the generated Markdown through a file upload, a ChatGPT Project, or a dedicated Drive folder supported by your account.

The result is a better ChatGPT conversation with much less repeated explanation.

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

## Real before / after

Both screenshots use the same question:

> 从本地电脑看看我今天要推进什么项目

### Before — ChatGPT has no local project context

ChatGPT correctly says it cannot inspect the computer, but it also cannot identify a concrete project or next step.

<p align="center">
  <img src="docs/assets/demo-before.png" alt="Before: ChatGPT cannot identify which local project to advance" width="820">
</p>

### After — ChatGPT reads a reviewed project briefing

After the dedicated context file is available, ChatGPT can ground the discussion in actual project facts and propose a concrete priority with explicit reasoning.

<p align="center">
  <img src="docs/assets/demo-after.png" alt="After: ChatGPT retrieves the reviewed project context" width="820">
</p>

The screenshot uses the maintainer's earlier private dogfooding prototype. That workflow proved the use case. Its audited, reusable capabilities now live in AI Context Linker; ChatGPT still does not receive direct disk or repository access.

## How it works

```text
Local project folders
        ↓
Discover project candidates from explicit roots
        ↓
Collect bounded, allowlisted facts on your computer
        ↓
Private candidate manifest + change report
        ↓  human review and approval
Stable Markdown briefing + derived relationship graph
        ↓
The file-delivery method supported by your ChatGPT account
        ↓
Grounded project strategy, prioritization, and brainstorming
```

AI Context Linker is a **local context compiler**, not a cloud crawler. The core package has no network or automatic upload behavior.

## Privacy model

Default scans may read approved project metadata such as README and AGENTS files, Git metadata, conventional entry-point filenames, test-file presence, and explicitly observed paths. They do not read source bodies.

Before anything is suitable for sharing, Linker creates private review artifacts. The final compiler then:

- accepts only a strict allowlist schema;
- rejects unknown fields, common secret patterns, and local absolute paths;
- keeps confirmed facts, unknowns, and derived relationships separate;
- verifies deterministic fact and change hashes;
- writes only to a directory you explicitly select.

An optional per-project `code_relationship_scan` can inspect bounded local code/config files for exact references to another approved project root. It is off by default and publishes neither source lines nor absolute roots. Every derived edge remains a review candidate.

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
  --config-out "C:/Private/ai-context-linker/workspace.json"

# 2. Remove unwanted candidates and review each metadata allowlist, then scan.
python -m ai_context_linker scan `
  --config "C:/Private/ai-context-linker/workspace.json" `
  --review-dir "C:/Private/ai-context-linker/review"

# 3. Review candidate-manifest.json and scan-report.json before publishing.
python -m ai_context_linker build `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --output-dir output

# 4. Optional: create a smaller briefing for one discussion.
python -m ai_context_linker slice `
  --manifest "C:/Private/ai-context-linker/review/candidate-manifest.json" `
  --question "What should I move forward today?" `
  --output-dir output
```

Generated files:

- `ai_context_linker.md` — the stable briefing for ordinary ChatGPT conversations;
- `ai_context_linker.graph.json` — a rebuildable relationship view;
- `ai_context_linker.question.md` — an optional question-directed briefing.

Keep the workspace config, candidate manifest, and scan report in a private local directory. Share only an output you have reviewed. Do not connect or synchronize your repository root, workspace root, or private data directory.

## Use it with ChatGPT

Choose the narrowest delivery method available to your account:

1. upload the reviewed Markdown to a conversation;
2. add it to a dedicated ChatGPT Project;
3. if your account or workspace supports a Google Drive connection, synchronize only a dedicated output folder.

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
- declared-dependency, explicit document-reference, and opt-in code-path relationships;
- separate SHA-256 identities for the fact snapshot and its comparison view;
- deterministic full and question-directed Markdown;
- a derived JSON relationship graph;
- fail-closed schema, secret, absolute-path, link, reparse-point, and root-escape checks;
- zero required model calls from local collection to final output.

In a 2026-08-16 private dogfooding audit, Linker covered all 29 approved projects and recovered 130 of 141 agreed core fact instances (92.2%). The generated artifacts contained no source lines, local absolute paths, or common secret-pattern hits. See the aggregate [prototype migration audit](docs/prototype-migration-baseline.md); no private project data is committed here.

## What it is not

AI Context Linker does not replace a coding agent. It does not inspect implementation details by default, run code, edit repositories, or decide priorities for you. It gives ChatGPT enough reviewed context to have a useful strategic conversation and tells it where evidence is still missing.

The graph is a derived navigation view, not a source of truth. Git activity is evidence of activity, not evidence of importance, adoption, or success.

## Project docs

- [Project charter](PROJECT_CHARTER.md)
- [Architecture](docs/architecture.md)
- [Context contract](docs/context-contract.md)
- [Security boundary](docs/security-boundary.md)
- [Roadmap](docs/roadmap.md)
- [Competitive landscape](docs/competitive-landscape.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Open source

AI Context Linker is MIT licensed. The standalone CLI and JSON Schemas are the product core; `skills/ai-context-linker/` is an optional thin interface for compatible agents.

If this solves a context problem you have with ChatGPT, try it on a synthetic or low-risk workspace first, share what was confusing, and consider starring the repository so more people can find it.
