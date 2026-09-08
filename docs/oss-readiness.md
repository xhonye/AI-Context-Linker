# Open-source release readiness

## Release gate

- [x] Independent CLI and importable Python package
- [x] Strict allowlist manifest and privacy failure tests
- [x] Open JSON Schema and synthetic examples
- [x] MIT license, contribution guide, security policy, and CI
- [x] Optional agent Skill that delegates to the CLI
- [x] Public GitHub repository
- [x] Tagged `v0.1.0` release
- [x] Public demonstration using synthetic or deliberately approved facts
- [x] Deterministic v0.2 action-context gold suite and checked-in aggregate report
- [x] Explicit snapshot approval, lifecycle-aware diff, and AI relationship review queue
- [x] Project-level semantic visibility plus raw Skill-description and prompt-injection isolation
- [x] Opt-in path-free Architecture Index, sharded bundle, and deterministic structure gold gates
- [ ] First external user feedback or contribution

## Positioning

Describe AI Context Linker as a privacy-first context compiler and open schema. The Skill is an optional interface, not the project itself.

## Evidence to collect before applying for OSS support

- Continued public maintenance history beyond the initial release
- Real questions answered better with the generated bundle
- Leakage tests and documented threat boundary
- Issues, contributors, stars, installs, or a precise ecosystem role
- Examples of Codex helping maintain, test, review, or release the project

The synthetic v0.2 and Architecture Index reports prove the documented compiler contract, not adoption or real-workspace parity. Project visibility and Skill injection regressions are additionally covered by scanner tests. Do not describe Linker as a complete `sol-context` replacement until the private code-navigation comparison and two private same-model action refreshes pass.

Local subagent evidence is a separate diagnostic track. Frozen inputs, original
answers, order effects and failures must remain auditable; one favorable pair
or a legacy scorecard cannot set replacement readiness. Lifecycle, revocation
and output-path regressions are release checks, not adoption evidence.

The repository-only `check` / `candidate` [verification profiles](../CONTRIBUTING.md#local-checks)
reuse those checks with frozen inputs, private logs and offline installed-wheel
smoke. A passing local candidate is not remote CI, human project-state approval,
a release or replacement acceptance; report these evidence tiers separately.

Do not manufacture adoption metrics. A small project should explain its ecosystem importance and provide concrete maintenance evidence.
