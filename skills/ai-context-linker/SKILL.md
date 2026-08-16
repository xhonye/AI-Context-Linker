---
name: ai-context-linker
description: Scan allowlisted local project metadata and build privacy-safe AI Context Linker bundles from a reviewed JSON manifest. Use when a user asks to prepare or refresh local project context for ChatGPT or another AI assistant, validate an AI Context Linker workspace config or manifest, generate a project briefing or relationship graph, or publish reviewed context to an explicit local or Drive-synced directory without uploading source code.
---

# AI Context Linker

Use the standalone `ai-context-linker` CLI as the execution truth. Keep this Skill as a thin review and invocation layer.

## Workflow

1. Locate a private workspace config or an existing approved manifest. Keep configs containing local paths outside the repository and cloud-synced directories.
2. When a workspace config exists, generate review artifacts first:

```text
ai-context-linker scan --config <private-workspace.json> --review-dir <private-review-directory> [--previous-manifest <approved.json>]
```

3. Confirm the scan report says `source_code_bodies_read: 0` unless the user explicitly enabled per-project `code_relationship_scan`. For an opt-in scan, report the bounded read count and review every derived code-path relationship; never publish source lines or absolute roots. Review the candidate manifest and its change summary. Refuse source code, diffs, credentials, connection strings, private runtime data, or unconfirmed model inference.
4. Require the user to approve the candidate before writing to a cloud-synced destination. Keep facts, unknowns, and derived relationships distinct.
5. Require an explicit output directory. Never select a workspace root, repository root, home directory, or broad Drive directory.
6. Run:

```text
ai-context-linker build --manifest <approved.json> --output-dir <explicit-directory>
```

7. Report the candidate/report paths, the two generated files, the fact hash and any validation failure. Do not bypass a failure or weaken a filter.

For a specific discussion question, optionally generate a compact derivative after approval:

```text
ai-context-linker slice --manifest <approved.json> --question <question> --output-dir <explicit-directory>
```

Treat the slice as deterministic selection from the approved facts, not as an AI conclusion. Report its single Markdown path separately from the full bundle.

## Missing CLI

If `ai-context-linker` is unavailable, stop before publishing and tell the user to install the repository package with `python -m pip install -e .`. Do not reimplement the compiler inside the Skill.

## Safety contract

- Treat the manifest as the sole approved input and the graph as derived output.
- Never connect or sync an entire repository through this workflow.
- Never claim a generated briefing proves current code or runtime state.
- Ask for the smallest additional fact when evidence is insufficient.
