# Prototype replacement audit

> Audited 2026-08-16. Percentages are engineering estimates against the same
> workflow stages, not adoption metrics or claims of scientific precision.

AI Context Linker grew out of a private dogfooding prototype named
`sol-context`. That prototype proved the core experience: a deliberately small
project briefing, synchronized through a dedicated folder, lets ordinary
ChatGPT discuss a local multi-project workspace without receiving the repos.

This document records the 2026-08-16 fact-family migration audit. A later
2026-08-27 live comparison found that the open-source implementation had not
yet reached action-oriented parity for “what should I advance today,” “where
is the project blocked,” and “what is the next action.” That finding drove the
v0.2 action contract: explicit approved review state, lifecycle resolution,
approved snapshot history, semantic diff, fixed priority slicing, and layered
relationships are now implemented and pass the synthetic gold suite. Real
same-model A/B parity has not yet been rerun with approved v0.2 action state,
so the prototype remains the action-context benchmark until the
[`sol-context parity plan`](sol-context-parity-plan.md) exit gate passes.

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
| What should I advance today? | V0.2 now selects at most three main projects from approved P0/P1 priority, attention, deadlines, blockers, and active projects with approved next actions, then explains omissions. The synthetic contract passes; real parity remains unverified until current review state is approved and the same-model A/B is rerun. |
| What is the next step for every project? | V0.2 transfers approved next actions and outputs unknown when none exists. It does not infer a next action from Git activity or broad goals. |
| Which projects overlap or may be merged? | Observed and approved-semantic layers are formal; AI merge proposals remain in a private review queue. Exact root references are now correctly labeled `scans-or-indexes`, not dependencies. |
| What facts changed recently? | Improved. Stable StateRecord lifecycle and semantic diff cover goals, next actions, blockers, deadlines, projects, and relationships; source disappearance becomes needs-review instead of resolved. |

## Accepted tradeoffs

- Linker omits source-code TODO text by design.
- Broad agent instructions are not copied as project constraints.
- Optional code-path relationships are review candidates, not automatic truth.
- Drive receives only the generated publication layer, never the repositories.
- Every newly discovered project defaults to `deny`; `summary-only` publishes only an explicitly approved summary.
- Raw Skill descriptions are audited as untrusted input and never copied into the publication layer.
- `sol-context` remains available only as a temporary rollback reference.
