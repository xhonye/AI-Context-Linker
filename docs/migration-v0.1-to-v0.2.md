# Migrating from manifest v0.1 to v0.2

V0.1 remains supported for validating and building an existing approved manifest. New scans emit v0.2 because action lifecycle, approved snapshots, semantic changes, and relationship layers cannot be represented safely in the old contract.

## Recommended migration

1. Keep the old approved v0.1 manifest unchanged as a rollback artifact.
2. Update the private workspace configuration to schema `0.2`.
3. Classify every project with `sensitivity`, `cloud_visibility`, and `redaction_profile`. Newly discovered or unclassified projects default to `deny`; choose `allow`, or choose `summary-only` and add an `approved_summary`, before cloud use.
4. For every Skill summary you want to publish, write a neutral phrase in the private root-level `approved_summaries` map. Raw frontmatter descriptions are no longer copied automatically.
5. Add an explicit private v0.2 review-state file for any current activity, attention, goal, blocker, next action, completion criterion, owner, or deadline you want ChatGPT to use.
6. Run `scan` without a previous snapshot for the first v0.2 baseline.
7. Review the candidate manifest, semantic changes, relationship review queue, semantic visibility counts, and Skill injection findings.
8. Record approval with `approve-snapshot` in a private non-synced history directory.
9. On the next refresh, pass `--previous-snapshot approved-snapshot-latest.json` so lifecycle resolution and semantic diff use only an explicitly approved predecessor.

## Semantic visibility migration

| Field | Meaning |
|---|---|
| `sensitivity` | `public`, `internal`, `private`, or `highly-sensitive` |
| `cloud_visibility` | `allow` for detailed facts, `summary-only` for one approved summary, or `deny` for complete omission |
| `redaction_profile` | a private policy identifier such as `standard`, `legal`, or `financial` |
| `approved_summary` | required project prose under `summary-only`; it is never derived from README |

`allow` requires explicit `sensitivity` and `redaction_profile`. `deny` projects and their relationships are absent from the candidate. Review-state and session-summary inputs cannot override visibility.

When changing an existing project to `summary-only`, discard its detailed
signals, state, evidence, constraints and architecture from the publishable
manifest, and use the neutral status
`summary-only; detailed project context withheld by policy`. The compiler now
rejects those detailed fields and incident relationships even in a hand-edited
manifest. Explicit revocation also limits the history comparison view; it does
not erase the original private approved snapshot.

## Review-state field mapping

The v0.1 review-state adapter is still accepted. Its `status` field migrates to v0.2 `activity`; goal, next action, blockers, and updated time keep their meaning.

V0.2 adds:

| Field | Meaning |
|---|---|
| `priority` | human-approved `P0`, `P1`, `P2`, `P3`, or `unknown`; more than three simultaneous P0/P1 entries is rejected |
| `attention` | `today`, `this-week`, `later`, `none`, or `unknown` |
| `why_now` | approved reason this work matters now |
| `done_when` | explicit completion criterion |
| `owner` | approved accountable owner label |
| `due_at` | ISO date or timezone-aware timestamp |
| `expires_at` | time after which approved state becomes stale |
| `records` | optional explicit lifecycle records with stable IDs and supersedes |

Missing fields remain unknown. Do not backfill them from Git activity.

## State lifecycle

V0.2 normalizes state into `StateRecord` objects with `record_id`, `kind`, `status`, `source_kind`, `source_ref`, `observed_at`, optional `expires_at`, and `supersedes`.

- `open` may participate in current action output.
- `resolved`, `superseded`, and `stale` stay auditable but are not current actions.
- `needs_review` means the evidence disappeared or has not received current approval; it is not resolved.
- Only the same stable record ID or explicit `supersedes` may close an older record.

## Relationship migration

Every v0.2 relationship requires a `layer`.

| Old usage | V0.2 type | Layer |
|---|---|---|
| exact reference to another approved project root | `scans-or-indexes` | `observed` |
| unique structured package dependency | `runtime-dependency` | `observed` |
| explicit build-only dependency | `build-dependency` | `observed` |
| explicit shared data contract | `shared-data` | `observed` |
| explicit blocker reference | `blocked-by` | `observed` |
| Markdown code/link mention | `document-reference` | `observed` |
| human-approved overlap, alternative, replacement, complement, separation, or merge judgment | corresponding semantic type | `approved-semantic` |
| AI proposal | semantic type | review queue only; never formal manifest promotion |

The old `code-path-dependency` name must not be carried forward: a project-root reference does not prove runtime dependency. Custom v0.1 relationship types must be reviewed and mapped to one of the v0.2 types rather than copied mechanically.

## Output changes

`scan` now writes five private review artifacts:

- `candidate-manifest.json`;
- `scan-report.json`;
- `changes.json`;
- `changes.md`;
- `relationship-review-queue.json`.

`build` still writes the stable Markdown and derived JSON graph. `slice` still writes one question-directed Markdown file. Neither command uploads files or accesses the network.

See [`synthetic-manifest-v02.json`](../examples/synthetic-manifest-v02.json) and [`synthetic-review-state-v02.json`](../examples/synthetic-review-state-v02.json) for path-free examples.
