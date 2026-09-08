# Synthetic behavior note

This is a fictional example, not a statement about a real project's capabilities. Keep real private notes and their source mapping outside public Git.

## Evidence and scope

- Behavior: replace a generated report.
- Version: synthetic example revision 1.
- Evidence grade: example only; no implementation inspected or tests executed.
- Recheck when: the report writer or its replacement rules change.

## Trigger and outcome

A user requests a new report. The example system writes and verifies a temporary candidate before replacing the previous report. A failure before replacement retains the previous file and reports failure. A retained previous file is not automatically repaired if it was already damaged.

## Limits and missing evidence

Power-loss recovery, concurrent writers and failure during rollback are unknown. Do not infer guaranteed data preservation from a backup feature alone.

## Review checklist

Keep only permitted behavior, failure/undo rules, version and evidence grade. Replace real identities and endpoints only when the remaining business rule is itself safe to share. Preserve the underlying source references and file hashes in private review storage. Do not add passwords, real user records, raw source or absolute paths to this note.
