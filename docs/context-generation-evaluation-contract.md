# Context Generation Evaluation Contract

## Purpose

This contract compares context generators by the quality of the answers they
enable, not by file size, repository activity, architecture preference, or the
name of the generator. The current local comparison is:

- **AI Context Linker** (repo-local Skill name: `ai-context-linker`):
  deterministic compilation from reviewed, publishable facts; no
  model-generated indexing layer;
- **SOL Context** (display name: `SOL_Context`; runtime Skill ID:
  `sol-context`): deterministic repository facts and Code Maps plus a hash-bound
  Hermes enrichment layer.

The evaluation does not make either artifact a source of truth. Human-approved
state and direct local evidence remain authoritative.

## Required evaluation tracks

Report each track separately. Never combine them into one score that hides a
privacy or coverage trade-off.

### 1. Common-surface track

- Use the same project set, approved action state, observation window, and
  fixed question pack.
- Restrict both artifacts to evidence that is permitted in the Linker cloud
  publication policy.
- This track measures extraction, state transfer, relationship precision,
  evidence quality, uncertainty, focus, and determinism.

### 2. Native-product track

- Generate each product through its normal contract and safety boundary.
- Record every material input difference, including AI enrichment, Code Map
  scope, denied projects, private evidence classes, and stale state.
- This track measures the actual ordinary-ChatGPT experience. A broader input
  surface may improve utility, but its privacy cost must remain visible.

### 3. Full-code oracle track (optional)

- Use only a synthetic/public repository, or a local code-capable model that
  does not upload private source.
- Ask code-navigation and architecture questions whose answers can be checked
  directly against the repository.
- Treat the oracle as an answer key, not as a third candidate and not as an
  authority for current priority, blockers, or user intent.

## Capture controls

- Capture both candidates from the same approved project state. Record their
  artifact hashes, schema versions, generation times, project counts, and the
  elapsed time between captures.
- A material repository or approved-state change between captures invalidates
  the pair. Regenerate both instead of explaining the difference away.
- Do not let one generator consume the other generator's output. Shared human
  review state is allowed; generated summaries and inferred relationships are
  not shared inputs.
- Preserve stable Drive entries. Comparison artifacts go to a separate,
  explicitly approved comparison directory and never replace
  `sol_context/sol_context.md` or `ai_context_linker/ai_context.md`.

## Judge controls

Local subagent runs may provide diagnostic evidence using the
[frozen blind-evaluation workflow](local-blind-evaluation.md). Record them as
local diagnostics, not ChatGPT Pro acceptance. A historical structural replay
without approved action state measures Q1-Q5 abstention only. Preserve raw
answers and failures, keep development cases separate from untouched holdouts,
and never silently substitute a repaired artifact in an already-scored round.

- Use the same answer model, system prompt, exact question text, temperature or
  equivalent settings, and fresh conversation state for both candidates.
- Blind the generator identity as `A` and `B`. Run both orderings when the
  answer model is nondeterministic.
- The model that generates SOL enrichment must not be treated as an independent
  judge. Record its model, reasoning level, token use, cost, and wall time as
  preprocessing facts.
- Keep real prompts, answers, manifests, paths, and reviewer notes outside Git.
  Commit only synthetic fixtures, schemas, and path-free aggregate reports.

## Fixed question pack

1. What should I advance today, and why?
2. Which active projects are blocked, and by what evidence?
3. What is the next concrete action for every active project?
4. Which projects depend on, overlap with, replace, complement, or should stay
   separate from another?
5. What changed since the previous approved snapshot, and which earlier advice
   should be reconsidered?
6. For selected projects, where should an engineer inspect or change the code,
   and what remains impossible to know without reading source bodies?

## Evidence and gold answers

- Build the action gold set from current human-approved state with expiry and
  lifecycle resolution.
- Build relationship gold from observed package/config evidence and explicitly
  approved semantic relationships.
- Build code-navigation gold by direct local repository inspection. Never use a
  candidate artifact as its own gold answer.
- Score unsupported claims as errors even when they sound plausible. Missing
  evidence should produce `unknown` or a minimal evidence request.

## Metrics

Score answer quality from 0 to 4 for factual grounding, current-state
freshness, blocker recall, next-action recall, relationship usefulness,
semantic-change usefulness, code-navigation usefulness, uncertainty discipline,
retrieval focus, and strategic-discussion usefulness.

Also record these objective measures:

- approved next-action transfer = 100%;
- blocker precision and recall >= 90% / 90%;
- resolved-blocker false-positive rate <= 5%;
- semantic-diff precision and recall >= 95% / 95%;
- factual-relationship precision >= 95%;
- published relationship evidence coverage = 100%;
- configured privacy leaks = 0;
- deterministic output = 100% for deterministic stages;
- artifact bytes, estimated input tokens, generation wall time, model/API calls,
  and model cost.

Git activity, file count, artifact length, and graph density are diagnostics,
not quality scores.

## Replacement gate

AI Context Linker may be declared a replacement for the ordinary-ChatGPT use
case only after two consecutive real refreshes satisfy all of the following:

- every objective release gate above passes;
- it is no worse than SOL Context on each of the first three action questions;
- it does not lose a material blocker, next action, relationship, or semantic
  change that is present in the shared gold set;
- it is strictly safer on the cloud-publication surface or documents an equal
  privacy result;
- no result relies on fabricated current state or a stale approved record.

Until then, report `not ready`, keep SOL Context as the private rollback
benchmark, and name the exact failing dimensions. A single favorable run,
synthetic success, or smaller artifact is not parity evidence.
