# Local blind evaluation and regression loop

Local subagents can diagnose context quality without waiting for a hosted
ChatGPT session. They do **not** certify ChatGPT Pro behavior or replace the
[two-refresh acceptance contract](context-generation-evaluation-contract.md).

## Input readiness before model calls

Classify each question as `ready`, `abstention-only` or `blocked-input` before
freezing a run. Without current approved action state, Q1-Q3 can test honest
abstention, not action recall. Without an approved previous snapshot, Q5 can
test "unknown", not real change detection. Check scope, expiry, evidence and
baseline separately; a ready Q6 does not make Q1-Q5 ready.

If a saved approval draft differs from the human's conditional authorization,
report the field-level differences and stop the affected real experiment.
Do not repair the draft and retroactively treat it as approved. Unchanged raw
subagent answers are diagnostic evidence, not hosted Pro answers and not an
automatic trigger for a preregistered second real-state transition.

## One failure type per iteration

Keep one current task card in the existing local working notes: failure ID,
hypothesis, affected modules, unchanged safety boundary, assertions, evidence
revision, exit gate and one next step. Preserve history; do not add a parallel
roadmap or copy the full status story into every document.

Reproduce the failure, make the smallest change, then use the shared
[verification profiles](../CONTRIBUTING.md#local-checks). Review affected
privacy, approval, lifecycle, history and output surfaces **before** freezing a
package candidate. The dev helper orchestrates existing CLI/evaluators; it is
not a second compiler or model runner. Use a new evaluation directory only
after the targeted objective regression is fixed.

Development cases may grow with fixes, but already seen cases are not a holdout.
Only call a set independent when its contents were withheld from implementers;
after exposure it becomes development data. Track byte/token/call/time measures
separately from answer quality, disclose unavailable measurements, and do not
claim byte reductions as token savings. Two iterations without an explained
improvement mean revisiting the root cause or input, not increasing judge calls.

## Three steps

1. Freeze the question set, rubric, candidate bytes, source observation window
   and hashes before judging. Use the same permitted project/evidence surface.
   Store generator mapping, private state and source gold separately from judge
   inputs. Do not construct a candidate using the competing candidate's output.
2. Use two fresh agents with no parent conversation, instructed to read only
   their assigned artifacts and not the repository, one reading A then B and
   the other B then A. Give identical instructions and
   inherited model/reasoning settings. Record any settings the host does not
   expose as unknown. Save original answers, order, scores and failures without
   rewriting them. This is application-level isolation, not a filesystem sandbox.
3. Reproduce failures with synthetic tests, then fix the smallest behavior.
   Re-run the frozen gold and safety tests; use a new run directory for a new
   model evaluation. Keep development failures distinct from untouched holdout
   cases. Never adjust expected answers or scoring to turn a failure green.

Use tool-free judges when available. Structural formatting may still reveal a
generator even after names are removed; report this residual blinding limitation.
Pairwise ordering also permits within-session comparison effects, so keep each
condition's answer fixed before loading the second condition.

## Dataset and acceptance

| Layer | Dataset | What it establishes |
|---|---|---|
| Fixed questions | Q1 today, Q2 blockers, Q3 actions, Q4 relationships, Q5 changes, Q6 navigation | Stable tasks, not automatically complete answers |
| Action gold | `examples/evaluation/gold-v02/gold-suite.json` | Synthetic lifecycle, priority, dependencies, missing baseline, privacy and semantic changes |
| Structure gold | `examples/evaluation/architecture-gold/` | Synthetic module/symbol/import/call coverage and exclusions |
| Adversarial regressions | `tests/test_action_surface_regressions.py`, `tests/test_scope_lifecycle_regressions.py` | Revocation, future/expired state, history labeling, priority conflicts, output links, instruction boundaries |
| Evidence audit | `tests/test_blind_evaluation.py` | Frozen inputs, raw answer integrity and complete double-order scores |
| Private real comparison | Two fresh same-state rounds and separate native/common-surface tracks | Required for actual replacement, never inferred from synthetic success |

An excerpt without approved state can test whether a model correctly abstains
on Q1-Q5. It cannot establish action recall or strategic parity, even when the
model earns high factual-grounding and uncertainty scores. Likewise, syntactic
module-level call targets do not establish exact caller pairs, function duties,
execution order or runtime behavior. Scores on different questions are not
pooled to hide these gaps.

## Offline evidence helper

`ai_context_linker.blind_evaluation` is an importable local helper, not an agent
runner or uploader. No network access or model calls are added to the compiler.

```python
from pathlib import Path
from ai_context_linker.blind_evaluation import freeze_blind_run, evaluate_blind_run

run = Path("C:/Private/ai-context-linker/evaluation/run-001")
freeze_blind_run(
    run,
    protocol={
        "questions": {f"Q{i}": question for i, question in enumerate(questions, 1)},
        "dimensions": ["factual_grounding", "uncertainty_discipline", "usefulness"],
        "rubric": {str(i): label for i, label in enumerate(rubric_labels)},
    },
    conditions={"A": context_a, "B": context_b},
)
# Separately run the judges and archive their unchanged JSON inside run.
report = evaluate_blind_run(run, responses={
    "order-ab": run / "order-ab.raw.json",
    "order-ba": run / "order-ba.raw.json",
})
```

Supply six fixed question strings and five rubric labels before freezing.
Responses contain `conditions.A.Q1` through `conditions.B.Q6`, each with
`answer`, `scores` keyed by the frozen dimensions (integer 0-4), and `failures`.
The helper refuses overwritten runs, changed inputs, escaped/linked response
paths, duplicate response files, incomplete questions and invalid scores.
Its deterministic aggregate includes hashes and scores, never answers or notes.
Hashes detect later changes; they do not prove who answered, model settings,
human approval or factual correctness. `replacement_ready` remains false.

The older `evaluate` CLI and v0.1 scorecard stay compatible but report only
`single-pair-diagnostic`; `paired_answer_checks_pass` does not mean replacement.

## Safety limits

- Local verification, installed-package behavior, remote CI, real usefulness
  and publication are separate evidence tiers; none automatically approves the next.
- No real review-state approval follows from a model score.
- No private mapping, source gold, local path, secret or source body belongs in
  judge artifacts. Negative test sentinels stay in synthetic tests only.
- Project and workspace prose is marked `UNTRUSTED_DATA` on every Markdown
  surface. This warning is not a proof against arbitrary prompt injection;
  human review and constrained judge tools remain necessary.
- Reclassifying a project as `summary-only` or `deny` prevents old details from
  reappearing through lifecycle history or generated differences. Original
  approved history stays private and unchanged. Known denied IDs and historical
  names in surviving candidate or inherited state cause a generic, non-leaking
  refusal. This exact-alias check is conservative, not semantic entity detection.
- Future-dated records cannot close an earlier known record with the same ID,
  even if that earlier record has become stale; the conflict requires review.
- Keep stable Drive entries untouched; model outputs are private evidence,
  not approved project facts or public demonstration copy.
