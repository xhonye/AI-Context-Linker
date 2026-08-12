---
name: ai-context-linker
description: Build and update privacy-safe AI Context Linker bundles from an explicitly approved JSON manifest. Use when a user asks to prepare local project context for ChatGPT or another AI assistant, validate an AI Context Linker manifest, generate a project briefing or relationship graph, or publish reviewed context to an explicit local or Drive-synced directory without uploading source code.
---

# AI Context Linker

Use the standalone `ai-context-linker` CLI as the execution truth. Keep this Skill as a thin review and invocation layer.

## Workflow

1. Locate an existing approved manifest. If none exists, copy the repository's `examples/real-project-template.json` into the user's private data area and edit only approved high-level facts.
2. Refuse to include source code, diffs, credentials, connection strings, absolute local paths, private runtime data, or unconfirmed model inference.
3. Show the exact manifest or meaningful diff before writing to a cloud-synced destination. Keep facts, unknowns, and derived relationships distinct.
4. Require an explicit output directory. Never select a workspace root, repository root, home directory, or broad Drive directory.
5. Run:

```text
ai-context-linker build --manifest <approved.json> --output-dir <explicit-directory>
```

6. Report the two generated files and any validation failure. Do not bypass a failure or weaken a filter.

## Missing CLI

If `ai-context-linker` is unavailable, stop before publishing and tell the user to install the repository package with `python -m pip install -e .`. Do not reimplement the compiler inside the Skill.

## Safety contract

- Treat the manifest as the sole approved input and the graph as derived output.
- Never connect or sync an entire repository through this workflow.
- Never claim a generated briefing proves current code or runtime state.
- Ask for the smallest additional fact when evidence is insufficient.
