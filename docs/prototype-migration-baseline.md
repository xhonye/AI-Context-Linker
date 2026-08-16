# Prototype replacement audit

> Audited 2026-08-16. Percentages are engineering estimates against the same
> workflow stages, not adoption metrics or claims of scientific precision.

AI Context Linker grew out of a private dogfooding prototype named
`sol-context`. That prototype proved the core experience: a deliberately small
project briefing, synchronized through a dedicated folder, lets ordinary
ChatGPT discuss a local multi-project workspace without receiving the repos.

The open-source implementation now replaces the prototype for this
ChatGPT/Drive strategic-discussion use case. The prototype remains a temporary
rollback and audit reference; Linker does not depend on it at runtime.

## What was compared

The replacement audit used a refreshed 29-project prototype snapshot and an
older Linker snapshot. Aggregate results are published here; private project
names, roots, source lines, and runtime data are intentionally omitted.

The rubric counts project identity, approved summaries, Git state,
conventional entry points, test-file presence, actionable open items, approved
contract constraints, strong cross-project dependencies, and snapshot-change
semantics. It excludes weaker document-reference and shared-dataset inferences
because those are navigation hints rather than confirmed facts.

| Core fact family | Linker / prototype baseline |
|---|---:|
| Project identity | 29 / 29 |
| Approved project summary | 27 / 28 |
| Git facts | 27 / 27 |
| Conventional entry points | 7 / 7 |
| Test-file presence | 18 / 18 |
| Actionable open items | 0 / 1 |
| Approved contract constraints | 17 / 26 |
| Strong cross-project dependencies | 4 / 4 |
| Snapshot change semantics | 1 / 1 |
| **Total** | **130 / 141 (92.2%)** |

The missing open item is a source-code TODO, which Linker deliberately does not
publish. Constraint recall is lower because Linker accepts only bullets under
explicitly relevant contract headings instead of copying broad agent
instructions into cloud context.

## Automation boundary

The workflow is estimated across ten equal stages: discovery, allowlisted fact
collection, normalization, deterministic relationships, snapshot changes,
review and approval, safety validation, Markdown rendering, graph rendering,
and stable publication.

| Boundary | Estimated automation | Required model content |
|---|---:|---:|
| Explicit workspace roots to reviewed bundle | **about 90%** | **0%** |
| Approved manifest to full bundle | **100%** | **0%** |
| Approved manifest to question-directed slice | **100%** | **0%** |

The remaining 10% is intentional human authority: the user approves project
roots, metadata scope, optional code relationship scans, material changes, and
the final publication surface. AI may help interpret the published bundle in
ChatGPT, but it is not allowed to manufacture confirmed facts during indexing.

## Optional code relationship audit

The opt-in adapter performs bounded local reads of approved code/config file
types to find exact references to other approved project roots. It skips
hidden, test, dependency, generated, sensitive, linked, and reparse-point paths.
Published output contains only project IDs and relative evidence locations,
never source text or absolute roots.

The post-hardening audit inspected 5,732 files, produced 24 candidate edges,
and reported three projects as truncated at a scan bound. The generated bundle
contained zero source lines, zero local absolute paths, and zero common
secret-pattern hits. Default scans still read zero source-code bodies.

## Fixed-question comparison

| Question | Result |
|---|---|
| What should I advance today? | No material loss. Projects retain summaries, Git/activity facts, approved constraints, and an explicit warning that activity is not value. Priority remains an AI inference. |
| What is the next step for every project? | Honest limitation. Each snapshot has an explicit actionable item for only one project; Linker preserves unknowns instead of inventing the other plans. |
| Which projects overlap or may be merged? | No material loss for evidence-backed dependencies. All four prototype strong edges are recovered, with additional reviewable candidates. Shared-dataset inference remains intentionally omitted. |
| What facts changed recently? | Improved. The comparison view has its own hash, records added, removed, and changed facts, and cannot alter the identity of the underlying fact snapshot. |

## Accepted tradeoffs

- Linker omits source-code TODO text by design.
- Broad agent instructions are not copied as project constraints.
- Optional code-path relationships are review candidates, not automatic truth.
- Drive receives only the generated publication layer, never the repositories.
- `sol-context` remains available only as a temporary rollback reference.
