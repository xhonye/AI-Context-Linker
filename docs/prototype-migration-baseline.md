# Prototype migration baseline

> Audit date: 2026-08-12. Percentages are engineering estimates based on the
> workflow stages below, not adoption metrics or claims of scientific precision.

Audit sample:

- the current prototype fact snapshot contained 27 discovered projects;
- the prototype test suite passed 14 tests;
- AI Context Linker passed 8 tests plus its public CI workflow;
- the audited facts-only prototype output contained 86,553 characters;
- the previous full output contained 112,642 characters, including a 28,942
  character semantic section (`28,942 / 112,642 = 25.7%`).

AI Context Linker grew out of a private dogfooding prototype named
`sol-context`. The prototype already proves that a locally generated project
briefing, synchronized through a dedicated Drive folder, can make an ordinary
ChatGPT conversation materially more project-aware. The open-source project is
not yet a feature-complete replacement for that prototype.

## Current quality comparison

| Dimension | `sol-context` prototype | AI Context Linker V0.1 |
|---|---|---|
| Real workspace coverage | Strong: discovers projects and collects Git, documentation, TODO, test and relationship signals | Limited: starts from a manually approved manifest |
| Daily dogfooding usefulness | Strong: currently covers the maintainer's multi-project workspace | Early: useful after the manifest has been prepared |
| Privacy boundary | Broad scanner with pruning, redaction and output scans; the large private output still needs careful review | Stronger default: strict schema, fail-closed secret/path checks, no repository scanning and minimal output |
| Provenance | Stronger: file-and-line evidence anchors and fact-snapshot hashes | Partial: evidence labels are preserved but are not yet resolved against source adapters |
| Reproducibility | Facts are deterministic; the optional semantic layer is model-generated | Strong: the same approved manifest produces stable Markdown and graph output |
| Open-source portability | Low: contains private workspace assumptions and a fixed publishing workflow | Strong: standalone package, public schema, synthetic examples, tests and CI |

The practical conclusion is two-sided:

- for the maintainer's current daily workflow, `sol-context` still has higher
  coverage and richer evidence;
- as a safe and reusable open-source foundation, AI Context Linker already has
  the cleaner contract and stronger default boundary.

V0.1 should therefore be treated as a **security-first product kernel**, not as
a renamed copy of the prototype.

## How much is scripted today?

The estimate uses ten equal workflow stages:

1. discover projects;
2. read allowlisted local evidence;
3. normalize facts;
4. infer deterministic relationships;
5. calculate snapshot changes;
6. preview and approve the publish surface;
7. validate schema, paths and secrets;
8. render a stable Markdown briefing;
9. render a derived graph;
10. publish a stable file to an explicitly selected sync directory.

| Measurement boundary | Estimated automation | Meaning |
|---|---:|---|
| `sol-context`: local workspace to facts-only briefing | **about 80%** | Discovery, collection, relationships, deltas, safety, rendering and stable publishing are scripted; approval and graph output are not complete |
| `sol-context`: full enriched briefing | **about 70%** | One semantic stage still requires an external model to read facts and selected evidence, then produce a hash-bound enrichment file |
| AI Context Linker: approved manifest to bundle | **100%** | Validation, Markdown, graph and atomic output are deterministic |
| AI Context Linker V0.1: local workspace to bundle | **about 35%** | The critical acquisition, provenance, change-preview and approval workflow had not yet been migrated |
| AI Context Linker V0.2: configured local workspace to bundle | **about 75–80%** | Allowlist collection, generated evidence labels, snapshot hashes and change review are scripted; project selection, explicit relationships and publication approval remain human decisions |

These percentages describe implemented workflow stages. They do not mean that
35% of the source code or 80% of the product value has been completed.

## How much must an AI read and summarize?

Strictly speaking, **none of the fact pipeline has to use AI**.

The prototype can generate a facts-only briefing without a model. Its full
operational workflow adds a semantic section for project positioning,
relationships, opportunities, risks and discussion questions. In the most
recent enriched dogfooding output audited here, that section represented
approximately **25.7% of rendered characters**; deterministic sections made up
approximately **74.3%**.

That 25.7% is a size observation, not a quality score. The semantic layer must
read a much larger fact surface to produce its summary, and it must be regenerated
whenever the bound fact hash changes. At the audit date, the newest fact snapshot
had already changed, so the previous enrichment could not be safely reused.

AI Context Linker V0.2 requires **0% model-generated content at build time**.
ChatGPT performs interpretation when the user asks a question. Preparing the
manifest is currently a human task and may be AI-assisted, but AI-generated
claims must never become confirmed facts merely because a model wrote them.

## Migration decision

The next milestone should increase local-to-bundle automation while keeping
mandatory pre-publication AI at zero:

1. add an explicit workspace and file allowlist;
2. migrate deterministic readers for selected README, agent-contract, Git and
   test-status facts;
3. replace free-form evidence labels with typed source anchors;
4. add snapshot hashes and an inspectable change preview;
5. require human approval for new or higher-risk publish fields;
6. keep semantic enrichment as an optional, clearly labelled layer after the
   deterministic bundle has been built.

V0.2 completed this first migration slice and moved estimated automation from
about **35% to 75–80%** without giving a model authority over the fact layer.
Automatic relationship discovery remains deferred until it can preserve the
same evidence and review guarantees.

## 2026-08-16 safe replacement audit

The migration was evaluated against a refreshed 29-project prototype snapshot
and an older Linker snapshot. Aggregate results are recorded here; private
project names, roots, source lines, and runtime data are intentionally omitted.

The core-fact recall rubric counts project identity, approved summary, Git
presence/state, conventional entry points, test-file presence, actionable open
items, approved contract constraints, strong cross-project dependencies, and
snapshot change semantics. It excludes weaker document-reference edges and
shared-dataset inferences because those are derived navigation views rather
than confirmed project facts.

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

The missing open item is a source-code TODO. Linker deliberately does not
publish source TODO text. Constraint recall is lower because Linker only accepts
bullets under explicitly relevant contract headings instead of copying broad
agent instructions into the cloud context.

An explicit opt-in code-path audit inspected 6,004 bounded local code/config
files across the approved set and produced 24 candidate strong edges. Three
projects reached a scan bound and were reported as truncated. The generated
bundle contained zero source lines, zero local absolute paths, and zero common
secret-pattern hits. Default scans still read zero source-code bodies.

Four fixed discussion questions were then checked:

| Question | Result |
|---|---|
| What should I advance today? | No material loss: all projects retain summaries, Git/activity facts, constraints where approved, and an explicit ban on treating activity as value. Priority remains an AI inference. |
| What is the next step for every project? | Comparable limitation: each snapshot has explicit actionable items for only one project. Linker preserves unknowns instead of inventing 28 project plans. |
| Which projects overlap or may be merged? | No material loss for evidence-backed dependencies: all four prototype strong edges are recovered, with additional reviewable candidates. Shared-dataset inference remains intentionally omitted. |
| What facts changed recently? | Improved: the change view has its own hash, records added/removed projects and changed fields, and cannot change the identity of the underlying fact snapshot. |

For the ChatGPT/Drive strategic-discussion use case, Linker now passes the
replacement gate. The prototype should be retained temporarily as a rollback
and audit reference, not deleted or used as a runtime dependency. Estimated
automation is now about **90% from explicit workspace roots to a reviewed
bundle**, and **100% from an approved manifest to full or question-directed
output**. Required model-generated preparation remains **0%**.
