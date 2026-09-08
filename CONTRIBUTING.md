# Contributing

AI Context Linker welcomes focused changes that preserve its privacy-first boundary.

## Before opening a change

1. Use only synthetic data in tests, examples, issues, and pull requests.
2. Do not paste source code, credentials, real absolute local paths, or private runtime data into fixtures. Clearly fake path/secret strings are allowed only in negative leakage tests.
3. Keep facts, inference, and unknowns visibly separate.
4. Treat the graph as derived output, never as the source of truth.
5. Add a leakage or regression test for every schema, adapter, or filter change, including missing semantic policy and instruction-like Skill metadata.

## Local checks

Use Python 3.11 or newer. Provision development dependencies explicitly; this
setup command may use a package index. The verification helper never installs
missing development dependencies. Its build backend requires setuptools 77+
for the existing SPDX license metadata ([backend documentation](https://setuptools.pypa.io/en/stable/userguide/license_migration.html)).

```powershell
python -m pip install -e ".[dev]"
python -I -B scripts/verify.py --profile check `
  --output-dir "C:/Private/ai-context-linker/verification/check-001"
```

Choose a **new absolute private directory outside the repository** for each run;
the path above is synthetic. Existing directories, linked ancestors, known sync
folder names and stable SOL/Linker entries are rejected. Custom sync folders
cannot be detected reliably: verifying that the chosen folder is not synced is
the operator's responsibility. Do not publish raw logs or `inputs-private.json`.

| Profile | Checks | Does not establish |
|---|---|---|
| `check` | Repository/interpreter preflight, full pytest, both gold suites, synthetic scan/build/slice, Python/JSON syntax, local Markdown links and Git whitespace | Installed-wheel behavior or real context quality |
| `candidate` | All `check` gates, clean wheel build, fresh offline virtual-environment install, site-packages origin, installed CLI and both gold suites | Project-state approval, human review identity, Pro parity, remote CI or release |

For a small fix, reproduce its focused test first, then run `check` before the
intention-bounded commit. Perform the applicable safety review before freezing
code and documentation for `candidate`:

```powershell
$linkerReviewFingerprint = python -I -B scripts/verify.py --print-fingerprint
if ($LASTEXITCODE -ne 0) { throw "Fingerprint failed" }
python -I -B scripts/verify.py --profile candidate `
  --reviewed-source $linkerReviewFingerprint `
  --output-dir "C:/Private/ai-context-linker/verification/candidate-001"
```

The fingerprint binds nonignored source, tests, fixtures, schemas, scripts,
documentation and execution configuration, including uncommitted changes. It is
an acknowledgement of the reviewed revision, **not proof of who reviewed it**.
CI computes it automatically and does not claim human review. A subsequent
source or packaging-metadata change invalidates the old candidate evidence;
review the new revision and build again rather than reusing the old wheel.

Tests and source CLI checks run from a frozen copy, rechecked after each gate;
packaging uses a separate clean copy whose original inputs must stay unchanged.
Inherited Python/pytest/pip options and unrelated application
environment variables cannot choose imports or package indexes. Installed
checks use an isolated interpreter and must import from the new environment.
Zero tests, all-skipped suites, inconsistent JUnit counts, command failures,
failed gold gates or changing inputs fail closed. Skips are reported explicitly.

Read `summary.json` for stage results, `commands-private.jsonl` for exact
commands, and `inputs-private.json` / `*.log` for local reproduction details.
This is verification of reviewed code, **not an OS
security sandbox**: tests/build backends remain executable code. The helper adds
no network/model calls, approval commands, uploads or publication. It records
environment versions but does not promise bit-identical wheels across systems.

CI uses the same entrypoint with synthetic inputs: Linux Python 3.11-3.13,
Windows Python 3.11, and an offline package check on Linux 3.11. Configuration
alone is not a successful remote CI run. See the
[evaluation loop](docs/local-blind-evaluation.md) for data-readiness and judging gates.

## Pull requests

Explain the user problem, privacy impact, evidence used, and verification performed. Keep unrelated changes separate. New automatic adapters require an explicit security review before merge.
