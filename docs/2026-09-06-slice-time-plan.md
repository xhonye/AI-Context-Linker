# Explicit time for question slices

## Goal and boundary

Continue the Linker/SOL quality competition with a bounded Linker improvement:
make the time basis of action recommendations visible and allow expired state
to be excluded at a caller-selected time. Keep deterministic replay, source
hashes, approval boundaries and zero-model preprocessing intact. Preserve all
pre-existing dirty changes. Do not read SOL outputs or publish real state.

## Implementation

1. Reproduce an approved action that is current at snapshot capture but expired
   when the question is asked.
2. Add optional `slice --as-of <timezone-aware ISO timestamp>` and Python API
   equivalent. Default remains snapshot-time replay; reject earlier-than-snapshot
   times and unsupported legacy re-evaluation rather than inventing history.
3. Show both snapshot capture and action evaluation timestamps, with an explicit
   statement that time re-evaluation does not refresh source facts or approvals.
4. Verify expiry boundaries, resolved-state preservation, input immutability,
   deterministic repeats, CLI forwarding, invalid inputs and both gold suites
   through the repository check profile.

## Acceptance

- Expired actions do not appear as today's actionable recommendations.
- Same manifest, question and time produce identical bytes.
- No input hash, approval state, or source file is modified.
- Existing no-argument replay and real comparison contracts remain supported.
- Automated verification does not establish real answer parity or replacement.

## Usage

For a reproducible check at the time of a new question:

```powershell
python -m ai_context_linker slice --manifest <reviewed-manifest.json> --question "今天推进什么？" --output-dir <private-candidate-dir> --as-of "2026-09-06T22:00:00+08:00"
```

Replace the example time with the actual question time, including timezone. For
live local use, PowerShell can pass `(Get-Date).ToString('o')` as the value. Record
the exact displayed timestamp to replay the same result. The API accepts the same
value as the keyword-only `as_of` argument. This mode requires schema v0.2 and
cannot evaluate before the source snapshot.

Omitting `--as-of` keeps snapshot-time replay. Only the question slice is affected;
the full `build` bundle remains a snapshot artifact. Time re-evaluation does not
rescan projects, approve new state, renew expired approvals or rewrite the input.
Expired records can remain labeled history in project-specific context; they must
not re-enter actionable recommendations. A current view requires current approved
facts as well as the time check.

## Verification result

- Repository frozen `check` profile passed: 350 tests, zero failures/errors/skips;
  action gold, architecture gold, synthetic scan, build and slice all passed.
- First frozen check exposed a test-only import that depended on pytest's import
  mode. The new test now owns a small synthetic fixture and passes in isolation.
- Evidence: the frozen check summary is retained in private validation storage.
- No real manifests, approval records, SOL output, cloud files or runtime Skill
  copies were read or modified by this iteration. Package installation and real
  same-model answer comparison were not performed.
