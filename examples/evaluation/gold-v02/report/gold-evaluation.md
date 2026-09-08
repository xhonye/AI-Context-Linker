# AI Context Linker v0.2 synthetic gold evaluation

> ALL GATES PASS
> Fixed suite observation time: 2026-08-28T12:00:00+08:00

## Release gates

| Gate | Result | Required | Status |
|---|---:|---:|---|
| `approved_next_action_transfer` | 1.0 | >= 1.0 | PASS |
| `blocker_precision` | 1.0 | >= 0.9 | PASS |
| `blocker_recall` | 1.0 | >= 0.9 | PASS |
| `resolved_blocker_false_positive_rate` | 0.0 | <= 0.05 | PASS |
| `semantic_diff_precision` | 1.0 | >= 0.95 | PASS |
| `semantic_diff_recall` | 1.0 | >= 0.95 | PASS |
| `factual_relationship_precision` | 1.0 | >= 0.95 | PASS |
| `published_relationship_evidence_coverage` | 1.0 | >= 1.0 | PASS |
| `configured_privacy_leaks` | 0 | = 0 | PASS |
| `deterministic_output` | 1.0 | >= 1.0 | PASS |

## Scenario contract

- Cases: 13
- Expected behaviors: PASS
- Mismatches: none

> The suite uses only synthetic projects and fixed timestamps. It contains no real manifest, path, source text, or private runtime data.
